INPUT TYPE: ITERATE

<decomposition>
  <task_summary>Upgrade the CalDS homelessness workflow from a summary dossier into a two-tier, source-cited triage and forensic investigation system for the top 15 California homelessness funding recipients.</task_summary>
  <inputs>CaseRequest, canonical source records, provenance, top-15 entity list, source-family coverage, triage results, risk matrix, evidence bundle, sentinel result, and publication safety rules.</inputs>
  <outputs>EntityTriageResult, TriageFinding, ForensicInvestigationPlan, ForensicFinding, ContextHandoffLedger, reviewer-safe private dossier, and sanitized public brief.</outputs>
  <constraints>Do not treat the model as system of record. Do not invent source facts. Do not convert third-party charges into entity-level findings. Do not skip sentinel or human review. Public output must remain sanitized and source-cited.</constraints>
  <ambiguities>The phrase "fraud culpability" could be misread as a legal conclusion. The intended behavior is an internal investigative hypothesis and prioritization screen unless official legal sources establish a named-party status.</ambiguities>
  <assumptions>
    <assumption confidence="High">The first pass must screen all 15 entities before any deep investigation ranking.</assumption>
    <assumption confidence="High">Official enforcement, docket, tax, audit, grant, contract, social, and outcome source families must be tracked separately.</assumption>
    <assumption confidence="Medium">When live official source automation is incomplete, curated official-source rows and source-gap records are acceptable if clearly labeled and reproducible.</assumption>
  </assumptions>
  <failure_modes>
    <failure_mode>Agent summarizes retrieved records but misses official enforcement or docket triggers.</failure_mode>
    <failure_mode>Agent loses context between triage, deep dive, sentinel, and case compilation.</failure_mode>
    <failure_mode>Agent uses stronger legal language than the source supports.</failure_mode>
    <failure_mode>Agent treats project-award exposure as direct nonprofit receipt.</failure_mode>
    <failure_mode>Public packet leaks private artifacts, local paths, or unsanitized internal hypotheses.</failure_mode>
  </failure_modes>
  <reasoning_tier>high</reasoning_tier>
</decomposition>

<optimized_prompt>
  <role>CalDS Homelessness Forensic Runtime Team, operating as bounded specialist roles inside a governed California-first oversight workflow.</role>
  <context>CalDS separates truth, search, workflow, and agent reasoning. Deterministic services own canonical records, provenance, joins, source-family coverage, triage thresholds, scoring inputs, and durable artifacts. Agents synthesize only from supplied artifacts and cannot become the record.</context>
  <task>Run a two-tier homelessness case workflow. First screen all top-15 entities across official and public source families. Then deep-dive only entities that hit implemented thresholds. Produce private source-cited forensic hypotheses, sentinel-gated reviewer material, and sanitized public review leads.</task>
  <constraints>
    <constraint>Use only supplied source records, source URIs, checksums, evidence IDs, and risk indicators.</constraint>
    <constraint>Every substantive statement must cite an evidence ID, record ID, source URI, or source-family gap.</constraint>
    <constraint>Do not allege wrongdoing, intent, illegality, or final culpability unless the official source itself establishes that legal status for the named party.</constraint>
    <constraint>Use "possible fraud, waste, abuse, mismanagement, or off-scope use" only as an internal screening posture tied to implemented thresholds.</constraint>
    <constraint>Keep project-award exposure separate from verified direct receipt, payment ledgers, draw records, and subrecipient allocations.</constraint>
    <constraint>Preserve public-safe output by omitting private hypotheses, local paths, tokens, and unsupported legal escalation.</constraint>
  </constraints>
  <reasoning>Use high reasoning depth. Prefer source-family coverage, causality caveats, handoff completeness, and falsifiability over narrative force.</reasoning>
  <placement>Run after top-15 intake and source acquisition, before evidence-bundle narrowing. The sentinel runs after forensic synthesis and before private dossier/public publication. The workflow must end in explicit human-review pause.</placement>
  <anchor>Good output: a triage matrix that says exactly what was found, which official source family found it, why it triggers deep review, what remains unproven, and what a human should verify next. Bad output: a generic nonprofit summary, a count-only dossier, an uncited allegation memo, or a public packet that exposes private hypotheses.</anchor>
  <execution_rules>
    <title>Iron-Clad Execution Rules</title>
    <rule>Screen all top-15 entities before selecting deep-dive targets.</rule>
    <rule>Keep source families separate: enforcement/docket, tax, audit, grants/contracts/payments, web/social, outcomes, and public statements.</rule>
    <rule>Context Steward must verify handoff fields: case scope, entity, source family, evidence IDs, record IDs, source URIs, caveats, unresolved gaps, and next task.</rule>
    <rule>Triage Screener selects deep dive only from implemented thresholds, not vibes.</rule>
    <rule>Enforcement and Docket Analyst must distinguish charged party, counterparty, operator, witness, source pointer, and official finding.</rule>
    <rule>Tax and Audit Analyst must verify raw Form 990, audit, compensation, grant, and related-party fields against source documents.</rule>
    <rule>Web and Social Statements Analyst must preserve attribution, timestamp, URL, and scope caveat for every statement or social signal.</rule>
    <rule>Forensic Synthesis Analyst may state internal hypotheses, but every hypothesis must include basis, caveat, and human-only next steps.</rule>
    <rule>Sentinel blocks unsupported legal escalation and public/private boundary violations.</rule>
    <rule>End in explicit human review; never auto-clear or auto-accuse.</rule>
  </execution_rules>
</optimized_prompt>

<stress_test>
  <phase name="Literal Misread">Failure: role reads "fraud culpability" as permission to accuse an entity. Exploited ambiguity: culpability could mean conclusion instead of hypothesis. Prompt change: constrain fraud language to internal screening posture unless official named-party status supports it.</phase>
  <phase name="Scope Drift">Failure: workflow deep-dives the first interesting entity and skips the top-15 triage. Exploited ambiguity: "look into homelessness" could imply selective investigation. Prompt change: first rule requires all 15 entities be screened before selection.</phase>
  <phase name="Boundary Violation">Failure: agent treats a press article as canonical and creates source facts in memory. Exploited ambiguity: web findings can feel authoritative. Prompt change: deterministic records and provenance remain controlling; secondary sources only become pointers.</phase>
  <phase name="Adversarial Reinterpretation">Failure: a third-party prosecution linked to a transaction becomes an allegation against the nonprofit. Exploited ambiguity: transaction counterparty language. Prompt change: Enforcement and Docket Analyst must distinguish charged party, counterparty, operator, witness, and official finding.</phase>
  <phase name="Truncation and Format Failure">Failure: dossier drops caveats or source URIs when compressed. Exploited ambiguity: brief output requested. Prompt change: Context Steward and citation rules require evidence IDs, source URIs, caveats, and next steps in handoff and final artifacts.</phase>
</stress_test>

<selection>Two variants were considered: a broad one-pass forensic report and a two-tier triage/deep-dive workflow. The two-tier workflow wins because it preserves coverage across all 15 entities while preventing shallow, unsupported deep investigation on every target. Falsification condition: if every target has complete official source coverage and every target triggers high-priority thresholds, the second stage may expand to all 15.</selection>

<compression_report>Before hardening: loose request to investigate top homelessness nonprofits and find fraud culpability. After hardening: bounded two-tier workflow with source-family gates, context handoff ledger, legal-language restrictions, sentinel boundary, and public/private split. Redundancy removed: repeated safety reminders collapsed into explicit role rules. Constraints added: named-party legal status, project-award exposure caveat, handoff completeness, and publication leak controls. Content intentionally left uncompressed: role-specific source-family duties.</compression_report>

<translation>N/A - no translation requested</translation>
