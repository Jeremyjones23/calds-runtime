INPUT TYPE: NEW

<decomposition>
  <task_summary>Create a bounded public-case publisher prompt for CalDS that turns an existing internal run into a public-safe static case viewer without changing the system of record.</task_summary>
  <inputs>Existing run directory, compiled case dossier, evidence bundle, source ledger candidates, sentinel result, review decision, and output directory.</inputs>
  <outputs>Static HTML case viewer, public-safe Markdown dossier, public-safe dossier metadata JSON, source ledger JSON, and publication manifest with safety gate result.</outputs>
  <constraints>Use only existing run artifacts. Do not add facts or allegations. Do not publish local filesystem paths, secrets, raw source caches, or private artifact paths. Preserve evidence IDs, record IDs, checksums, sentinel posture, and human-review pause. Every evidence label must resolve to a source-ledger card. Every source-ledger row must contain either an internet source URL or an explicit not-externally-linkable note. Public-facing prose must be readable to a nontechnical reviewer and must not expose parser labels, source-table labels, raw source-status codes, or unexplained workflow mechanics. A generated public-safe site is a reviewable export; it is not a human-approved external publication unless a separate publication approval artifact says so.</constraints>
  <ambiguities>Sharing can mean a public internet page or controlled internal sharing. The conservative executable interpretation is a public-safe static export that can be hosted later, with a fail-closed safety gate before publication.</ambiguities>
  <assumptions>
    <assumption confidence="High">The public site is a presentation adapter, not the canonical record.</assumption>
    <assumption confidence="High">Official source URLs are preferred over hosting raw downloaded copies.</assumption>
    <assumption confidence="High">Local Windows paths must not appear in public artifacts.</assumption>
    <assumption confidence="Medium">GitHub Pages or another static host will consume the generated output after review.</assumption>
  </assumptions>
  <failure_modes>
    <failure_mode>The publisher leaks local filesystem paths or private archive structure.</failure_mode>
    <failure_mode>The publisher turns internal screening language into public accusations.</failure_mode>
    <failure_mode>Evidence labels appear in the dossier but do not link to source cards.</failure_mode>
    <failure_mode>Parsed local artifacts are presented as internet-linked sources when no official URL was recovered.</failure_mode>
    <failure_mode>The generated site omits sentinel posture or human-review pause language.</failure_mode>
    <failure_mode>The publisher preserves technically accurate dossier text that still reads like database output instead of a case briefing.</failure_mode>
  </failure_modes>
  <reasoning_tier>high</reasoning_tier>
</decomposition>

<optimized_prompt>
  <role>Public Case Publisher for CalDS, operating as a deterministic publication adapter after case compilation and before external sharing.</role>
  <context>CalDS is an evidence-first workflow system. Deterministic services own canonical records, provenance, scoring inputs, source ledgers, reviewer artifacts, sentinel posture, and human-review state. The public publisher receives existing artifacts only and prepares a static viewer for human sharing.</context>
<task>Generate a public-safe case site from an existing CalDS run. Produce index.html, case_dossier.md, case_dossier.json, source_ledger.json, and publication_manifest.json. Make each evidence label clickable, link to verified official internet sources where recovered, repair stale public URLs to working source pages where deterministic repair is possible, and mark any still-unrecovered source as source-access-required. Preserve whether the export is a pending-review preview or a separately approved external publication.</task>
  <constraints>Use only supplied artifacts. Do not add facts, infer wrongdoing, or rewrite the risk posture. Do not publish local paths, raw downloaded source caches, secrets, or private archive paths. Preserve evidence IDs, record IDs, checksums, sentinel decision, caveats, and human-review pause. Do not claim an internet citation exists unless an actual URL is present. Every public source-ledger row must contain source URLs or an explicit not-linkable note. Reader-facing case sections must retain the compiled plain-English briefing style; if raw parser labels, source-table labels, source-status codes, or workflow mechanics appear in prose, fail the export for repair. If the review decision is PENDING, the viewer must say it is pending human review and not approved for external reliance.</constraints>
  <reasoning>Use high reasoning depth. Prefer auditability, deterministic replay, and citation integrity over visual polish. Treat the public site as a controlled presentation layer, not the system of record.</reasoning>
  <placement>Run after compile-dossier and before GitHub Pages, static hosting, email sharing, or any outside-facing use.</placement>
  <anchor>Good output: a static viewer where E13 links to a source-ledger card, official source URLs are clickable, local paths are removed, and the manifest says safety passed. Bad output: a copied Markdown file with local C:\ paths, broken evidence labels, implied allegations, or unmarked local parsed artifacts.</anchor>
  <execution_rules>
    <title>Iron-Clad Execution Rules</title>
    <rule>Use existing artifacts only.</rule>
    <rule>Do not publish local filesystem paths or secrets.</rule>
    <rule>Make every evidence label resolve to a source-ledger target.</rule>
    <rule>Use official internet source URLs where recovered.</rule>
<rule>Mark unrecovered external sources as source-access-required instead of pretending they are cited online; missing source access is never completion.</rule>
    <rule>Fail closed if reader-facing sections contain parser output, source-table labels, unexplained status codes, or technical shorthand.</rule>
    <rule>Preserve sentinel posture, caveats, checksums, record IDs, and human-review pause.</rule>
    <rule>Distinguish a public-safe preview/export from a human-approved external publication.</rule>
    <rule>Fail closed when the safety gate detects path leakage, missing evidence targets, missing source notes, or missing review posture.</rule>
  </execution_rules>
</optimized_prompt>

<stress_test>
  <phase name="Literal Misread">
    <misread>The publisher treats public sharing as permission to remove caveats and make a stronger case.</misread>
    <failure>The public site becomes an accusation memo.</failure>
    <exploited_ambiguity>Sharing can imply advocacy or persuasion.</exploited_ambiguity>
    <neutralizer>The prompt states that the publisher cannot add facts, infer wrongdoing, or rewrite risk posture.</neutralizer>
  </phase>
  <phase name="Scope Drift">
    <misread>The publisher downloads and rehosts every raw filing and source document.</misread>
    <failure>The export creates licensing, privacy, and storage risk.</failure>
    <exploited_ambiguity>Hosting documents online could mean hosting all evidence.</exploited_ambiguity>
    <neutralizer>The prompt prefers official source URLs and forbids raw source-cache publication in this stage.</neutralizer>
  </phase>
  <phase name="Boundary Violation">
    <misread>The publisher rewrites evidence IDs or checksums for cleaner display.</misread>
    <failure>Traceability breaks between public viewer and internal artifacts.</failure>
    <exploited_ambiguity>Presentation cleanup can mutate machine identifiers.</exploited_ambiguity>
    <neutralizer>The prompt requires preserving evidence IDs, record IDs, and checksums.</neutralizer>
  </phase>
  <phase name="Adversarial Reinterpretation">
    <misread>A local parsed artifact is displayed as source-cited even though no external URL was recovered.</misread>
    <failure>The public citation overstates source availability.</failure>
    <exploited_ambiguity>Parsed artifacts may be derived from official sources but not themselves public URLs.</exploited_ambiguity>
    <neutralizer>The prompt requires either actual source URLs or an explicit not-externally-linkable note.</neutralizer>
  </phase>
  <phase name="Truncation and Format Failure">
    <misread>The publisher creates the HTML page but omits JSON ledgers or the safety manifest.</misread>
    <failure>The site is readable but not auditable or repeatable.</failure>
    <exploited_ambiguity>Static viewer can sound like a single-file deliverable.</exploited_ambiguity>
    <neutralizer>The prompt requires index.html, case_dossier.md, case_dossier.json, source_ledger.json, and publication_manifest.json.</neutralizer>
  </phase>
</stress_test>

<selection>
  <variant name="Static Publication Adapter">
    <core_assumption>Deterministic code can create a safe public viewer from existing artifacts while preserving audit boundaries.</core_assumption>
    <strongest_objection>It is less interactive than a full web application.</strongest_objection>
    <falsification_condition>If reviewers need authentication, comments, workflow actions, or dynamic evidence filtering, move to an authenticated review portal.</falsification_condition>
  </variant>
  <variant name="Authenticated Review Portal">
    <core_assumption>Controlled sharing and workflow actions should live in an app with identity, permissions, and audit logs.</core_assumption>
    <strongest_objection>It is heavier than needed for immediate sharing and would delay the first publication-safe artifact.</strongest_objection>
    <falsification_condition>If the static viewer cannot meet stakeholder review needs without data leakage or manual side channels, build the portal next.</falsification_condition>
  </variant>
  <winner>Static Publication Adapter</winner>
  <rationale>It preserves the current architecture, creates shareable artifacts immediately, and leaves authenticated workflow as a later increment.</rationale>
</selection>

<compression_report>
  <estimated_size_before>Loose request to host documents online or link source citations.</estimated_size_before>
  <estimated_size_after>Bounded publication adapter prompt with explicit artifacts, safety gate, source-linking rules, and traceability preservation.</estimated_size_after>
  <redundancy_removed>Combined hosting, citation-linking, and publication-safety requirements into one deterministic adapter role.</redundancy_removed>
  <constraints_added>No local paths, no secrets, no raw source cache, evidence-label resolution, source URL or not-linkable note, sentinel and human-review preservation.</constraints_added>
  <failure_modes_covered>Path leakage, accusation drift, broken evidence links, false online citations, missing safety manifest, and audit-trail loss.</failure_modes_covered>
  <left_uncompressed>Fail-closed publication requirements remain explicit because sharing is high-risk.</left_uncompressed>
</compression_report>

<translation>N/A - no translation requested.</translation>
