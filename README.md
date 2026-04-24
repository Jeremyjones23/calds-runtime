# CalDS Runtime Spine

CalDS (California Doge Services) is a California-first, evidence-first oversight workflow prototype. The runtime is built around strict separation between deterministic truth/search services, durable workflow state, bounded agent roles, sentinel review, and human-review pause semantics.

This repository is not an autonomous accusation engine. It produces reviewer-safe triage leads, provenance-bearing evidence bundles, and audit-ready review packets for human verification.

## Publish Note

The repository was published through the GitHub connector. Core runtime files, tests, evals, docs, and the live case entrypoint are present directly in the tree. The full source-only bundle, including the large live ingestion scripts, is also published as base64 zip parts under `.github/bootstrap/`.

To expand the exact full source bundle in a clone, run:

```powershell
pwsh scripts\rehydrate_source_bundle.ps1
```

If GitHub Actions is enabled for the repository, the `Bootstrap Source Bundle` workflow can perform the same unpacking from the Actions tab.

## What Is Included

- `calds_runtime/` - core contracts, deterministic truth/search/scoring/review services, local workflow adapter, bounded role adapters, sentinel gate, WFA screening matrix, and CLI.
- `scripts/` - live pipeline entrypoint and bootstrap guards; rehydrate the full bundle for the complete source ingestion, deterministic extraction, gap recovery, official outcome ingestion, and live orchestration scripts.
- `cases/` - live case configuration for the California recovery NGO workflow.
- `data/sample_corpus/` - small synthetic/sample corpus for tests and evals.
- `evals/` - three-case regression harness: easy, messy low-linkage, and adversarial/politically charged cases.
- `tests/` - runtime spine tests.
- `docs/` and root `calds-*.md` files - architecture, operator, and prompt/source-acquisition notes.

Generated live artifacts, run outputs, PDFs, and downloaded corpora are intentionally excluded from Git by `.gitignore`.

## Safety Boundaries

CalDS treats retrieved material as evidence context, not conclusions. The runtime keeps:

- canonical records and provenance in deterministic services,
- durable case state in the workflow plane,
- bounded role reasoning in local agent adapters,
- sentinel gating before review packaging,
- explicit human review as the terminal workflow state.

Review packets may use WFA screening language, but rows are screening prompts only. County/CoC outcome movements are contextual and are not provider-attributable results without direct program outcome evidence.

## Quick Start

Use Python 3.11+.

```powershell
python -m unittest discover -s tests
python evals\run_calds_eval.py
```

Run a sample bounded case:

```powershell
python -m calds_runtime run-case --case-file evals\cases\easy_case.json --corpus-dir data\sample_corpus --runs-dir runs\local-smoke
```

Run the live recovery NGO pipeline after rehydrating the full source bundle and restoring or regenerating live corpora:

```powershell
python scripts\run_live_case_pipeline.py --resume-from outcomes --runs-dir runs\live-outcomes-local
```

A full live replay is possible but can take significantly longer because it fetches public IRS, FAC, DHCS, county, and outcome sources:

```powershell
python scripts\run_live_case_pipeline.py --runs-dir runs\live-full-local
```

## Current Verification Baseline

The latest local checks passed before publishing:

```powershell
python -m compileall calds_runtime evals tests scripts
python -m unittest discover -s tests
python evals\run_calds_eval.py
python scripts\run_live_case_pipeline.py --resume-from outcomes --runs-dir runs\live-outcomes-resume-pipeline-20260424T1855Z
```

The latest live workflow reached `AWAITING_HUMAN_REVIEW` with sentinel decision `DOWNGRADE_FOR_REVIEW` and review decision `PENDING`.

## Source Notes

The live pipeline can ingest public official sources such as California HDIS homelessness/SPM datasets, CHHS MAT and overdose profile datasets, DOJ OpenJustice crime data, DHCS CalOMS/adverse-action pages, IRS Form 990 XML, Federal Audit Clearinghouse reports, county records, and target organization public statement pages.

The product remains incomplete until direct provider-attributable treatment completion, full DHCS license/adverse-action histories, and governed social/traffic metrics are added.
