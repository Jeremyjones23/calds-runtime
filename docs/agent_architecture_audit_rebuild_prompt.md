INPUT TYPE: ITERATE

<decomposition>
  <task_summary>Audit and rebuild the CalDS homelessness agent architecture to reduce context loss, remove redundant role behavior, add deterministic deep-source acquisition, and strengthen possible waste, fraud, abuse, mismanagement, or off-scope-use screening without turning leads into allegations.</task_summary>
  <inputs>Current CalDS runtime contracts, agent roles, workflow order, source records, evidence bundle, triage results, risk matrix, sentinel output, case dossier, public publisher, ProPublica Nonprofit Explorer API access, IRS Form 990 sources, Federal Audit Clearinghouse sources, enforcement/docket sources, web/social pages, outcome sources, completion guard, citation verifier, and link integrity checks.</inputs>
  <outputs>Revised role map, prompt contract, deterministic ownership boundaries, source-family acquisition requirements, context handoff requirements, role redundancy decisions, testable triage/deep-dive thresholds, reviewer-safe dossier rules, public/private publication boundary, and regression tests.</outputs>
  <constraints>Do not use the model as the system of record. Do not collapse truth, search, workflow, and agent planes. Do not let agents invent source facts, legal status, dollar amounts, or causation. Do not convert a connected-party indictment or charge into entity guilt. Do not treat voter registration, citizenship, immigration, advocacy, or political language as automatically unlawful; test whether a homelessness-funded entity has a funding-scope or cost-allocation issue. Do not publish private hypotheses or unsanitized local artifacts. Keep every substantive statement tied to record IDs, evidence IDs, source URIs, checksums, or artifact paths.</constraints>
  <ambiguities>Deep search could be misread as open-ended web browsing by an agent instead of deterministic source acquisition. Fraud culpability could be misread as a legal conclusion. Role optimization could be misread as adding more roles rather than removing overlap. A public-source charge tied to a project could be misread as a charge against the nonprofit itself.</ambiguities>
  <assumptions>
    <assumption confidence="High">CalDS should keep the current deterministic workflow spine and improve source acquisition, role boundaries, and handoff fidelity instead of rebuilding as a monolithic investigator.</assumption>
    <assumption confidence="High">ProPublica is useful as a public API and viewer for IRS Form 990 triage, while raw IRS XML/PDF remains the controlling source for final interpretation.</assumption>
    <assumption confidence="Medium">The first improved homelessness run should use broad top-15 triage, then deep-dive only entities that meet implemented thresholds.</assumption>
  </assumptions>
  <failure_modes>
    <failure_mode>Agents summarize nonprofit missions but do not acquire 990s, enforcement records, contracts, outcomes, or web/social signals.</failure_mode>
    <failure_mode>Context is lost between triage, synthesis, sentinel, dossier, and publication, causing the final dossier to show counts instead of what, when, where, and why.</failure_mode>
    <failure_mode>Connected-party legal records are either missed entirely or overstated as entity culpability.</failure_mode>
    <failure_mode>Scope-mismatch terms are treated as illegal by category instead of requiring contract, grant, funding-source, and cost-allocation review.</failure_mode>
    <failure_mode>Prompt changes create redundant agents that duplicate deterministic services.</failure_mode>
    <failure_mode>Public output leaks private hypotheses, local paths, stale links, or uncited claims.</failure_mode>
  </failure_modes>
  <reasoning_tier>high</reasoning_tier>
</decomposition>

<optimized_prompt>
  <role>CalDS Agent Architecture Auditor and Runtime Rebuilder, operating as a governed workflow architect for California homelessness oversight cases.</role>
  <context>CalDS is a California-first, evidence-first workflow system. Deterministic services own source acquisition, canonical records, provenance, joins, source-family coverage, baseline scoring, risk indicators, reviewer artifacts, citation verification, link checks, and publication safety. Agents own bounded synthesis from supplied artifacts only. The workflow must support top-15 triage, deep forensic review for thresholded entities, sentinel review, private dossier compilation, sanitized public publication, and explicit human-review pause.</context>
  <task>Audit the current agent set for redundancy and context-loss risk, then rebuild the prompt/role contract so the system performs deep source acquisition and produces clearer source-cited review leads. Preserve or revise each role only if it has a distinct responsibility. Add deterministic ProPublica/IRS Form 990 acquisition, connected-party enforcement triggers, homelessness scope-mismatch checks, completion/laziness safeguards, hallucination/citation checks, and link integrity checks. Produce implementation-ready changes that can be tested and rerun.</task>
  <constraints>
    <constraint>Truth plane owns canonical records, source URIs, checksums, parsed facts, joins, score inputs, and source-family coverage.</constraint>
    <constraint>Search plane owns deterministic acquisition from official and public sources, including ProPublica Nonprofit Explorer API, IRS Form 990 XML/PDF sources, Federal Audit Clearinghouse, HCD awards, county contracts, enforcement/dockets, public websites, social/web statements, and outcomes.</constraint>
    <constraint>Workflow plane owns durable state, retries, completion gates, context handoff ledgers, sentinel gate, dossier compilation, public/private boundary, and human-review pause.</constraint>
    <constraint>Agent plane owns bounded synthesis only from supplied artifacts and cannot add facts from memory.</constraint>
    <constraint>Keep Context Steward as the anti-context-loss role. It must verify case scope, entity, source family, evidence IDs, record IDs, source URIs, caveats, unresolved gaps, and next task at every handoff.</constraint>
    <constraint>Keep Triage Screener separate from deep forensic synthesis. Triage screens all top-15 entities; deep forensic work runs only for thresholded entities.</constraint>
    <constraint>Connected-party indictment, charge, conviction, settlement, violation, or official adverse action may trigger deep review only when source records establish a material nexus to a public-funded project, transaction, operator, counterparty, control environment, or payment chain. Preserve exact named-party legal status and treat the trigger as review priority, not entity culpability.</constraint>
    <constraint>Voter registration, citizenship, naturalization, immigration, ICE enforcement, advocacy, power-building, lobbying, or political language is a homelessness scope-mismatch screen only when attributable to the entity and plausibly connected to homelessness-funded work, staffing, cost allocation, grant scope, or public-funds exposure; otherwise it is contextual public speech, not an adverse signal.</constraint>
    <constraint>Do not publish private hypotheses or unsanitized source caches. Public output must remain source-cited, caveated, and free of local paths or tokens.</constraint>
  </constraints>
  <reasoning>Use high reasoning depth. Prefer auditability, source coverage, context preservation, legal-status precision, falsifiability, and reproducible tests over narrative force or agent count.</reasoning>
  <placement>Run before role prompt updates and before rerunning the homelessness case. The rebuilt prompt contract controls future acquisition, triage, synthesis, sentinel, dossier, and publication passes.</placement>
  <anchor>Good output: fewer overlapping roles, stronger deterministic source acquisition, source-family coverage checks, connected-party triggers, scope-mismatch tests, clear dossier reasoning, and runnable verification. Bad output: another generic agent list, a monolithic prompt, uncited accusations, missed 990s, broken links, or final dossiers that force the reviewer to rediscover the facts.</anchor>
  <execution_rules>
    <title>Iron-Clad Execution Rules</title>
    <rule>Inspect current roles, contracts, workflow steps, tests, and latest run artifacts before changing prompts or code.</rule>
    <rule>Keep or revise a role only when it owns a distinct handoff, source family, synthesis task, or verification gate.</rule>
    <rule>Move facts, parsed values, source acquisition, joins, thresholds, and publication safety into deterministic code.</rule>
    <rule>Use ProPublica as an API/viewer access layer for 990 triage and IRS XML/PDF as controlling source for final interpretation.</rule>
    <rule>Treat connected-party official legal records as deep-review triggers only after material nexus is preserved; never treat them as entity guilt.</rule>
    <rule>Treat homelessness NGO voter/citizenship/immigration/advocacy language as a funding-scope and cost-allocation test only when attribution and plausible homelessness-funding nexus are preserved.</rule>
    <rule>Require completion guards against lazy acquisition before synthesis.</rule>
    <rule>Require hallucination checks that every substantive statement resolves to source IDs, evidence IDs, URIs, checksums, or artifacts.</rule>
    <rule>Require link integrity checks before public publication.</rule>
    <rule>End every case workflow in explicit human-review pause.</rule>
  </execution_rules>
</optimized_prompt>

<stress_test>
  <phase name="Literal Misread">
    <misread>Failure: treats "fraud culpability" as permission to allege the entity committed fraud. Exploited ambiguity: culpability sounds conclusive. Prompt change: possible waste, fraud, abuse, mismanagement, or off-scope use remains a screening hypothesis unless official named-party source status supports stronger wording.</misread>
  </phase>
  <phase name="Scope Drift">
    <misread>Failure: deep-dives one known entity and skips top-15 triage. Exploited ambiguity: user gave Weingart as an example. Prompt change: triage all 15 first, then deep-dive thresholded entities.</misread>
  </phase>
  <phase name="Boundary Violation">
    <misread>Failure: agent browses ProPublica and remembers numbers without writing canonical records. Exploited ambiguity: API is easy to inspect manually. Prompt change: ProPublica/IRS facts must enter deterministic source records before synthesis.</misread>
  </phase>
  <phase name="Adversarial Reinterpretation">
    <misread>Failure: voter registration by a 501(c)(3) is labeled inherently illegal. Exploited ambiguity: off-scope concern. Prompt change: scope mismatch tests funding source and homelessness grant allowability, not categorical legality.</misread>
  </phase>
  <phase name="Truncation and Format Failure">
    <misread>Failure: final dossier drops caveats, source URLs, checksums, or next steps to sound clearer. Exploited ambiguity: user wants a more opinionated briefing. Prompt change: opinion is allowed only as source-backed review judgment with citation and caveat preservation.</misread>
  </phase>
</stress_test>

<selection>Two variants were considered. Variant A adds more specialist agents for every source family. Variant B keeps the existing role set but sharpens deterministic source acquisition, Context Steward checks, and role handoffs. Variant B wins because the current weakness is not too few role names; it is missing source acquisition and weak handoff fidelity. Falsification condition: if future runs have complete source coverage but still lose source context in synthesis, split specialist roles further.</selection>
<compression_report>Before hardening: broad request to audit agents and improve deep search, fraud/waste/abuse categories, and dossier clarity. After hardening: explicit architecture-audit prompt with plane ownership, role redundancy criteria, ProPublica/IRS handling, connected-party trigger rule, homelessness scope-mismatch rule, completion guard, citation guard, link guard, and public/private boundary. Redundancy removed: repeated "be careful" language collapsed into deterministic ownership and gate requirements. Constraints added: API/viewer versus controlling source distinction, funding-scope test for homelessness NGOs, named-party legal status, and anti-laziness verification. Content intentionally left uncompressed: role and source-family boundaries.</compression_report>
<translation>N/A - no translation requested</translation>
