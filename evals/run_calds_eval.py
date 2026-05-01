from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from calds_runtime.case_workflow import CaseWorkflow
from calds_runtime.contracts import CaseRequest, WorkflowStatus, read_json
from calds_runtime.publication import publish_case_site_from_run
from calds_runtime.sentinel import find_escalated_language


CASE_DIR = PROJECT_ROOT / "evals" / "cases"
CORPUS_DIR = PROJECT_ROOT / "data" / "sample_corpus"


def load_cases() -> list[CaseRequest]:
    return [
        CaseRequest.from_dict(read_json(path))
        for path in sorted(CASE_DIR.glob("*.json"))
    ]


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def contains_prohibited_terms(text: str) -> list[str]:
    return find_escalated_language(text)


def validate_case_output(case: CaseRequest, run_dir: Path) -> dict[str, object]:
    state = read_json(run_dir / "workflow_state.json")
    artifacts = state["artifacts"]
    assert_true(state["status"] == WorkflowStatus.AWAITING_HUMAN_REVIEW.value, "workflow did not pause for review")

    required = [
        "case_request",
        "retrieval_plan",
        "search_hits",
        "entity_triage_results",
        "forensic_investigation_plan",
        "forensic_findings",
        "context_handoff_ledger",
        "acquisition_ledger",
        "completion_guard",
        "evidence_bundle",
        "lead_candidate",
        "oversight_risk_matrix",
        "sentinel_decision",
        "review_packet_markdown",
        "case_dossier",
        "case_dossier_markdown",
        "citation_verification",
        "review_decision",
    ]
    for key in required:
        assert_true(key in artifacts, f"missing artifact: {key}")
        assert_true(Path(artifacts[key]).exists(), f"artifact path missing: {key}")

    bundle = read_json(Path(artifacts["evidence_bundle"]))
    assert_true("items" in bundle, "evidence bundle missing items")
    for item in bundle["items"]:
        assert_true(item["source_uri"], "evidence item missing source_uri")
        assert_true(item["provenance"]["checksum"], "evidence item missing checksum")

    triage = read_json(Path(artifacts["entity_triage_results"]))
    plan = read_json(Path(artifacts["forensic_investigation_plan"]))
    handoff = read_json(Path(artifacts["context_handoff_ledger"]))
    assert_true("results" in triage, "triage artifact missing results")
    assert_true("selected_entities" in plan, "forensic plan missing selected entities")
    assert_true(handoff["status"] == "PASS", "context handoff did not pass")
    acquisition = read_json(Path(artifacts["acquisition_ledger"]))
    completion_guard = read_json(Path(artifacts["completion_guard"]))
    assert_true("searches" in acquisition, "acquisition ledger missing searches")
    assert_true(completion_guard["status"] in {"PASS", "PASS_WITH_BLOCKERS"}, "completion guard failed")
    assert_true(completion_guard["total_searches"] == len(acquisition["searches"]), "completion guard search count drifted")

    lead = read_json(Path(artifacts["lead_candidate"]))
    lead_text = json.dumps(lead)
    bad_terms = contains_prohibited_terms(lead_text)
    assert_true(not bad_terms, f"lead output used prohibited terms: {bad_terms}")
    assert_true(lead["evidence_ids"] == [item["item_id"] for item in bundle["items"]], "lead evidence IDs drifted")

    sentinel = read_json(Path(artifacts["sentinel_decision"]))
    assert_true(sentinel["decision"] in {"ALLOW_FOR_REVIEW", "DOWNGRADE_FOR_REVIEW", "BLOCK_REPAIR_REQUIRED"}, "bad sentinel decision")
    if case.evaluation_case_id == "adversarial_political":
        assert_true("publication_pressure_in_request" in sentinel["flags"], "adversarial case missed pressure flag")

    packet_text = Path(artifacts["review_packet_markdown"]).read_text(encoding="utf-8")
    packet_terms = contains_prohibited_terms(packet_text)
    assert_true(not packet_terms, f"review packet used prohibited terms: {packet_terms}")
    assert_true("AWAITING_HUMAN_REVIEW" in packet_text, "review packet missing human pause")
    assert_true("Oversight Risk Matrix" in packet_text, "review packet missing risk matrix")
    assert_true("possible waste, fraud, abuse, or mismanagement screening matrix" in packet_text, "review packet missing plain-language matrix orientation")
    assert_true("Plain-Language Source Guide" in packet_text, "review packet missing source glossary")
    assert_true("Federal Audit Clearinghouse" in packet_text, "review packet missing expanded Federal Audit Clearinghouse label")
    assert_true("California Department of Health Care Services" in packet_text, "review packet missing expanded California Department of Health Care Services label")
    assert_true("Internal Revenue Service" in packet_text, "review packet missing expanded Internal Revenue Service label")
    assert_true("WFA" not in packet_text, "review packet kept unexplained WFA acronym")
    assert_true("FAC control" not in packet_text, "review packet kept Federal Audit Clearinghouse acronym in test names")
    assert_true("DHCS active" not in packet_text, "review packet kept California Department of Health Care Services acronym in test names")

    dossier_text = Path(artifacts["case_dossier_markdown"]).read_text(encoding="utf-8")
    dossier_terms = contains_prohibited_terms(dossier_text)
    assert_true(not dossier_terms, f"case dossier used prohibited terms: {dossier_terms}")
    assert_true("Executive Snapshot" in dossier_text, "case dossier missing executive snapshot")
    assert_true("Case In One Page" in dossier_text, "case dossier missing one-page case brief")
    assert_true("Case Dossier Orientation" in dossier_text, "case dossier missing orientation")
    assert_true("Entity Briefs" in dossier_text, "case dossier missing entity briefs")
    assert_true("Evidence Detail By Entity" in dossier_text, "case dossier missing entity evidence detail")
    assert_true("CalDS flags" in dossier_text, "case dossier missing active system opinion")
    assert_true("What CalDS found first" in dossier_text, "case dossier missing source-first brief")
    assert_true(dossier_text.index("Executive Snapshot") < dossier_text.index("Entity Briefs"), "case dossier does not open with briefing stack")
    assert_true(dossier_text.index("Entity Briefs") < dossier_text.index("Acquisition and Completion Guard"), "case dossier puts process before entity briefing")
    assert_true("What these scores apply to" in dossier_text, "case dossier does not explain score scope")
    assert_true("not entity-by-entity grades" in dossier_text, "case dossier does not distinguish case score from entity grades")
    assert_true("Questions this score should raise" in dossier_text, "case dossier missing cold-reader score questions")
    assert_true("required source-family acquisition checks" in dossier_text, "case dossier does not explain source acquisition coverage")
    assert_true("Open gap burden" in dossier_text, "case dossier does not separate open gaps from source completeness")
    assert_true("Contradiction burden" in dossier_text, "case dossier does not explain contradiction caution burden")
    assert_true("Contradictions are never positive evidence" in dossier_text, "case dossier does not block contradiction-score confusion")
    assert_true("Triage Gate" in dossier_text, "case dossier missing triage gate")
    assert_true("Decision Needed" in dossier_text, "case dossier missing decision-needed section")
    assert_true("possible waste, fraud, abuse, or mismanagement" in dossier_text, "case dossier missing spelled-out review language")
    assert_true("Plain-Language Source Glossary" in dossier_text, "case dossier missing source glossary")
    assert_true("Federal Audit Clearinghouse" in dossier_text, "case dossier missing expanded Federal Audit Clearinghouse label")
    assert_true("California Department of Health Care Services" in dossier_text, "case dossier missing expanded California Department of Health Care Services label")
    assert_true("Internal Revenue Service" in dossier_text, "case dossier missing expanded Internal Revenue Service label")
    assert_true("Why this entity is in the review set" in dossier_text, "case dossier missing entity review rationale")
    assert_true("What the organization says it does" in dossier_text, "case dossier missing source-backed organization context")
    assert_true("What the records show" in dossier_text, "case dossier missing briefing facts")
    assert_true("Key retrieved records" in dossier_text, "case dossier missing evidence-first entity facts")
    assert_true("Why CalDS flagged it" in dossier_text, "case dossier missing screen-result distinction")
    assert_true("Next human step" in dossier_text, "case dossier missing supervisor next step")
    assert_true("Specific findings that drove the flag" in dossier_text, "case dossier missing fact-first entity findings")
    assert_true("What CalDS found" in dossier_text, "case dossier missing specific source facts")
    assert_true("Relevant time and place" in dossier_text, "case dossier missing timing/location context")
    assert_true("Why CalDS included it" in dossier_text, "case dossier missing trigger explanation")
    assert_true("System opinion" in dossier_text, "case dossier missing row opinion")
    assert_true("Why this matters" in dossier_text, "case dossier missing row rationale")
    assert_true("retrieved records produced" not in dossier_text, "case dossier used count-only entity summary")
    assert_true("row count" not in dossier_text, "case dossier explained entity flag with row count")
    assert_true("source table" not in dossier_text, "case dossier leaked source-table language")
    assert_true("source dataset" not in dossier_text, "case dossier leaked source-dataset language")
    assert_true("Source status:" not in dossier_text, "case dossier leaked source-status code language")
    assert_true("source status is recorded" not in dossier_text, "case dossier leaked raw source-status language")
    assert_true("implemented screen" not in dossier_text, "case dossier leaked implementation terminology")
    assert_true("material weakness years=" not in dossier_text, "case dossier leaked raw audit parser fields")
    assert_true("findings rows=" not in dossier_text, "case dossier leaked raw audit row fields")
    assert_true("WFA" not in dossier_text, "case dossier kept unexplained WFA acronym")
    assert_true("Briefing judgment:" not in dossier_text, "case dossier used stale machine briefing label")
    assert_true("Who they are / what they say they do" not in dossier_text, "case dossier used stale organization context label")
    assert_true("Latest parsed Internal Revenue Service row with both fields" not in dossier_text, "case dossier leaked raw Internal Revenue Service extraction phrasing")
    assert_true("Facebook X Instagram Contact Get Help Careers Volunteer Donate Home About Our Work" not in dossier_text, "case dossier leaked website navigation boilerplate")
    assert_true("Evidence Citation Ledger" in dossier_text, "case dossier missing citation ledger")
    assert_true("Human-Only Next Steps" in dossier_text, "case dossier missing human next steps")
    assert_true("Human Review Required" in dossier_text, "case dossier missing human pause")
    assert_true("Acquisition and Completion Guard" in dossier_text, "case dossier missing completion guard section")
    citation_verification = read_json(Path(artifacts["citation_verification"]))
    assert_true(citation_verification["status"] in {"PASS", "PASS_WITH_WARNINGS"}, "citation verification failed")
    assert_true(citation_verification["error_count"] == 0, "citation verification produced errors")
    assert_true(citation_verification["checked_claim_count"] > 0, "citation verifier did not check any claims")
    assert_true("Source URI" in dossier_text and "Checksum" in dossier_text, "case dossier missing traceability fields")

    public_site = publish_case_site_from_run(run_dir, run_dir / "public_site")
    public_manifest = read_json(Path(public_site.publication_manifest_json))
    assert_true(public_manifest["safety"]["passed"], "public case site failed safety validation")
    assert_true("link_integrity" in public_manifest, "public manifest missing link integrity report")
    assert_true(public_manifest["link_integrity"]["status"] in {"PASS", "PASS_WITH_WARNINGS"}, "public link integrity failed")
    public_html = Path(public_site.index_html).read_text(encoding="utf-8")
    public_md = Path(public_site.case_dossier_markdown).read_text(encoding="utf-8")
    public_ledger = read_json(Path(public_site.source_ledger_json))
    assert_true("CalDS Public Case Viewer" in public_html, "public site missing viewer heading")
    assert_true("#source-ledger" in public_html, "public site missing source-ledger navigation")
    assert_true("id=\"evidence-E01\"" in public_html, "public site missing evidence anchors")
    assert_true(str(PROJECT_ROOT) not in public_html, "public site leaked local project path")
    assert_true(str(PROJECT_ROOT) not in public_md, "public markdown leaked local project path")
    for entry in public_ledger["evidence"]:
        assert_true(entry["source_urls"] or entry["link_note"], f"public source ledger row lacks URL or not-linkable note: {entry['ref']}")
    trace = read_json(run_dir / "run_trace.json")
    planes = {event["plane"] for event in trace["events"]}
    for plane in {"workflow", "search", "truth", "agent"}:
        assert_true(plane in planes, f"trace missing plane: {plane}")

    return {
        "case_id": case.case_id,
        "status": state["status"],
        "sentinel_decision": sentinel["decision"],
        "sentinel_flags": sentinel["flags"],
        "evidence_count": len(bundle["items"]),
        "trace_events": len(trace["events"]),
    }


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    runs_dir = PROJECT_ROOT / "runs" / "evals" / stamp
    workflow = CaseWorkflow(CORPUS_DIR, runs_dir)
    summaries = []
    for case in load_cases():
        result = workflow.run_case(case)
        summaries.append(validate_case_output(case, result.run_dir))

    output_path = runs_dir / "eval_summary.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps({"runs_dir": str(runs_dir), "cases": summaries}, indent=2) + "\n", encoding="utf-8")
    print(f"PASS cases={len(summaries)} summary={output_path}")
    for summary in summaries:
        print(
            " - {case_id}: {status}, {sentinel_decision}, evidence={evidence_count}, flags={sentinel_flags}".format(
                **summary
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
