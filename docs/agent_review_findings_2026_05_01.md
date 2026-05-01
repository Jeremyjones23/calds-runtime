# CalDS Three-Agent Review Findings - 2026-05-01

Three bounded reviewers inspected the repo and generated public cases: a civic UI/UX reviewer, a forensic workflow reviewer, and a public-sector communications reviewer. The integration pass implemented the highest-value shared findings that improved public reviewer comprehension, citation navigation, link correctness, and source-access honesty.

## Implemented In This Pass

- Public case pages now open as case-specific reviewer dockets instead of generic viewers.
- Hero/status panels now show review priority, evidence count, sentinel posture, public-link status, and completion-guard source blockers.
- `public_link_access` is separated from `source_access`; verified public URLs no longer imply raw-source or completion-guard completion.
- Source-ledger cards now include what each link opens, whether it is exact or upstream, verified-link status, and collapsible audit identifiers.
- A generated source-ledger digest gives reviewers a scan layer before the full evidence cards.
- The public index is generated from case manifests with per-case posture, link status, source-access status, and manifest/source-ledger links.
- Public prose no longer says `Current workflow state: PENDING`; it distinguishes workflow pause from pending human decision.
- Public Markdown/HTML generation removes stale internal-token phrases such as `source_table_`, `[internal local artifact]`, and `no direct evidence ref`.
- Inline URL rendering now avoids malformed `href` values caused by trailing punctuation or URLs inside code spans.
- Accessibility and print/share basics were improved with skip links, visible focus states, evidence-link labels, reduced-motion handling, and a print/save-PDF control.

## Deferred Methodology Work

The forensic reviewer identified deeper runtime changes that should be handled as a focused next increment because they affect scoring, truth links, and acquisition semantics:

- Add a two-tier completion guard: broad top-15 screening coverage for every requested entity, plus deep-source completion checks for selected entities.
- Split state-award coverage into award-list, standard-agreement, payment/draw-ledger, and subrecipient-allocation checks.
- Prevent injected context/source-gap records from increasing relevance or risk scores.
- Add a blocker-aware evidentiary readiness grade separate from risk severity.
- Add provenance types to entity links so aggregate source tables cannot create hard links by co-occurrence alone.
- Tighten citation verification so money/date/legal/status claims require explicit evidence refs even when caveated.
- Add no-paid-credential source families for charity registry, Secretary of State records, county board/contract packet manifests, and public web/archive manifests.

