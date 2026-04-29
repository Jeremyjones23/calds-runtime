# CalDS Repository Layout

This folder is the runnable CalDS runtime workspace. It should stay small enough for a new engineer to identify the canonical code path without sorting through historical runs or downloaded evidence.

## Canonical Runtime Surface

- `calds_runtime/` contains the runtime contracts, workflow adapter, deterministic truth/search/scoring/review services, waste/fraud/abuse/mismanagement risk matrix, sentinel policy, and CLI.
- `scripts/` contains reproducible ingestion and live pipeline entrypoints. These scripts may create generated artifacts, but generated outputs do not belong in the source tree.
- `tests/` and `evals/` contain the regression checks for the runtime spine and the easy, messy low-linkage, and adversarial case loop.
- `cases/` contains bounded case request files.
- `data/sample_corpus/` contains the small fixture corpus used by tests and evals.
- `docs/` and the root `calds-*.md` files contain architecture, operator, and source-acquisition notes.

## Generated Or Archived Outputs

The following paths are generated or local-only and should not be treated as source:

- `artifacts/`
- `runs/`
- `data/live_corpus/`
- `consolidated-docx/`
- `publish/`
- `*.zip`

For the April 25 cleanup, prior generated outputs were archived at:

`C:\Users\jerem\OneDrive\Documents\CalDS-archive\2026-04-25-cleanup-prep`

That archive includes `archive_manifest.json`, `archive_summary.json`, and `legacy_tools_manifest.json` with SHA256 hashes and original paths.

## Cleanup Rule

Keep one canonical implementation path in the repo. If a file is a generated run output, downloaded live evidence artifact, publish staging copy, local packaging bundle, or one-off document-generation helper, archive it outside the runtime workspace before pruning it from this folder.
