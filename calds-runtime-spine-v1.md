# CalDS Runtime Spine v1

## Purpose

This runnable spine turns the existing CalDS design into one narrow local workflow. It is not the production stack. It preserves the intended boundaries so Temporal, LangGraph, provider SDK calls, real indexes, and real corpora can replace the local adapters without changing the core contracts.

## Plane Map

| Plane | Local implementation | Production replacement |
|---|---|---|
| Truth | `JsonCorpusTruthStore`, `LeadScoringService`, `ReviewArtifactService` | PostgreSQL/object storage plus deterministic scoring and packet services |
| Search | `KeywordSearchIndex` | OpenSearch or another hybrid retrieval service |
| Workflow | `FileWorkflowStore` and `CaseWorkflow` | Temporal workflow with durable retries and approvals |
| Agent | Bounded role classes in `calds_runtime.agents` | LangGraph case graph with the same role boundaries |
| Provider SDK | `LocalProviderAdapter` metadata stub | Model/tool SDK with tracing and handoffs |

## Locked Runtime Contracts

The runtime starts with `CaseRequest`, delegates bounded `AgentTask` records, creates a provenance-bearing `EvidenceBundle`, drafts a `LeadCandidate`, gates it through `SentinelResult`, and then writes a pending `ReviewDecision`. `RunTrace` records the plane, actor, action, artifacts, and guardrail metadata for the full execution.

## Vertical Slice

The first slice runs:

1. Open a bounded California case.
2. Plan deterministic retrieval terms.
3. Retrieve from the fixture corpus.
4. Assemble evidence with source URI, checksum, and entity links.
5. Create a reviewer-safe lead candidate using deterministic scoring inputs.
6. Run sentinel review.
7. Write a review packet.
8. Pause with `AWAITING_HUMAN_REVIEW`.

## Local Commands

```powershell
python -m calds_runtime run-case --case-file evals/cases/easy_case.json
python evals/run_calds_eval.py
python -m unittest discover -s tests
```

Use the bundled Python runtime if `python` is not on PATH.
