# CalDS Methodology Integrity Audit

Updated: 2026-05-01

## Purpose

This audit records the repo-wide review for logic that could hide evidence gaps, downgrade source-access failures into normal completion, or allow optional shortcuts in live investigative runs.

CalDS must preserve the full picture for state and city users. Missing records, blocked pages, stale URLs, no-result public searches, and secondary sources are not hideable defects. They must remain visible as source-access blockers, repair tasks, or explicit caveats.

## Findings And Repairs

| Area | Risk found | Repair made |
| --- | --- | --- |
| Public source links | Public source rows could pass with old no-public-link language. | Replaced that posture with `source_access_required`; the public manifest now includes a `source_access` report and the viewer marks incomplete source access visibly. |
| Stale public URLs | Earlier publication work could remove broken links after a failed check. | Link removal is not used. Known stale URLs are repaired to verified public source pages and recorded in `link_repair`; unrepaired missing source access remains visible. |
| Completion guard | `searched_no_public_official_record` previously counted as resolved source coverage. | It now remains a source-access blocker unless a citation-ready hit exists. Public no-record searches are preserved, but they are not legal clearance or full coverage. |
| Live recovery pipeline | `--skip-federal-awards` allowed a required Federal Audit Clearinghouse source family to be skipped. | Removed the skip flag from both the pipeline and ingestor. Federal award rows are always attempted. |
| Service-page ingestion | A hardcoded service-page text fallback could substitute prior recovered text when a live fetch failed. | Removed the text fallback. Failed service-page fetches now become `source_access_required` rows with a reviewer action. |
| Provider adapter wording | The local provider boundary used disposable-adapter wording. | Renamed the mode to a deterministic local adapter to avoid implying fake or disposable behavior. |

## Current Methodology Rules

- No source family may be skipped in a live run.
- No failed source fetch may be replaced by hand-entered text and treated as fetched.
- No public no-record search may be treated as clearance.
- No evidence row should be considered complete without a verified public URL or an explicit source-access-required marker.
- No broken URL should be removed as a substitute for repair.
- Deterministic services, not agents, own source-access state, link repair, completion guard blockers, and publication manifests.

## Verification Hooks

- `tests/test_runtime_spine.py::test_live_pipeline_has_no_skip_flags_for_required_source_families`
- `tests/test_runtime_spine.py::test_live_outcome_ingestor_configures_direct_service_pages`
- `tests/test_runtime_spine.py::test_completion_guard_counts_official_no_record_search_as_blocker_not_clearance`
- Public manifests expose `source_access`, `link_repair`, `link_integrity`, and `citation_verification`.
