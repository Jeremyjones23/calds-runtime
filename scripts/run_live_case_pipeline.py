from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STAGE1_CORPUS = PROJECT_ROOT / "data" / "live_corpus" / "ca_recovery_ngos_2026_04_24"
DEFAULT_STAGE2_CORPUS = PROJECT_ROOT / "data" / "live_corpus" / "ca_recovery_ngos_2026_04_24_stage2"
DEFAULT_STAGE3_CORPUS = PROJECT_ROOT / "data" / "live_corpus" / "ca_recovery_ngos_2026_04_24_stage3"
DEFAULT_STAGE4_CORPUS = PROJECT_ROOT / "data" / "live_corpus" / "ca_recovery_ngos_2026_04_24_stage4"
DEFAULT_STAGE5_CORPUS = PROJECT_ROOT / "data" / "live_corpus" / "ca_recovery_ngos_2026_04_24_stage5"
DEFAULT_ARTIFACTS = PROJECT_ROOT / "artifacts" / "live_recovery_sources_2026_04_24"
DEFAULT_CASE_FILE = PROJECT_ROOT / "cases" / "live_ca_recovery_ngos_case.json"
DEFAULT_TAX_PERIOD_YEARS = [2023, 2024, 2025]


def utc_label() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_step(label: str, command: list[str]) -> None:
    print(f"\n== {label} ==")
    print(" ".join(command))
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    subprocess.run(command, cwd=PROJECT_ROOT, env=env, check=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the CalDS live recovery NGO case pipeline.")
    parser.add_argument("--tax-period-years", type=int, nargs="+", default=DEFAULT_TAX_PERIOD_YEARS)
    parser.add_argument("--stage1-corpus", type=Path, default=DEFAULT_STAGE1_CORPUS)
    parser.add_argument("--stage2-corpus", type=Path, default=DEFAULT_STAGE2_CORPUS)
    parser.add_argument("--stage3-corpus", type=Path, default=DEFAULT_STAGE3_CORPUS)
    parser.add_argument("--stage4-corpus", type=Path, default=DEFAULT_STAGE4_CORPUS)
    parser.add_argument("--stage5-corpus", type=Path, default=DEFAULT_STAGE5_CORPUS)
    parser.add_argument("--artifacts-dir", type=Path, default=DEFAULT_ARTIFACTS)
    parser.add_argument("--case-file", type=Path, default=DEFAULT_CASE_FILE)
    parser.add_argument("--runs-dir", type=Path, default=None)
    parser.add_argument("--skip-federal-awards", action="store_true")
    parser.add_argument("--resume-from", choices=["ingest", "tables", "recovery", "outcomes", "workflow"], default="ingest", help="Resume from a named stage using existing prior-stage artifacts.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    tax_years = sorted(set(args.tax_period_years))
    runs_dir = args.runs_dir or (PROJECT_ROOT / "runs" / f"live-web-year-window-{utc_label()}")
    py = sys.executable
    stage_order = {"ingest": 0, "tables": 1, "recovery": 2, "outcomes": 3, "workflow": 4}
    resume_index = stage_order[args.resume_from]

    ingest = [
        py,
        str(PROJECT_ROOT / "scripts" / "ingest_live_recovery_sources.py"),
        "--stage1-corpus",
        str(args.stage1_corpus),
        "--stage2-corpus",
        str(args.stage2_corpus),
        "--artifacts-dir",
        str(args.artifacts_dir),
        "--tax-period-years",
        *[str(year) for year in tax_years],
    ]
    if args.skip_federal_awards:
        ingest.append("--skip-federal-awards")

    if resume_index <= 0:
        run_step("ingest live source corpus", ingest)
    if resume_index <= 1:
        run_step(
            "extract deterministic source tables",
            [
                py,
                str(PROJECT_ROOT / "scripts" / "extract_live_source_tables.py"),
                "--stage2-corpus",
                str(args.stage2_corpus),
                "--stage3-corpus",
                str(args.stage3_corpus),
                "--artifacts-dir",
                str(args.artifacts_dir),
            ],
        )
    if resume_index <= 2:
        run_step(
            "recover or document source gaps",
            [
                py,
                str(PROJECT_ROOT / "scripts" / "recover_live_gaps.py"),
                "--stage3-corpus",
                str(args.stage3_corpus),
                "--stage4-corpus",
                str(args.stage4_corpus),
                "--recovery-dir",
                str(args.artifacts_dir / "recovery"),
            ],
        )
    if resume_index <= 3:
        run_step(
            "ingest official outcome sources and public statements",
            [
                py,
                str(PROJECT_ROOT / "scripts" / "ingest_outcome_sources.py"),
                "--stage4-corpus",
                str(args.stage4_corpus),
                "--stage5-corpus",
                str(args.stage5_corpus),
                "--artifacts-dir",
                str(args.artifacts_dir),
                "--outcome-dir",
                str(args.artifacts_dir / "outcomes"),
            ],
        )
    if resume_index <= 4:
        run_step(
            "run bounded workflow to human-review pause",
            [
                py,
                "-m",
                "calds_runtime",
                "run-case",
                "--case-file",
                str(args.case_file),
                "--corpus-dir",
                str(args.stage5_corpus),
                "--runs-dir",
                str(runs_dir),
            ],
        )
    print("\n== pipeline complete ==")
    print(f"tax_period_years={tax_years}")
    print(f"resume_from={args.resume_from}")
    print(f"stage4_corpus={args.stage4_corpus}")
    print(f"stage5_corpus={args.stage5_corpus}")
    print(f"runs_dir={runs_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

