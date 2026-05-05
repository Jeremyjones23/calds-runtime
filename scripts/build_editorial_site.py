from __future__ import annotations

from pathlib import Path
import argparse
import html
import json
from typing import Any


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def plain_id(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in value.lower()).strip("-")


def first_items(items: list[Any], count: int) -> list[Any]:
    return items[:count] if len(items) > count else items


def write_clean_text(path: Path, text: str) -> None:
    cleaned = "\n".join(line.rstrip() for line in text.splitlines()) + "\n"
    path.write_text(cleaned, encoding="utf-8", newline="\n")


def render_index(data_dir: Path, output_dir: Path) -> str:
    public_cases = read_json(data_dir / "public-cases.json")
    case_summaries = read_json(data_dir / "case-summaries.json")["cases"]
    claims = read_json(data_dir / "claim-ledger.json")
    sources = read_json(data_dir / "source-ledger.json")["sources"]
    entities = read_json(data_dir / "entities.json")["entities"]
    money_rows = read_json(data_dir / "money-trail.json")["money_trail"]
    blockers = read_json(data_dir / "blockers.json")["blockers"]
    verification = read_json(data_dir / "verification-manifest.json")

    claims_by_case: dict[str, list[dict[str, Any]]] = {case["case_id"]: [] for case in case_summaries}
    for claim in claims:
        claims_by_case.setdefault(claim["case_id"], []).append(claim)

    sources_by_case: dict[str, list[dict[str, Any]]] = {case["case_id"]: [] for case in case_summaries}
    for source in sources:
        sources_by_case.setdefault(source["case_id"], []).append(source)

    top_entities = sorted(
        entities,
        key=lambda item: len(item.get("red_flags", [])) + len(item.get("official_records_found", [])) + len(item.get("public_money_found", [])),
        reverse=True,
    )[:18]

    total_sources = len(sources)
    live_sources = sum(1 for source in sources if source.get("archive_status") == "Live")
    total_claims = len(claims)
    source_blockers = sum(int(case.get("source_blocker_count", 0) or 0) for case in case_summaries)
    build_marker = esc(public_cases.get("publication_id", "editorial-build"))

    case_cards = []
    for case in case_summaries:
        case_claims = claims_by_case.get(case["case_id"], [])
        case_sources = sources_by_case.get(case["case_id"], [])
        flags = "".join(f"<li>{esc(flag)}</li>" for flag in first_items(case.get("strongest_supported_flags", []), 3))
        caveats = "".join(f"<li>{esc(caveat)}</li>" for caveat in first_items(case.get("what_this_does_not_prove", []), 3))
        case_cards.append(
            f"""
            <article class="case-panel" id="{esc(case['case_id'])}" data-case="{esc(case['case_id'])}" data-area="{esc(case['issue_area'])}">
              <div class="case-panel__header">
                <p>{esc(case['geography'])} / {esc(case['issue_area'])}</p>
                <h3>{esc(case['title'])}</h3>
              </div>
              <p class="case-summary">{esc(case['public_summary'])}</p>
              <div class="case-stats">
                <span><strong>{len(case.get('entities', []))}</strong> organizations</span>
                <span><strong>{len(case_claims)}</strong> claims</span>
                <span><strong>{len(case_sources)}</strong> sources</span>
                <span><strong>{esc(case.get('source_blocker_count', 0))}</strong> records still needed</span>
              </div>
              <details class="case-detail">
                <summary>What stood out</summary>
                <ul>{flags}</ul>
              </details>
              <details class="case-detail">
                <summary>What this does not prove</summary>
                <ul>{caveats}</ul>
              </details>
              <a class="case-link" href="cases/{esc(case['case_id'])}/">Open original case file</a>
            </article>
            """
        )

    entity_cards = []
    for entity in top_entities:
        flags = first_items(entity.get("red_flags", []) + entity.get("official_records_found", []) + entity.get("public_money_found", []), 3)
        flag_html = "".join(f"<li>{esc(flag)}</li>" for flag in flags)
        caveats = "".join(f"<li>{esc(caveat)}</li>" for caveat in first_items(entity.get("caveats", []), 2))
        entity_cards.append(
            f"""
            <details class="entity-card" data-entity="{esc(entity['display_name'])}">
              <summary>
                <span>{esc(entity['display_name'])}</span>
                <small>{len(entity.get('case_ids', []))} case link(s)</small>
              </summary>
              <div class="entity-card__body">
                <p>{esc(entity.get('what_it_claims_to_do', 'CalDS publishes only source-backed descriptions.'))}</p>
                <h4>Records CalDS found</h4>
                <ul>{flag_html or '<li>No high-priority public sentence was exported for this organization.</li>'}</ul>
                <h4>What this does not prove</h4>
                <ul>{caveats or '<li>This does not prove wrongdoing. It marks records that deserve review.</li>'}</ul>
              </div>
            </details>
            """
        )

    money_cards = []
    for row in first_items(money_rows, 18):
        money_cards.append(
            f"""
            <article class="money-card" data-case="{esc(row['case_id'])}">
              <strong>{esc(row['amount'])}</strong>
              <span>{esc(row.get('year') or 'year not stated')}</span>
              <p>{esc(row['amount_type'])}</p>
              <button class="source-jump" data-source="{esc(row['source_id'])}">Open source receipt</button>
            </article>
            """
        )

    evidence_cards = []
    for claim in first_items(claims, 36):
        evidence_cards.append(
            f"""
            <article class="evidence-card" data-case="{esc(claim['case_id'])}" data-claim="{esc(claim['claim_id'])}">
              <p class="evidence-card__type">{esc(claim['claim_type'])} / {esc(claim['source_family'])}</p>
              <h3>{esc(claim['plain_language_sentence'])}</h3>
              <p><strong>Why it matters:</strong> This is a source-backed red flag or caveat. It is not a verdict.</p>
              <p><strong>What it does not prove:</strong> It does not prove wrongdoing unless the cited official source says so.</p>
              <div class="evidence-card__refs">
                <span>{esc(', '.join(ref for ref in claim.get('evidence_ids', []) if ref))}</span>
                <span>{esc(claim['legal_language_status'])}</span>
              </div>
            </article>
            """
        )

    source_rows = []
    for source in sources:
        url = source.get("url") or ""
        link = f'<a href="{esc(url)}" target="_blank" rel="noreferrer">Open source</a>' if url else "<span>Blocked</span>"
        source_rows.append(
            f"""
            <tr data-source-id="{esc(source['source_id'])}" data-case="{esc(source['case_id'])}">
              <td>{esc(source['case_id'])}</td>
              <td>{esc(source['source_family'])}</td>
              <td>{esc(source['title'])}</td>
              <td>{esc(source['archive_status'])}</td>
              <td>{link}</td>
            </tr>
            """
        )

    source_options = "".join(f'<option value="{esc(case["case_id"])}">{esc(case["short_title"])}</option>' for case in case_summaries)
    manifest_rows = "".join(
        f"<li>{esc(item['case_id'])}: citations {esc(item['citation_status'])}, links {esc(item['link_status'])}, safety {esc(item['safety_passed'])}, records still needed {esc(item['source_blocker_count'])}</li>"
        for item in verification.get("case_manifest_status", [])
    )

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="calds-build" content="{build_marker}">
  <title>The California Case File | CalDS</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&family=Fraunces:opsz,wght@9..144,600;9..144,800&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <a class="skip-link" href="#story">Skip to story</a>
  <nav class="top-nav" aria-label="Primary navigation">
    <a class="brand" href="#top">CalDS</a>
    <div class="nav-links">
      <a href="#pattern">Pattern</a>
      <a href="#cases">Cases</a>
      <a href="#money">Money trail</a>
      <a href="#sources">Sources</a>
      <a href="#method">Method</a>
    </div>
  </nav>

  <main id="top">
    <header class="hero" id="story">
      <div class="hero__inner">
        <p class="eyebrow">The California Case File</p>
        <h1><span>Public money</span><span>moved.</span><span>What came back?</span></h1>
        <p class="hero-copy">{esc(public_cases['dek'])}</p>
        <div class="hero-actions">
          <a href="#money">See the money trail</a>
          <a href="#cases">Open the cases</a>
          <a href="#sources">Check the sources</a>
        </div>
        <div class="hero-ledger" aria-label="Publication status">
          <div><span>{len(case_summaries)}</span><p>case families</p></div>
          <div><span>{total_claims}</span><p>source-backed public claims</p></div>
          <div><span>{live_sources}/{total_sources}</span><p>live source receipts</p></div>
          <div><span>{source_blockers}</span><p>records still needed</p></div>
        </div>
      </div>
    </header>

    <section class="story-section" id="pattern">
      <div class="section-kicker">The pattern</div>
      <div class="split">
        <div>
          <h2>More public money. More pressure. Not enough easy answers.</h2>
          <p>CalDS checked public records across homelessness, recovery, and treatment nonprofit cases. The same problem kept showing up: money and public outcomes are hard to connect in a clean way.</p>
          <p>That does not prove wrongdoing. It does mean the public should be able to see more.</p>
        </div>
        <div class="pattern-grid">
          <article><strong>Money trail</strong><p>Dollar figures stay tied to source records or a visible gap.</p></article>
          <article><strong>Official records</strong><p>Audit findings, charges, and violations keep their exact source status.</p></article>
          <article><strong>Missing records</strong><p>Missing records stay visible. They are not treated as proof.</p></article>
          <article><strong>Plain language</strong><p>The public story avoids internal terms and explains the limits.</p></article>
        </div>
      </div>
    </section>

    <section class="story-section" id="cases">
      <div class="section-kicker">Case map</div>
      <h2>Three case families, one oversight story.</h2>
      <div class="case-accordion" role="list">
        {''.join(case_cards)}
      </div>
    </section>

    <section class="story-section pinned-section" id="money">
      <div class="pin-copy">
        <div class="section-kicker">Money trail</div>
        <h2>Every number needs a receipt.</h2>
        <p>These cards show dollar figures that were exported from cited public records. Some figures are partial. A partial figure is not a total.</p>
        <label for="caseFilter">Filter by case</label>
        <select id="caseFilter">
          <option value="all">All cases</option>
          {source_options}
        </select>
      </div>
      <div class="money-grid">
        {''.join(money_cards)}
      </div>
    </section>

    <section class="story-section" id="entities">
      <div class="section-kicker">Organizations</div>
      <h2>Open an organization to see the red flags and limits.</h2>
      <div class="entity-grid">
        {''.join(entity_cards)}
      </div>
    </section>

    <section class="story-section dark-section" id="evidence">
      <div class="section-kicker">Evidence stack</div>
      <h2>What CalDS found, one source-backed claim at a time.</h2>
      <div class="evidence-stack">
        {''.join(evidence_cards)}
      </div>
    </section>

    <section class="story-section" id="limits">
      <div class="section-kicker">What this does not prove</div>
      <div class="split">
        <div>
          <h2>A red flag is not a verdict.</h2>
          <p>CalDS is not making a legal finding. The site shows records that deserve review. Some records are still missing. Missing records do not prove wrongdoing.</p>
        </div>
        <aside class="definition-card">
          <h3>Possible fraud, waste, or abuse</h3>
          <p>Possible fraud, waste, or abuse means the records show a red flag. It does not mean CalDS has proved a crime.</p>
        </aside>
      </div>
    </section>

    <section class="story-section" id="sources">
      <div class="section-kicker">Source room</div>
      <h2>Check the receipts.</h2>
      <p>Every source row connects back to an evidence record and a public claim. Live links open in a new tab. Blocked rows explain what still needs to be recovered.</p>
      <input id="sourceSearch" class="source-search" type="search" placeholder="Search sources, cases, organizations, or record types" aria-label="Search sources">
      <div class="source-table-wrap">
        <table class="source-table">
          <thead><tr><th>Case</th><th>Source family</th><th>Title</th><th>Status</th><th>Receipt</th></tr></thead>
          <tbody>{''.join(source_rows)}</tbody>
        </table>
      </div>
    </section>

    <section class="story-section" id="method">
      <div class="section-kicker">Method</div>
      <h2>How CalDS keeps the public story tied to records.</h2>
      <div class="method-grid">
        <article><strong>Claims need records.</strong><p>No public claim ships unless it maps to a claim row and a source record.</p></article>
        <article><strong>Links are checked.</strong><p>Sources must be live, archived, or visibly blocked.</p></article>
        <article><strong>Language is checked.</strong><p>Legal words stay tied to official source status.</p></article>
        <article><strong>Private data stays private.</strong><p>The public app is built from sanitized JSON, not private runs.</p></article>
      </div>
      <details class="gate-detail">
        <summary>Publication gates for this build</summary>
        <ul>{manifest_rows}</ul>
      </details>
    </section>
  </main>

  <footer class="site-footer">
    <p>CalDS publishes source-backed review leads, not legal findings.</p>
    <a href="#top">Back to top</a>
  </footer>

  <script src="app.js"></script>
</body>
</html>"""
    output_dir.mkdir(parents=True, exist_ok=True)
    write_clean_text(output_dir / "index.html", html_doc)
    return html_doc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    render_index(args.data_dir, args.output_dir)
    print(f"index_html={args.output_dir / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
