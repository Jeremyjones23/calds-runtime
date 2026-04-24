from __future__ import annotations

import sys

MESSAGE = "Full source-table extractor is in the published bootstrap bundle. Run: pwsh scripts/rehydrate_source_bundle.ps1"

if __name__ == "__main__":
    print(MESSAGE, file=sys.stderr)
    raise SystemExit(2)
