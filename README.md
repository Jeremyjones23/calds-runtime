# CalDS Runtime Spine

CalDS (California Doge Services) is a California-first, evidence-first oversight workflow prototype. The runtime is built around strict separation between deterministic truth/search services, durable workflow state, bounded agent roles, sentinel review, and human-review pause semantics.

This repository is not an autonomous accusation engine. It produces reviewer-safe triage leads, provenance-bearing evidence bundles, and audit-ready review packets for human verification.

## What Is Included

- `calds_runtime/` - core contracts, deterministic truth/search/scoring/review services, generic investigation profiles, Review Value Score pruning, active completeness controller, local workflow adapter, bounded role adapters, sentinel gate, and CLI.
- `scripts/` - source ingestion, deterministic extraction, gap recovery, official outcome ingestion, and live pipeline orchestration.
- `cases/` - live case configurations for the California recovery NGO and homelessness top-15 workflows.
- `data/sample_corpus/` - small synthetic/sample corpus for tests and evals.
- `evals/` - three-case regression harness: easy, messy low-linkage, and adversarial/politically charged cases.
- `tests/` - runtime spine tests.
- `docs/` and root `calds-*.md` files - architecture, operator, and prompt/source-acquisition notes.

Generated live artifacts, run outputs, PDFs, and downloaded corpora are intentionally excluded from Git by `.gitignore`.

For the canonical folder map and cleanup rules, see `docs/repo_layout.md`. For the current no-shortcut methodology audit, see `docs/methodology_integrity_audit.md`. For statewide source-family coverage and official California connector planning, see `docs/california_source_catalog.md`.

## Safety Boundaries

CalDS treats retrieved material as evidence context, not conclusions. The runtime keeps:

- canonical records and provenance in deterministic services,
- durable case state in the workflow plane,
- bounded role reasoning in local agent adapters,
- sentinel gating before review packaging,
- explicit human review as the terminal workflow state.

Review packets use possible waste, fraud, abuse, or mismanagement screening language, but rows are screening prompts only. County or Continuum of Care outcome movements are contextual and are not provider-attributable results without direct program outcome evidence.

The investigation workflow now starts from an `InvestigationProfile`: topic, jurisdiction, target universe, required source families, scoring weights, language rules, publication policy, and completion gates. Target pruning uses `Review Value Score`, which combines public-dollar exposure, official adverse records or public-record dings, off-scope activity signals, spending growth versus outcome movement, tax/audit/compensation anomalies, source opacity, network role, and citation quality.

The homelessness workflow includes a first-pass triage gate before deep investigation. The gate records entity-level source-family findings, Review Value Score, deep-dive selection, and context handoff status before the normal evidence bundle, sentinel, dossier, public-site, and human-review pause steps.

The generic spine now emits first-class artifacts for the reusable investigation depth layer:

- `profile_gate_audit.json` verifies that a profile declares the required gates before execution.
- `entity_resolution.json` records canonical entities, aliases, unresolved names, and basis without merging truth records.
- `target_universe.json` ranks named and source-discovered entities by Review Value Score.
- `source_acquisition_plan.json` records deep source requirements, connectors, required artifacts, status, retryability, and blockers.
- `evidence_store_manifest.json` records checksums, immutable references, parser versions, and snapshot availability for retrieved records.
- `forensic_test_results.json` records which forensic checks are ready and which are blocked by source gaps.
- `human_action_plan.json` turns risk rows, source blockers, and forensic-test blockers into cited human-only next actions.

The source acquisition planner now loads a California source catalog for every profile. Statewide connectors cover IRS Form 990 sources, ProPublica filing summaries, Federal Audit Clearinghouse audits, California charity and business registries, California Grants Portal, Open FI$Cal, HDIS homelessness outcomes, CAL-ACCESS/Power Search, FPPC ethics sources, PACER, and generic county records families. Jurisdiction-specific overlays are added when a known local portal exists; San Francisco profiles now include the Legislative Research Center, Ethics lobbying data, Controller reports, HSH sources, and Open Data payment rows. County contract, payment, board-file, and provider-outcome records remain explicit source blockers until a public hit, verified no-public-record search, or records-request blocker is documented.

The workflow also includes four anti-drift quality gates:

- `CompletionGuardService` records source-family acquisition hits, no-record public searches, and misses before synthesis. Anything short of a citation-ready hit remains a source-access blocker, not clearance.
- `CompletenessControllerService` audits source, retry, handoff, citation, link, hallucination, sentinel, presentation, and human-review gates. A failed gate creates a concrete repair action and rerun target before the workflow can accept the step as complete.
- `CitationVerifierService` checks the compiled dossier for unresolved evidence labels, missing traceability, named-party legal-status drift, and provider-attribution overclaim.
- `LinkIntegrityService` checks public source links during static-site publication and blocks publication when external citation links are broken. The public publisher repairs known stale URLs to working source pages and reports remaining source-access gaps instead of hiding them.
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

Audit a case profile and preview the deep source plan before a full run:

```powershell
python -m calds_runtime audit-profile --profile-file data\investigation_profiles\sf_homelessness.json --output-file runs\profile-audits\sf_homelessness_profile_gate.json
python -m calds_runtime source-catalog --jurisdiction "San Francisco, California" --profile-file data\investigation_profiles\sf_homelessness.json --output-file runs\source-catalog\sf_catalog.json
python -m calds_runtime source-catalog --jurisdiction "California" --profile-file data\investigation_profiles\ca_statewide_homelessness.json --output-file runs\source-catalog\ca_statewide_catalog.json
python -m calds_runtime plan-source-acquisition --case-file evals\cases\easy_case.json --corpus-dir data\sample_corpus --output-file runs\local-smoke\source_acquisition_preview.json
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
python scripts\ingest_homelessness_top15_sources.py --profile ca_statewide_homelessness --corpus-dir data\live_corpus\live_ca_homelessness_top15_2026_04_29_stage2
python -m calds_runtime run-case --case-file cases\live_ca_homelessness_top15_case.json --corpus-dir data\live_corpus\live_ca_homelessness_top15_2026_04_29_stage2 --runs-dir runs\live-homelessness-forensic-local
python -m calds_runtime publish-case-site --run-dir runs\live-homelessness-forensic-local\live_ca_homelessness_top15_2026_04_29 --output-dir site\cases\live_ca_homelessness_top15_2026_04_29
python -m calds_runtime publish-site-index --site-dir site
python -m calds_runtime compare-run-readiness --current-run-dir runs\live-homelessness-forensic-local\live_ca_homelessness_top15_2026_04_29 --baseline-run-dir runs\<baseline-run>\live_ca_homelessness_top15_2026_04_29 --output-file runs\live-homelessness-forensic-local\live_ca_homelessness_top15_2026_04_29\artifacts\run_readiness.json
```

Run the San Francisco homelessness complex profile from scratch:

```powershell
python scripts\ingest_homelessness_top15_sources.py --profile sf_homelessness --target-limit 15 --corpus-dir data\live_corpus\live_ca_sf_homelessness_complex_fresh --case-file-out runs\live-sf-homelessness\live_ca_sf_homelessness_complex_case.json
python -m calds_runtime run-case --case-file runs\live-sf-homelessness\live_ca_sf_homelessness_complex_case.json --corpus-dir data\live_corpus\live_ca_sf_homelessness_complex_fresh --runs-dir runs\live-sf-homelessness
python -m calds_runtime publish-case-site --run-dir runs\live-sf-homelessness\live_ca_sf_homelessness_complex --output-dir site\cases\live_ca_sf_homelessness_complex
python -m calds_runtime publish-site-index --site-dir site
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

The product remains incomplete until direct provider-attributable treatment completion, full DHCS license/adverse-action histories, governed social/traffic metrics, and county-specific scrapers or records-request adapters are added for all target jurisdictions. The statewide catalog makes those gaps visible and repeatable instead of hiding them.
