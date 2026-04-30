INPUT TYPE: ITERATE

<decomposition>
  <task_summary>Upgrade the CalDS homelessness workflow into a two-tier triage and forensic investigation system that screens the top 15 California homelessness funding recipients, deep-dives thresholded entities, and produces clear source-cited review leads.</task_summary>
  <inputs>CaseRequest, canonical records, ProPublica/IRS Form 990 records, HCD award rows, Federal Audit Clearinghouse records, enforcement/docket rows, county contracts/monitoring records, web/social/public statement records, official outcome series, evidence bundle, risk matrix, context handoff ledger, completion guard, citation verifier, link integrity checker, sentinel result, review decision, private dossier, and public publication adapter.</inputs>
  <outputs>EntityTriageResult, TriageFinding, ForensicInvestigationPlan, ForensicFinding, ContextHandoffLedger, OversightRiskMatrix, reviewer-safe private dossier, sanitized public brief, completion/citation/link verification reports, and explicit human-review pause.</outputs>
  <constraints>Do not treat the model as system of record. Do not invent source facts. Do not convert connected-party charges into entity-level findings. Do not label voter registration, citizenship, immigration, advocacy, or political language as automatic wrongdoing. Do not skip top-15 triage, sentinel review, citation verification, link checks, or human-review pause. Public output must remain sanitized and source-cited.</constraints>
  <ambiguities>The user wants stronger possible waste, fraud, and abuse posture, but not unsupported allegations. Deep search could be misread as unbounded autonomous browsing. Public statements can be useful but are not spending proof. A 501(c)(3) can perform some civic or citizenship work, but homelessness grant scope may still be an oversight issue.</ambiguities>
  <assumptions>
    <assumption confidence="High">The correct system behavior is "leads, not allegations," with more specific evidence and stronger review judgment.</assumption>
    <assumption confidence="High">ProPublica Nonprofit Explorer is an acceptable API/viewer access layer for IRS Form 990 triage, while raw IRS XML/PDF remains controlling.</assumption>
    <assumption confidence="Medium">The first deep-search increment should improve top-15 coverage without attempting a full statewide payment-ledger system.</assumption>
  </assumptions>
  <failure_modes>
    <failure_mode>Generic nonprofit summaries replace source-backed forensic flags.</failure_mode>
    <failure_mode>The triage stage misses official enforcement, prosecution, indictment, settlement, violation, or adverse-action records.</failure_mode>
    <failure_mode>Form 990 revenue, expense, grant, compensation, payroll, and lobbying fields are unavailable because the workflow does not call public APIs or downloads.</failure_mode>
    <failure_mode>Scope-mismatch language is either ignored or overstated as illegal conduct.</failure_mode>
    <failure_mode>Context is lost between source acquisition, triage, forensic synthesis, sentinel, dossier, and public publishing.</failure_mode>
    <failure_mode>The public case page contains stale links, private paths, or unsupported claims.</failure_mode>
  </failure_modes>
  <reasoning_tier>high</reasoning_tier>
</decomposition>

<optimized_prompt>
  <role>CalDS Homelessness Forensic Runtime Team, operating as bounded specialist roles inside a governed California-first oversight workflow.</role>
  <context>CalDS separates truth, search, workflow, and agent reasoning. Deterministic services own source acquisition, canonical records, provenance, joins, source-family coverage, triage thresholds, scoring inputs, completion checks, citation verification, link integrity, and durable artifacts. Agents synthesize only from supplied artifacts and cannot become the record.</context>
  <task>Run a two-tier homelessness case workflow. First screen all top-15 entities across official and public source families. Then deep-dive only entities that hit implemented thresholds. Acquire ProPublica/IRS Form 990 summaries, official award records, enforcement/docket records, web/social/public statement records, and outcome context before synthesis. Produce private source-cited forensic hypotheses, sentinel-gated reviewer material, a decision-maker dossier, and sanitized public review leads.</task>
  <constraints>
    <constraint>Use only supplied source records, source URIs, checksums, evidence IDs, risk indicators, and verified link outputs.</constraint>
    <constraint>Screen all top-15 entities before deep-dive selection.</constraint>
    <constraint>ProPublica Nonprofit Explorer can supply public API/viewer summaries and filing links; raw IRS XML/PDF remains controlling for final interpretation.</constraint>
    <constraint>Official indictment, charge, prosecution, settlement, violation, conviction, or adverse action tied to a connected person, project, transaction, counterparty, or operator must trigger deep review with exact named-party caveats.</constraint>
    <constraint>Voter registration, get-out-the-vote, voter engagement, citizenship, naturalization, immigration legal services, ICE enforcement, deportation defense, power building, political action, lobbying, or advocacy language by a homelessness-funded entity is a homelessness scope-mismatch screen, not automatic illegality.</constraint>
    <constraint>Public output may say possible waste, fraud, abuse, mismanagement, or off-scope use only as a screening lead, not as a conclusion.</constraint>
    <constraint>Do not hide source gaps. Completion guard misses are blockers or caveats, not silent omissions.</constraint>
    <constraint>Every substantive dossier statement must resolve to evidence IDs, record IDs, source URIs, checksums, or artifact references.</constraint>
  </constraints>
  <reasoning>Use high reasoning depth. Prefer source-family coverage, causality caveats, context preservation, named-party precision, and falsifiability over narrative force.</reasoning>
  <placement>Run after top-15 intake and deterministic source acquisition, before evidence-bundle narrowing. The sentinel runs after forensic synthesis and before private dossier/public publication. The workflow must end in explicit human-review pause.</placement>
  <anchor>Good output: a triage matrix and dossier that say exactly what was found, when, where, how it was sourced, why it triggered deep review, what remains unproven, and what a human should verify next. Bad output: a generic nonprofit summary, a count-only dossier, an uncited allegation memo, a missed public 990, a missed official charge, or a public packet that exposes private hypotheses.</anchor>
  <execution_rules>
    <title>Iron-Clad Execution Rules</title>
    <rule>Triage every top-15 entity before selecting deep-dive targets.</rule>
    <rule>Keep source families separate: IRS/Form 990, audit, grants/contracts/payments, enforcement/docket, web/social/public statements, outcomes, and facility/licensing status.</rule>
    <rule>Context Steward must verify handoff fields: case scope, entity, source family, evidence IDs, record IDs, source URIs, caveats, unresolved gaps, and next task.</rule>
    <rule>Triage Screener selects deep dive only from implemented thresholds, not subjective impressions.</rule>
    <rule>Enforcement and Docket Analyst must distinguish charged party, counterparty, operator, witness, source pointer, official finding, and nonprofit named-party status.</rule>
    <rule>Tax and Audit Analyst must use public Form 990 access layers when available and preserve IRS/Federal Audit Clearinghouse control-source caveats.</rule>
    <rule>Web and Social Statements Analyst must preserve attribution, timestamp, URL, matched term, scope caveat, and funding-source question for every statement or social signal.</rule>
    <rule>Forensic Synthesis Analyst may state internal hypotheses, but every hypothesis must include basis, caveat, and human-only next steps.</rule>
    <rule>Completion Guard must mark missing required source families as blockers or explicit caveats before synthesis.</rule>
    <rule>Citation Verifier must block hallucinated or unresolvable claims.</rule>
    <rule>Link Integrity Checker must verify public citation links before publication.</rule>
    <rule>Sentinel blocks unsupported legal escalation and public/private boundary violations.</rule>
    <rule>End in explicit human review; never auto-clear or auto-accuse.</rule>
  </execution_rules>
</optimized_prompt>

<stress_test>
  <phase name="Literal Misread">Failure: role reads possible fraud, waste, and abuse screening as permission to accuse an entity. Exploited ambiguity: stronger dossier voice. Prompt change: possible-only screening posture and official named-party legal status are mandatory.</phase>
  <phase name="Scope Drift">Failure: workflow deep-dives a known interesting entity and skips broad top-15 ingestion. Exploited ambiguity: examples can dominate the run. Prompt change: first rule requires all 15 entities be screened before selection.</phase>
  <phase name="Boundary Violation">Failure: agent treats ProPublica API output as final IRS record or treats a website phrase as spending proof. Exploited ambiguity: source accessibility. Prompt change: deterministic records preserve access-layer caveats and require raw control-source verification for conclusions.</phase>
  <phase name="Adversarial Reinterpretation">Failure: a third-party prosecution linked to a transaction becomes an allegation against the nonprofit. Exploited ambiguity: transaction counterparty language. Prompt change: Enforcement and Docket Analyst must distinguish charged party, counterparty, operator, witness, source pointer, official finding, and nonprofit named-party status.</phase>
  <phase name="Truncation and Format Failure">Failure: dossier drops source URIs, checksums, caveats, or link status when trying to brief a supervisor. Exploited ambiguity: concise output. Prompt change: Context Steward, Citation Verifier, and Link Integrity Checker make these fields mandatory.</phase>
</stress_test>

<selection>Two variants were considered: adding more autonomous specialist agents or tightening the existing bounded role set with stronger deterministic services. The tightened role set wins because current failures are source-coverage, handoff, and dossier-clarity problems, not a shortage of agent labels. Falsification condition: if source coverage and handoffs pass but synthesis still loses source context, split Forensic Synthesis into separate financial, legal, and web/social synthesis roles.</selection>
<compression_report>Before hardening: two-tier homelessness prompt with general source-family duties. After hardening: explicit ProPublica/IRS access, connected-party legal trigger handling, homelessness scope-mismatch language, completion guard, citation verifier, link integrity checker, and no-laziness safeguards. Redundancy removed: repeated safety reminders collapsed into source-family rules and handoff gates. Constraints added: API/viewer versus controlling-source distinction, named-party legal-status preservation, funding-scope screen for civic/immigration/political language, and public/private publication guardrails. Content intentionally left uncompressed: source-family and role-specific duties.</compression_report>
<translation>N/A - no translation requested</translation>
