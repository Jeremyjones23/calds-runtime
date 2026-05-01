# CalDS Prompt Logic Audit

Date: 2026-05-01

This audit applies the `master-prompt-builder` AUDIT posture to the current CalDS role prompts, prompt-derived workflow steps, and deterministic runtime gates. The goal is to catch logical fallacies before they appear in case dossiers or public-safe case viewers.

## Scope Reviewed

- `docs/case_compiler_agent_prompt.md`
- `docs/homelessness_forensic_agent_prompts.md`
- `docs/agent_architecture_audit_rebuild_prompt.md`
- `docs/outcome_source_acquisition_master_prompt.md`
- `docs/public_case_publisher_prompt.md`
- Runtime role behavior in `calds_runtime/agents.py`, `case_workflow.py`, `forensic_triage.py`, `quality_gates.py`, `risk_matrix.py`, `scoring.py`, and `sentinel.py`

## Findings

| Issue | Fallacy or failure mode | Runtime impact | Resolution |
|---|---|---|---|
| Source completeness reused source diversity when no completion guard existed | Category error | A run with varied evidence but no acquisition ledger could look source-complete | Source completeness now remains `0.0` unless the completion guard exists |
| Completion guard misses and blockers could be counted twice | Double counting | Source completeness could be over-penalized in confusing ways | `blocker_count` is now the authoritative unresolved-required-check count; `miss_count` remains diagnostic |
| Keyword-only voter/citizenship/advocacy page language could become High | Hasty generalization | Legal nonprofit activity could be treated as a high-priority scope issue without expenditure or funding nexus | Keyword-only scope matches are Medium; High requires funding-source, contract-scope, or cost-allocation nexus |
| Discovery-gap rows counted as present source-family coverage in triage | False coverage | A searched-but-not-citation-ready row could hide a required-source gap | Triage missing-source logic now ignores discovery/source-gap-only rows |
| Lead candidate entity text used request order instead of selected deep-dive entities | Context handoff loss | The synthesized lead could brief the wrong entities after triage selected a subset | Lead scorer now accepts and uses `selected_entities` from the forensic plan |
| Old completed runs short-circuited after prompt/runtime changes | Stale artifact reuse | New scoring or prompt logic could be bypassed by old `AWAITING_HUMAN_REVIEW` artifacts | Workflow state now records `runtime_logic_version`; completed runs only short-circuit when versions match |
| Sentinel did not catch several legal or causal overclaims | Safety gap | Phrases like "misconduct occurred" or "caused provider failure" could pass | Sentinel language patterns now block legal-status and causal overclaims while preserving "possible waste, fraud, abuse, or mismanagement" |
| Citation verifier skipped opinionated dossier lines | Uncited synthesis risk | "Why this matters" or "Reviewer readout" lines could avoid citation checks | Citation verifier now treats briefing/opinion lines as claim-like and requires evidence/source pointers |

## Prompt Updates

The prompt set now distinguishes:

- Review leads from allegations.
- Public-safe preview/export from human-approved external publication.
- Keyword-only scope signals from funded-scope or cost-allocation signals.
- Connected-party legal exposure from entity-level legal conclusions.
- Missing source coverage from negative findings or legal clearance.

## Deferred Follow-Ups

- Rename `risk_severity_score` in the contract to something closer to `evidence_support_score` or add a backward-compatible alias. The current field name can still be misunderstood, although explanatory text now constrains it.
- Add a run-input fingerprint that covers case request, corpus manifest, prompt version, and scoring model version. The current runtime version gate prevents stale logic reuse but does not yet detect all corpus/request drift.
- Add a stronger contradiction taxonomy. Contradictions should never improve confidence; they should be reported as unresolved burden until reconciled.
- Expand eval cases to include a funded-scope nexus example and a keyword-only public statement example.

## Audit Rule

Future prompt changes should continue to pass through `master-prompt-builder`, but runtime enforcement remains mandatory. A prompt instruction is not considered implemented until a deterministic gate, artifact, or regression test enforces the same boundary.
