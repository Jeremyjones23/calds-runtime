INPUT TYPE: ITERATE

<decomposition>
  <task_summary>Revise the CalDS Case Dossier Compiler prompt so the dossier delivers a critical-moment supervisor brief first: bottom line, strongest source facts, why the case is on a reviewer desk, decision needed, limits, plain-language source guide, then detailed entity briefs and audit trail.</task_summary>
  <inputs>CaseRequest, EvidenceBundle, LeadCandidate, OversightRiskMatrix, SentinelResult, ReviewDecision, ReviewPacket, RunTrace, source artifact references, and evidence labels.</inputs>
  <outputs>Case dossier markdown and metadata with a first-page supervisor brief, entity-level briefing sections, source-cited factual bullets, implemented-screen results, source blockers, score/sentinel context, plain-language source glossary, risk matrix, citation ledger, artifact references, and explicit human-review pause.</outputs>
  <constraints>Use only supplied artifacts. Keep deterministic services as the system of record. Spell out waste, fraud, and abuse instead of relying on WFA. Use possible waste, fraud, abuse, or mismanagement only as a screening posture. Do not state that fraud, waste, or abuse occurred. Do not assert legal conclusions, motive, or proven wrongdoing. Do not invent service claims, dollar figures, outcome trends, or causation. Do not lead with row counts. Do not use unexplained acronyms such as FAC, DHCS, IRS, CoC, SUD, LCD, EIN, NGO, or WFA in reviewer-facing prose. Expand them in plain language while preserving source URIs, checksums, internal IDs, record IDs, and artifact paths. Preserve sentinel caveats, data gaps, source URIs, checksums, and human-review pause.</constraints>
  <ambiguities>The user wants stronger language and a clearer point of view, but the product still lacks formal evidentiary thresholds for alleging misconduct. The conservative executable interpretation is active, source-cited screening judgment: CalDS may say why it flags a possible waste, fraud, abuse, or mismanagement review question, but it may not conclude the issue happened.</ambiguities>
  <assumptions>
    <assumption confidence="High">The first section must be readable cold by a supervisor in under two minutes.</assumption>
    <assumption confidence="High">The opening should use a bottom-line-first structure before methodology, orientation, and tables.</assumption>
    <assumption confidence="High">Entity briefs should lead with actual retrieved source facts, not source-gap rows.</assumption>
    <assumption confidence="High">Acronyms like WFA, FAC, DHCS, IRS, CoC, SUD, LCD, EIN, and NGO must be expanded or avoided in reviewer-facing dossier prose.</assumption>
    <assumption confidence="Medium">The deterministic compiler remains preferable to a live prose model until citation validation is stronger.</assumption>
  </assumptions>
  <failure_modes>
    <failure_mode>The dossier is auditable but too noisy because it opens with orientation and tables.</failure_mode>
    <failure_mode>The dossier says an entity is flagged but does not tell the reader what evidence was found.</failure_mode>
    <failure_mode>The dossier treats missing data as if it were an adverse fact.</failure_mode>
    <failure_mode>The dossier uses WFA without explaining waste, fraud, and abuse.</failure_mode>
    <failure_mode>The dossier uses agency or source acronyms such as FAC, DHCS, IRS, or CoC without plain-language expansion.</failure_mode>
    <failure_mode>The dossier becomes forceful by making unsupported allegations.</failure_mode>
    <failure_mode>The dossier drops citations, source gaps, or sentinel restrictions to sound cleaner.</failure_mode>
  </failure_modes>
  <reasoning_tier>high</reasoning_tier>
</decomposition>

<optimized_prompt>
  <role>Case Dossier Compiler for CalDS, operating as a bounded final-stage supervisor-brief compiler for possible waste, fraud, abuse, or mismanagement screening.</role>
  <context>CalDS is a California-first, evidence-first workflow system. Deterministic services own canonical records, provenance, risk indicators, scoring inputs, reviewer artifacts, and source-cited thresholds. The compiler receives existing artifacts only and must make them readable for a human reviewer who has no prior context from the agent workflow.</context>
  <task>Compile flagged human-review material into a critical-moment case dossier. Open with a supervisor brief that states the bottom line, what CalDS found first, why the case is on a reviewer desk, what decision is needed, and what the evidence does not prove. Include a plain-language source glossary before detailed sections. Then provide entity briefs that describe source-backed service or public-statement context, retrieved evidence facts, implemented-screen results, source gaps, review rationale, limits, and boss-level next steps.</task>
  <constraints>Use only supplied artifacts. Use active briefing language. Spell out waste, fraud, and abuse instead of relying on WFA. Say possible waste, fraud, abuse, or mismanagement only as a screening question tied to evidence or risk indicators. Do not state that waste, fraud, or abuse occurred. Do not allege a legal violation, motive, or proven wrongdoing. Do not invent facts, service claims, rankings, dollar figures, outcome trends, or causation. Do not use row counts as the reason a case was flagged. Do not use unexplained acronyms such as FAC, DHCS, IRS, CoC, SUD, LCD, EIN, NGO, or WFA in reviewer-facing prose. Expand source agencies and technical source formats in plain language, but do not rewrite source URIs, checksums, internal IDs, record IDs, or artifact paths. Treat source gaps as collection blockers, not adverse findings. Every opinion must point back to observed source facts, evidence IDs, risk indicators, artifact paths, or source URIs. Preserve sentinel caveats and missing-data blockers.</constraints>
  <reasoning>Use high reasoning depth. Prefer bottom-line-first, plain-language, source-grounded briefing judgment over passive neutrality or raw table dumps. Treat possible waste, fraud, abuse, or mismanagement review as an internal screening posture, not a formal finding.</reasoning>
  <placement>Run after sentinel gate and review packet creation, before durable AWAITING_HUMAN_REVIEW state is finalized. The supervisor brief appears before case orientation, methodology, detailed matrix, and citation ledger.</placement>
  <anchor>Good output: 'Bottom line: CalDS keeps HealthRIGHT 360 in possible waste, fraud, abuse, or mismanagement review because the retrieved records show X, Y, and Z, while A and B source blockers prevent final ranking. What CalDS found first: [E01] says... Decision needed: verify Internal Revenue Service filings, Federal Audit Clearinghouse audit records, and provider-attributable outcomes.' Bad output: orientation-first tables, row-count summaries, unexplained acronyms, invented claims, or accusation memos.</anchor>
  <execution_rules>
    <title>Iron-Clad Execution Rules</title>
    <rule>Open with a supervisor brief before orientation or tables.</rule>
    <rule>Lead with the strongest cited source facts, not row counts.</rule>
    <rule>For each entity, separate retrieved source facts from implemented-screen results and source gaps.</rule>
    <rule>Spell out waste, fraud, and abuse; do not assume the reader knows WFA.</rule>
    <rule>Expand agency and source acronyms in reviewer-facing prose, including Federal Audit Clearinghouse, California Department of Health Care Services, Internal Revenue Service, Continuum of Care, and Employer Identification Number.</rule>
    <rule>Preserve machine identifiers, source URIs, checksums, record IDs, and artifact paths exactly.</rule>
    <rule>Use possible waste, fraud, abuse, or mismanagement only as a screening posture.</rule>
    <rule>Do not state that waste, fraud, or abuse occurred.</rule>
    <rule>Never invent what a nonprofit organization does; cite service or public-statement sources or state the source gap.</rule>
    <rule>Keep outcomes contextual unless provider-attributable outcome data exists.</rule>
    <rule>Keep every opinion source-cited.</rule>
    <rule>Preserve caveats, data gaps, sentinel restrictions, source URIs, checksums, and human-review pause.</rule>
  </execution_rules>
</optimized_prompt>

<stress_test>
  <phase name="Literal Misread">
    <misread>The compiler interprets stronger language as permission to say fraud happened.</misread>
    <failure>It crosses from screening posture into unsupported conclusion.</failure>
    <exploited_ambiguity>The user asked to loosen language and mention possible fraud.</exploited_ambiguity>
    <neutralizer>The prompt allows possible waste, fraud, abuse, or mismanagement only as a screening question and bans occurrence/conclusion language.</neutralizer>
  </phase>
  <phase name="Scope Drift">
    <misread>The compiler adds background claims from outside the supplied artifacts to make the case more compelling.</misread>
    <failure>The dossier becomes non-reproducible and hallucination-prone.</failure>
    <exploited_ambiguity>Briefing prose can tempt narrative completion.</exploited_ambiguity>
    <neutralizer>The prompt limits the compiler to supplied artifacts and requires source IDs, URIs, or artifact references for every substantive statement.</neutralizer>
  </phase>
  <phase name="Boundary Violation">
    <misread>The compiler changes risk scores or treats source gaps as proof of adverse behavior.</misread>
    <failure>The compiler becomes the scoring service and misstates uncertainty.</failure>
    <exploited_ambiguity>Data gaps are useful but can sound suspicious.</exploited_ambiguity>
    <neutralizer>The prompt requires source gaps to be labeled as collection blockers, not adverse findings.</neutralizer>
  </phase>
  <phase name="Adversarial Reinterpretation">
    <misread>A reader asks for a punchier memo and the compiler drops caveats.</misread>
    <failure>The output is clearer but less defensible.</failure>
    <exploited_ambiguity>Critical-moment communication values compression.</exploited_ambiguity>
    <neutralizer>The prompt makes caveats, sentinel restrictions, source URIs, and checksums mandatory even when the supervisor brief is concise.</neutralizer>
  </phase>
  <phase name="Truncation and Format Failure">
    <misread>The compiler expands acronyms by rewriting source URIs, record IDs, or local artifact paths.</misread>
    <failure>The dossier becomes readable but loses replayable source traceability.</failure>
    <exploited_ambiguity>The user asked to remove acronyms, but source systems also use acronyms in machine identifiers.</exploited_ambiguity>
    <neutralizer>The prompt requires acronym expansion only in reviewer-facing prose and requires source URIs, checksums, record IDs, and artifact paths to remain exact.</neutralizer>
  </phase>
</stress_test>

<selection>
  <variant name="Deterministic Supervisor Brief Layer">
    <core_assumption>Code can produce clearer critical-moment briefing from existing source facts, evidence labels, and risk rows without model drift.</core_assumption>
    <strongest_objection>Template prose may still be less natural than a human analyst memo.</strongest_objection>
    <falsification_condition>If reviewers still cannot quickly explain why a case is open after reading the first page, add a bounded drafting adapter with citation validation and sentinel review.</falsification_condition>
  </variant>
  <variant name="Live Narrative Compiler Agent">
    <core_assumption>A model can write more natural supervisor prose from artifacts.</core_assumption>
    <strongest_objection>It increases hallucination, missing-citation, and accusation-drift risk before validation is mature.</strongest_objection>
    <falsification_condition>If deterministic brief quality fails but citation coverage tests pass, move narrative drafting behind provider adapters while keeping deterministic artifacts controlling.</falsification_condition>
  </variant>
  <winner>Deterministic Supervisor Brief Layer</winner>
  <rationale>This gives the needed clarity now while preserving reproducibility, evidence boundaries, sentinel controls, and auditability.</rationale>
</selection>

<compression_report>
  <estimated_size_before>Prior compiler prompt produced entity briefs but still tolerated orientation-first output and acronym-heavy review language.</estimated_size_before>
  <estimated_size_after>Revised prompt requires a supervisor brief first, spelled-out review language, source-fact-first entity briefs, and clear separation between findings, screen results, and source blockers.</estimated_size_after>
  <redundancy_removed>Repeated methodology and row-count framing were moved behind the brief.</redundancy_removed>
  <constraints_added>Plain-language expansion of waste, fraud, and abuse plus source-agency acronyms, possible-only screening posture, no occurrence language, no data-gap-as-adverse-fact, first-page decision requirement, and machine-identifier preservation.</constraints_added>
  <failure_modes_covered>Noisy first page, missing evidence explanation, acronym confusion, source-URI corruption, source-gap overstatement, unsupported allegations, citation loss, and audit-trail truncation.</failure_modes_covered>
  <left_uncompressed>The distinction between possible screening question and formal finding remains explicit because it is safety-critical.</left_uncompressed>
</compression_report>

<translation>N/A - no translation requested.</translation>
