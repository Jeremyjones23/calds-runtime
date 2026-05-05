# CalDS Vercel Editorial Case Site Task Sheet

## Purpose

This document is the end-to-end task sheet for rebuilding the CalDS public case viewer as one combined, interactive, editorial investigation site and deploying it on Vercel.

The next site should not feel like three separate review packets. It should read like one public investigation. It should show what CalDS found, why it matters, what the records do and do not prove, and where a reader can check the receipts.

The standard is simple:

CalDS can have a point of view. The facts still need receipts.

## Current Starting Point

The current CalDS repo is `C:\Users\jerem\OneDrive\Documents\CalDS`.

The private runtime currently owns:

- `calds_runtime/`
- `scripts/`
- `tests/`
- `evals/`
- `cases/`
- `data/`
- `runs/`
- generated public output under `site/`

The current public worktree is:

`C:\Users\jerem\OneDrive\Documents\CalDS\artifacts\public-cases-worktree`

The current public cases are:

- `live_ca_homelessness_top15_2026_04_29`
- `live_ca_sf_homelessness_complex`
- `live_ca_recovery_ngos_2026_04_24`

The current publication system already has important safety machinery:

- public citation verification
- link integrity checks
- source blocker reporting
- public safety scan
- phrase blocking for internal parser language
- private runtime / public artifact split
- public source ledgers
- human-review status preservation

The Vercel rebuild must preserve these gates. It should make the public experience stronger without weakening the evidence boundary.

## Core Product Decision

Build a new combined editorial public site, preferably as a Next.js app deployed to Vercel.

Do not make Vercel the investigation runtime.

Vercel should host only sanitized public data and public presentation code. It must not run private ingestion, private agent orchestration, source scraping, model calls, or raw evidence processing.

## Non-Negotiable Boundaries

The private CalDS runtime remains the system of record.

Deterministic CalDS services own:

- source records
- provenance
- evidence IDs
- source URLs
- source blockers
- claim ledgers
- scoring calculations
- link checks
- citation verification
- leak scans
- public artifact generation

The Vercel public app owns:

- public storytelling
- interactive navigation
- public filtering
- public source viewing
- public-safe data display
- accessible and responsive presentation

The Vercel public app must not own:

- raw source ingestion
- private evidence review
- private run traces
- model memory
- legal determinations
- unsupported public claims
- secret-bearing environment variables
- local Windows paths

## Design Plan

The `gpt-taste` design contract was applied for the visual direction. The public site is not a marketing page, so the AIDA structure is adapted into an editorial investigation flow.

```text
Python RNG execution:
seed = 1145
hero = Cinematic Center
font = Outfit
components = Infinite Marquee, Inline Typography Images, Horizontal Accordions
motion = Image Scale & Fade Scroll, Scroll Pinning
```

### AIDA Adaptation

- Navigation: clear, premium top navigation with source and method access.
- Attention: a cinematic editorial opening that names the public problem.
- Interest: interactive case map, pattern cards, and money-trail explorer.
- Desire: pinned evidence narrative, scroll-revealed source receipts, and expandable organization drawers.
- Action: public source room, next-step section, and clear method page.

### Hero Math

The opening headline must use an ultra-wide container equivalent to `max-w-6xl`.

The headline must cap at two or three lines on desktop. On mobile it must remain readable and must not clip.

No stamp icons, fake official badges, cheap labels, or parser language.

### Bento Density

Use a 12-column desktop grid with dense placement.

Every row must fill cleanly. No empty corners. No orphan cards. Mobile collapses into one deliberate reading order.

### Interaction Rule

Motion must help the reader understand the evidence.

Allowed motion:

- pinned story rail
- source-card reveals
- evidence-card stacking
- subtle image scale and fade
- horizontal accordion expansion for case families

Blocked motion:

- decorative motion that hides content
- motion that breaks keyboard navigation
- motion that causes mobile overflow
- motion that implies guilt or dramatizes a case beyond the evidence

## Working Editorial Direction

Working title:

`The California Case File`

Working thesis:

California is sending large amounts of public money through nonprofit service systems. In the cases CalDS has checked so far, the records raise serious questions about money, outcomes, missing oversight records, and public accountability. That does not prove wrongdoing. It does show where the public record deserves a closer look.

The site should sound like a clear briefing to the public, not a government dashboard and not an internal audit packet.

Good public language:

- “Here is what we found.”
- “Here is why it matters.”
- “Here is what the records do not prove.”
- “Here are the documents.”
- “Here is what still needs to be checked.”

Avoid:

- “review packet”
- “workflow state”
- “sentinel”
- “source completeness”
- “risk matrix”
- “low-linkage”
- “row count”
- “parser”
- “source table”
- “WFA”
- unexplained acronyms

## Public Writing Standard

Use Jeremy’s direct, precise, builder-oriented voice, but keep the public reading level close to fifth or sixth grade.

Rules:

- Short sentences.
- Concrete nouns.
- Active verbs.
- One idea per paragraph.
- Explain every acronym the first time.
- Keep caveats near the claim.
- Do not make the reader hunt through a source ledger to understand the point.
- Do not soften the finding into nothing.
- Do not intensify a finding beyond the record.

Example public sentence shapes:

- “California paid money to these groups.”
- “The records do not always show what the public got back.”
- “That does not prove wrongdoing.”
- “It does mean the public should be able to see more.”
- “This is a red flag, not a verdict.”

Legal-language rule:

Words like `fraud`, `abuse`, `criminal`, `illegal`, `convicted`, `violation`, `settlement`, `prosecution`, or `indictment` may appear only when the source supports that exact status. If the site uses “possible fraud, waste, or abuse,” it must define the phrase in plain English:

“Possible fraud, waste, or abuse means the records show a red flag. It does not mean CalDS has proved a crime.”

## Combined Public Site Information Architecture

### 1. Opening Story

Purpose: explain the public problem in one screen.

Must answer:

- What did CalDS look at?
- Why do these cases belong together?
- What pattern showed up?
- What can the reader verify now?

Content:

- one sharp headline
- one plain-language thesis
- three visible public case families
- clear caveat that the site publishes review leads, not legal findings
- buttons for `See the money trail`, `Open the cases`, and `Check the sources`

### 2. The Pattern

Purpose: show why the three cases are one larger oversight story.

Pattern cards:

- public dollars
- official records of problems
- outcomes or service-pressure context
- missing oversight records
- unclear public benefit
- organization-level red flags where supported

Each pattern card must show:

- what we found
- why it matters
- what it does not prove
- source receipt links

### 3. Case Map

Purpose: let the reader move through all cases from one surface.

Each case card must include:

- case name
- short plain-English summary
- issue area
- geography
- organizations named in the public case
- strongest supported red flags
- number of public source links
- number of visible source blockers
- case status
- link to full case section

### 4. Money Trail Explorer

Purpose: make the funding picture visible.

Features:

- timeline by year where data allows
- filter by issue area
- filter by organization
- filter by source family
- public dollar exposure cards
- audit and tax filing source links

Rules:

- No number without a source, calculation note, or blocker.
- Do not merge incompatible funding categories without labeling them.
- Do not imply total statewide spend unless the dataset supports it.
- If a dollar figure is partial, label it as partial.

### 5. What Stood Out

Purpose: editorialized but source-backed finding section.

Every item uses this structure:

- What we found
- Why it matters
- What this does not prove
- Source receipts

The tone should be direct:

“The records raise a serious question.”

Not:

“The records prove wrongdoing.”

### 6. Organization Drawers

Purpose: show each organization in a reader-friendly way.

Each drawer includes:

- who the organization is
- what it says it does
- public money found
- official records found
- source-backed red flags
- records still missing
- what CalDS can and cannot say
- source links

Do not show dense raw tables first. Make the reader understand the case before showing raw source rows.

### 7. Evidence Stack

Purpose: let the reader inspect the receipts.

Each evidence card includes:

- plain-language claim
- entity
- date or period
- source type
- evidence ID
- claim ID
- public URL
- source status
- what the source supports

### 8. Missing Records Ledger

Purpose: keep blockers visible without treating missing records as proof.

Use simple labels:

- “We found this.”
- “We looked for this.”
- “We did not recover this.”
- “A person should request this record.”

Never turn a missing record into an accusation.

### 9. What This Does Not Prove

Purpose: protect trust and legal safety.

This section must be visible, not hidden in a footer.

It should say:

- CalDS is not making a legal finding.
- A red flag is not proof of wrongdoing.
- Some records are missing or blocked.
- Some links may show official records, but readers should still check the source.

### 10. Source Room

Purpose: searchable public source ledger.

Filters:

- case
- organization
- source family
- year
- public URL status
- evidence ID
- claim ID
- source status

Every source row should include:

- source title
- public URL
- source type
- retrieval date
- final URL if redirected
- content type
- checksum when available
- claim IDs supported
- blocker note if not public

### 11. Method

Purpose: explain how CalDS avoids unsupported claims.

Use fifth/sixth-grade language.

Explain:

- CalDS checks public records.
- CalDS links claims to records.
- CalDS checks links.
- CalDS checks for private path leaks.
- CalDS blocks unsupported legal claims.
- CalDS keeps missing records visible.

Do not expose internal implementation jargon.

## Data Contract

Create a deterministic public data export before building the Vercel UI.

Recommended generated files:

```text
artifacts/public-cases-worktree/data/
  public-cases.json
  claim-ledger.json
  source-ledger.json
  case-summaries.json
  entities.json
  money-trail.json
  blockers.json
  verification-manifest.json
```

### `public-cases.json`

Fields:

- `publication_id`
- `generated_at`
- `cases`
- `site_language_level`
- `public_policy`
- `verification_status`

### `case-summaries.json`

Fields per case:

- `case_id`
- `title`
- `short_title`
- `issue_area`
- `geography`
- `public_summary`
- `strongest_supported_flags`
- `what_this_does_not_prove`
- `source_link_count`
- `source_blocker_count`
- `entities`
- `case_url`

### `claim-ledger.json`

Fields per claim:

- `claim_id`
- `public_sentence`
- `plain_language_sentence`
- `claim_type`
- `case_id`
- `entity`
- `source_family`
- `evidence_ids`
- `source_urls`
- `source_excerpt`
- `date_of_source`
- `retrieval_date`
- `confidence`
- `public_language_allowed`
- `legal_language_status`
- `meaning_preservation_status`
- `sentinel_notes`

### `source-ledger.json`

Fields per source:

- `source_id`
- `case_id`
- `evidence_ids`
- `claim_ids`
- `title`
- `source_type`
- `source_family`
- `url`
- `final_url`
- `http_status`
- `content_type`
- `retrieval_date`
- `checksum`
- `archive_status`
- `blocker_reason`

### `entities.json`

Fields per organization:

- `entity_id`
- `display_name`
- `case_ids`
- `issue_area`
- `geography`
- `what_it_claims_to_do`
- `public_money_found`
- `official_records_found`
- `red_flags`
- `caveats`
- `source_ids`

### `money-trail.json`

Fields:

- `case_id`
- `entity_id`
- `year`
- `amount`
- `amount_type`
- `source_id`
- `claim_id`
- `calculation_note`
- `is_partial`
- `missing_records_note`

### `blockers.json`

Fields:

- `blocker_id`
- `case_id`
- `entity`
- `source_family`
- `what_was_sought`
- `why_it_matters`
- `status`
- `next_human_step`

## Claim Ledger Rule

No public sentence about an organization, payment, source, official record, audit, outcome, red flag, or missing record can appear unless it maps to a claim ledger row.

Every claim ledger row must map to:

- one or more evidence IDs, or
- a documented source blocker, or
- a methodology/caveat ID

The public site can be more editorial. It cannot be less traceable.

## Hallucination-Control System

### Before Writing

- Generate the claim ledger from deterministic artifacts.
- Remove stale duplicate records.
- Mark source gaps as blockers.
- Separate official records from press, summaries, and agent synthesis.
- Mark legal-language limits per claim.

### During Writing

- Editorial agents can use only claim IDs and approved source context.
- No new names, dates, dollars, charges, violations, outcomes, or program claims.
- Every paragraph must carry claim IDs internally before render.
- Caveats must stay near the claim.

### After Writing

- Extract public sentences.
- Match each sentence back to claim IDs.
- Fail if any material sentence has no support.
- Fail if rewrite changes meaning.
- Fail if legal status is intensified.
- Fail if missing records are treated as proof.

## Citation Verification

Each citation must pass four checks:

1. Existence: the link resolves or has a safe fallback.
2. Relevance: the cited source contains the fact.
3. Excerpt match: the public sentence matches the retrieved excerpt.
4. Status match: the legal or factual status is not intensified.

If a source says “charged,” the public story cannot say “convicted.”

If a source says “audit finding,” the public story cannot say “fraud.”

If a source says “review,” the public story cannot say “proven.”

## Link Checks

Each public source URL must be checked before deployment.

Store:

- URL
- status code
- final URL after redirect
- content type
- timestamp
- hash if downloaded
- archive or fallback status
- failure reason if blocked

Public link statuses:

- `Live`
- `Archived`
- `Blocked`

No public page deploys with a broken link unless the page shows an archive fallback or clear blocker note.

## Leak Scan

The public output must fail if it contains:

- GitHub tokens
- Vercel tokens
- OpenAI keys
- local Windows paths
- private run directories
- raw model traces
- private agent notes
- unpublished hypotheses
- internal prompt text
- unresolved handoff text
- raw stack traces

Current banned path patterns should include:

- `C:\Users\`
- `runs\`
- `data\live_corpus\`
- `artifacts\` unless intentionally safe and public-facing

## Plain-Language Gate

Public narrative sections should be fifth/sixth-grade readable.

Rules:

- Keep sentences short.
- Avoid acronyms.
- Expand necessary acronyms on first use.
- Replace internal words with public words.
- Use active voice.
- Put the main point before the caveat.
- Keep caveats visible.

Replacement guide:

| Internal phrase | Public phrase |
|---|---|
| source completeness | records we still could not get |
| risk matrix | red flags |
| entity | organization |
| sentinel | legal-language check |
| review packet | public case story |
| workflow state | case status |
| low linkage | weak record link |
| publication confidence | how safe this is to publish |
| source table | records |
| row count | number of records |
| FAC | Federal Audit Clearinghouse |
| WFA | possible fraud, waste, or abuse |

## Visual and Interaction Requirements

### Required Components

- cinematic editorial opening
- combined case map
- gapless pattern-card grid
- money-trail explorer
- horizontal accordions for case families
- organization drawers
- evidence stack
- source receipt viewer
- missing records ledger
- method section
- sticky case compass on desktop
- compact drawer navigation on mobile

### Source and Asset Strategy

Prefer real public-record assets:

- cropped public document screenshots
- audit table excerpts
- grant award page snippets
- source website screenshots with capture metadata
- simple charts generated from verified artifacts
- California map or county outlines

Avoid:

- generic poverty imagery
- random stock photos
- dramatic crime-board visuals
- decorative official-looking badges
- NGO logos as decoration
- images that imply guilt

Every image that represents evidence must have:

- source URL
- capture date
- alt text
- evidence or source ID

## Accessibility Requirements

Every interactive element must work without a mouse.

Required checks:

- keyboard navigation through drawers, accordions, filters, cards, and links
- visible focus states
- WCAG AA color contrast
- no information conveyed by color alone
- reduced-motion mode
- descriptive link labels
- readable chart data in text form
- alt text for evidence images
- skip links or equivalent keyboard path

## Responsive Requirements

Must pass at these widths:

- 320
- 375
- 390
- 430
- 768
- 1024
- 1440

Requirements:

- no horizontal scroll
- no clipped headings
- no hidden source links
- no chart label collisions
- no buttons with unreadable wrapping
- mobile source drawers open cleanly
- long URLs do not break layout
- evidence cards remain readable
- motion is reduced on small screens where needed

## Performance Requirements

- Static-first rendering where possible.
- Build from sanitized JSON.
- Do not parse massive markdown client-side.
- Lazy-load document screenshots.
- Scope GSAP to high-value sections only.
- Avoid animation that blocks reading.
- Keep public JSON payloads reasonably small.
- Split large source ledgers if needed.

## Vercel Architecture

Use Vercel for public presentation only.

Preferred layout in `artifacts/public-cases-worktree`:

```text
artifacts/public-cases-worktree/
  app/
    page.tsx
    cases/
      page.tsx
      [caseId]/
        page.tsx
    sources/
      page.tsx
    method/
      page.tsx
  components/
    CaseCompass.tsx
    CaseMap.tsx
    EvidenceStack.tsx
    EntityDrawer.tsx
    MoneyTrail.tsx
    PatternCards.tsx
    SourceReceiptViewer.tsx
  data/
    public-cases.json
    claim-ledger.json
    source-ledger.json
    case-summaries.json
    entities.json
    money-trail.json
    blockers.json
    verification-manifest.json
  public/
    assets/
  scripts/
    verify-public-data.mjs
    check-readable-copy.mjs
    check-links.mjs
    check-leaks.mjs
    check-claim-coverage.mjs
  package.json
  next.config.ts
  vercel.json
```

For a Next.js Vercel app, do not override `outputDirectory` unless needed. Vercel can auto-detect Next.js.

If deploying a static generated directory instead, use:

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "outputDirectory": "site"
}
```

Vercel documentation confirms that `outputDirectory` can override the deployed output folder and that a prebuilt deployment can use `vercel build` followed by `vercel deploy --prebuilt`.

References:

- https://vercel.com/docs/project-configuration/vercel-json
- https://vercel.com/docs/cli/deploying-from-cli
- https://vercel.com/docs/cli/deploy

## Environment Variables

The public viewer should need no secrets for rendering.

Allowed public variables:

- `NEXT_PUBLIC_SITE_URL`
- `NEXT_PUBLIC_BUILD_ID`
- `NEXT_PUBLIC_PUBLICATION_DATE`
- `NEXT_PUBLIC_SOURCE_POLICY_URL`

CI or deployment variables, if needed:

- `VERCEL_TOKEN`
- `VERCEL_ORG_ID`
- `VERCEL_PROJECT_ID`

These must live in Vercel or CI secrets, not in repo files.

Never expose:

- GitHub tokens
- Vercel tokens
- OpenAI keys
- raw ingestion API keys
- local paths
- private run IDs that expose local structure

## Sub-Agent System

All changed prompts must be run through `master-prompt-builder` before execution.

Each sub-agent must receive a shared context packet and must emit a handoff ledger.

### Shared Context Packet

Every sub-agent receives:

- investigation scope
- public site goal
- current cases included
- target audience
- reading level
- public/private boundary
- allowed language
- blocked language
- claim ledger path
- source ledger path
- evidence IDs
- source URLs
- unresolved blockers
- Vercel deployment target
- acceptance gates
- current task
- expected output

### Handoff Ledger

Every sub-agent emits:

- `handoff_id`
- `agent_role`
- `input_artifacts`
- `output_artifacts`
- `claims_added`
- `claims_revised`
- `claims_blocked`
- `source_ids_used`
- `open_gaps`
- `caveats`
- `next_agent`
- `next_task`
- `gate_status`

No agent should receive only prose. Every handoff must include structured artifacts.

## Required Sub-Agents

### 1. Context Steward

Purpose: prevent context loss.

Responsibilities:

- verify each handoff includes scope, cases, entities, evidence IDs, source URLs, caveats, gaps, and next task
- block incomplete handoffs
- keep one current context packet
- prevent stale case artifacts from entering the public build

### 2. Evidence Steward

Purpose: create the claim ledger.

Responsibilities:

- read deterministic public artifacts
- extract public-safe claims
- map claims to evidence IDs and source URLs
- distinguish facts, comparisons, inferences, gaps, and caveats
- mark public-language limits

### 3. Citation Auditor

Purpose: verify that the sources support the claims.

Responsibilities:

- check link existence
- check excerpt match
- check legal status match
- check dates and dollar figures
- block unsupported claims

### 4. Editorial Story Architect

Purpose: turn cases into one public story.

Responsibilities:

- build the public narrative outline
- decide the order of facts
- show why the cases belong together
- keep the story pointed but source-backed
- use only approved claim IDs

### 5. Plain-Language Editor

Purpose: make the story readable.

Responsibilities:

- rewrite to fifth/sixth-grade level
- remove acronyms or define them
- preserve meaning
- keep caveats visible
- make each section answer “so what?”

### 6. Interaction Designer

Purpose: design the site experience.

Responsibilities:

- create page sections and interaction model
- design mobile behavior
- apply `gpt-taste` rules
- prevent decorative or misleading motion
- define screenshot and accessibility checks

### 7. Frontend Build Agent

Purpose: implement the Vercel public app.

Responsibilities:

- build UI from sanitized JSON
- keep data and presentation separate
- implement accessible interactions
- avoid client-side parsing of huge markdown
- preserve source links and evidence references

### 8. Legal-Language Sentinel

Purpose: block unsupported escalation.

Responsibilities:

- scan for unsupported legal terms
- verify official-source support
- downgrade or block risky claims
- preserve “red flag, not verdict” framing

### 9. Leak Scanner

Purpose: stop private artifacts from reaching public deploy.

Responsibilities:

- scan HTML, JS, JSON, markdown, sourcemaps, logs, and manifests
- block secrets
- block local paths
- block private trace text
- block raw internal notes

### 10. Release Controller

Purpose: block deploy until all gates pass.

Responsibilities:

- run verification suite
- deploy Vercel preview
- verify preview
- promote to production only after preview passes
- verify production URL
- write release notes

## Hardened Master Prompt For Build Agents

Use this prompt family as the baseline. Before final execution, run each role-specific variant through `master-prompt-builder`.

```xml
<role>Bounded CalDS public-site build agent operating inside a governed evidence-first publication workflow.</role>
<context>CalDS is rebuilding its public case viewer into one combined Vercel-hosted editorial investigation site. The private runtime owns truth, provenance, citations, link checks, scoring, source blockers, and safety gates. The public app may render only sanitized data and source-backed public language.</context>
<task>Complete the assigned build stage without weakening evidence boundaries. Use only supplied artifacts, preserve claim-to-source traceability, and emit a handoff ledger for the next agent.</task>
<constraints>Do not invent facts. Do not publish uncited claims. Do not hide source blockers. Do not use unsupported legal conclusions. Do not expose private paths, secrets, raw traces, or internal model notes. Keep public language fifth/sixth-grade readable. Keep UI responsive, accessible, and source-first.</constraints>
<reasoning>Use high reasoning depth. Favor auditability, public clarity, and release safety over speed.</reasoning>
<placement>Run inside the end-to-end Vercel editorial public-site build, after the prior gate has passed and before the next handoff.</placement>
<anchor>Good output: concrete artifact changes, passed gates, clear handoff, no private leaks, no unsupported claims. Bad output: persuasive but uncited story, flashy UI that hides evidence, or deploys without verification.</anchor>
<execution_rules>
  <title>Iron-Clad Execution Rules</title>
  <rule>No public claim without a claim ledger row.</rule>
  <rule>No claim ledger row without evidence or a documented blocker.</rule>
  <rule>No citation without link and excerpt verification.</rule>
  <rule>No plain-language rewrite without meaning-preservation review.</rule>
  <rule>No visual flourish that weakens comprehension or source access.</rule>
  <rule>No agent handoff without scope, artifacts, evidence IDs, caveats, gaps, and next task.</rule>
  <rule>No Vercel production deploy until local, preview, and live verification pass.</rule>
</execution_rules>
```

## End-To-End Implementation Sequence

### Phase 0. Freeze The Goal

Deliverables:

- this task sheet
- agreed public-site objective
- current case list
- current deployment target

Exit gate:

- one canonical task sheet exists in `docs/`

### Phase 1. Inspect The Current Repo

Tasks:

- confirm current runtime repo
- confirm public worktree
- inspect `site/`
- inspect `calds_runtime/publication.py`
- inspect public manifests
- inspect current tests and evals
- confirm Git state
- confirm Vercel project or decide to create one

Exit gate:

- repo map written in implementation notes
- no edits start before repo state is understood

### Phase 2. Choose Build Architecture

Recommended decision:

Build a Next.js public app in `artifacts/public-cases-worktree`.

Alternative:

Build a static generated app from the runtime and deploy `site/` to Vercel.

Decision criteria:

- choose Next.js if interactive filtering and editorial modules are required
- choose static if speed matters and interactions can be vanilla JS

Exit gate:

- architecture decision recorded
- Vercel output path defined
- rollback path defined

### Phase 3. Build Public Data Export

Tasks:

- add deterministic public-data exporter in runtime
- generate combined public case dataset
- generate claim ledger
- generate source ledger
- generate blockers ledger
- generate entity summaries
- generate money-trail data
- generate verification manifest

Exit gate:

- all public JSON files generated
- JSON schema validates
- no private fields are present

### Phase 4. Build Claim Ledger Gate

Tasks:

- create claim ledger schema
- map each public claim to evidence IDs
- map each evidence ID to source URLs or blockers
- add sentence-to-claim verification
- add failure output that shows unsupported sentences

Exit gate:

- every public sentence has claim support or caveat support

### Phase 5. Build Link And Citation Gates

Tasks:

- reuse existing `LinkIntegrityService` where possible
- verify live URLs
- verify redirected URLs
- verify content type
- verify excerpts against public claims
- classify `Live`, `Archived`, or `Blocked`

Exit gate:

- no unsupported citation
- no broken link without visible fallback or blocker

### Phase 6. Build Plain-Language And Meaning Gate

Tasks:

- add readability checker
- add acronym checker
- add banned internal phrase checker
- add meaning-preservation check between claim and public sentence
- create allowed replacement dictionary

Exit gate:

- public narrative passes fifth/sixth-grade target
- no unsupported meaning change
- no unexplained acronym

### Phase 7. Design The Combined Story

Tasks:

- create editorial outline
- choose top-level thesis
- group cases under one public pattern
- define “what stood out”
- define organization drawers
- define money-trail views
- define source-room behavior

Exit gate:

- outline uses only approved claim IDs
- story has a point of view without unsupported accusations

### Phase 8. Implement Frontend Foundation

Tasks:

- create Next.js or selected frontend structure
- configure TypeScript if using Next.js
- add data loading from sanitized JSON
- add base layout
- add navigation
- add global styles
- add responsive shell
- add reduced-motion handling

Exit gate:

- local app runs
- public data loads
- no private data is imported

### Phase 9. Implement Interactive Modules

Tasks:

- build opening story section
- build pattern cards
- build case map
- build money-trail explorer
- build horizontal accordions
- build entity drawers
- build evidence stack
- build source receipt viewer
- build missing records ledger
- build method section

Exit gate:

- all current cases appear in one combined site
- interactions work with keyboard and mouse
- source links are visible

### Phase 10. Add Motion Safely

Tasks:

- add GSAP or equivalent motion only where it improves comprehension
- implement scroll pinning
- implement image scale and fade
- implement source-card reveals
- respect `prefers-reduced-motion`
- test mobile overflow after animation

Exit gate:

- no animation hides evidence
- no horizontal overflow
- reduced motion works

### Phase 11. Add Verification Scripts

Required scripts:

- `verify-public-data`
- `check-claim-coverage`
- `check-citations`
- `check-links`
- `check-leaks`
- `check-readable-copy`
- `check-acronyms`
- `check-banned-phrases`
- `check-mobile-overflow`
- `check-build-output`

Exit gate:

- verification scripts fail on known bad fixtures
- verification scripts pass on current public data

### Phase 12. Browser QA

Desktop widths:

- 1024
- 1280
- 1440
- 1728

Mobile widths:

- 320
- 375
- 390
- 430
- 768

Test:

- home story
- case map
- organization drawer
- source receipt
- source search
- money trail
- keyboard navigation
- reduced motion
- print/save behavior if included

Exit gate:

- screenshots saved
- no visible clipping
- no horizontal overflow
- no console errors

### Phase 13. Local Build Verification

Run:

```powershell
C:\Users\jerem\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m compileall calds_runtime tests scripts
C:\Users\jerem\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest discover -s tests
C:\Users\jerem\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe evals\run_calds_eval.py
npm run build
npm run verify:public
```

Exact Node commands may change after the frontend stack is created.

Exit gate:

- runtime tests pass
- evals pass
- frontend build passes
- public verification passes

### Phase 14. Vercel Preview Deploy

Tasks:

- connect or create Vercel project
- deploy preview from public app root
- inspect build logs
- verify preview URL
- run link and browser checks against preview

Vercel options:

```bash
vercel
```

or controlled prebuilt flow:

```bash
vercel build
vercel deploy --prebuilt
```

Exit gate:

- preview deploy succeeds
- preview content matches local build
- no Vercel build errors
- no preview console errors

### Phase 15. Production Deploy

Tasks:

- promote preview or deploy production
- verify production URL
- check all primary routes
- run leak and phrase scan against live content
- record deployment URL and deployment ID

Production options:

```bash
vercel build --prod
vercel deploy --prebuilt --prod
```

or promote known-good preview when available.

Exit gate:

- production URL returns 200
- live content contains latest build marker
- no private leaks
- all case sections accessible

### Phase 16. GitHub And Release Sync

Tasks:

- commit runtime exporter and verification changes
- commit public frontend app
- push runtime repo if runtime changed
- push public worktree if public app changed
- preserve GitHub Pages as fallback for one release unless explicitly retired
- document Vercel URL in README or publication docs

Exit gate:

- both repos clean
- pushed commits recorded
- release notes written

### Phase 17. Post-Launch Review

Tasks:

- open production site as a cold reader
- confirm first screen says what was found
- confirm source receipts are easy to open
- confirm source blockers are visible
- confirm copy is plain
- confirm legal caveats are clear
- confirm the site feels like one investigation, not three raw outputs

Exit gate:

- post-launch review notes saved
- defects either fixed or explicitly logged

## Deployment Acceptance Checklist

Do not ship production until every item is true:

- all current public cases are included
- site reads as one combined investigation
- every material public sentence maps to a claim ID or caveat ID
- every claim maps to evidence or a blocker
- every source link is live, archived, or visibly blocked
- every number has a source or calculation note
- every legal term passes legal-language review
- every acronym is expanded on first use
- public copy meets fifth/sixth-grade target
- no banned internal phrases appear
- no private local path appears
- no token or secret appears
- source blockers remain visible
- no missing record is treated as proof
- desktop visual QA passes
- mobile visual QA passes
- keyboard navigation passes
- reduced motion passes
- Vercel preview passes
- Vercel production passes
- live production URL is verified after deploy

## Rollback Plan

Keep GitHub Pages live until Vercel has proven stable.

If Vercel production is bad:

1. Do not patch production manually.
2. Roll back to the prior Vercel deployment.
3. If needed, point users to the GitHub Pages fallback.
4. Repair locally.
5. Re-run all gates.
6. Deploy a new preview.
7. Promote only after verification.

## Final Standard

The new site should move the reader because the facts are clear.

It should not ask the reader to trust CalDS.

It should show the records, explain why they matter, name what is missing, and keep the legal line clean.

The public story can say:

“The records raise a serious question.”

It cannot say:

“The records prove wrongdoing.”

That line is the product.
