from __future__ import annotations

import argparse
from pathlib import Path

from .case_compiler import compile_dossier_from_run
from .case_workflow import CaseWorkflow
from .contracts import CaseRequest, HumanDecision, read_json, write_json
from .editorial_export import export_editorial_public_data
from .generic_spine import EntityResolutionService, ProfileGateService, SourceAcquisitionPlannerService, TargetDiscoveryService
from .investigation_profiles import InvestigationProfileService
from .publication import publish_case_site_from_run, publish_site_index
from .quality_gates import RunReadinessService
from .source_catalog import CaliforniaSourceCatalogService
from .truth import JsonCorpusTruthStore


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS_DIR = PROJECT_ROOT / "data" / "sample_corpus"
DEFAULT_RUNS_DIR = PROJECT_ROOT / "runs" / "local"


def load_case(path: Path) -> CaseRequest:
    return CaseRequest.from_dict(read_json(path))


def run_case(args: argparse.Namespace) -> int:
    workflow = CaseWorkflow(args.corpus_dir, args.runs_dir)
    result = workflow.run_case(load_case(args.case_file))
    print(f"case_id={result.case_id}")
    print(f"status={result.status.value}")
    print(f"run_dir={result.run_dir}")
    print(f"review_packet={result.review_packet_path}")
    print(f"trace={result.trace_path}")
    return 0


def record_review(args: argparse.Namespace) -> int:
    workflow = CaseWorkflow(args.corpus_dir, args.runs_dir)
    path = workflow.record_review(
        case_id=args.case_id,
        reviewer=args.reviewer,
        decision=HumanDecision(args.decision),
        rationale=args.rationale,
    )
    print(f"review_decision={path}")
    return 0



def compile_dossier(args: argparse.Namespace) -> int:
    dossier = compile_dossier_from_run(args.run_dir, args.output_dir)
    print(f"case_id={dossier.case_id}")
    print(f"sentinel_decision={dossier.sentinel_decision.value}")
    print(f"case_dossier={dossier.markdown_path}")
    return 0

def publish_case_site(args: argparse.Namespace) -> int:
    site = publish_case_site_from_run(args.run_dir, args.output_dir)
    print(f"case_id={site.case_id}")
    print(f"safety_passed={site.safety_passed}")
    print(f"index_html={site.index_html}")
    print(f"case_dossier={site.case_dossier_markdown}")
    print(f"source_ledger={site.source_ledger_json}")
    print(f"publication_manifest={site.publication_manifest_json}")
    return 0


def publish_case_index(args: argparse.Namespace) -> int:
    path = publish_site_index(args.site_dir)
    print(f"site_index={path}")
    return 0


def export_editorial_site_data(args: argparse.Namespace) -> int:
    export = export_editorial_public_data(args.site_dir, args.output_dir)
    print(f"output_dir={export.output_dir}")
    print(f"status={export.verification_manifest['status']}")
    print(f"cases={len(export.verification_manifest['included_cases'])}")
    print(f"claims={export.verification_manifest['claim_coverage']['claim_count']}")
    for name, path in sorted(export.files.items()):
        print(f"{name}={path}")
    return 0 if export.verification_manifest["status"] == "PASS" else 1


def compare_run_readiness(args: argparse.Namespace) -> int:
    result = RunReadinessService().compare(args.current_run_dir, args.baseline_run_dir, args.output_file)
    print(f"case_id={result.case_id}")
    print(f"status={result.status}")
    print(f"material_changes={len(result.material_changes)}")
    print(f"blockers={len(result.blockers)}")
    if args.output_file:
        print(f"run_readiness={args.output_file}")
    return 0


def audit_profile(args: argparse.Namespace) -> int:
    request = CaseRequest(
        case_id=args.case_id,
        title="Profile audit",
        objective="Audit investigation profile gates.",
        metadata={"investigation_profile_path": str(args.profile_file)},
    )
    profile = InvestigationProfileService().load_for_case(request)
    result = ProfileGateService().audit(profile)
    if args.output_file:
        write_json(args.output_file, result)
    print(f"profile_id={profile.profile_id}")
    print(f"status={result.status}")
    print(f"missing_gates={','.join(result.missing_gates)}")
    if args.output_file:
        print(f"profile_gate_audit={args.output_file}")
    return 0


def plan_source_acquisition(args: argparse.Namespace) -> int:
    request = load_case(args.case_file)
    profile = InvestigationProfileService().load_for_case(request)
    truth = JsonCorpusTruthStore(args.corpus_dir)
    entity_resolution = EntityResolutionService().resolve(request, profile, truth.records)
    target_universe = TargetDiscoveryService().discover(request, profile, truth.records)
    source_plan = SourceAcquisitionPlannerService().build_plan(request, profile, truth.records, target_universe.selected_entities)
    output_file = args.output_file or (args.runs_dir / request.case_id / "source_acquisition_preview.json")
    write_json(
        output_file,
        {
            "profile_gate_audit": ProfileGateService().audit(profile),
            "entity_resolution": entity_resolution,
            "target_universe": target_universe,
            "source_acquisition_plan": source_plan,
        },
    )
    print(f"case_id={request.case_id}")
    print(f"profile_id={profile.profile_id}")
    print(f"selected_entities={','.join(target_universe.selected_entities)}")
    print(f"requirements={len(source_plan.requirements)}")
    print(f"satisfied={source_plan.satisfied_count}")
    print(f"blocked={source_plan.blocked_count}")
    print(f"needs_ingestor={source_plan.needs_ingestor_count}")
    print(f"source_acquisition_preview={output_file}")
    return 0


def source_catalog(args: argparse.Namespace) -> int:
    metadata = {}
    if args.profile_file:
        metadata["investigation_profile_path"] = str(args.profile_file)
    request = CaseRequest(
        case_id=args.case_id,
        title="Source catalog preview",
        objective="Preview California source catalog coverage for an investigation profile.",
        jurisdiction=args.jurisdiction,
        metadata=metadata,
    )
    profile = InvestigationProfileService().load_for_case(request)
    catalog = CaliforniaSourceCatalogService()
    connectors = catalog.connector_specs_for_profile(profile)
    summary = catalog.coverage_summary(profile)
    payload = {
        "profile_id": profile.profile_id,
        "jurisdiction": profile.jurisdiction,
        "summary": summary,
        "connectors": connectors,
    }
    if args.output_file:
        write_json(args.output_file, payload)
    print(f"profile_id={profile.profile_id}")
    print(f"jurisdiction={profile.jurisdiction}")
    print(f"connectors={len(connectors)}")
    print(f"source_families={','.join(summary['source_families'])}")
    print(f"public_http_connectors={summary['public_http_connector_count']}")
    print(f"manual_or_records_request_connectors={summary['manual_or_records_request_connector_count']}")
    if args.output_file:
        print(f"source_catalog={args.output_file}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CalDS local workflow spine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run-case", help="Run a case to human-review pause.")
    run_parser.add_argument("--case-file", type=Path, required=True)
    run_parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS_DIR)
    run_parser.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS_DIR)
    run_parser.set_defaults(func=run_case)

    review_parser = subparsers.add_parser("record-review", help="Record an explicit human review decision.")
    review_parser.add_argument("--case-id", required=True)
    review_parser.add_argument("--reviewer", required=True)
    review_parser.add_argument(
        "--decision",
        choices=[decision.value for decision in HumanDecision if decision is not HumanDecision.PENDING],
        required=True,
    )
    review_parser.add_argument("--rationale", required=True)
    review_parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS_DIR)
    review_parser.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS_DIR)
    review_parser.set_defaults(func=record_review)

    compile_parser = subparsers.add_parser("compile-dossier", help="Compile an existing run directory into a case dossier.")
    compile_parser.add_argument("--run-dir", type=Path, required=True)
    compile_parser.add_argument("--output-dir", type=Path, default=None)
    compile_parser.set_defaults(func=compile_dossier)
    publish_parser = subparsers.add_parser("publish-case-site", help="Build a public-safe static case site from an existing run directory.")
    publish_parser.add_argument("--run-dir", type=Path, required=True)
    publish_parser.add_argument("--output-dir", type=Path, required=True)
    publish_parser.set_defaults(func=publish_case_site)

    index_parser = subparsers.add_parser("publish-site-index", help="Build the public case index from published case manifests.")
    index_parser.add_argument("--site-dir", type=Path, required=True)
    index_parser.set_defaults(func=publish_case_index)

    editorial_parser = subparsers.add_parser("export-editorial-site-data", help="Export sanitized combined public data for the editorial Vercel site.")
    editorial_parser.add_argument("--site-dir", type=Path, required=True)
    editorial_parser.add_argument("--output-dir", type=Path, required=True)
    editorial_parser.set_defaults(func=export_editorial_site_data)

    readiness_parser = subparsers.add_parser("compare-run-readiness", help="Compare a rerun against a baseline run before relying on it.")
    readiness_parser.add_argument("--current-run-dir", type=Path, required=True)
    readiness_parser.add_argument("--baseline-run-dir", type=Path, required=True)
    readiness_parser.add_argument("--output-file", type=Path, default=None)
    readiness_parser.set_defaults(func=compare_run_readiness)

    audit_parser = subparsers.add_parser("audit-profile", help="Audit an investigation profile for required generic-spine gates.")
    audit_parser.add_argument("--profile-file", type=Path, required=True)
    audit_parser.add_argument("--case-id", default="profile_audit")
    audit_parser.add_argument("--output-file", type=Path, default=None)
    audit_parser.set_defaults(func=audit_profile)

    plan_parser = subparsers.add_parser("plan-source-acquisition", help="Preview entity resolution, target discovery, and deep source requirements for a case.")
    plan_parser.add_argument("--case-file", type=Path, required=True)
    plan_parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS_DIR)
    plan_parser.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS_DIR)
    plan_parser.add_argument("--output-file", type=Path, default=None)
    plan_parser.set_defaults(func=plan_source_acquisition)

    catalog_parser = subparsers.add_parser("source-catalog", help="Preview statewide and local California source connectors for a profile.")
    catalog_parser.add_argument("--jurisdiction", default="California")
    catalog_parser.add_argument("--profile-file", type=Path, default=None)
    catalog_parser.add_argument("--case-id", default="source_catalog_preview")
    catalog_parser.add_argument("--output-file", type=Path, default=None)
    catalog_parser.set_defaults(func=source_catalog)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
