from __future__ import annotations

from pathlib import Path
import shutil
import unittest
from uuid import uuid4

from calds_runtime.case_workflow import CaseWorkflow
from calds_runtime.contracts import CanonicalRecord, CaseRequest, Provenance, WorkflowStatus, read_json
from calds_runtime.search import KeywordSearchIndex, SearchPlan


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

            review_decision = read_json(Path(state["artifacts"]["review_decision"]))
            self.assertEqual(review_decision["decision"], "PENDING")
            self.assertTrue(result.review_packet_path.exists())
            packet_text = result.review_packet_path.read_text(encoding="utf-8")
            self.assertIn("## 1. Reviewer Orientation", packet_text)
            self.assertIn("## 3. Oversight Risk Matrix", packet_text)
            self.assertIn("Waste, Fraud, and Abuse (WFA) screening matrix", packet_text)
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
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

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


if __name__ == "__main__":
    unittest.main()


