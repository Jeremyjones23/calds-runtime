INPUT TYPE: ITERATE

<decomposition>
  <task_summary>Revise the CalDS Case Dossier Compiler prompt so the dossier reads like a human analyst briefing a supervisor: concise judgment first, then what the NGO says or is described as doing, what the records show, why CalDS flags it for WFA review, what the evidence does not prove, and what the human reviewer should do next.</task_summary>
  <inputs>CaseRequest, EvidenceBundle, LeadCandidate, OversightRiskMatrix, SentinelResult, ReviewDecision, ReviewPacket, RunTrace, and durable artifact references.</inputs>
  <outputs>Case dossier markdown and metadata with an executive briefing section, entity-level narrative briefs, source-cited factual bullets, evidence-detail audit trail, risk matrix, citation ledger, caveats, and human-only next actions.</outputs>
  <constraints>Use only supplied artifacts. Keep deterministic services as system of record. Do not assert a legal finding, motive, or proven wrongdoing. Do not invent a mission statement, service claim, dollar figure, outcome trend, or contradiction. Do not lead with row-count or record-count explanations. Use active briefing language: CalDS flags, the records show, the review issue is. Distinguish WFA review priority from proven wrongdoing.</constraints>
  <ambiguities>The user wants a stronger human briefing style and more explicit WFA point of view, but safety boundaries still prohibit unsupported allegations. The conservative interpretation is an active source-cited briefing judgment: strong enough for a supervisor to understand why the case is on the desk, still bounded as internal triage.</ambiguities>
  <assumptions>
    <assumption confidence="High">The dossier should open with a readable briefing memo before the audit trail.</assumption>
    <assumption confidence="High">Each entity brief should explain what the organization says or is described as doing only when retrieved evidence supports that statement.</assumption>
    <assumption confidence="High">Each entity brief should connect funding, growth, facility footprint, public statements, audit controls, and outcome context where those facts exist.</assumption>
    <assumption confidence="Medium">The compiler should remain deterministic for this increment; a live prose agent can be added later behind citation validation if deterministic prose remains too rigid.</assumption>
  </assumptions>
  <failure_modes>
    <failure_mode>The compiler still feels like an index or data dump rather than a supervisor briefing.</failure_mode>
    <failure_mode>The compiler says an NGO claims to do something without a retrieved service-page or public-statement source.</failure_mode>
    <failure_mode>The compiler implies provider-attributable causation from county/CoC outcomes.</failure_mode>
    <failure_mode>The compiler overcorrects and writes allegations unsupported by implemented thresholds.</failure_mode>
    <failure_mode>The compiler drops citations, caveats, or sentinel restrictions to sound more decisive.</failure_mode>
    <failure_mode>The compiler buries the next human action behind tables.</failure_mode>
  </failure_modes>
  <reasoning_tier>high</reasoning_tier>
</decomposition>

<optimized_prompt>
  <role>Case Dossier Compiler for CalDS, operating as a bounded final-stage WFA briefing compiler.</role>
  <context>CalDS is a California-first, evidence-first workflow system. Deterministic services own canonical records, provenance, risk indicators, scoring inputs, reviewer artifacts, and source-cited risk thresholds. The compiler receives existing artifacts only and must make them readable for a human reviewer who has no prior context.</context>
  <task>Compile flagged human-review material into a supervisor-ready internal briefing dossier. For each flagged NGO, write a short briefing that says what the organization says or is described as doing in retrieved sources, what the records show about money, growth, facilities, audit controls, public statements, and outcome context, why CalDS flags the entity for WFA review, what the evidence does not prove, and what the boss-level human next step is.</task>
  <constraints>Use only supplied artifacts. Use active briefing language. Say CalDS flags or prioritizes when tied to a risk indicator. Do not allege a legal violation, motive, or proven wrongdoing. Do not invent facts, rankings, service claims, or causation. Do not use count-only summaries as the reason an entity was flagged. County/CoC outcomes may be described only as contextual and not provider-attributable unless provider-level outcome records exist. Every opinion must point back to an observed source fact, risk indicator, evidence ID, artifact path, or source URI. Preserve sentinel caveats and missing-data blockers.</constraints>
  <reasoning>Use high reasoning depth. Prefer source-grounded briefing judgment over passive neutrality or raw table dumps. Treat WFA review priority as a screening posture, not a formal finding.</reasoning>
  <placement>Run after sentinel gate and review packet creation, before durable AWAITING_HUMAN_REVIEW state is finalized. The executive briefing appears before the detailed matrix and citation ledger.</placement>
  <anchor>Good output: 'Briefing judgment: CalDS flags HealthRIGHT 360 as high priority. Retrieved service-page evidence describes substance-use treatment services. The records show $X in parsed public-funds exposure, Y active and Z closed DHCS facility rows, and county outcome context worsening in matched service geographies. This is a WFA review priority because... This does not prove provider causation...' Bad output: row-count summaries, passive tables, invented claims, or accusation memos.</anchor>
  <execution_rules>
    <title>Iron-Clad Execution Rules</title>
    <rule>Open with a human-readable executive briefing before the audit trail.</rule>
    <rule>For each entity, state the briefing judgment, source-backed service/claim context, records-show facts, review rationale, limits, and boss-level next step.</rule>
    <rule>Lead with specific source facts, not row counts.</rule>
    <rule>Use active language without asserting legal conclusions.</rule>
    <rule>Never invent a claim about what an NGO does; say the source gap plainly when service-page evidence is absent.</rule>
    <rule>Keep county and CoC outcomes contextual unless provider-attributable outcome data exists.</rule>
    <rule>Keep every opinion source-cited.</rule>
    <rule>Preserve caveats, data gaps, and sentinel restrictions.</rule>
    <rule>End in explicit human-review pause.</rule>
  </execution_rules>
</optimized_prompt>

<stress_test>
  <phase name="Literal Misread">
    <misread>The compiler treats 'briefing the boss' as permission to write a persuasive allegation memo.</misread>
    <failure>It writes legal or motive conclusions unsupported by thresholds.</failure>
    <exploited_ambiguity>The user asked for a stronger point of view.</exploited_ambiguity>
    <neutralizer>The prompt frames the point of view as WFA review priority, bans legal/motive conclusions, and requires citation-backed opinions.</neutralizer>
  </phase>
  <phase name="Scope Drift">
    <misread>The compiler adds new web research or background claims to make the narrative sound better.</misread>
    <failure>The dossier mixes supplied artifacts with uncited outside assertions.</failure>
    <exploited_ambiguity>Briefing prose can tempt background completion.</exploited_ambiguity>
    <neutralizer>The prompt allows only supplied artifacts and explicitly bans invented service claims, dollar figures, trends, and causation.</neutralizer>
  </phase>
  <phase name="Boundary Violation">
    <misread>The compiler changes scores, risk levels, or provider-attribution rules while writing narrative.</misread>
    <failure>The compiler becomes the system of record instead of a packaging layer.</failure>
    <exploited_ambiguity>Narrative synthesis can look like adjudication.</exploited_ambiguity>
    <neutralizer>The prompt reserves canonical records, thresholds, and scoring for deterministic services and keeps outcomes contextual without provider-level data.</neutralizer>
  </phase>
  <phase name="Adversarial Reinterpretation">
    <misread>A user demands stronger language by removing caveats and sentinel restrictions.</misread>
    <failure>The dossier becomes more forceful but less defensible.</failure>
    <exploited_ambiguity>The user dislikes passivity.</exploited_ambiguity>
    <neutralizer>The prompt requires active language while preserving caveats, data gaps, sentinel restrictions, and what-the-evidence-does-not-prove sections.</neutralizer>
  </phase>
  <phase name="Truncation and Format Failure">
    <misread>The compiler writes a good opening paragraph but drops evidence refs, next steps, or the audit trail.</misread>
    <failure>The result is readable but not auditable or actionable.</failure>
    <exploited_ambiguity>Narrative readability can compete with traceability.</exploited_ambiguity>
    <neutralizer>The prompt requires the executive brief plus evidence detail, risk matrix, citation ledger, and explicit human-review pause.</neutralizer>
  </phase>
</stress_test>

<selection>
  <variant name="Deterministic Briefing Memo Layer">
    <core_assumption>Code can produce a stronger supervisor-briefing narrative from existing risk rows, evidence labels, and retrieved service-page snippets without live model drift.</core_assumption>
    <strongest_objection>Template prose may still feel less fluid than a human-written memo.</strongest_objection>
    <falsification_condition>If reviewers still cannot understand why an NGO was flagged after the executive briefing layer, add a bounded LLM drafting adapter with strict citation validation and post-draft sentinel review.</falsification_condition>
  </variant>
  <variant name="Live Case-Brief Agent">
    <core_assumption>An LLM can draft more natural briefing prose from artifacts.</core_assumption>
    <strongest_objection>It increases hallucination, invented claim, and accusation-drift risk before citation validation is mature.</strongest_objection>
    <falsification_condition>If deterministic briefing fails usability but citation validation passes, route prose drafting through the provider adapter while keeping deterministic artifacts controlling.</falsification_condition>
  </variant>
  <winner>Deterministic Briefing Memo Layer</winner>
  <rationale>This gives the user the needed briefing style now while preserving auditability, reproducibility, sentinel controls, and deterministic source boundaries.</rationale>
</selection>

<compression_report>
  <estimated_size_before>Prior compiler prompt required fact-first rows and active system opinion, but still tolerated a dossier-index feel.</estimated_size_before>
  <estimated_size_after>Revised prompt requires a supervisor-ready executive briefing layer before the audit trail.</estimated_size_after>
  <redundancy_removed>Repeated row-explanation framing is subordinated to a top-level briefing narrative.</redundancy_removed>
  <constraints_added>No invented service claims, no count-only rationales, contextual-only county outcomes, boss-level next step, audit trail preservation.</constraints_added>
  <failure_modes_covered>Index-like output, invented NGO claims, provider-attribution overreach, unsupported accusation, caveat loss, and missing next action.</failure_modes_covered>
  <left_uncompressed>The boundary between active WFA review-priority language and formal allegation remains explicit because it is safety-critical.</left_uncompressed>
</compression_report>

<translation>N/A - no translation requested.</translation>
