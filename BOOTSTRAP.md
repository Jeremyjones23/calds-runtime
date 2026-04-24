# Bootstrap Full Source Bundle

The GitHub connector published the complete CalDS source bundle as base64 zip parts under `.github/bootstrap/`.

If GitHub Actions is enabled for the repository, run the `Bootstrap Source Bundle` workflow from the Actions tab. It rehydrates the bundle, expands the source tree, removes the bootstrap parts, and commits the unpacked source.

If running from a clone, use PowerShell:

```powershell
pwsh scripts/rehydrate_source_bundle.ps1
```

This expands `calds-runtime-github-publish.zip` into the repository root. The bundle is source-only and intentionally excludes generated run artifacts, downloaded live corpora, and caches.
