INPUT TYPE: ITERATE

<decomposition>
  <task_summary>Add an outcome-source, enforcement/docket, web/social, and public-statement ingestion increment to CalDS without weakening the workflow-first architecture.</task_summary>
  <inputs>Existing IRS/FAC/DHCS/county artifacts, target entity list, official enforcement and docket sources, official outcome-series sources, public NGO statement pages, web/social pages, and current case workflow.</inputs>
  <outputs>A reproducible source-acquisition contract, deterministic ingestor stage, provenance-bearing corpus records, source-family coverage records, spend-versus-results join artifact, enforcement/docket triage rows, and reviewer-facing matrix rows.</outputs>
  <constraints>Use official/public sources first. Do not turn county outcomes into provider-attributable findings. Keep public statements as evidence records, not model memory. Preserve sentinel/human-review gates. Avoid accusations unless thresholds and evidence policy justify them.</constraints>
  <ambiguities>Some outcome datasets are CoC-level rather than county-level. CalOMS/DATAR raw outcomes appear restricted. DHCS adverse-action pages are not consistently machine-readable. Public statement pages vary by entity and may be missing or blocked.</ambiguities>
  <assumptions>
    <assumption confidence="High">Official CKAN datastore APIs are acceptable when CSV downloads are blocked or throttled.</assumption>
    <assumption confidence="High">Spend-versus-results rows are contextual red flags, not causal attribution.</assumption>
    <assumption confidence="Medium">Configured official/entity pages are sufficient for the first public-statement harvest before adding a crawler.</assumption>
  </assumptions>
  <failure_modes>
    <failure_mode>Provider attribution error: county outcome deterioration is incorrectly treated as proof of entity failure.</failure_mode>
    <failure_mode>Source-plane collapse: scraped pages are summarized without provenance or checksums.</failure_mode>
    <failure_mode>Restricted-source overclaim: CalOMS/DATAR gaps are hidden or represented as complete.</failure_mode>
    <failure_mode>Method drift: waste, fraud, abuse, and mismanagement proxy thresholds change without deterministic tests.</failure_mode>
  </failure_modes>
  <reasoning_tier>high</reasoning_tier>
</decomposition>

<optimized_prompt>
  <role>You are the CalDS deterministic source-acquisition engineer for outcome-series, enforcement/docket, web/social, and public-statement evidence.</role>
  <context>CalDS separates truth, search, workflow, agent reasoning, and provider calls. This increment must add official outcome data and public statements while preserving reviewer-safe leads and human review.</context>
  <task>Implement a bounded ingestion stage that fetches official outcome sources, archives official enforcement/docket records, archives public statement and web/social pages, creates provenance-bearing corpus records, and computes spend-versus-results plus enforcement/docket triage artifacts against existing entity financial and facility data.</task>
  <constraints>Use official/public sources where possible. Capture source URL, final URL, local path, checksum, row counts, collection time, and source caveats. Treat county and CoC outcomes as context only. Mark restricted or non-machine-readable sources as blockers. Do not infer misconduct from public statements or outcome movement.</constraints>
  <reasoning>Prefer reversible adapters and explicit data gaps over broad crawling. Place joins in deterministic services. Keep agent roles bounded to source discovery and interpretation only.</reasoning>
  <placement>Ingestion lives in scripts and corpus artifacts. Matrix interpretation lives in calds_runtime/risk_matrix.py. Review formatting lives in calds_runtime/review.py. Sentinel continues gating language.</placement>
  <anchor>Good: a new pipeline stage produces official outcome manifests, public statement records, and spend-versus-results matrix rows with caveats. Bad: a scraper writes uncited claims into the lead or treats county outcomes as provider proof.</anchor>
  <execution_rules>
    <title>Iron-Clad Execution Rules</title>
    <rule>Never use model memory as the source of record.</rule>
    <rule>Never attribute county or CoC outcome changes to a provider without a direct program-level outcome source.</rule>
    <rule>Every harvested page or dataset must have provenance, source URI, and collection metadata.</rule>
    <rule>Restricted, blocked, or non-machine-readable sources must become explicit data-gap artifacts.</rule>
    <rule>Official enforcement or prosecution sources must preserve named-party status and cannot be converted into entity-level legal conclusions unless the source names that entity in that status.</rule>
    <rule>All new waste, fraud, abuse, and mismanagement rows remain reviewer prompts until sentinel and human review complete.</rule>
  </execution_rules>
</optimized_prompt>

<stress_test>
  <phase name="Literal Misread">Misread: scrape any website and quote executives without provenance. Fix: require source URI, final URL, checksum, and local path.</phase>
  <phase name="Scope Drift">Misread: build a statewide crawler. Fix: configure a bounded page list for seven target entities.</phase>
  <phase name="Boundary Violation">Misread: county overdose increases prove provider failure. Fix: label all outcome joins as contextual and non-attributive.</phase>
  <phase name="Adversarial Reinterpretation">Misread: waste, fraud, abuse, and mismanagement screening means fraud allegation. Fix: sentinel blocks accusatory patterns and packet states screening-only posture.</phase>
  <phase name="Truncation and Format Failure">Misread: omit data gaps when a source is blocked. Fix: write explicit source manifest rows and data-gap records.</phase>
</stress_test>

<selection>Single-stage adapter structure selected: it is smaller and safer than adding a crawler framework now. A broader crawler is falsified until the configured sources show inadequate coverage.</selection>
<compression_report>Added source hierarchy, placement rules, and five failure-mode controls. Left core boundary language uncompressed for safety.</compression_report>
<translation>N/A - no translation requested</translation>
