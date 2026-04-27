# Public Case Publication Workflow

CalDS can publish a review-ready static case viewer from an existing run without treating the website as the system of record. The workflow keeps the internal dossier, evidence bundle, risk matrix, sentinel decision, and review decision as controlling artifacts, then generates a public-safe copy for sharing.

## Command

```powershell
python -m calds_runtime publish-case-site --run-dir <run-dir> --output-dir <output-dir>
```

For the current live recovery case:

```powershell
python -m calds_runtime publish-case-site --run-dir "C:\Users\jerem\OneDrive\Documents\CalDS-archive\2026-04-25-cleanup-prep\runs\live-outcomes-resume-pipeline-20260424T1855Z\live_ca_recovery_ngos_2026_04_24" --output-dir "C:\Users\jerem\OneDrive\Documents\CalDS\runs\public-case-sites\live_ca_recovery_ngos_2026_04_24"
```

## Generated Files

- `index.html` - static human-readable case viewer.
- `case_dossier.md` - public-safe Markdown copy with local paths removed.
- `case_dossier.json` - public-safe dossier metadata.
- `source_ledger.json` - evidence-label ledger with official source URLs where recovered.
- `publication_manifest.json` - safety gate result and file manifest.

## Safety Gate

The publisher fails closed if:

- a local filesystem path is present in public output,
- a token-like secret is present,
- an evidence label in the dossier lacks a source-ledger target,
- a source-ledger row lacks both an external source URL and an explicit not-linkable note,
- sentinel posture or human-review pause language is missing.

## Citation Behavior

Evidence labels such as `E13` become clickable anchors in `index.html`. Each anchor resolves to a source-ledger card with source type, record ID, checksum, excerpt, and source links.

If the evidence item points directly to an internet URL, the ledger links that URL. If the item is a local parsed artifact, the publisher attempts to extract official upstream URLs from the artifact or infer them from related evidence in the bundle. If no internet source can be recovered, the row is marked `not_externally_linkable` and preserves the internal evidence ID, record ID, source type, checksum, and title for follow-up.

## Hosting Recommendation

Use the generated output as the input to a static host such as GitHub Pages. Do not publish raw downloaded source files in the first pass. Link to official Internal Revenue Service, Federal Audit Clearinghouse, California Department of Health Care Services, county, court, and organization pages instead. Add a hosted evidence cache only after a separate review of licensing, privacy, and file-size implications.

## GitHub Pages Output

For a case that has passed publication review, generate into `site\cases\<case-id>` and update `site\index.html` so GitHub Pages can host it after the repo is pushed:

```powershell
python -m calds_runtime publish-case-site --run-dir <run-dir> --output-dir site\cases\<case-id>
```

The repository includes `.github/workflows/pages.yml`, which deploys the `site/` directory to GitHub Pages on pushes to `main` that touch `site/**` or the Pages workflow.