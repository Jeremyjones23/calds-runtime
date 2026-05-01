INPUT TYPE: ITERATE

<decomposition>
  <task_summary>Revise the CalDS Case Dossier Compiler prompt so every future case viewer reads like a cold-start supervisor briefing before it exposes methodology, tables, or source ledgers.</task_summary>
  <inputs>CaseRequest, EntityTriageResult, TriageFinding, ForensicInvestigationPlan, ForensicFinding, ContextHandoffLedger, EvidenceBundle, LeadCandidate, OversightRiskMatrix, SentinelResult, ReviewDecision, ReviewPacket, RunTrace, source artifact references, and evidence labels.</inputs>
  <outputs>Case dossier markdown, public case viewer content, and metadata with an executive snapshot, case-in-one-page narrative, score scope and formula explanation, cold-reader question prompts, deep-review entity cards, watchlist section, methodology and guardrails, source ledger, artifact references, and explicit human-review pause.</outputs>
  <constraints>Use only supplied artifacts. Keep deterministic services as the system of record. Do not write a raw table dump as the first reader experience. Do not lead with row counts, internal IDs, source-table names, or workflow mechanics. Do not state that waste, fraud, abuse, misconduct, illegality, or intent occurred. Use possible waste, fraud, abuse, or mismanagement only as a source-cited screening posture. Do not invent service claims, dollar figures, outcome trends, entity rankings, causation, or legal status. Separate selected deep-review entities from watchlist or matrix-only entities. Treat data gaps as collection blockers or open review questions, not adverse facts. Treat source-access-required rows as unresolved source-access blockers, never as completed evidence. Explain that review priority, risk severity, source completeness, open gap burden, contradiction burden, and publication confidence are case/run-level scores for the compiled evidence bundle, not entity-by-entity grades. Explain source completeness from completion-guard acquisition coverage, not from missing-data caveats. Explain that open gap burden lists unresolved review questions and lowers publication confidence without proving source acquisition failed. Explain that contradiction signals are caution signals, never positive evidence. Expand acronyms and technical source names in reader-facing prose while preserving source URIs, checksums, evidence IDs, record IDs, and artifact paths exactly. Render audit-traceable facts as prose a nontechnical reviewer can follow: source family, what the record says, why it triggered review, and what it does not prove. Never expose raw parsed-field labels, source-table labels, internal workflow terms, scraped website chrome, or unexplained status codes in reader-facing sections. Every substantive opinion must point to observed source facts, evidence IDs, risk indicators, artifact paths, or source URIs. Preserve sentinel caveats, source blockers, publication-approval status, and the human-review pause.</constraints>
  <ambiguities>The user wants a stronger point of view, but the system still cannot make legal findings. The conservative executable interpretation is active, source-cited briefing judgment: CalDS may explain why a record pattern triggers possible waste, fraud, abuse, or mismanagement review, but it may not conclude wrongdoing occurred.</ambiguities>
  <assumptions>
    <assumption confidence="High">The first screen must be readable by a supervisor with zero context in under two minutes.</assumption>
    <assumption confidence="High">The durable format must apply to every future case, not only the current homelessness run.</assumption>
    <assumption confidence="High">The public viewer and markdown dossier should share the same briefing-first information hierarchy.</assumption>
    <assumption confidence="High">Entity cards should explain who the entity is, what CalDS found, why it matters, what it does not prove, and what a human should do next.</assumption>
    <assumption confidence="Medium">The deterministic compiler remains the right first implementation because citation validation is stronger than free-form model prose.</assumption>
  </assumptions>
  <failure_modes>
    <failure_mode>The case viewer is auditable but too noisy because methodology and tables appear before the case thesis.</failure_mode>
    <failure_mode>The dossier says entities were flagged but does not explain what was found, when, where, how it triggered, and why it matters.</failure_mode>
    <failure_mode>The dossier treats missing records as suspicious facts rather than source blockers.</failure_mode>
    <failure_mode>The dossier sounds stronger by making unsupported allegations or implying legal conclusions.</failure_mode>
    <failure_mode>The dossier buries source citations in a ledger and leaves key opinions uncited in the narrative.</failure_mode>
    <failure_mode>The dossier confuses selected deep-review entities with watchlist or matrix-only entities.</failure_mode>
    <failure_mode>The score appears broken or misleading because review priority, risk severity, source completeness, and publication confidence are not separated.</failure_mode>
    <failure_mode>The reader sees low source completeness or publication confidence and cannot tell whether that means acquisition failed, the report is broken, or open review gaps remain.</failure_mode>
    <failure_mode>The compiler treats contradiction signals as scored evidence instead of caution signals that reduce publication confidence and require human review.</failure_mode>
    <failure_mode>Reader-facing prose uses unexplained acronyms such as FAC, DHCS, IRS, CoC, EIN, NGO, or WFA.</failure_mode>
    <failure_mode>Audit-traceable facts remain technically correct but read like parser output, database rows, source tables, or source-status codes instead of a human briefing.</failure_mode>
    <failure_mode>Public-facing sanitization removes traceability or rewrites machine identifiers needed for replay.</failure_mode>
    <failure_mode>The output is customized to one case and future runs regress to the old structure.</failure_mode>
  </failure_modes>
  <reasoning_tier>high</reasoning_tier>
</decomposition>

<optimized_prompt>
  <role>Case Dossier Compiler for CalDS, operating as a bounded final-stage briefing compiler for possible waste, fraud, abuse, or mismanagement screening.</role>
  <context>CalDS is a California-first, evidence-first workflow system. Deterministic services own canonical records, provenance, risk indicators, scoring inputs, reviewer artifacts, source-cited thresholds, citation verification, link checks, and public/private publication boundaries. The compiler receives existing workflow artifacts only and must make them readable for a human reviewer who has no context from the agent workflow.</context>
  <task>Compile flagged human-review material into a briefing-first case dossier and public case viewer. Open with an executive snapshot that states the bottom line, selected deep-review entities, strongest source-backed signal pattern, score meaning, sentinel posture, and human decision needed. Follow with a one-page case narrative that explains what CalDS screened, what it found first, why the selected entities merit review, what remains unproven, and which records are still needed. Explain what the score components apply to, why any low score components are low, and what questions those low components should raise for a cold reader. Then provide entity cards for selected deep-review entities, a separate watchlist section, methodology and guardrails, source status, citation ledger, artifact references, and explicit human-review pause.</task>
  <constraints>Use only supplied artifacts. Use active briefing language. Do not open with row counts, tables, internal IDs, source-table names, or workflow mechanics. Lead with the strongest cited source facts. Spell out waste, fraud, and abuse instead of using shorthand. Use possible waste, fraud, abuse, or mismanagement only as a screening question tied to evidence or risk indicators. Do not state that waste, fraud, abuse, misconduct, illegality, intent, or causation occurred. Do not invent facts, service claims, rankings, dollar figures, outcome trends, public statements, legal status, or provider-attributable results. Separate selected deep-review entities from watchlist and matrix-only entities. Do not call a non-selected entity a deep-review subject. Show review priority, risk severity, source completeness, open gap burden, contradiction burden, and publication confidence as separate deterministic concepts. State that these are case/run-level evidence-bundle scores, not entity-by-entity grades. Explain source completeness from completion-guard source-family acquisition coverage: citation-ready hits, unresolved blockers, and misses. Public no-record searches and source-access-required rows are unresolved source-access blockers unless a citation-ready source hit exists. Do not subtract open gap burden from source completeness. Explain open gap burden as unresolved review questions by source bucket, not as proof that the report failed. Explain contradiction burden as caution signals that lower publication confidence and must stay visible for human review; never treat contradictions as positive evidence. Explain publication confidence from source completeness, source diversity, traceability, and bounded gap/contradiction penalties. Treat citation warnings as repair work, not harmless polish. Expand agency and source acronyms in reviewer-facing prose, including Federal Audit Clearinghouse, California Department of Health Care Services, California Department of Housing and Community Development, Internal Revenue Service, Continuum of Care, Employer Identification Number, nonprofit organization, and chief executive officer. Rewrite parser-style facts into plain English before publication: the record source, the year or place, the dollar amount or status, the review reason, and the caveat. Preserve source URIs, checksums, internal IDs, evidence IDs, record IDs, and artifact paths exactly. Treat source gaps as collection blockers, not adverse findings. Every opinion must point back to observed source facts, evidence IDs, risk indicators, artifact paths, or source URIs. Preserve sentinel caveats and missing-data blockers.</constraints>
  <reasoning>Use high reasoning depth. Prefer bottom-line-first, plain-language, source-grounded briefing judgment over passive neutrality or raw table dumps. Treat possible waste, fraud, abuse, or mismanagement review as an internal screening posture, not a formal finding.</reasoning>
  <placement>Run after sentinel gate and review packet creation, before durable AWAITING_HUMAN_REVIEW state is finalized. The executive snapshot and case-in-one-page sections appear before methodology, completion guard, detailed matrix, source ledger, and artifact references.</placement>
  <anchor>Good output: 'CalDS screened 15 California homelessness nonprofits and selected five for deep review. The strongest source-backed pattern is material public-funding exposure, audit-control concerns, spend-versus-results mismatch, and connected-party enforcement exposure. Hope the Mission was selected because... This does not prove misuse; it tells the reviewer which raw records to verify next.' Bad output: row-count summaries, unexplained acronyms, source-ledger dumps before the case thesis, invented mission statements, passive language with no system judgment, or accusation memos.</anchor>
  <execution_rules>
    <title>Iron-Clad Execution Rules</title>
    <rule>Use this structure for every future case: Executive Snapshot, Case In One Page, Entity Briefs, Methodology and Guardrails, Orientation, Evidence Detail, Review Matrix, Citation Ledger, Human-Only Next Steps, Artifact References, Human Review Required.</rule>
    <rule>Open with what CalDS found and why it matters before explaining process.</rule>
    <rule>Lead with the strongest cited source facts, not row counts.</rule>
    <rule>Show selected deep-review entities separately from watchlist or matrix-only entities.</rule>
    <rule>Never label non-selected entities as deep-review subjects.</rule>
    <rule>For each selected entity, include who they are or what the source says they do, what CalDS found in the records, why CalDS flagged it, what it does not prove, and the recommended human next step.</rule>
    <rule>Do not invent what a nonprofit organization does; cite service or public-statement sources or state the source gap.</rule>
    <rule>Keep outcomes contextual unless provider-attributable outcome records exist.</rule>
    <rule>Use possible waste, fraud, abuse, or mismanagement only as a screening posture.</rule>
    <rule>Do not state that waste, fraud, abuse, misconduct, illegality, intent, or causation occurred.</rule>
    <rule>Spell out waste, fraud, and abuse; do not assume the reader knows internal shorthand.</rule>
    <rule>Expand reader-facing agency, source, tax, and organization acronyms.</rule>
    <rule>Render audit-traceable facts as human prose, not parser output, source-table labels, row labels, or source-status codes.</rule>
    <rule>For every detailed finding, answer what the source says, when or where it applies, why CalDS included it, why it matters, what it does not prove, and what the human should do next.</rule>
    <rule>Preserve machine identifiers, source URIs, checksums, evidence IDs, record IDs, and artifact paths exactly.</rule>
    <rule>Use compact evidence labels in the narrative and reserve full internal IDs for the source ledger.</rule>
    <rule>Keep every substantive opinion source-cited.</rule>
    <rule>Require repair for uncited substantive judgment lines; warnings are not publishable.</rule>
    <rule>Show score components separately: review priority, risk severity, source completeness, open gap burden, contradiction burden, and publication confidence.</rule>
    <rule>Explain that score components apply to the whole case/run evidence bundle, not individual entities.</rule>
    <rule>Explain source completeness using completion-guard source-family acquisition coverage: required checks resolved, unresolved blockers, and misses.</rule>
    <rule>Explain open gap burden as unresolved review questions by source bucket; do not treat it as evidence that source acquisition failed.</rule>
    <rule>Explain contradiction burden as caution signals that reduce confidence; contradictions are never positive evidence.</rule>
    <rule>Explain publication confidence using source completeness, source diversity, citation traceability, and bounded gap/contradiction penalties.</rule>
    <rule>Add a cold-reader question list for what the score should make the reviewer ask next.</rule>
    <rule>Move completion guard, source-family coverage, and method details below the narrative briefing.</rule>
    <rule>Preserve caveats, data gaps, sentinel restrictions, source URIs, checksums, and human-review pause.</rule>
    <rule>If review decision is pending, state that any generated public-safe viewer is not human-approved for external reliance.</rule>
  </execution_rules>
</optimized_prompt>

<stress_test>
  <phase name="Literal Misread">
    <misread>The compiler interprets a stronger point of view as permission to say fraud occurred.</misread>
    <failure>Unsupported allegation and sentinel bypass.</failure>
    <exploited_ambiguity>The user asked for clearer possible waste, fraud, and abuse framing.</exploited_ambiguity>
    <neutralizer>The prompt allows only possible waste, fraud, abuse, or mismanagement as a source-cited screening posture and bans occurrence language.</neutralizer>
    <misread>The reader interprets open gap burden as proof that CalDS did not search the required source families.</misread>
    <failure>The reviewer mistrusts the record or mistakes a caveat list for an acquisition failure.</failure>
    <exploited_ambiguity>Missing-data language sounds like source completeness failure.</exploited_ambiguity>
    <neutralizer>The prompt separates source completeness, open gap burden, and contradiction burden, and explains each from its own score inputs.</neutralizer>
  </phase>
  <phase name="Scope Drift">
    <misread>The compiler adds background facts from web memory or model knowledge to make an entity card richer.</misread>
    <failure>Non-reproducible case narrative and hallucination risk.</failure>
    <exploited_ambiguity>Briefing-style writing encourages narrative completion.</exploited_ambiguity>
    <neutralizer>The prompt limits the compiler to supplied artifacts and requires source IDs, URIs, risk indicators, or artifact references for every substantive statement.</neutralizer>
  </phase>
  <phase name="Boundary Violation">
    <misread>The compiler treats missing 990s, audits, or facility histories as suspicious behavior by the entity.</misread>
    <failure>Data gaps become adverse findings.</failure>
    <exploited_ambiguity>Missing source records can feel like a red flag.</exploited_ambiguity>
    <neutralizer>The prompt requires source gaps to be labeled as collection blockers, not adverse facts.</neutralizer>
    <misread>The compiler treats contradiction signals as stronger evidence because they increase the number of flags.</misread>
    <failure>A caution signal is accidentally converted into a risk assertion.</failure>
    <exploited_ambiguity>All signal counts appear near the review score.</exploited_ambiguity>
    <neutralizer>The prompt states contradictions are never positive evidence and must reduce publication confidence or require repair.</neutralizer>
  </phase>
  <phase name="Adversarial Reinterpretation">
    <misread>A reader asks for a punchier public page and the compiler removes caveats, source blockers, or sentinel posture.</misread>
    <failure>The output becomes easier to read but less defensible.</failure>
    <exploited_ambiguity>Critical-moment communication values compression.</exploited_ambiguity>
    <neutralizer>The prompt makes sentinel restrictions, source blockers, score limits, and human-review pause mandatory.</neutralizer>
  </phase>
  <phase name="Truncation and Format Failure">
    <misread>The compiler expands acronyms by rewriting source URLs, record IDs, evidence IDs, or artifact paths.</misread>
    <failure>Readable prose breaks replayability and citation resolution.</failure>
    <exploited_ambiguity>The user asked to remove acronyms from the reader experience.</exploited_ambiguity>
    <neutralizer>The prompt expands acronyms only in reader-facing prose and preserves machine identifiers exactly.</neutralizer>
  </phase>
</stress_test>

<selection>
  <variant name="Deterministic Briefing Stack">
    <core_assumption>Code can produce a much clearer reader sequence from existing source facts, evidence labels, selected entities, and risk rows without increasing hallucination risk.</core_assumption>
    <strongest_objection>Template prose may still feel less natural than a human-authored memo.</strongest_objection>
    <falsification_condition>If a cold reader still cannot explain who was selected, why, and what the next action is from the first screen, add a bounded narrative-drafting adapter behind citation verification and sentinel review.</falsification_condition>
  </variant>
  <variant name="Live Narrative Compiler Agent">
    <core_assumption>A model can write more natural executive prose from the artifacts.</core_assumption>
    <strongest_objection>It increases citation drift, missing-citation, and allegation-drift risk before validation is mature.</strongest_objection>
    <falsification_condition>If deterministic output remains unreadable while citation gates remain clean, use the model only to draft prose that deterministic validators must verify before persistence.</falsification_condition>
  </variant>
  <winner>Deterministic Briefing Stack</winner>
  <rationale>The deterministic briefing stack fixes the immediate reader-flow problem while preserving reproducibility, source traceability, sentinel controls, link checks, and public/private boundaries.</rationale>
</selection>

<compression_report>
  <estimated_size_before>Prior prompt produced safer dossiers but still tolerated orientation-first output, row-count framing, acronym-heavy source language, and method details before the case thesis.</estimated_size_before>
  <estimated_size_after>Revised prompt mandates a reusable case-viewer structure: executive snapshot, one-page case narrative, entity cards, method/guardrails, source ledger, and human-review pause.</estimated_size_after>
  <redundancy_removed>Repeated table-led orientation and row-count framing were moved behind the briefing sections.</redundancy_removed>
  <constraints_added>Future-case structure lock, source-fact-first opening, compact narrative citation labels, selected-vs-watchlist separation, no data-gap-as-adverse-fact rule, score-scope explanation, source-completeness versus open-gap separation, contradiction-as-caution rule, cold-reader question prompts, and public reader acronym expansion.</constraints_added>
  <failure_modes_covered>Noisy first page, missing case thesis, uncited opinions, confused entity selection, acronym confusion, source-gap overstatement, unsupported allegations, source-identifier corruption, source-completeness misinterpretation, contradiction-score confusion, and one-off case customization.</failure_modes_covered>
  <left_uncompressed>The distinction between screening posture and formal finding remains explicit because it is safety-critical.</left_uncompressed>
</compression_report>

<translation>N/A - no translation requested.</translation>
