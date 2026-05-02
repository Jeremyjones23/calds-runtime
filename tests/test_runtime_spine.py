from __future__ import annotations

from pathlib import Path
import importlib.util
import shutil
import unittest
from uuid import uuid4

from calds_runtime.agents import LeadScorerAgent
from calds_runtime.case_compiler import CaseDossierService
from calds_runtime.case_workflow import CaseWorkflow
from calds_runtime.completeness import CompletenessControllerService
from calds_runtime.contracts import AcquisitionSearchRun, CanonicalRecord, CaseRequest, CompletionGuardResult, ContextHandoffLedger, EvidenceBundle, EvidenceItem, InvestigationProfile, LinkIntegrityReport, Provenance, SourceLinkCheck, TriageFinding, WorkflowStatus, read_json, write_json
from calds_runtime.forensic_triage import HomelessnessTriageService
from calds_runtime.generic_spine import (
    EntityResolutionService,
    EvidenceStoreManifestService,
    ForensicTestService,
    HumanActionCompilerService,
    ProfileGateService,
    SourceAcquisitionPlannerService,
    TargetDiscoveryService,
)
from calds_runtime.investigation_profiles import InvestigationProfileService, ReviewValueScoringService
from calds_runtime.publication import extract_urls, mark_unverified_source_urls, publish_case_site_from_run, repair_public_source_urls, source_access_report
from calds_runtime.quality_gates import CitationVerifierService, CompletionGuardService, RunReadinessService
from calds_runtime.risk_matrix import OversightRiskMatrixService
from calds_runtime.search import KeywordSearchIndex, SearchPlan
from calds_runtime.sentinel import find_escalated_language
from calds_runtime.source_catalog import CaliforniaSourceCatalogService
from calds_runtime.scoring import LeadScoringService


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class RuntimeSpineTests(unittest.TestCase):
    def test_case_runs_to_human_review_pause_with_provenance(self) -> None:
        case = CaseRequest.from_dict(read_json(PROJECT_ROOT / "evals" / "cases" / "easy_case.json"))
        temp_dir = PROJECT_ROOT / "runs" / "tests" / f"calds-test-{uuid4().hex}"
        try:
            workflow = CaseWorkflow(PROJECT_ROOT / "data" / "sample_corpus", temp_dir)
            result = workflow.run_case(case)
            self.assertEqual(result.status, WorkflowStatus.AWAITING_HUMAN_REVIEW)

            state = read_json(result.state_path)
            self.assertEqual(state["status"], WorkflowStatus.AWAITING_HUMAN_REVIEW.value)
            bundle = read_json(Path(state["artifacts"]["evidence_bundle"]))
            self.assertGreaterEqual(len(bundle["items"]), 1)
            for item in bundle["items"]:
                self.assertTrue(item["source_uri"])
                self.assertTrue(item["provenance"]["checksum"])

            matrix = read_json(Path(state["artifacts"]["oversight_risk_matrix"]))
            self.assertGreaterEqual(len(matrix["indicators"]), 1)
            self.assertIn("score_scale", matrix)
            self.assertTrue(any(item["risk_area"] == "Spend-versus-results" for item in matrix["indicators"]))

            triage = read_json(Path(state["artifacts"]["entity_triage_results"]))
            forensic_plan = read_json(Path(state["artifacts"]["forensic_investigation_plan"]))
            handoff = read_json(Path(state["artifacts"]["context_handoff_ledger"]))
            acquisition = read_json(Path(state["artifacts"]["acquisition_ledger"]))
            completion_guard = read_json(Path(state["artifacts"]["completion_guard"]))
            completeness_report = read_json(Path(state["artifacts"]["completeness_controller_report"]))
            profile_gate = read_json(Path(state["artifacts"]["profile_gate_audit"]))
            entity_resolution = read_json(Path(state["artifacts"]["entity_resolution"]))
            target_universe = read_json(Path(state["artifacts"]["target_universe"]))
            source_plan = read_json(Path(state["artifacts"]["source_acquisition_plan"]))
            evidence_manifest = read_json(Path(state["artifacts"]["evidence_store_manifest"]))
            forensic_tests = read_json(Path(state["artifacts"]["forensic_test_results"]))
            human_actions = read_json(Path(state["artifacts"]["human_action_plan"]))
            self.assertIn("results", triage)
            self.assertIn("selected_entities", forensic_plan)
            self.assertEqual(handoff["status"], "PASS")
            self.assertIn("searches", acquisition)
            self.assertGreaterEqual(len(acquisition["searches"]), len(forensic_plan["selected_entities"]))
            self.assertIn(completion_guard["status"], {"PASS", "PASS_WITH_BLOCKERS"})
            self.assertIn(completeness_report["status"], {"PASS", "PASS_WITH_BLOCKERS"})
            self.assertGreaterEqual(completeness_report["handoff_count"], 1)
            self.assertEqual(completeness_report["retry_required_count"], 0)
            self.assertEqual(profile_gate["status"], "PASS")
            self.assertIn("entity_resolution", profile_gate["checked_gates"])
            self.assertIn(case.entities[0], entity_resolution["canonical_entities"])
            self.assertIn("aliases", entity_resolution)
            self.assertGreaterEqual(len(target_universe["candidates"]), 1)
            self.assertIn("review_value_score", target_universe["candidates"][0])
            self.assertIn("selected_entities", target_universe)
            self.assertGreaterEqual(len(source_plan["requirements"]), len(forensic_plan["selected_entities"]))
            self.assertIn("connector_specs", source_plan)
            self.assertGreaterEqual(evidence_manifest["entry_count"], len(bundle["items"]))
            self.assertTrue(all(entry["checksum"] for entry in evidence_manifest["entries"]))
            self.assertGreaterEqual(len(forensic_tests["results"]), len(forensic_plan["selected_entities"]))
            self.assertGreaterEqual(len(human_actions["actions"]), 1)
            self.assertTrue(human_actions["highest_leverage_action"])
            checked_gates = {check["gate"] for check in completeness_report["checks"]}
            for gate in {"profile", "entity_resolution", "target_discovery", "forensic_tests", "evidence_store", "human_action"}:
                self.assertIn(gate, checked_gates)
            self.assertIn("entity_resolved", state["completed_steps"])
            self.assertIn("target_universe_discovered", state["completed_steps"])
            self.assertIn("completeness_checked", state["completed_steps"])
            self.assertGreaterEqual(completion_guard["total_searches"], len(acquisition["searches"]))
            self.assertIn("anything short of a citation-ready hit remains a source-access blocker", " ".join(completion_guard["notes"]))
            self.assertIn("triaged", state["completed_steps"])

            dossier_path = Path(state["artifacts"]["case_dossier_markdown"])
            dossier = read_json(Path(state["artifacts"]["case_dossier"]))
            self.assertEqual(dossier["compiler_role"], "Case Compiler")
            self.assertTrue(dossier_path.exists())
            dossier_text = dossier_path.read_text(encoding="utf-8")
            self.assertIn("## 1. Executive Snapshot", dossier_text)
            self.assertIn("## 2. Case In One Page", dossier_text)
            self.assertIn("## 3. Entity Briefs", dossier_text)
            self.assertIn("## 4. Methodology, Guardrails, and Source Status", dossier_text)
            self.assertIn("## 5. Case Dossier Orientation", dossier_text)
            self.assertIn("## 6. Evidence Detail By Entity", dossier_text)
            self.assertIn("## 7. Flagged Review Matrix", dossier_text)
            self.assertIn("## 8. Evidence Citation Ledger", dossier_text)
            self.assertIn("## 9. Human-Only Next Steps", dossier_text)
            self.assertIn("## 11. Human Review Required", dossier_text)
            self.assertIn("Source: human_action_plan.json", dossier_text)
            self.assertLess(dossier_text.index("## 1. Executive Snapshot"), dossier_text.index("## 3. Entity Briefs"))
            self.assertLess(dossier_text.index("## 3. Entity Briefs"), dossier_text.index("### Acquisition and Completion Guard"))
            self.assertIn("Source URI", dossier_text)
            self.assertIn("Checksum", dossier_text)
            self.assertIn("CalDS flags", dossier_text)
            self.assertIn("What CalDS found first", dossier_text)
            self.assertIn("What The Score Means", dossier_text)
            self.assertIn("What these scores apply to", dossier_text)
            self.assertIn("not entity-by-entity grades", dossier_text)
            self.assertIn("Questions this score should raise", dossier_text)
            self.assertIn("required source-family acquisition checks", dossier_text)
            self.assertIn("Open gap burden", dossier_text)
            self.assertIn("Contradiction burden", dossier_text)
            self.assertIn("Contradictions are never positive evidence", dossier_text)
            self.assertIn("Triage Gate", dossier_text)
            self.assertIn("Acquisition and Completion Guard", dossier_text)
            self.assertIn("Completion guard status", dossier_text)
            self.assertIn("Decision Needed", dossier_text)
            self.assertIn("possible waste, fraud, abuse, or mismanagement", dossier_text)
            self.assertIn("Plain-Language Source Glossary", dossier_text)
            self.assertIn("Federal Audit Clearinghouse", dossier_text)
            self.assertIn("California Department of Health Care Services", dossier_text)
            self.assertIn("Internal Revenue Service", dossier_text)
            self.assertIn("Why this entity is in the review set", dossier_text)
            self.assertIn("What the organization says it does", dossier_text)
            self.assertIn("What the records show", dossier_text)
            self.assertIn("Key retrieved records", dossier_text)
            self.assertIn("Why CalDS flagged it", dossier_text)
            self.assertIn("Next human step", dossier_text)
            self.assertIn("Specific findings that drove the flag", dossier_text)
            self.assertIn("What CalDS found", dossier_text)
            self.assertIn("Relevant time and place", dossier_text)
            self.assertIn("Why CalDS included it", dossier_text)
            self.assertIn("System opinion", dossier_text)
            self.assertIn("Why this matters", dossier_text)
            self.assertIn("What this does not prove", dossier_text)
            self.assertNotIn("retrieved records produced", dossier_text)
            self.assertNotIn("row count", dossier_text)
            self.assertNotIn("source table", dossier_text)
            self.assertNotIn("source dataset", dossier_text)
            self.assertNotIn("Source status:", dossier_text)
            self.assertNotIn("source status is recorded", dossier_text)
            self.assertNotIn("screen fired", dossier_text)
            self.assertNotIn("implemented screen", dossier_text)
            self.assertNotIn("material weakness years=", dossier_text)
            self.assertNotIn("internal-control deficiency years=", dossier_text)
            self.assertNotIn("findings rows=", dossier_text)
            self.assertNotIn("Parsed salaries/compensation/benefits", dossier_text)
            self.assertNotIn("Parsed entity growth context:", dossier_text)
            self.assertIn("source collection", dossier_text)
            self.assertNotIn("WFA", dossier_text)
            self.assertNotIn("Briefing judgment:", dossier_text)
            self.assertNotIn("Who they are / what they say they do", dossier_text)
            self.assertNotIn("Latest parsed Internal Revenue Service row with both fields", dossier_text)
            self.assertNotIn("Facebook X Instagram Contact Get Help Careers Volunteer Donate Home About Our Work", dossier_text)
            self.assertFalse(find_escalated_language(dossier_text))

            review_decision = read_json(Path(state["artifacts"]["review_decision"]))
            self.assertEqual(review_decision["decision"], "PENDING")
            self.assertTrue(result.review_packet_path.exists())
            citation_verification = read_json(Path(state["artifacts"]["citation_verification"]))
            self.assertEqual(citation_verification["status"], "PASS")
            self.assertEqual(citation_verification["error_count"], 0)
            self.assertEqual(citation_verification["warning_count"], 0)
            self.assertGreater(citation_verification["checked_claim_count"], 0)
            packet_text = result.review_packet_path.read_text(encoding="utf-8")
            self.assertIn("## 1. Reviewer Orientation", packet_text)
            self.assertIn("## 3. Oversight Risk Matrix", packet_text)
            self.assertIn("possible waste, fraud, abuse, or mismanagement screening matrix", packet_text)
            self.assertIn("Plain-Language Source Guide", packet_text)
            self.assertIn("Federal Audit Clearinghouse", packet_text)
            self.assertIn("California Department of Health Care Services", packet_text)
            self.assertIn("Internal Revenue Service", packet_text)
            self.assertNotIn("Waste, Fraud, and Abuse (WFA)", packet_text)
            self.assertNotIn("WFA", packet_text)
            self.assertNotIn("FAC control", packet_text)
            self.assertNotIn("DHCS active", packet_text)
            self.assertIn("| Risk area | Entity | Level | Test | Observed fact | Evidence refs | Reviewer action |", packet_text)
            self.assertIn("Spend-versus-results", packet_text)
            self.assertIn("Data gap", packet_text)
            self.assertIn("## 8. Evidence Citation Map", packet_text)
            self.assertIn("`E01`", packet_text)
            self.assertIn("Internal evidence ID", packet_text)
            self.assertIn("Score Summary", packet_text)
            self.assertIn("Score Formula", packet_text)
            self.assertIn("Risk severity score", packet_text)
            self.assertIn("Publication confidence score", packet_text)
            self.assertIn("What this flags", packet_text)
            self.assertIn("How to use it", packet_text)
            self.assertNotIn("Evidence IDs:", packet_text)

            public_site = publish_case_site_from_run(result.run_dir, temp_dir / "public_site")
            self.assertTrue(Path(public_site.index_html).exists())
            self.assertTrue(Path(public_site.case_dossier_markdown).exists())
            self.assertTrue(Path(public_site.source_ledger_json).exists())
            public_html = Path(public_site.index_html).read_text(encoding="utf-8")
            public_md = Path(public_site.case_dossier_markdown).read_text(encoding="utf-8")
            public_ledger = read_json(Path(public_site.source_ledger_json))
            public_manifest = read_json(Path(public_site.publication_manifest_json))
            self.assertTrue(public_manifest["safety"]["passed"])
            self.assertEqual(public_manifest["citation_verification"]["status"], "PASS")
            self.assertIn("link_integrity", public_manifest)
            self.assertIn(public_manifest["link_integrity"]["status"], {"PASS", "PASS_WITH_WARNINGS"})
            self.assertIn("source_access", public_manifest)
            self.assertIn("source_access_required_count", public_manifest["source_access"])
            self.assertIn("deep_source_blocker_count", public_manifest["source_access"])
            self.assertIn("total_source_blocker_count", public_manifest["source_access"])
            self.assertIn("public_link_access", public_manifest)
            self.assertIn("publication_context", public_manifest)
            self.assertIn("completeness_status", public_manifest["publication_context"])
            self.assertIn("deep_source_blocker_count", public_manifest["publication_context"])
            self.assertIn("CalDS Public Case Viewer", public_html)
            self.assertIn("California Evidence Room", public_html)
            self.assertIn("class=\"case-hero\"", public_html)
            self.assertIn("class=\"reviewer-panel\"", public_html)
            self.assertIn("Source Ledger Digest", public_html)
            self.assertIn("Publication Manifest", public_html)
            self.assertIn("class=\"status-strip\"", public_html)
            self.assertIn("#source-ledger", public_html)
            self.assertIn("id=\"evidence-E01\"", public_html)
            self.assertIn("aria-label=\"Open evidence E01 in source ledger\"", public_html)
            self.assertNotIn("font-family: Arial", public_html)
            self.assertNotIn(str(PROJECT_ROOT), public_html)
            self.assertNotIn(str(PROJECT_ROOT), public_md)
            self.assertNotIn("Facebook X Instagram Contact Get Help Careers Volunteer Donate Home About Our Work", public_html)
            if public_manifest["publication_context"]["completion_guard_blocker_count"]:
                self.assertFalse(public_manifest["source_access"]["completion_guard_access_complete"])
            if public_manifest["publication_context"]["deep_source_blocker_count"]:
                self.assertFalse(public_manifest["source_access"]["complete"])
            for entry in public_ledger["evidence"]:
                self.assertTrue(entry["source_urls"] or entry["link_note"])
                self.assertIn("source_role", entry)
                self.assertIn("source_exactness", entry)
                if not entry["source_urls"]:
                    self.assertEqual(entry["link_status"], "source_access_required")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_citation_verifier_requires_repair_for_uncited_claims(self) -> None:
        case = CaseRequest(case_id="citation_gate", title="Citation gate", objective="Block uncited claims.")
        bundle = EvidenceBundle(bundle_id="bundle", case_id="citation_gate", query_terms=[], items=[], entity_links=[])
        matrix = OversightRiskMatrixService().build(case, [], bundle)
        result = CitationVerifierService().verify(
            case,
            "Briefing judgment: CalDS flags Example NGO as a high-priority possible waste, fraud, abuse, or mismanagement review subject.",
            bundle,
            matrix,
        )
        self.assertEqual(result.status, "REPAIR_REQUIRED")
        self.assertEqual(result.error_count, 0)
        self.assertGreater(result.warning_count, 0)

    def test_investigation_profile_loads_sf_review_value_defaults(self) -> None:
        case = CaseRequest(
            case_id="sf_profile_test",
            title="SF profile",
            objective="Load profile.",
            jurisdiction="San Francisco, California",
            metadata={"investigation_profile_path": "data/investigation_profiles/sf_homelessness.json"},
        )
        profile = InvestigationProfileService().load_for_case(case)

        self.assertEqual(profile.profile_id, "sf_homelessness_review_value_v1")
        self.assertEqual(profile.selection_metric, "Review Value Score")
        self.assertIn("enforcement_or_docket", profile.required_source_families)
        self.assertIn("raw_irs_990", profile.deep_source_families)
        self.assertIn("state_charity_registry", profile.deep_source_families)
        self.assertIn("state_entity_registry", profile.deep_source_families)
        self.assertIn("campaign_finance", profile.deep_source_families)
        self.assertIn("source_connectors", profile.__dataclass_fields__)
        self.assertGreater(profile.scoring_weights["official_adverse_record"], profile.scoring_weights["source_opacity"])
        self.assertIn("entity_resolution", profile.completion_gates)
        self.assertIn("target_discovery", profile.completion_gates)
        self.assertIn("human_action", profile.completion_gates)
        self.assertIn("human_review", profile.completion_gates)

    def test_california_source_catalog_adds_statewide_and_sf_connectors(self) -> None:
        case = CaseRequest(
            case_id="sf_catalog_test",
            title="SF catalog",
            objective="Load catalog.",
            jurisdiction="San Francisco, California",
            metadata={"investigation_profile_path": "data/investigation_profiles/sf_homelessness.json"},
        )
        profile = InvestigationProfileService().load_for_case(case)
        catalog = CaliforniaSourceCatalogService()
        connectors = catalog.connector_specs_for_profile(profile)
        connector_ids = {spec.connector_id for spec in connectors}
        source_families = {spec.source_family for spec in connectors}

        self.assertIn("irs_teos_bulk_xml", connector_ids)
        self.assertIn("fac_public_api", connector_ids)
        self.assertIn("ca_ag_charity_registry", connector_ids)
        self.assertIn("ca_sos_business_search", connector_ids)
        self.assertIn("sf_legislative_research_center", connector_ids)
        self.assertIn("sf_ethics_lobbying_data", connector_ids)
        self.assertIn("county_contract_monitoring_records", connector_ids)
        self.assertIn("state_charity_registry", source_families)
        self.assertIn("state_entity_registry", source_families)
        self.assertIn("campaign_finance", source_families)
        sf_lrc = next(spec for spec in connectors if spec.connector_id == "sf_legislative_research_center")
        self.assertIn("https://www.sf.gov/legislative-research-center-lrc", sf_lrc.source_uris)
        summary = catalog.coverage_summary(profile)
        self.assertGreaterEqual(summary["public_http_connector_count"], 1)
        self.assertGreaterEqual(summary["manual_or_records_request_connector_count"], 1)

    def test_source_acquisition_planner_uses_california_catalog_for_statewide_profile(self) -> None:
        case = CaseRequest(
            case_id="statewide_catalog_test",
            title="Statewide catalog",
            objective="Preview statewide source coverage.",
            jurisdiction="California",
            entities=["Example Shelter"],
            metadata={"investigation_profile_path": "data/investigation_profiles/ca_statewide_homelessness.json"},
        )
        profile = InvestigationProfileService().load_for_case(case)
        source_plan = SourceAcquisitionPlannerService().build_plan(case, profile, [], ["Example Shelter"])
        families = {req.source_family for req in source_plan.requirements}
        connector_ids = {spec.connector_id for spec in source_plan.connector_specs}

        self.assertIn("state_charity_registry", families)
        self.assertIn("state_entity_registry", families)
        self.assertIn("campaign_finance", families)
        self.assertIn("county_contracts", families)
        self.assertIn("ca_ag_charity_registry", connector_ids)
        self.assertIn("ca_sos_business_search", connector_ids)
        self.assertIn("ca_cal_access_power_search", connector_ids)
        self.assertIn("county_contract_monitoring_records", connector_ids)
        registry_requirement = next(req for req in source_plan.requirements if req.source_family == "state_charity_registry")
        self.assertIn("https://oag.ca.gov/charities", registry_requirement.blocker_reason)
        self.assertEqual(registry_requirement.status, "needs_ingestor_or_records_request")

    def test_profile_gate_rejects_missing_generic_spine_gates(self) -> None:
        profile = InvestigationProfile(
            profile_id="thin_profile",
            title="Thin profile",
            topic="test",
            jurisdiction="California",
            target_universe="configured targets",
            selection_metric="Review Value Score",
            required_source_families=["state_awards"],
            scoring_weights={"public_money_exposure": 1.0},
            completion_gates=["source", "human_review"],
            deep_source_families=["raw_irs_990"],
        )

        result = ProfileGateService().audit(profile)

        self.assertEqual(result.status, "REPAIR_REQUIRED")
        self.assertIn("entity_resolution", result.missing_gates)
        self.assertIn("target_discovery", result.missing_gates)
        self.assertIn("human_action", result.missing_gates)

    def test_generic_spine_services_emit_depth_layer_artifacts(self) -> None:
        case = CaseRequest(case_id="generic_spine_test", title="Generic spine", objective="Exercise depth layer.", entities=["Example Shelter"])
        profile = InvestigationProfileService().load_for_case(case)
        provenance = Provenance(
            record_id="payment_row",
            source_uri="https://example.org/payment",
            source_type="sf_hsh_payment_exposure",
            collected_at="2026-05-02T00:00:00+00:00",
            checksum="abc",
            corpus_name="test",
            chunk_id="payment_row#body",
        )
        records = [
            CanonicalRecord(
                record_id="payment_row",
                title="Payment ledger row",
                body="Example Shelter received public payment exposure.",
                source_uri="https://example.org/payment",
                source_type="sf_hsh_payment_exposure",
                published_at="2026-05-02",
                entities=["Example Shelter"],
                attributes={
                    "total_award_exposure": 2500000,
                    "signals": {"sf_hsh_completed_payment_exposure": True},
                    "aliases": ["Example Shelter Services"],
                },
                provenance=provenance,
            )
        ]

        audit = ProfileGateService().audit(profile)
        resolution = EntityResolutionService().resolve(case, profile, records)
        universe = TargetDiscoveryService().discover(case, profile, records)
        source_plan = SourceAcquisitionPlannerService().build_plan(case, profile, records, universe.selected_entities)
        forensic_results = ForensicTestService().run_tests(case, profile, records, universe.selected_entities, source_plan)
        manifest = EvidenceStoreManifestService().build_manifest(case, profile, records)
        matrix = OversightRiskMatrixService().build(case, records, EvidenceBundle(bundle_id="bundle", case_id=case.case_id, query_terms=[], items=[], entity_links=[]))
        actions = HumanActionCompilerService().compile(case, matrix, source_plan, forensic_results)

        self.assertEqual(audit.status, "PASS")
        self.assertEqual(resolution.canonical_entities, ["Example Shelter"])
        self.assertTrue(any(alias.alias == "Example Shelter Services" for alias in resolution.aliases))
        self.assertEqual(universe.selected_entities[0], "Example Shelter")
        self.assertGreater(universe.candidates[0].review_value_score.final_score, 0)
        self.assertGreater(source_plan.needs_ingestor_count + source_plan.blocked_count, 0)
        self.assertTrue(any(result.status == "BLOCKED_BY_SOURCE_GAP" for result in forensic_results))
        self.assertEqual(manifest.entry_count, 1)
        self.assertEqual(manifest.entries[0].immutable_reference, "sha256:abc")
        self.assertGreaterEqual(len(actions.actions), 1)
        self.assertTrue(actions.highest_leverage_action)

    def test_review_value_score_elevates_public_money_and_official_adverse_records(self) -> None:
        case = CaseRequest(case_id="review_value_test", title="Review value", objective="Rank target.", entities=["Example Shelter"])
        profile = InvestigationProfile(
            profile_id="test_profile",
            title="Test",
            topic="homelessness",
            jurisdiction="California",
            target_universe="test",
            selection_metric="Review Value Score",
            required_source_families=["state_awards", "enforcement_or_docket"],
            scoring_weights={
                "public_money_exposure": 0.3,
                "official_adverse_record": 0.3,
                "scope_mismatch": 0.1,
                "spend_outcome_mismatch": 0.1,
                "tax_audit_financial_anomaly": 0.1,
                "source_opacity": 0.05,
                "network_centrality": 0.025,
                "verifiability": 0.025,
            },
            deep_dive_threshold=55,
        )
        provenance = Provenance(
            record_id="official_row",
            source_uri="https://example.org/official",
            source_type="enforcement_or_docket_source",
            collected_at="2026-05-02T00:00:00+00:00",
            checksum="abc",
            corpus_name="test",
            chunk_id="official_row#body",
        )
        records = [
            CanonicalRecord(
                record_id="funding_row",
                title="SF HSH payment row",
                body="Example Shelter has public completed-payment exposure.",
                source_uri="https://data.sfgov.org/resource/qkex-vh98",
                source_type="state_homelessness_award",
                published_at="2026-05-02",
                entities=["Example Shelter"],
                attributes={"total_award_exposure": 125000000, "signals": {"sf_hsh_completed_payment_exposure": True}},
                provenance=provenance,
            ),
            CanonicalRecord(
                record_id="official_row",
                title="Official violation row",
                body="Official agency source says a violation occurred.",
                source_uri="https://example.org/official",
                source_type="enforcement_or_docket_source",
                published_at="2026-05-02",
                entities=["Example Shelter"],
                attributes={"signals": {"official_enforcement_or_docket_flag": True}},
                provenance=provenance,
            ),
        ]
        finding = TriageFinding(
            finding_id="finding",
            case_id=case.case_id,
            entity="Example Shelter",
            source_family="enforcement_or_docket",
            finding_type="official_adverse_record",
            observed_fact="Official source row exists.",
            risk_level="High",
            data_status="Official source recovered",
            trigger_reason="Official adverse record.",
            source_uris=["https://example.org/official"],
            record_ids=["official_row"],
        )

        score = ReviewValueScoringService().score_entity(case, profile, "Example Shelter", records, [finding], [])

        self.assertGreaterEqual(score.final_score, profile.deep_dive_threshold)
        self.assertEqual(score.component_scores["public_money_exposure"], 100.0)
        self.assertEqual(score.component_scores["official_adverse_record"], 100.0)
        self.assertIn("Review Value Score combines materiality", score.rationale)

    def test_completeness_controller_requires_repair_for_missing_handoff_and_sources(self) -> None:
        case = CaseRequest(case_id="controller_gate", title="Controller gate", objective="Force repair.")
        profile = InvestigationProfileService().load_for_case(case)
        guard = CompletionGuardResult(
            guard_id="guard",
            case_id=case.case_id,
            status="FAIL",
            required_source_families=profile.required_source_families,
            selected_entities=[],
            total_searches=0,
            hit_count=0,
            miss_count=0,
            blocker_count=0,
            missing_required=[],
        )

        report = CompletenessControllerService().build_report(
            request=case,
            profile=profile,
            artifact_refs={},
            handoffs=[],
            acquisition_ledger=[],
            completion_guard=guard,
            workflow_status=WorkflowStatus.RETRIEVED,
        )

        self.assertEqual(report.status, "REPAIR_REQUIRED")
        self.assertGreaterEqual(report.retry_required_count, 2)
        self.assertTrue(any(action.rerun_step == "rerun source acquisition" for action in report.repair_actions))
        self.assertTrue(any(action.rerun_step == "rerun affected agent handoff" for action in report.repair_actions))

    def test_completeness_controller_catches_handoff_context_loss(self) -> None:
        case = CaseRequest(case_id="handoff_loss", title="Handoff loss", objective="Catch context loss.")
        profile = InvestigationProfileService().load_for_case(case)
        handoff = ContextHandoffLedger(
            ledger_id="handoff",
            case_id=case.case_id,
            from_step="triage",
            to_step="forensic",
            required_fields=["case_scope", "entities", "evidence_ids", "source_uris", "caveats", "unresolved_gaps", "next_task"],
            present_fields=["case_scope", "entities"],
            missing_fields=["evidence_ids", "source_uris", "caveats", "unresolved_gaps", "next_task"],
            artifact_refs=[],
            status="REPAIR_REQUIRED",
        )
        ledger = [
            AcquisitionSearchRun(
                search_id="search",
                case_id=case.case_id,
                entity="Example Shelter",
                source_family="state_awards",
                query="Example Shelter funding",
                attempted_sources=["official source"],
                matched_record_ids=["record"],
                source_uris=["https://example.org/record"],
                status="hit",
                confidence="High",
            )
        ]
        guard = CompletionGuardResult(
            guard_id="guard",
            case_id=case.case_id,
            status="PASS",
            required_source_families=["state_awards"],
            selected_entities=["Example Shelter"],
            total_searches=1,
            hit_count=1,
            miss_count=0,
            blocker_count=0,
            missing_required=[],
        )

        report = CompletenessControllerService().build_report(
            request=case,
            profile=profile,
            artifact_refs={"acquisition_ledger": "acquisition_ledger.json"},
            handoffs=[handoff],
            acquisition_ledger=ledger,
            completion_guard=guard,
            workflow_status=WorkflowStatus.AWAITING_HUMAN_REVIEW,
        )

        self.assertEqual(report.status, "REPAIR_REQUIRED")
        self.assertTrue(any(check.gate == "handoff" and check.status == "REPAIR_REQUIRED" for check in report.checks))
        self.assertIn("source_uris", report.checks[0].missing_context)

    def test_completeness_controller_surfaces_deep_source_plan_blockers(self) -> None:
        case = CaseRequest(case_id="source_plan_blocker", title="Source plan blocker", objective="Surface blockers.", entities=["Example Shelter"])
        profile = InvestigationProfileService().load_for_case(case)
        temp_dir = PROJECT_ROOT / "runs" / "tests" / f"calds-source-plan-test-{uuid4().hex}"
        try:
            plan_path = temp_dir / "source_acquisition_plan.json"
            write_json(
                plan_path,
                {
                    "requirements": [
                        {
                            "entity": "Example Shelter",
                            "source_family": "board_files",
                            "status": "needs_ingestor_or_records_request",
                            "blocker_reason": "No board-file ingestor is configured for this source family.",
                        }
                    ]
                },
            )
            artifact_refs = {
                "investigation_profile": "investigation_profile.json",
                "profile_gate_audit": "profile_gate_audit.json",
                "entity_resolution": "entity_resolution.json",
                "target_universe": "target_universe.json",
                "source_acquisition_plan": str(plan_path),
                "acquisition_ledger": "acquisition_ledger.json",
                "completion_guard": "completion_guard.json",
                "forensic_test_results": "forensic_test_results.json",
                "evidence_store_manifest": "evidence_store_manifest.json",
                "human_action_plan": "human_action_plan.json",
            }
            handoff = ContextHandoffLedger(
                ledger_id="handoff",
                case_id=case.case_id,
                from_step="triage",
                to_step="forensic",
                required_fields=["case_scope", "entities", "evidence_ids", "source_uris", "caveats", "unresolved_gaps", "next_task"],
                present_fields=["case_scope", "entities", "evidence_ids", "source_uris", "caveats", "unresolved_gaps", "next_task"],
                missing_fields=[],
                artifact_refs=[],
                status="PASS",
            )
            ledger = [
                AcquisitionSearchRun(
                    search_id="search",
                    case_id=case.case_id,
                    entity="Example Shelter",
                    source_family="state_awards",
                    query="Example Shelter funding",
                    attempted_sources=["official source"],
                    matched_record_ids=["record"],
                    source_uris=["https://example.org/record"],
                    status="hit",
                    confidence="High",
                )
            ]
            guard = CompletionGuardResult(
                guard_id="guard",
                case_id=case.case_id,
                status="PASS",
                required_source_families=["state_awards"],
                selected_entities=["Example Shelter"],
                total_searches=1,
                hit_count=1,
                miss_count=0,
                blocker_count=0,
                missing_required=[],
            )

            report = CompletenessControllerService().build_report(
                request=case,
                profile=profile,
                artifact_refs=artifact_refs,
                handoffs=[handoff],
                acquisition_ledger=ledger,
                completion_guard=guard,
                workflow_status=WorkflowStatus.AWAITING_HUMAN_REVIEW,
            )

            self.assertEqual(report.status, "PASS_WITH_BLOCKERS")
            self.assertEqual(report.retry_required_count, 0)
            self.assertEqual(report.blocked_count, 1)
            self.assertTrue(any(check.gate == "source" and check.status == "PASS_WITH_BLOCKERS" for check in report.checks))
            self.assertEqual(report.repair_actions[0].status, "blocked_with_documented_reason")
            self.assertIn("board-file ingestor", report.repair_actions[0].blocker_reason)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_case_compiler_rewrites_human_action_audit_shorthand(self) -> None:
        temp_dir = PROJECT_ROOT / "runs" / "tests" / f"calds-human-action-test-{uuid4().hex}"
        try:
            plan_path = temp_dir / "human_action_plan.json"
            write_json(
                plan_path,
                {
                    "highest_leverage_action": "Open audit source documents.",
                    "actions": [
                        {
                            "entity": "Example Shelter",
                            "priority": "High",
                            "action_type": "audit verification",
                            "action": "Open the audit source documents.",
                            "rationale": "FAC summary reports material weakness years=2023, internal-control deficiency years=2024, not-low-risk years=2022, 2023, findings rows=3.",
                            "required_authority": "authorized human reviewer",
                            "source_refs": ["source_table_fac_audit"],
                        }
                    ],
                },
            )

            actions = CaseDossierService()._compiled_human_actions([str(plan_path)])
            text = "\n".join(actions)

            self.assertIn("Source: human_action_plan.json", text)
            self.assertIn("Federal Audit Clearinghouse data in this run shows", text)
            self.assertNotIn("material weakness years=", text)
            self.assertNotIn("internal-control deficiency years=", text)
            self.assertNotIn("findings rows=", text)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_publication_repairs_stale_public_source_links_before_publish(self) -> None:
        ledger = [
            {
                "ref": "E01",
                "source_urls": ["https://www.tarzanatc.org/news-events/"],
                "link_status": "external_source_linked",
                "source_reference": "https://www.tarzanatc.org/news-events/",
                "link_note": "",
            },
            {
                "ref": "E02",
                "source_urls": ["https://www.socialmodelrecovery.org/programs/"],
                "link_status": "external_source_linked",
                "source_reference": "https://www.socialmodelrecovery.org/programs/",
                "link_note": "",
            },
        ]
        updated, repair = repair_public_source_urls(ledger)

        self.assertEqual(repair["repaired_public_links"], 2)
        self.assertEqual(updated[0]["source_urls"], ["https://www.tarzanatc.org/treatment-news/"])
        self.assertEqual(updated[0]["link_status"], "external_source_linked")
        self.assertEqual(updated[1]["source_urls"], ["https://socialmodelrecovery.org/services/"])
        self.assertEqual(updated[1]["source_reference"], "https://socialmodelrecovery.org/services/")
        self.assertEqual(updated[1]["link_status"], "external_source_linked")
        self.assertIn("replaced 1 stale or renamed public URL", updated[1]["link_note"])
        self.assertIn("Links are not removed as a substitute for repair", repair["note"])
        self.assertEqual(repair["replacements"][0]["old_unlinked_reference"], "www.tarzanatc.org/news-events/")
        self.assertNotIn("old_url", repair["replacements"][0])

    def test_publication_repairs_or_marks_unverified_public_source_links(self) -> None:
        ledger = [
            {
                "ref": "E01",
                "title": "IRS loose XML",
                "source_urls": ["https://apps.irs.gov/pub/epostcard/990/xml/2024/2024120622935468_public.xml"],
                "link_status": "external_source_linked",
                "source_reference": "https://apps.irs.gov/pub/epostcard/990/xml/2024/2024120622935468_public.xml",
                "link_note": "",
            },
            {
                "ref": "E02",
                "title": "Blocked source",
                "source_urls": ["https://example.test/blocked-source.pdf", "https://example.test/good-source"],
                "link_status": "external_source_linked",
                "source_reference": "https://example.test/blocked-source.pdf; https://example.test/good-source",
                "link_note": "",
            },
        ]
        repaired, _ = repair_public_source_urls(ledger)
        self.assertEqual(repaired[0]["source_urls"], ["https://apps.irs.gov/pub/epostcard/990/xml/2024/index_2024.csv"])

        report = LinkIntegrityReport(
            report_id="links",
            status="FAIL",
            checked_url_count=2,
            error_count=1,
            warning_count=0,
            checks=[
                SourceLinkCheck(
                    check_id="bad",
                    url="https://example.test/blocked-source.pdf",
                    status="ERROR",
                    http_status=None,
                    final_url="",
                    content_type="",
                    error="HTTP Error 403: Forbidden",
                )
            ],
        )
        updated, unresolved = mark_unverified_source_urls(repaired, report)
        self.assertEqual(updated[1]["source_urls"], ["https://example.test/good-source"])
        self.assertEqual(updated[1]["link_status"], "external_source_linked")
        self.assertIn("unverified_source_references", updated[1])
        self.assertIn("Source access required", updated[1]["link_note"])
        self.assertEqual(unresolved["unverified_public_links"], 1)

    def test_source_access_distinguishes_verified_links_from_completion_guard(self) -> None:
        ledger = [{"ref": "E01", "source_urls": ["https://example.test"], "link_note": ""}]
        report = source_access_report(
            ledger,
            {
                "status": "PASS_WITH_BLOCKERS",
                "blocker_count": 1,
                "missing_required": ["Shelter Group: enforcement_or_docket"],
            },
        )
        self.assertTrue(report["public_link_access_complete"])
        self.assertFalse(report["completion_guard_access_complete"])
        self.assertFalse(report["complete"])

    def test_source_access_includes_deep_source_plan_blockers(self) -> None:
        ledger = [{"ref": "E01", "source_urls": ["https://example.test"], "link_note": ""}]
        report = source_access_report(
            ledger,
            {
                "status": "PASS",
                "blocker_count": 0,
                "missing_required": [],
            },
            {
                "status": "PASS_WITH_BLOCKERS",
                "blocked_count": 1,
                "retry_required_count": 0,
                "repair_actions": [
                    {
                        "step": "source_acquisition",
                        "issue": "Deep source requirement remains unresolved: Example Shelter / board_files.",
                        "status": "blocked_with_documented_reason",
                    }
                ],
            },
        )

        self.assertTrue(report["public_link_access_complete"])
        self.assertTrue(report["completion_guard_access_complete"])
        self.assertFalse(report["deep_source_access_complete"])
        self.assertFalse(report["complete"])
        self.assertEqual(report["deep_source_blocker_count"], 1)
        self.assertEqual(report["total_source_blocker_count"], 1)
        self.assertIn("Example Shelter / board_files", report["deep_source_missing_required"])

    def test_sentinel_escalated_language_catches_legal_and_causal_overclaims(self) -> None:
        self.assertTrue(find_escalated_language("The records prove misconduct occurred."))
        self.assertTrue(find_escalated_language("The provider was found liable for fraud."))
        self.assertTrue(find_escalated_language("The entity caused provider failure."))
        self.assertFalse(find_escalated_language("CalDS flags possible waste, fraud, abuse, or mismanagement for human review."))

    def test_briefing_claim_context_requires_direct_entity_source(self) -> None:
        service_item = EvidenceItem(
            item_id="healthright_service",
            record_id="healthright_services",
            title="HealthRIGHT 360 substance use disorder services",
            source_uri="https://www.healthright360.org/our-services/substance-use-disorder/",
            source_type="org_service_page",
            published_at="2026-04-24",
            excerpt=(
                "Service summary from official source(s): https://www.healthright360.org/our-services/substance-use-disorder/: "
                "HealthRIGHT 360 describes substance use disorder treatment services, chronic disease care, and residential programs. "
                "Facebook X Instagram Contact Get Help Careers Volunteer Donate Home About Our Work."
            ),
            relevance_score=1.0,
            matched_terms=["substance", "treatment"],
            provenance=Provenance(
                record_id="healthright_services",
                source_uri="https://www.healthright360.org/our-services/substance-use-disorder/",
                source_type="org_service_page",
                collected_at="2026-04-24T00:00:00+00:00",
                checksum="healthright_service",
                corpus_name="test",
                chunk_id="healthright_services#body",
            ),
        )
        bundle = EvidenceBundle(
            bundle_id="bundle_test",
            case_id="case_test",
            query_terms=["treatment"],
            items=[service_item],
            entity_links=[],
        )
        service = CaseDossierService()

        context = service._entity_claim_context("HealthRIGHT 360", bundle, {"healthright_service": "E01"})
        self.assertIn("The recovered official service page", context)
        self.assertIn("substance use disorder treatment", context)
        self.assertNotIn("Facebook X Instagram Contact Get Help Careers Volunteer Donate Home About Our Work", context)
        self.assertIn("does not fill that gap", service._entity_claim_context("CRI-Help Inc", bundle, {"healthright_service": "E01"}))

    def test_live_outcome_ingestor_configures_direct_service_pages(self) -> None:
        script_path = PROJECT_ROOT / "scripts" / "ingest_outcome_sources.py"
        spec = importlib.util.spec_from_file_location("ingest_outcome_sources", script_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        missing = [target["name"] for target in module.TARGETS if not target.get("service_urls")]
        self.assertEqual(missing, [])
        for target in module.TARGETS:
            for url in target["service_urls"]:
                self.assertTrue(url.startswith("https://"), f"{target['name']} has non-HTTPS service URL: {url}")

        source_text = script_path.read_text(encoding="utf-8")
        self.assertNotIn("SERVICE_TEXT_FALLBACKS", source_text)
        self.assertNotIn("official_search_fallback", source_text)
        self.assertIn("do not substitute hand-entered fallback text", source_text)

    def test_live_pipeline_has_no_skip_flags_for_required_source_families(self) -> None:
        for script_name in ["run_live_case_pipeline.py", "ingest_live_recovery_sources.py"]:
            text = (PROJECT_ROOT / "scripts" / script_name).read_text(encoding="utf-8")
            self.assertNotIn("--skip-federal-awards", text)
            self.assertNotIn("skip_federal_awards", text)

    def test_search_diversifies_required_source_types_before_relevance_fill(self) -> None:
        records = []
        for record_id, source_type, body in [
            ("high_a", "source_a", "alpha beta gamma named entity"),
            ("low_b", "source_b", "alpha named entity"),
            ("low_c", "source_c", "alpha named entity"),
        ]:
            records.append(
                CanonicalRecord(
                    record_id=record_id,
                    title=record_id,
                    body=body,
                    source_uri=f"local://{record_id}",
                    source_type=source_type,
                    published_at="2026-04-24",
                    entities=["Named Entity"],
                    attributes={},
                    provenance=Provenance(
                        record_id=record_id,
                        source_uri=f"local://{record_id}",
                        source_type=source_type,
                        collected_at="2026-04-24T00:00:00+00:00",
                        checksum=record_id,
                        corpus_name="test",
                        chunk_id=f"{record_id}#body",
                    ),
                )
            )

        hits = KeywordSearchIndex(records).search(
            SearchPlan(
                terms=["alpha", "beta", "gamma", "named", "entity"],
                allowed_sources=["source_a", "source_b", "source_c"],
                max_results=2,
                required_source_types=["source_b", "source_c"],
            )
        )

        self.assertEqual([hit.record_id for hit in hits], ["low_b", "low_c"])

    def test_weingart_style_official_enforcement_source_triggers_triage(self) -> None:
        record = CanonicalRecord(
            record_id="enforcement_docket_weingart_center_1",
            title="Official enforcement/docket triage source: Weingart Center Association",
            body=(
                "Official federal source describes a charged third-party Cheviot Hills transaction "
                "and municipal records identify the Weingart Shelby project."
            ),
            source_uri="https://www.fhfaoig.gov/example.pdf",
            source_type="enforcement_or_docket_source",
            published_at="2025-10-16",
            entities=["Weingart Center Association"],
            attributes={"signals": {"official_enforcement_or_docket_flag": True, "connected_party_enforcement_exposure": True, "missing_data": True}},
            provenance=Provenance(
                record_id="enforcement_docket_weingart_center_1",
                source_uri="https://www.fhfaoig.gov/example.pdf",
                source_type="enforcement_or_docket_source",
                collected_at="2026-04-29T00:00:00+00:00",
                checksum="enforcement",
                corpus_name="test",
                chunk_id="enforcement#body",
            ),
        )
        case = CaseRequest(
            case_id="triage_test",
            title="Triage regression",
            objective="Find official enforcement misses.",
            entities=["Weingart Center Association"],
        )
        results = HomelessnessTriageService().build(case, [record])
        self.assertEqual(results[0].triage_priority, "High")
        self.assertTrue(results[0].deep_dive_recommended)
        self.assertEqual(results[0].findings[0].source_family, "enforcement_or_docket")
        self.assertEqual(results[0].findings[0].finding_type, "connected-party official charge trigger")
        self.assertIn("mandatory deep-dive trigger", results[0].findings[0].trigger_reason)
        self.assertIn("presumed innocent", " ".join(results[0].findings[0].caveats))

    def test_completion_guard_does_not_count_discovery_only_records(self) -> None:
        record = CanonicalRecord(
            record_id="enforcement_docket_discovery_shelter_group",
            title="Systematic enforcement search target: Shelter Group",
            body="Search target row only; no official enforcement record recovered.",
            source_uri="https://www.justice.gov/",
            source_type="enforcement_docket_discovery",
            published_at="2026-04-30",
            entities=["Shelter Group"],
            attributes={"signals": {"discovery_only_source_gap": True, "source_gap_only": True, "not_citation_ready": True}},
            provenance=Provenance(
                record_id="enforcement_docket_discovery_shelter_group",
                source_uri="https://www.justice.gov/",
                source_type="enforcement_docket_discovery",
                collected_at="2026-04-30T00:00:00+00:00",
                checksum="discovery",
                corpus_name="test",
                chunk_id="discovery#body",
            ),
        )
        case = CaseRequest(case_id="guard_test", title="Guard regression", objective="Do not count discovery gaps.", entities=["Shelter Group"])
        ledger = CompletionGuardService().build_acquisition_ledger(case, [record], ["Shelter Group"], ["enforcement_or_docket"])
        self.assertEqual(ledger[0].status, "miss")
        self.assertEqual(ledger[0].matched_record_ids, [])
        self.assertIn("Only discovery/source-gap", ledger[0].blocker_reason)

    def test_completion_guard_accepts_official_no_record_search_without_treating_it_as_clearance(self) -> None:
        record = CanonicalRecord(
            record_id="enforcement_docket_no_record_shelter_group",
            title="Official enforcement search: Shelter Group",
            body="Configured public official searches completed; no public adverse record recovered. PACER and local courts remain manual.",
            source_uri="https://search.justice.gov/search?affiliate=justice&query=%22Shelter%20Group%22",
            source_type="enforcement_docket_official_no_record_search",
            published_at="2026-04-30",
            entities=["Shelter Group"],
            attributes={"signals": {"official_source_search_completed_no_hit": True, "searched_no_public_official_record": True}},
            provenance=Provenance(
                record_id="enforcement_docket_no_record_shelter_group",
                source_uri="https://search.justice.gov/search?affiliate=justice&query=%22Shelter%20Group%22",
                source_type="enforcement_docket_official_no_record_search",
                collected_at="2026-04-30T00:00:00+00:00",
                checksum="official-no-record",
                corpus_name="test",
                chunk_id="official-no-record#body",
            ),
        )
        case = CaseRequest(case_id="guard_no_record_test", title="Guard no-record regression", objective="Accept official no-record searches with caveats.", entities=["Shelter Group"])
        service = CompletionGuardService()
        ledger = service.build_acquisition_ledger(case, [record], ["Shelter Group"], ["enforcement_or_docket"])
        guard = service.guard(case, ledger, ["Shelter Group"], ["enforcement_or_docket"])
        self.assertEqual(ledger[0].status, "searched_no_public_official_record")
        self.assertEqual(ledger[0].matched_record_ids, ["enforcement_docket_no_record_shelter_group"])
        self.assertEqual(guard.status, "PASS")
        self.assertEqual(guard.blocker_count, 0)
        self.assertEqual(guard.missing_required, [])
        self.assertIn("not legal clearance", " ".join(guard.notes))

    def test_triage_missing_source_families_ignore_discovery_gap_records(self) -> None:
        record = CanonicalRecord(
            record_id="enforcement_docket_discovery_shelter_group",
            title="Enforcement/docket discovery gap: Shelter Group",
            body="Searches attempted but no citation-ready official enforcement row was recovered.",
            source_uri="https://www.justice.gov/",
            source_type="enforcement_docket_discovery",
            published_at="2026-05-01",
            entities=["Shelter Group"],
            attributes={"signals": {"discovery_only_source_gap": True, "not_citation_ready": True}},
            provenance=Provenance(
                record_id="enforcement_docket_discovery_shelter_group",
                source_uri="https://www.justice.gov/",
                source_type="enforcement_docket_discovery",
                collected_at="2026-05-01T00:00:00+00:00",
                checksum="discovery-gap",
                corpus_name="test",
                chunk_id="discovery#body",
            ),
        )
        case = CaseRequest(case_id="triage_gap_test", title="Triage gap", objective="Do not count discovery gap as coverage.", entities=["Shelter Group"])
        result = HomelessnessTriageService().build(case, [record])[0]
        self.assertIn("enforcement_or_docket", result.missing_source_families)
        self.assertEqual(result.triage_priority, "Source-gap")

    def test_scoring_separates_acquisition_coverage_from_gap_burden(self) -> None:
        provenance = Provenance(
            record_id="gap_record",
            source_uri="https://example.test/source",
            source_type="contract_payment_discovery",
            collected_at="2026-04-30T00:00:00+00:00",
            checksum="checksum",
            corpus_name="test",
            chunk_id="gap#body",
        )
        bundle = EvidenceBundle(
            bundle_id="bundle",
            case_id="score_gap_test",
            query_terms=[],
            items=[
                EvidenceItem(
                    item_id="E1",
                    record_id="gap_record",
                    title="Contract payment gap",
                    source_uri="https://example.test/source",
                    source_type="contract_payment_discovery",
                    published_at="2026-04-30",
                    excerpt="No direct payment ledger was recovered in this pass.",
                    relevance_score=0.9,
                    matched_terms=["payment"],
                    provenance=provenance,
                    signals={"missing_data": True},
                ),
                EvidenceItem(
                    item_id="E2",
                    record_id="gap_record_2",
                    title="IRS filing gap",
                    source_uri="https://example.test/irs",
                    source_type="irs_990_summary",
                    published_at="2026-04-30",
                    excerpt="IRS profile row exists, but raw filing source was not recovered.",
                    relevance_score=0.8,
                    matched_terms=["irs"],
                    provenance=Provenance(
                        record_id="gap_record_2",
                        source_uri="https://example.test/irs",
                        source_type="irs_990_summary",
                        collected_at="2026-04-30T00:00:00+00:00",
                        checksum="checksum-2",
                        corpus_name="test",
                        chunk_id="irs#body",
                    ),
                    signals={"missing_data": True},
                ),
            ],
            entity_links=[],
        )
        guard = CompletionGuardResult(
            guard_id="guard",
            case_id="score_gap_test",
            status="PASS",
            required_source_families=["contracts", "tax"],
            selected_entities=["Shelter Group"],
            total_searches=2,
            hit_count=2,
            miss_count=0,
            blocker_count=0,
            missing_required=[],
        )
        score = LeadScoringService().score(bundle, guard)
        self.assertEqual(score.source_completeness_score, 100.0)
        self.assertEqual(score.gap_burden_count, 2)
        self.assertEqual(score.completion_guard_resolved, 2)
        self.assertLess(score.publication_confidence_score, 100.0)
        self.assertEqual(score.missing_data_source_types["contract_payment_discovery"], 1)
        self.assertEqual(score.missing_data_source_types["irs_990_summary"], 1)

    def test_scoring_does_not_double_count_completion_guard_misses(self) -> None:
        guard = CompletionGuardResult(
            guard_id="guard",
            case_id="score_miss_test",
            status="PASS_WITH_BLOCKERS",
            required_source_families=["contracts", "tax"],
            selected_entities=["Shelter Group"],
            total_searches=2,
            hit_count=1,
            miss_count=1,
            blocker_count=1,
            missing_required=["Shelter Group: tax"],
        )
        bundle = EvidenceBundle(bundle_id="bundle", case_id="score_miss_test", query_terms=[], items=[], entity_links=[])
        score = LeadScoringService().score(bundle, guard)
        self.assertEqual(score.completion_guard_resolved, 1)
        self.assertEqual(score.completion_guard_miss_count, 1)
        self.assertEqual(score.completion_guard_blocker_count, 1)
        self.assertEqual(score.source_completeness_score, 50.0)

    def test_scoring_does_not_substitute_source_diversity_for_completion_coverage(self) -> None:
        provenance = Provenance(
            record_id="record",
            source_uri="https://example.test/source",
            source_type="irs_990_summary",
            collected_at="2026-05-01T00:00:00+00:00",
            checksum="checksum",
            corpus_name="test",
            chunk_id="record#body",
        )
        bundle = EvidenceBundle(
            bundle_id="bundle",
            case_id="score_no_guard_test",
            query_terms=[],
            items=[
                EvidenceItem(
                    item_id="E1",
                    record_id="record",
                    title="IRS summary",
                    source_uri="https://example.test/source",
                    source_type="irs_990_summary",
                    published_at="2026-05-01",
                    excerpt="IRS summary row.",
                    relevance_score=1.0,
                    matched_terms=["irs"],
                    provenance=provenance,
                )
            ],
            entity_links=[],
        )
        score = LeadScoringService().score(bundle)
        self.assertEqual(score.completion_guard_total, 0)
        self.assertEqual(score.source_completeness_score, 0.0)
        self.assertGreater(score.source_diversity_confidence_score, 0.0)

    def test_lead_scorer_uses_selected_deep_dive_entities(self) -> None:
        case = CaseRequest(
            case_id="selected_entities_test",
            title="Selected entities",
            objective="Use selected entities.",
            entities=["Unselected One", "Unselected Two"],
        )
        bundle = EvidenceBundle(bundle_id="bundle", case_id="selected_entities_test", query_terms=[], items=[], entity_links=[])
        lead = LeadScorerAgent(LeadScoringService()).create_candidate(
            case,
            bundle,
            selected_entities=["Flagged Entity"],
        )
        self.assertIn("Flagged Entity", lead.statement)
        self.assertNotIn("Unselected One", lead.statement)

    def test_workflow_adds_selected_entity_deep_source_context_hits(self) -> None:
        temp_dir = PROJECT_ROOT / "runs" / "tests" / f"deep-source-context-{uuid4().hex}"
        corpus = temp_dir / "corpus"
        try:
            write_json(
                corpus / "contract_payment_discovery_shelter_group.json",
                {
                    "record_id": "contract_payment_discovery_shelter_group",
                    "title": "Contract/payment acquisition gap: Shelter Group",
                    "source_uri": "https://www.hcd.ca.gov/funding/homekey/funding-overview",
                    "source_type": "contract_payment_discovery",
                    "published_at": "2026-04-30",
                    "entities": ["Shelter Group"],
                    "attributes": {"signals": {"discovery_only_source_gap": True}},
                    "body": "No direct standard agreement, payment ledger, monitoring letter, or corrective-action record was recovered in this pass.",
                },
            )
            workflow = CaseWorkflow(corpus, temp_dir / "runs")
            hits = workflow._ensure_source_acquisition_context_hits(["Shelter Group"], [])
            self.assertEqual([hit.record_id for hit in hits], ["contract_payment_discovery_shelter_group"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_run_readiness_detects_material_change(self) -> None:
        temp_dir = PROJECT_ROOT / "runs" / "tests" / f"readiness-{uuid4().hex}"
        baseline = temp_dir / "baseline" / "case"
        current = temp_dir / "current" / "case"
        try:
            for run_dir, evidence_count, source_type, high_count, guard_hits in [
                (baseline, 1, "state_homelessness_award", 0, 1),
                (current, 2, "irs_990_raw_artifact", 1, 2),
            ]:
                artifacts = run_dir / "artifacts"
                write_json(run_dir / "workflow_state.json", {"case_id": "readiness_case", "status": "AWAITING_HUMAN_REVIEW"})
                write_json(
                    artifacts / "evidence_bundle.json",
                    {"case_id": "readiness_case", "items": [{"source_type": source_type} for _ in range(evidence_count)]},
                )
                write_json(
                    artifacts / "oversight_risk_matrix.json",
                    {
                        "case_id": "readiness_case",
                        "indicators": [{"risk_level": "High" if index < high_count else "Medium", "data_status": "Complete"} for index in range(evidence_count)],
                    },
                )
                write_json(artifacts / "completion_guard.json", {"status": "PASS", "hit_count": guard_hits, "blocker_count": 0, "missing_required": []})
                write_json(artifacts / "acquisition_ledger.json", {"searches": [{"status": "hit"} for _ in range(guard_hits)]})
                write_json(artifacts / "citation_verification.json", {"status": "PASS", "error_count": 0})
                write_json(artifacts / "forensic_investigation_plan.json", {"selected_entities": ["Shelter Group"]})
                write_json(run_dir / "public_site" / "publication_manifest.json", {"passed": True})
            output = current / "artifacts" / "run_readiness.json"
            result = RunReadinessService().compare(current, baseline, output)
            self.assertEqual(result.status, "MATERIAL_CHANGE_READY")
            self.assertTrue(output.exists())
            self.assertTrue(any("evidence item count" in item for item in result.material_changes))
            self.assertEqual(result.blockers, [])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_homelessness_scope_mismatch_keeps_keyword_only_signal_medium(self) -> None:
        record = CanonicalRecord(
            record_id="public_statements_shelter_group",
            title="Public statement page harvest: Shelter Group",
            body="The shelter group page advertises a voter registration drive, housing services, and outreach.",
            source_uri="https://example.org/shelter",
            source_type="public_statement_source",
            published_at="2026-04-30",
            entities=["Shelter Group"],
            attributes={"signals": {"public_statement_source_checked": True, "off_scope_keyword_match": True}, "matched_terms": ["voter registration"]},
            provenance=Provenance(
                record_id="public_statements_shelter_group",
                source_uri="https://example.org/shelter",
                source_type="public_statement_source",
                collected_at="2026-04-30T00:00:00+00:00",
                checksum="scope",
                corpus_name="test",
                chunk_id="scope#body",
            ),
        )
        case = CaseRequest(
            case_id="scope_test",
            title="Scope regression",
            objective="Flag homelessness scope mismatch.",
            entities=["Shelter Group"],
        )
        matrix = OversightRiskMatrixService().build(case, [record], EvidenceBundle(bundle_id="bundle", case_id="scope_test", query_terms=[], items=[], entity_links=[]))
        scope_rows = [item for item in matrix.indicators if item.risk_area == "Homelessness scope mismatch" and item.entity == "Shelter Group"]
        self.assertTrue(scope_rows)
        self.assertTrue(any(item.risk_level == "Medium" and item.data_status == "observed_keyword_only" for item in scope_rows))
        self.assertIn("501(c)(3)", " ".join(caveat for item in scope_rows for caveat in item.caveats))

    def test_homelessness_scope_mismatch_requires_funding_nexus_for_high(self) -> None:
        record = CanonicalRecord(
            record_id="public_statements_shelter_group_nexus",
            title="Public statement page harvest: Shelter Group",
            body="The shelter group page advertises a voter registration drive charged to a homelessness grant outreach budget.",
            source_uri="https://example.org/shelter-nexus",
            source_type="public_statement_source",
            published_at="2026-05-01",
            entities=["Shelter Group"],
            attributes={
                "signals": {
                    "public_statement_source_checked": True,
                    "off_scope_keyword_match": True,
                    "funding_scope_linked": True,
                },
                "matched_terms": ["voter registration"],
            },
            provenance=Provenance(
                record_id="public_statements_shelter_group_nexus",
                source_uri="https://example.org/shelter-nexus",
                source_type="public_statement_source",
                collected_at="2026-05-01T00:00:00+00:00",
                checksum="scope-nexus",
                corpus_name="test",
                chunk_id="scope-nexus#body",
            ),
        )
        case = CaseRequest(
            case_id="scope_nexus_test",
            title="Scope nexus regression",
            objective="Flag homelessness scope mismatch.",
            entities=["Shelter Group"],
        )
        matrix = OversightRiskMatrixService().build(case, [record], EvidenceBundle(bundle_id="bundle", case_id="scope_nexus_test", query_terms=[], items=[], entity_links=[]))
        scope_rows = [item for item in matrix.indicators if item.risk_area == "Homelessness scope mismatch" and item.entity == "Shelter Group"]
        self.assertTrue(any(item.risk_level == "High" and item.data_status == "observed_with_funding_nexus" for item in scope_rows))

    def test_homelessness_ingestor_configures_propublica_and_scope_terms(self) -> None:
        script_path = PROJECT_ROOT / "scripts" / "ingest_homelessness_top15_sources.py"
        spec = importlib.util.spec_from_file_location("ingest_homelessness_top15_sources", script_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        self.assertIn("projects.propublica.org/nonprofits/api/v2", module.PROPUBLICA_API_BASE)
        self.assertIn("voter registration", module.HOMELESSNESS_SCOPE_HIGH_TERMS)
        self.assertIn("citizenship", module.HOMELESSNESS_SCOPE_HIGH_TERMS)
        self.assertIn("ice enforcement", module.HOMELESSNESS_SCOPE_HIGH_TERMS)
        self.assertEqual(module.propublica_org_page("956054617"), "https://projects.propublica.org/nonprofits/organizations/956054617")
        self.assertTrue(str(module.IRS_RAW_DIR).endswith("irs_raw"))
        self.assertTrue(str(module.DEFAULT_ARTIFACT_BASE_DIR).endswith("homelessness_top15_sources_2026_04_29"))
        self.assertTrue(hasattr(module, "configure_artifact_dirs"))
        self.assertTrue(str(module.FAC_DIR).endswith("fac"))
        self.assertTrue(str(module.CONTRACT_DIR).endswith("contracts"))
        self.assertTrue(str(module.DOCKET_DIR).endswith("enforcement_dockets"))
        self.assertIn("app.fac.gov/dissemination/public-data/gsa/full/general.csv", module.FAC_GENERAL_CSV_URL)
        self.assertTrue(any(source["entity"] == "DignityMoves" for source in module.LOCAL_CONTRACT_MONITORING_SOURCES))
        self.assertTrue(any(source["entity"] == "The People Concern" for source in module.LOCAL_CONTRACT_MONITORING_SOURCES))
        self.assertIn("https://search.justice.gov/search", module.US_DOJ_SEARCH_URL)
        self.assertTrue(module.PUBLIC_ENFORCEMENT_SEARCH_SOURCES)
        self.assertTrue(module.MANUAL_ENFORCEMENT_SEARCH_SOURCES)
        module.configure_profile("ca_statewide_homelessness", target_limit=15)
        statewide_payload = module.build_case_request_payload(PROJECT_ROOT / "data" / "live_corpus" / "statewide_test")
        self.assertEqual(module.CASE_ID, "live_ca_homelessness_top15_2026_04_29")
        self.assertEqual(module.ACTIVE_PROFILE, "ca_statewide_homelessness")
        self.assertEqual(
            statewide_payload["metadata"]["investigation_profile_path"],
            "data/investigation_profiles/ca_statewide_homelessness.json",
        )
        self.assertIn("California Attorney General charity registry", statewide_payload["allowed_sources"])
        self.assertIn("CAL-ACCESS, Power Search, and FPPC campaign/lobbying sources", statewide_payload["allowed_sources"])
        module.configure_profile("sf_homelessness", target_limit=15)
        self.assertEqual(module.CASE_ID, "live_ca_sf_homelessness_complex")
        self.assertEqual(module.ACTIVE_PROFILE, "sf_homelessness")
        self.assertIn("United Council of Human Services", module.SF_ADVERSE_ENTITY_BOOSTS)
        self.assertIn("San Francisco", module.build_case_request_payload(PROJECT_ROOT / "data" / "live_corpus" / "sf_test")["jurisdiction"])
        self.assertEqual(
            module.build_case_request_payload(PROJECT_ROOT / "data" / "live_corpus" / "sf_test")["metadata"]["selection_metric"],
            "Review Value Score",
        )
        self.assertEqual(
            module.extract_object_id_from_pdf_url("https://projects.propublica.org/nonprofits/download-filing?path=IRS%2F956054617_202304_990_2024040522347579.pdf"),
            "2024040522347579",
        )
        self.assertTrue(module.irs_xml_candidate_urls({"pdf_url": "https://projects.propublica.org/nonprofits/download-filing?path=IRS%2F956054617_202304_990_2024040522347579.pdf", "ein": "956054617", "tax_period": "202304"}))

    def test_risk_matrix_uses_raw_irs_xml_fields(self) -> None:
        temp_dir = PROJECT_ROOT / "runs" / "tests" / f"calds-raw-irs-test-{uuid4().hex}"
        try:
            table_path = temp_dir / "raw_irs_990_artifact_summary.json"
            write_json(
                table_path,
                {
                    "rows": [
                        {
                            "entity": "Shelter Group",
                            "ein": "123456789",
                            "tax_period": "202304",
                            "tax_period_year": 2023,
                            "xml_downloaded": True,
                            "xml_local_path": str(temp_dir / "return.xml"),
                            "xml_sha256": "abc123",
                            "parsed_detail_fields": {
                                "total_revenue": 1000000,
                                "government_grants": 900000,
                                "total_expenses": 800000,
                                "top_compensation_total": 525000,
                                "top_compensation_person": "Jane Doe",
                                "top_compensation_title": "CEO",
                                "compensation_is_aggregate": False,
                                "political_campaign_activity": False,
                                "lobbying_activities": True,
                            },
                        }
                    ]
                },
            )
            provenance = Provenance("raw_table", str(table_path), "source_extraction_irs_990_raw_artifact_table", "2026-04-30", "abc123", "test", "raw_table")
            record = CanonicalRecord(
                record_id="raw_table",
                title="Raw IRS table",
                body="Raw IRS XML fields",
                source_uri=str(table_path),
                source_type="source_extraction_irs_990_raw_artifact_table",
                published_at="2026-04-30",
                entities=["Shelter Group"],
                attributes={"table_path": str(table_path), "signals": {}},
                provenance=provenance,
            )
            case = CaseRequest(case_id="raw_irs_case", title="Raw IRS case", objective="Use raw XML fields.", entities=["Shelter Group"])
            matrix = OversightRiskMatrixService().build(case, [record], EvidenceBundle(bundle_id="bundle", case_id="raw_irs_case", query_terms=[], items=[], entity_links=[]))
            facts = "\n".join(item.observed_fact for item in matrix.indicators)
            self.assertIn("government grants $900,000 / total revenue $1,000,000 = 90.0%", facts)
            self.assertIn("Jane Doe (CEO)", facts)
            self.assertIn("LobbyingActivitiesInd=yes", facts)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_risk_matrix_reports_public_enforcement_no_record_blocker(self) -> None:
        temp_dir = PROJECT_ROOT / "runs" / "tests" / f"calds-enforcement-search-test-{uuid4().hex}"
        try:
            table_path = temp_dir / "enforcement_docket_discovery_summary.json"
            write_json(
                table_path,
                {
                    "rows": [
                        {
                            "entity": "Shelter Group",
                            "status": "searched_no_public_official_record",
                            "public_official_search_completed_count": 4,
                            "manual_sources_remaining": [{"name": "PACER Case Locator"}, {"name": "Local trial court portal"}],
                        }
                    ]
                },
            )
            provenance = Provenance("enforcement_search", str(table_path), "source_extraction_enforcement_docket_discovery_table", "2026-04-30", "abc123", "test", "search#body")
            record = CanonicalRecord(
                record_id="enforcement_search",
                title="Official enforcement search table",
                body="Official public searches completed with no adverse public record recovered.",
                source_uri=str(table_path),
                source_type="source_extraction_enforcement_docket_discovery_table",
                published_at="2026-04-30",
                entities=["Shelter Group"],
                attributes={"table_path": str(table_path), "signals": {"official_source_search_completed_no_hit": True}},
                provenance=provenance,
            )
            case = CaseRequest(case_id="enforcement_search_case", title="Enforcement search case", objective="Distinguish no-record blockers.", entities=["Shelter Group"])
            matrix = OversightRiskMatrixService().build(case, [record], EvidenceBundle(bundle_id="bundle", case_id="enforcement_search_case", query_terms=[], items=[], entity_links=[]))
            rows = [item for item in matrix.indicators if item.risk_area == "Enforcement and docket history" and item.entity == "Shelter Group"]
            self.assertEqual(rows[0].risk_level, "Low")
            self.assertEqual(rows[0].data_status, "searched_no_public_official_record")
            self.assertIn("not a legal clearance", " ".join(rows[0].caveats))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_public_url_extractor_stops_at_escaped_newline(self) -> None:
        value = "ProPublica API: https://projects.propublica.org/nonprofits/api/\\nIRS source: https://www.irs.gov/example"
        self.assertEqual(
            extract_urls(value),
            ["https://projects.propublica.org/nonprofits/api/", "https://www.irs.gov/example"],
        )


if __name__ == "__main__":
    unittest.main()
