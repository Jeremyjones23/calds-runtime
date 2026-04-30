from __future__ import annotations

from pathlib import Path
import importlib.util
import shutil
import unittest
from uuid import uuid4

from calds_runtime.case_compiler import CaseDossierService
from calds_runtime.case_workflow import CaseWorkflow
from calds_runtime.contracts import CanonicalRecord, CaseRequest, EvidenceBundle, EvidenceItem, Provenance, WorkflowStatus, read_json, write_json
from calds_runtime.forensic_triage import HomelessnessTriageService
from calds_runtime.publication import extract_urls, publish_case_site_from_run
from calds_runtime.quality_gates import CompletionGuardService, RunReadinessService
from calds_runtime.risk_matrix import OversightRiskMatrixService
from calds_runtime.search import KeywordSearchIndex, SearchPlan
from calds_runtime.sentinel import find_escalated_language


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
            self.assertIn("results", triage)
            self.assertIn("selected_entities", forensic_plan)
            self.assertEqual(handoff["status"], "PASS")
            self.assertIn("searches", acquisition)
            self.assertGreaterEqual(len(acquisition["searches"]), len(forensic_plan["selected_entities"]))
            self.assertIn(completion_guard["status"], {"PASS", "PASS_WITH_BLOCKERS"})
            self.assertGreaterEqual(completion_guard["total_searches"], len(acquisition["searches"]))
            self.assertIn("misses are blockers", " ".join(completion_guard["notes"]))
            self.assertIn("triaged", state["completed_steps"])

            dossier_path = Path(state["artifacts"]["case_dossier_markdown"])
            dossier = read_json(Path(state["artifacts"]["case_dossier"]))
            self.assertEqual(dossier["compiler_role"], "Case Compiler")
            self.assertTrue(dossier_path.exists())
            dossier_text = dossier_path.read_text(encoding="utf-8")
            self.assertIn("## 1. Supervisor Brief", dossier_text)
            self.assertIn("## 2. Entity Briefs", dossier_text)
            self.assertIn("## 5. Evidence Detail By Entity", dossier_text)
            self.assertIn("## 4. Case Dossier Orientation", dossier_text)
            self.assertIn("## 6. Flagged Review Matrix", dossier_text)
            self.assertIn("## 7. Evidence Citation Ledger", dossier_text)
            self.assertIn("## 8. Human-Only Next Steps", dossier_text)
            self.assertIn("## 10. Human Review Required", dossier_text)
            self.assertIn("Source URI", dossier_text)
            self.assertIn("Checksum", dossier_text)
            self.assertIn("CalDS flags", dossier_text)
            self.assertIn("What CalDS Found First", dossier_text)
            self.assertIn("Triage Gate", dossier_text)
            self.assertIn("Acquisition and Completion Guard", dossier_text)
            self.assertIn("Completion guard status", dossier_text)
            self.assertIn("Decision Needed", dossier_text)
            self.assertIn("possible waste, fraud, abuse, or mismanagement", dossier_text)
            self.assertIn("Plain-Language Source Glossary", dossier_text)
            self.assertIn("Federal Audit Clearinghouse", dossier_text)
            self.assertIn("California Department of Health Care Services", dossier_text)
            self.assertIn("Internal Revenue Service", dossier_text)
            self.assertIn("Briefing judgment", dossier_text)
            self.assertIn("What the organization says or is described as doing", dossier_text)
            self.assertIn("What the records show", dossier_text)
            self.assertIn("Most relevant retrieved records", dossier_text)
            self.assertIn("Implemented screen results", dossier_text)
            self.assertIn("Why this is on the review list", dossier_text)
            self.assertIn("Boss-level next step", dossier_text)
            self.assertIn("Specific findings that drove the flag", dossier_text)
            self.assertIn("What CalDS found", dossier_text)
            self.assertIn("When/where", dossier_text)
            self.assertIn("How this triggered review", dossier_text)
            self.assertIn("System opinion", dossier_text)
            self.assertIn("Why this matters", dossier_text)
            self.assertIn("What this does not prove", dossier_text)
            self.assertNotIn("retrieved records produced", dossier_text)
            self.assertNotIn("row count", dossier_text)
            self.assertNotIn("WFA", dossier_text)
            self.assertFalse(find_escalated_language(dossier_text))

            review_decision = read_json(Path(state["artifacts"]["review_decision"]))
            self.assertEqual(review_decision["decision"], "PENDING")
            self.assertTrue(result.review_packet_path.exists())
            citation_verification = read_json(Path(state["artifacts"]["citation_verification"]))
            self.assertIn(citation_verification["status"], {"PASS", "PASS_WITH_WARNINGS"})
            self.assertEqual(citation_verification["error_count"], 0)
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
            self.assertIn("link_integrity", public_manifest)
            self.assertIn(public_manifest["link_integrity"]["status"], {"PASS", "PASS_WITH_WARNINGS"})
            self.assertIn("CalDS Public Case Viewer", public_html)
            self.assertIn("#source-ledger", public_html)
            self.assertIn("id=\"evidence-E01\"", public_html)
            self.assertNotIn(str(PROJECT_ROOT), public_html)
            self.assertNotIn(str(PROJECT_ROOT), public_md)
            for entry in public_ledger["evidence"]:
                self.assertTrue(entry["source_urls"] or entry["link_note"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_briefing_claim_context_requires_direct_entity_source(self) -> None:
        service_item = EvidenceItem(
            item_id="healthright_service",
            record_id="healthright_services",
            title="HealthRIGHT 360 substance use disorder services",
            source_uri="https://www.healthright360.org/our-services/substance-use-disorder/",
            source_type="org_service_page",
            published_at="2026-04-24",
            excerpt="HealthRIGHT 360 describes substance use disorder treatment services, chronic disease care, and residential programs.",
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

        self.assertIn("HealthRIGHT 360 describes", service._entity_claim_context("HealthRIGHT 360", bundle, {"healthright_service": "E01"}))
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

    def test_completion_guard_counts_official_no_record_search_as_coverage_not_hit(self) -> None:
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
        case = CaseRequest(case_id="guard_no_record_test", title="Guard no-record regression", objective="Count official no-record searches as source coverage.", entities=["Shelter Group"])
        service = CompletionGuardService()
        ledger = service.build_acquisition_ledger(case, [record], ["Shelter Group"], ["enforcement_or_docket"])
        guard = service.guard(case, ledger, ["Shelter Group"], ["enforcement_or_docket"])
        self.assertEqual(ledger[0].status, "searched_no_public_official_record")
        self.assertEqual(ledger[0].matched_record_ids, ["enforcement_docket_no_record_shelter_group"])
        self.assertEqual(guard.status, "PASS")
        self.assertEqual(guard.blocker_count, 0)
        self.assertIn("not legal clearance", " ".join(guard.notes))

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

    def test_homelessness_scope_mismatch_flags_voter_registration(self) -> None:
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
        self.assertTrue(any(item.risk_level == "High" for item in scope_rows))
        self.assertIn("501(c)(3)", " ".join(caveat for item in scope_rows for caveat in item.caveats))

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
        self.assertTrue(str(module.FAC_DIR).endswith("fac"))
        self.assertTrue(str(module.CONTRACT_DIR).endswith("contracts"))
        self.assertTrue(str(module.DOCKET_DIR).endswith("enforcement_dockets"))
        self.assertIn("app.fac.gov/dissemination/public-data/gsa/full/general.csv", module.FAC_GENERAL_CSV_URL)
        self.assertTrue(any(source["entity"] == "DignityMoves" for source in module.LOCAL_CONTRACT_MONITORING_SOURCES))
        self.assertTrue(any(source["entity"] == "The People Concern" for source in module.LOCAL_CONTRACT_MONITORING_SOURCES))
        self.assertIn("https://search.justice.gov/search", module.US_DOJ_SEARCH_URL)
        self.assertTrue(module.PUBLIC_ENFORCEMENT_SEARCH_SOURCES)
        self.assertTrue(module.MANUAL_ENFORCEMENT_SEARCH_SOURCES)
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

    def test_risk_matrix_reports_public_enforcement_no_record_coverage(self) -> None:
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
            case = CaseRequest(case_id="enforcement_search_case", title="Enforcement search case", objective="Distinguish no-record coverage.", entities=["Shelter Group"])
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
