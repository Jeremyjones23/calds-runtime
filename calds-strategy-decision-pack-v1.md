# CalDS Strategy and Agent Harness Decision Pack

## Executive Framing

CalDS is not trying to build a flashy agent demo. It is trying to build a California-first audit intelligence system that can survive serious scrutiny from operators, reviewers, procurement teams, and eventually government buyers. That changes the architecture question immediately. The core issue is not whether an agent can perform an impressive one-off workflow. The real issue is whether the system can preserve provenance, recover from interruptions, pause for human review, and produce reviewer-safe outputs when the work becomes long-running, politically sensitive, or operationally messy.

The right way to think about this program is as a layered system with a strict separation between truth, search, workflow, and agent reasoning. The documents already built for CalDS point in that direction. What was missing was a decision-grade explanation of which harness should actually run the agents, how that harness should be bounded, and why some seemingly attractive frameworks should not become the system of record.

This pack closes that gap. It explains what has already been designed, compares the leading harness options, gives a concrete recommendation, and then runs that recommendation through a hostile reliability review before settling on a plan of action.

## What We Have Already Designed

The foundation is stronger than it may look at first glance. The prior work already established the California-first product posture, the evidence-first lead-generation model, the agent role split, the scale architecture, and the government-ready business framing. In practical terms, the system concept is already constrained in the right direction: use AI to compress document triage and ranking, not to manufacture accusations.

That means the architecture must honor five operating rules. First, the canonical record layer cannot be owned by the model. Second, every lead has to carry documentary provenance. Third, human review has to be an explicit control point rather than a vague promise. Fourth, long-running workflows must survive failures and resume cleanly. Fifth, any orchestration choice has to remain understandable to a future technical buyer or implementation partner.

Those rules matter because most agent-stack mistakes come from blending orchestration, memory, truth, and autonomy into one fuzzy runtime. That is a consumer-agent pattern. It is not an oversight-grade system pattern.

## Architectural Spine

The architecture should continue to center on four planes that each do one job well and expose clear boundaries to the others.

| Plane | Primary responsibility | Why it exists |
|---|---|---|
| Truth plane | Canonical records, provenance, entity history, joins | Keeps the model from becoming the system of record |
| Search plane | Hybrid retrieval, chunk search, ranking support | Makes evidence retrieval fast without redefining truth |
| Workflow plane | Durable jobs, timers, retries, approvals, resumability | Prevents long-running work from disappearing or restarting badly |
| Agent plane | Bounded specialist reasoning, synthesis, escalation control | Lets models reason over evidence without owning durable state |

This separation is the practical reason the current design can become production-grade. It prevents the common failure mode where an agent framework quietly becomes the database, the scheduler, the approval layer, and the explanation engine all at once.

## Agent Runtime and Harness Decision

The harness question should be answered by asking which runtime best supports reliability-first public-interest work, not which framework feels the most autonomous or impressive in a demo. There are three real options worth considering.

| Option | What it gets right | What it gets wrong | Best use |
|---|---|---|---|
| Hermes forked or adapted as core harness | Strong operator UX, built-in skills, persistent memory, flexible model routing, fast experimentation | Current public materials describe in-process delegated children, shared terminal-backend concerns, and synchronous delegation limits that weaken coordinator reliability for production oversight workflows | Internal research lane, experimentation, operator copilot |
| LangGraph + Temporal + provider SDK layer | Durable execution, interruptibility, explicit graph state, clean workflow separation, stronger fit for human review and resumability | More moving parts, more implementation discipline required, less out-of-the-box personality than Hermes | Production reliability, audit workflows, government-ready runtime |
| Thin custom orchestrator with selective SDK usage | Lowest conceptual surface area, full control, no framework lock-in | High engineering burden, easy to underbuild durability and observability, likely to recreate workflow bugs already solved elsewhere | Very small MVPs or teams with strong platform depth and narrow scope |

The decisive point is that the CalDS use case is not a general personal-agent problem. It is a governed workflow problem with agentic reasoning inside it. That difference pushes the answer toward a workflow-first stack rather than an agent-first runtime.

Hermes deserves serious consideration because it does several things well. Its public README emphasizes self-improving skills, persistent context, multi-channel reach, and subagent delegation. For a research copilot or an internal operations assistant, those are legitimate strengths. But the public issue trail also shows where the current design is less mature for a production oversight coordinator. The cross-CLI orchestration discussion describes delegated children as in-process clones of the Hermes runtime. Another issue highlights terminal backend sharing across subagents as a risk for filesystem and environment isolation. A separate issue documents synchronous delegation that blocks the coordinator pattern. Those are not cosmetic problems. They go directly to blast radius, operator control, and recoverability.

LangGraph and Temporal solve a different class of problem. LangGraph explicitly positions itself around durable execution, persistence, streaming, and human-in-the-loop state management. Temporal explicitly positions itself around crash-proof workflow execution and precise resume semantics. OpenAI's Agents SDK, meanwhile, is useful as a provider-facing layer because its official guidance covers handoffs, tool orchestration, and tracing well. Put together, those pieces line up with the CalDS requirement set much more cleanly than a Hermes-centric core runtime does today.

## Recommended Operating Model

The recommended model is straightforward: Temporal should own long-running business workflows, LangGraph should own bounded agent-state orchestration inside a case, and a provider SDK layer should own model invocation ergonomics, handoffs, and tracing. The system should keep deterministic services responsible for truth management, provenance, entity joins, scoring logic, and review artifacts.

Stated plainly, the recommendation is this: For production reliability, use Temporal for durable business workflows, LangGraph for agent-state orchestration, and a provider SDK layer for model and tool handoffs and tracing. Hermes remains useful as inspiration, a research copilot, or an internal experimentation lane, but not the primary oversight runtime.

This model is more boring than a single-agent super-runtime, and that is a feature. Boring boundaries are what let reliability survive contact with real workloads.

## Ownership Boundary

The harness only stays safe if the responsibilities are explicit.

- Temporal owns long-running job state, retries, approvals, timers, and resumability.
- LangGraph owns intra-case agent flow, state transitions, interrupts, and bounded specialist coordination.
- Provider SDKs own model invocation ergonomics, handoffs, tracing, and tool-call plumbing.
- Deterministic services own canonical records, joins, provenance, scoring math, and reviewer-facing artifacts.

When this line is respected, agents can pause, resume, escalate, and hand off without silently mutating the underlying truth store or hiding state inside an opaque runtime.

## Minimum Runtime Contracts

The orchestration layers need a small shared language. They do not need huge schemas in this document, but they do need stable concepts that travel cleanly between services.

- `CaseRequest` is the bounded instruction to open or continue a case.
- `AgentTask` is the unit of bounded delegated work assigned to a specialist role.
- `EvidenceBundle` is the cited documentary packet attached to a finding or intermediate claim.
- `LeadCandidate` is the reviewer-safe anomaly or risk statement before final review.
- `ReviewDecision` is the human approval, rejection, downgrade, or repair instruction.
- `RunTrace` is the end-to-end execution record that explains what happened, in what order, with which tools and guardrails.

These contracts matter because they keep the workflow understandable even when the models, prompts, or vendors change later.

## Why Not Hermes As Core Runtime Today

The case against Hermes as the primary oversight harness is not ideological. It is architectural. Hermes appears strongest when the product goal is a persistent personal agent that can accumulate memory, build skills, and operate across channels with a rich tool ecosystem. CalDS is different. It needs rigorous workflow durability, explicit approval points, reproducible run state, and clean isolation across specialist workstreams.

The current public Hermes materials suggest that delegated children are still tightly coupled to the parent runtime model and execution environment. That coupling is manageable in a personal-agent context and much riskier in an oversight context. Once the system is expected to route parallel work, preserve review state, and maintain a defensible evidence chain, the coordinator cannot afford hidden shared state or blocking delegation semantics.

Hermes should therefore be treated as a useful secondary lane. It can inform operator tooling, experimentation, and research workflows. It should not be the first place CalDS stores confidence in resume semantics, approval control, or multi-agent isolation.

## Reliability Prosecutor

The strongest version of the skeptical case goes like this: the proposed stack may be correct in theory but dangerously complex in implementation. Every extra layer introduces another place for state to drift, retries to duplicate work, and engineers to misunderstand where a decision actually happened.

### Top 7 Failure Modes

- The workflow retries a side effect and creates duplicate downstream artifacts.
- Agent state and durable workflow state diverge after an interrupt or partial failure.
- Retrieval results change between runs and create apparent non-determinism in the evidence path.
- Human review becomes ceremonial because reviewers see summaries instead of raw evidence bundles.
- Tool-call tracing exists, but the trace cannot be cleanly mapped to a reviewer-safe explanation.
- Model-provider abstractions leak, causing handoff logic to behave differently across vendors.
- The engineering team spends so much time wiring orchestration that the actual product wedge ships late.

### Strongest Case Against LangGraph Plus Temporal Complexity

The recommended stack is not lightweight. It demands discipline around state contracts, idempotency, side-effect boundaries, and operational ownership. A weak team could absolutely overbuild it, hide simple decisions behind too much machinery, and end up with a system that is durable on paper but slow to evolve. This is the best argument against the recommendation, and it is a fair one.

### Strongest Case For Hermes Simplicity

Hermes offers a more unified operator experience. It has a strong terminal identity, rich skills, persistent memory, and a lower ceremony path to getting useful delegated work out of a live agent. For internal research or founder-led execution, that simplicity is attractive because it shortens the gap between idea and action.

### Mitigations That Survive Review

The answer is not to ignore the complexity objection. The answer is to constrain the architecture hard.

- Keep Temporal responsible only for durable workflow concerns, not model reasoning.
- Keep LangGraph graphs small and bounded to case-level orchestration.
- Push scoring math, joins, and provenance into deterministic services.
- Require raw evidence access in every reviewer-facing decision point.
- Make side effects idempotent and isolate them behind explicit task boundaries.
- Start with one provider SDK lane and add others only after trace and review semantics are stable.
- Treat Hermes as an internal acceleration surface rather than a production dependency.

### Residual Risks

Even with those mitigations, three risks remain. The first is engineering overhead: this stack requires real implementation discipline. The second is retrieval drift: evidence search quality will still need careful regression control. The third is organizational temptation: once agents appear capable, teams tend to push them beyond the evidence boundary unless governance is explicit.

## Surviving Recommendation

After hostile review, the recommendation still stands. CalDS should use a workflow-first architecture in which Temporal owns durable execution, LangGraph owns bounded agent coordination, and a provider SDK layer handles model-facing handoffs and tracing. Hermes should remain in the toolbelt, but not at the center of the production oversight runtime.

## Near-Term Plan of Action

The next move is not to build everything at once. The right sequence is to stand up a narrow production spine first: one durable case workflow, one bounded retrieval graph, one evidence-bundle contract, one lead-review checkpoint, and one trace path that operators can inspect end to end. Once that path is stable, CalDS can add more specialist agents, more sources, and more procurement-grade packaging without changing the core operating model.

That sequence matters because a stable narrow spine beats a broad but ambiguous agent system every time.

## Source Notes

This decision relies on current primary-source documentation and issue discussions, including the Hermes Agent README, Hermes issues discussing cross-CLI orchestration, terminal-backend isolation, and synchronous delegation, the LangGraph overview and durable-execution documentation, the Temporal platform overview, and the OpenAI Agents guidance for handoffs and tracing.

- Hermes Agent README: https://github.com/NousResearch/hermes-agent/blob/main/README.md
- Hermes cross-CLI orchestration issue: https://github.com/NousResearch/hermes-agent/issues/413
- Hermes terminal isolation issue: https://github.com/NousResearch/hermes-agent/issues/4271
- Hermes coordinator blocking issue: https://github.com/NousResearch/hermes-agent/issues/11508
- LangGraph overview: https://docs.langchain.com/oss/python/langgraph/overview
- LangGraph durable execution: https://docs.langchain.com/oss/python/langgraph/durable-execution
- Temporal platform overview: https://docs.temporal.io/
- OpenAI Agents guide: https://developers.openai.com/api/docs/guides/agents
- OpenAI Agents handoffs: https://openai.github.io/openai-agents-js/guides/handoffs/
- OpenAI Agents tracing: https://openai.github.io/openai-agents-js/guides/tracing/
