from __future__ import annotations

import argparse
from pathlib import Path

from .case_workflow import CaseWorkflow
from .contracts import CaseRequest, HumanDecision, read_json


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

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
