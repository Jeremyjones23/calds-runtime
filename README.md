# CalDS Runtime Spine

CalDS (California Doge Services) is a California-first, evidence-first oversight workflow prototype. The runtime is built around strict separation between deterministic truth/search services, durable workflow state, bounded agent roles, sentinel review, and human-review pause semantics.

This repository is not an autonomous accusation engine. It produces reviewer-safe triage leads, provenance-bearing evidence bundles, and audit-ready review packets for human verification.

## What Is Included

- `calds_runtime/` - core contracts, deterministic truth/search/scoring/review services, local workflow adapter, bounded role adapters, sentinel gate, and CLI.
- `scripts/` - source ingestion, deterministic extraction, gap recovery, official outcome ingestion, and live pipeline orchestration.
- `cases/` - live case configurations for the California recovery NGO and homelessness top-15 workflows.
- `data/sample_corpus/` - small synthetic/sample corpus for tests and evals.
- `evals/` - three-case regression harness: easy, messy low-linkage, and adversarial/politically charged cases.
- `tests/` - runtime spine tests.
- `docs/` and root `calds-*.md` files - architecture, operator, and prompt/source-acquisition notes.

Generated live artifacts, run outputs, PDFs, and downloaded corpora are intentionally excluded from Git by `.gitignore`.

For the canonical folder map and cleanup rules, see `docs/repo_layout.md`.

## Safety Boundaries

CalDS treats retrieved material as evidence context, not conclusions. The runtime keeps:

- canonical records and provenance in deterministic services,
- durable case state in the workflow plane,
- bounded role reasoning in local agent adapters,
- sentinel gating before review packaging,
- explicit human review as the terminal workflow state.

Review packets use possible waste, fraud, abuse, or mismanagement screening language, but rows are screening prompts only. County or Continuum of Care outcome movements are contextual and are not provider-attributable results without direct program outcome evidence.

The homelessness workflow now includes a first-pass top-15 triage gate before deep investigation. The gate records entity-level source-family findings, deep-dive selection, and context handoff status before the normal evidence bundle, sentinel, dossier, public-site, and human-review pause steps.

The workflow also includes four anti-drift quality gates:

- `CompletionGuardService` records source-family acquisition hits and misses before synthesis, so missing searches become explicit blockers rather than silent omissions.
- `CitationVerifierService` checks the compiled dossier for unresolved evidence labels, missing traceability, named-party legal-status drift, and provider-attribution overclaim.
- `LinkIntegrityService` checks public source links during static-site publication and blocks publication when external citation links are broken.
- `RunReadinessService` compares a rerun against a baseline and reports whether the new run is materially deeper before treating it as an improved result.

## Quick Start

Use Python 3.11+. In this local workspace, `python` may not be on PATH; the bundled Codex runtime has worked at:

```powershell
C:\Users\jerem\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe
```

```powershell
python -m unittest discover -s tests
python evals\run_calds_eval.py
```

Run a sample bounded case:

```powershell
python -m calds_runtime run-case --case-file evals\cases\easy_case.json --corpus-dir data\sample_corpus --runs-dir runs\local-smoke
```

Run the live recovery NGO pipeline from an existing recovered corpus through the newest outcome stage and human-review pause. If `data\live_corpus` is not present, regenerate it with a full live replay or restore it from the local archive described in `docs/repo_layout.md`.

```powershell
python scripts\run_live_case_pipeline.py --resume-from outcomes --runs-dir runs\live-outcomes-local
```

A full live replay is possible but can take significantly longer because it fetches public IRS, FAC, DHCS, county, and outcome sources:

```powershell
python scripts\run_live_case_pipeline.py --runs-dir runs\live-full-local
```

Run the homelessness top-15 corpus refresh and workflow:

```powershell
python scripts\ingest_homelessness_top15_sources.py --corpus-dir data\live_corpus\live_ca_homelessness_top15_2026_04_29_stage2
python -m calds_runtime run-case --case-file cases\live_ca_homelessness_top15_case.json --corpus-dir data\live_corpus\live_ca_homelessness_top15_2026_04_29_stage2 --runs-dir runs\live-homelessness-forensic-local
python -m calds_runtime publish-case-site --run-dir runs\live-homelessness-forensic-local\live_ca_homelessness_top15_2026_04_29 --output-dir site\cases\live_ca_homelessness_top15_2026_04_29
python -m calds_runtime compare-run-readiness --current-run-dir runs\live-homelessness-forensic-local\live_ca_homelessness_top15_2026_04_29 --baseline-run-dir runs\<baseline-run>\live_ca_homelessness_top15_2026_04_29 --output-file runs\live-homelessness-forensic-local\live_ca_homelessness_top15_2026_04_29\artifacts\run_readiness.json
```

## Current Verification Baseline

The latest local checks passed:

```powershell
python -m compileall calds_runtime evals tests scripts
python -m unittest discover -s tests
python evals\run_calds_eval.py
python scripts\run_live_case_pipeline.py --resume-from outcomes --runs-dir runs\live-outcomes-resume-pipeline-20260424T1855Z
```

The latest live workflow reached `AWAITING_HUMAN_REVIEW` with sentinel decision `DOWNGRADE_FOR_REVIEW` and review decision `PENDING`.

## Source Notes

The live pipeline can ingest public official and public-access sources such as California HDIS homelessness/SPM datasets, CHHS MAT and overdose profile datasets, DOJ OpenJustice crime data, DHCS CalOMS/adverse-action pages, ProPublica Nonprofit Explorer API summaries linked to IRS Form 990 filings, IRS Form 990 XML index and bulk-batch sources, full Form 990 PDFs when public endpoints permit download, Federal Audit Clearinghouse reports, county records, and target organization public statement pages.

The homelessness triage model treats connected-party official legal records as mandatory deep-review triggers while preserving named-party status. It also screens voter registration, citizenship, immigration, advocacy, lobbying, and political-language matches as homelessness funding-scope and cost-allocation questions rather than automatic illegality.

The product remains incomplete until direct provider-attributable treatment completion, full DHCS license/adverse-action histories, and governed social/traffic metrics are added.
