from __future__ import annotations

from pathlib import Path
import importlib.util
import shutil
import unittest
from uuid import uuid4

from calds_runtime.case_compiler import CaseDossierService
from calds_runtime.case_workflow import CaseWorkflow
from calds_runtime.contracts import CanonicalRecord, CaseRequest, EvidenceBundle, EvidenceItem, Provenance, WorkflowStatus, read_json
from calds_runtime.forensic_triage import HomelessnessTriageService
from calds_runtime.publication import publish_case_site_from_run
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
            self.assertIn("results", triage)
            self.assertIn("selected_entities", forensic_plan)
            self.assertEqual(handoff["status"], "PASS")
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
            attributes={"signals": {"official_enforcement_or_docket_flag": True, "missing_data": True}},
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
        self.assertIn("presumed innocent", " ".join(results[0].findings[0].caveats))


if __name__ == "__main__":
    unittest.main()
