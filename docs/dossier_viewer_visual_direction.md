# Dossier Viewer Visual Direction

CalDS public case pages should feel like a reviewer has opened a disciplined case room, not a blog post or a raw markdown dump. The interface needs to help a cold reader answer four questions quickly:

- What is this case about?
- What did CalDS flag?
- What source evidence supports the flag?
- What remains blocked before a human can rely on it?

## Reference Direction

- GOV.UK dashboard case study: clear operational dashboards that summarize risk and decision state for public-sector users. https://www.gov.uk/government/case-studies/interactive-dashboards-maps-and-visualisations/
- Africa Data Hub investigative dashboard walkthrough: investigative dashboards should support document review, hypothesis testing, and narrative comprehension without overwhelming the reader. https://www.africadatahub.org/blog/how-to-building-a-dashboard-for-an-investigative-journalism-story
- Overview visual document mining report: investigative document systems work best when they preserve document clusters and original-source drilldown. https://www.cs.ubc.ca/labs/imager/tr/2014/Overview/
- Salt Lake County audit recommendations dashboard: public audit tools need plain status language and next-action framing. https://www.saltlakecounty.gov/auditor/audit-recommendations-dashboard/
- Trove investigative dashboard positioning: investigation tools benefit from one unified surface for entities, documents, relationships, analytics, and source navigation. https://trove.report/

These references are not copied visually. They inform the product direction: dense, serious, source-first, and decision-useful.

## Design System

- Tone: executive case room, public audit desk, evidence ledger.
- Palette: charcoal, oxidized green, docket red, file-folder paper, audit amber.
- Typography: serif display for case framing, mono for evidence, source, and workflow state.
- Layout: command header, gapless status bento, sticky read order, briefing pane, ledger digest, evidence cards.
- Motion: restrained GSAP-enhanced reveal and sticky-card rhythm for readers who allow motion; static fallback for print and reduced-motion users.

## Product Rules

- Human-review state must be visible above the fold.
- Source blockers must be visible, not hidden in the manifest.
- Evidence labels must remain clickable and land on source-ledger cards.
- The public posture must remain review aid, not formal finding.
- No reader-facing parser language, conflict markers, token-like strings, or local file paths may be published.
