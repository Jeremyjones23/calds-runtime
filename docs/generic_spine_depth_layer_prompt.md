# Generic Spine Depth Layer Prompt

INPUT TYPE: ITERATE

<decomposition>
  <task_summary>Upgrade the CalDS generic investigation spine so any queued case can move from profile intake through source acquisition, entity resolution, target discovery, deep forensic readiness, evidence custody, quality gates, human-action compilation, sentinel review, and human-review pause without relying on model memory or monolithic synthesis.</task_summary>
  <inputs>Existing CalDS runtime repo, current InvestigationProfile model, case configs, source corpus records, evidence bundle, risk matrix, sentinel result, completeness controller report, and user requirement to add the missing spine items 1-10.</inputs>
  <outputs>Deterministic contracts, runtime services, workflow artifacts, tests, and documentation for source depth, entity resolution, target discovery, forensic tests, citation verification, durable workflow state, evidence store manifest, profile library, profile-specific gates, and final human-action compilation.</outputs>
  <constraints>Do not make the LLM the system of record. Do not collapse truth, search, workflow, and agent responsibilities. Do not turn blocked source access into clearance. Do not publish or escalate uncited legal conclusions. Do not finish a run unless every required gate is pass, pass-with-blockers, or documented as an external blocker after a repair-and-rerun attempt.</constraints>
  <ambiguities>Production connectors may not be available for every official source. A local filesystem workflow is acceptable only if it preserves durable-state semantics and adapter boundaries. The final human-action compiler may recommend next steps but cannot claim those steps have been completed.</ambiguities>
  <assumptions>
    <assumption confidence="High">The first implementation can use deterministic local adapters where production credentials or external systems are absent.</assumption>
    <assumption confidence="High">The runtime should keep artifacts explicit and JSON-readable for audit, tests, and public-safe publication.</assumption>
    <assumption confidence="Medium">Profile-specific gates should fail closed when a profile omits generic-spine requirements.</assumption>
  </assumptions>
  <failure_modes>
    <failure_mode>Source acquisition appears complete because a broad summary exists, while raw filings, audits, contracts, or dockets remain missing.</failure_mode>
    <failure_mode>Entity aliases or connected parties are silently merged into canonical truth without cited basis.</failure_mode>
    <failure_mode>Target pruning overweights money alone and misses lower-dollar entities with official adverse records or source opacity.</failure_mode>
    <failure_mode>Forensic tests are described narratively but not represented as repeatable checks with blockers.</failure_mode>
    <failure_mode>Human next steps are useful but not cited, causing the dossier to fail citation review or confuse the reader.</failure_mode>
  </failure_modes>
  <reasoning_tier>high</reasoning_tier>
</decomposition>

<optimized_prompt>
  <role>Generic CalDS Investigation Spine Builder and Completeness Controller.</role>
  <context>CalDS is a California-first, evidence-first workflow system. Deterministic services own canonical records, provenance, joins, source acquisition status, scoring inputs, evidence manifests, citation checks, and reviewer artifacts. Bounded agents synthesize only from supplied artifacts. The workflow plane owns durable state, retries, gates, and human-review pause semantics.</context>
  <task>Implement the missing generic-spine depth layer: source acquisition depth, entity resolution, target universe discovery, deep forensic test readiness, hard citation verification, durable workflow artifacts, evidence store manifest, case profile library support, profile-specific quality gates, and final human-action compilation. Wire these into the runtime sequence before the human-review pause and add regression coverage that fails if any required artifact or gate disappears.</task>
  <constraints>Use only deterministic code for truth, source status, scoring, and persistence. Treat credentialed, manual, or unavailable sources as blockers, not evidence absence. Preserve aliases as resolution artifacts; do not merge canonical records without cited basis. Rank targets by Review Value Score rather than money alone. Keep legal, fraud, waste, abuse, and intent language source-cited and sentinel-gated. Every substantive dossier action must carry an evidence label, source URI, record ID, or workflow artifact pointer. End at explicit human review.</constraints>
  <reasoning>Use high reasoning depth. Prefer auditability, resumability, and testable gates over broad investigation breadth. When external infrastructure is missing, create a narrow adapter or source-acquisition requirement that records the exact blocker and next human/ingestor action.</reasoning>
  <placement>Run immediately after profile load and before normal case-director/retrieval synthesis, then re-enter after risk-matrix generation to compile forensic blockers and human-only next actions. The final output feeds the case dossier and completeness controller before AWAITING_HUMAN_REVIEW.</placement>
  <anchor>Good output: a generic case can produce profile gate audit, entity resolution, target universe, source acquisition plan, evidence store manifest, forensic test results, human action plan, citation-pass dossier, completeness report, and human-review pause. Bad output: a larger prompt, a monolithic agent, source-gap handwaving, or a dossier that tells the reviewer to read raw files without explaining the actionable next step.</anchor>
  <execution_rules>
    <title>Iron-Clad Execution Rules</title>
    <rule>Inspect the repo before changing structure.</rule>
    <rule>Implement one deterministic artifact per missing spine layer.</rule>
    <rule>Do not weaken citation, link, hallucination, sentinel, or presentation gates to make a run pass.</rule>
    <rule>When a source family is missing, emit a source acquisition requirement with connector, required artifact, status, blocker reason, and retryability.</rule>
    <rule>When a handoff or artifact is incomplete, create a concrete repair action and rerun target.</rule>
    <rule>Every human action must cite source refs or the workflow artifact that generated the blocker.</rule>
    <rule>Run compile, unit, and eval verification before reporting done.</rule>
  </execution_rules>
</optimized_prompt>

<stress_test>
  <phase name="Literal Misread">
    <misread>Implement 1-10 as a planning document only. Failure: no runtime artifacts. Fix: require one deterministic artifact per spine layer.</misread>
    <misread>Treat "durable workflow backend" as mandatory Temporal. Failure: blocked by unavailable infra. Fix: allow local adapter only when durable-state semantics and boundaries are preserved.</misread>
  </phase>
  <phase name="Scope Drift">
    <misread>Add broad nationwide investigation connectors. Failure: loses California-first vertical slice. Fix: profile-driven source families with generic contracts but local scope.</misread>
    <misread>Deep-dive every possible entity. Failure: runtime noise and unfocused output. Fix: use Review Value Score and profile thresholds for pruning.</misread>
  </phase>
  <phase name="Boundary Violation">
    <misread>Let an agent decide whether a source was acquired. Failure: model becomes record owner. Fix: SourceAcquisitionPlannerService and CompletionGuardService own status.</misread>
    <misread>Merge aliases into canonical names without provenance. Failure: false linkage. Fix: EntityResolutionResult records aliases, basis, confidence, and source records separately.</misread>
  </phase>
  <phase name="Adversarial Reinterpretation">
    <misread>Use missing records as evidence that no problem exists. Failure: false clearance. Fix: missing records become source-access blockers.</misread>
    <misread>Use fraud language because the case is meant to find fraud. Failure: unsupported legal escalation. Fix: sentinel and citation gates block uncited legal conclusions.</misread>
  </phase>
  <phase name="Truncation and Format Failure">
    <misread>Emit human actions without source pointers. Failure: citation verifier blocks dossier. Fix: each action includes source refs or human_action_plan artifact pointer.</misread>
    <misread>Forget tests for new artifacts. Failure: future refactor silently drops the depth layer. Fix: unit tests assert artifacts, gates, and completed steps.</misread>
  </phase>
</stress_test>

<selection>
  <variant name="Single generic spine service set">
    <core_assumption>Small deterministic services can be added without replacing the current workflow.</core_assumption>
    <strongest_objection>It leaves production connector execution for later.</strongest_objection>
    <falsification_condition>If tests cannot prove durable artifacts and gates exist for each layer, this variant fails.</falsification_condition>
  </variant>
  <variant name="Full external workflow and connector rewrite">
    <core_assumption>The runtime should move directly to production-grade external services.</core_assumption>
    <strongest_objection>It risks breaking the runnable spine and conflating infrastructure migration with investigation quality.</strongest_objection>
    <falsification_condition>If local adapters cannot preserve boundaries, the rewrite becomes necessary.</falsification_condition>
  </variant>
  <winner>Single generic spine service set. It preserves the existing runnable product spine while making every missing layer explicit, auditable, and test-covered.</winner>
</selection>

<compression_report>
  <estimated_size_before>Short user request plus prior 1-10 list.</estimated_size_before>
  <estimated_size_after>Medium prompt specification with execution gates and failure-mode mapping.</estimated_size_after>
  <redundancy_removed>Collapsed repeated "go deeper" instructions into concrete contracts, services, artifacts, and gates.</redundancy_removed>
  <constraints_added>Artifact ownership, source-blocker semantics, alias provenance, Review Value Score pruning, cited human actions, and verification commands.</constraints_added>
  <failure_modes_covered>Source shortcutting, alias overmerge, money-only pruning, narrative-only forensic review, uncited action steps, and silent artifact loss.</failure_modes_covered>
  <left_uncompressed>Iron-clad rules and stress-test misreads were left explicit to prevent shortcut behavior.</left_uncompressed>
</compression_report>

<translation>N/A - no translation requested</translation>
