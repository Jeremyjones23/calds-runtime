from __future__ import annotations

from pathlib import Path
import argparse
import html
import json
import shutil


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_clean_text(path: Path, text: str) -> None:
    cleaned = "\n".join(line.rstrip() for line in text.splitlines()) + "\n"
    path.write_text(cleaned, encoding="utf-8", newline="\n")


def page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)} | CalDS</title>
  <link rel="stylesheet" href="../styles.css">
</head>
<body>
  <nav class="top-nav" aria-label="Primary navigation">
    <a class="brand" href="../">CalDS</a>
    <div class="nav-links">
      <a href="../#pattern">Pattern</a>
      <a href="../cases/">Cases</a>
      <a href="../#money">Money trail</a>
      <a href="../#sources">Sources</a>
      <a href="../method/">Method</a>
    </div>
  </nav>
  <main class="story-section" style="padding-top: 140px">
    {body}
  </main>
</body>
</html>"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    cases = read_json(args.data_dir / "case-summaries.json")["cases"]
    sources = read_json(args.data_dir / "source-ledger.json")["sources"]

    cases_dir = args.output_dir / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)
    cards = []
    for case in cases:
        original = cases_dir / case["case_id"]
        if original.exists():
            # Keep the original static case file as a deep source room.
            pass
        flags = "".join(f"<li>{esc(flag)}</li>" for flag in case.get("strongest_supported_flags", [])[:4])
        cards.append(
            f"""
            <article class="case-panel">
              <div class="case-panel__header"><p>{esc(case['geography'])}</p><h3>{esc(case['title'])}</h3></div>
              <p class="case-summary">{esc(case['public_summary'])}</p>
              <ul>{flags}</ul>
              <a class="case-link" href="{esc(case['case_id'])}/">Open source-backed case file</a>
            </article>
            """
        )
    write_clean_text(
        cases_dir / "index.html",
        page("Cases", f"<p class=\"section-kicker\">Case map</p><h1>All current CalDS public cases</h1><div class=\"case-accordion\">{''.join(cards)}</div>"),
    )

    method_dir = args.output_dir / "method"
    method_dir.mkdir(exist_ok=True)
    method_body = """
    <p class="section-kicker">Method</p>
    <h1>How CalDS keeps the public story tied to records.</h1>
    <div class="method-grid">
      <article><strong>Claims need records.</strong><p>No public claim ships unless it maps to a claim row and a source record.</p></article>
      <article><strong>Links are checked.</strong><p>Sources must be live, archived, or visibly blocked.</p></article>
      <article><strong>Language is checked.</strong><p>Legal words stay tied to official source status.</p></article>
      <article><strong>Private data stays private.</strong><p>The public app is built from sanitized JSON, not private runs.</p></article>
    </div>
    """
    write_clean_text(method_dir / "index.html", page("Method", method_body))

    sources_dir = args.output_dir / "sources"
    sources_dir.mkdir(exist_ok=True)
    rows = "".join(
        f"<tr><td>{esc(source['case_id'])}</td><td>{esc(source['source_family'])}</td><td>{esc(source['title'])}</td><td>{esc(source['archive_status'])}</td><td>{('<a href=' + esc(source['url']) + ' target=_blank rel=noreferrer>Open source</a>') if source.get('url') else 'Blocked'}</td></tr>"
        for source in sources
    )
    source_body = f"""
    <p class="section-kicker">Source room</p>
    <h1>Public source receipts</h1>
    <div class="source-table-wrap"><table class="source-table"><thead><tr><th>Case</th><th>Source family</th><th>Title</th><th>Status</th><th>Receipt</th></tr></thead><tbody>{rows}</tbody></table></div>
    """
    write_clean_text(sources_dir / "index.html", page("Sources", source_body))

    # Copy shared assets to route folders so relative CSS works for simple static hosting.
    for folder in (cases_dir, method_dir, sources_dir):
        for asset in ("styles.css", "app.js"):
            src = args.output_dir / asset
            if src.exists():
                shutil.copy2(src, folder / asset)
    print("routes=cases,method,sources")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
