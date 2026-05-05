from __future__ import annotations

from pathlib import Path
import argparse
import html
import json
import re
import shutil
from typing import Any

from build_editorial_site import (
    case_status,
    case_visual,
    clean_public_summary,
    compact_sentence,
    esc,
    head,
    is_mechanical_public_sentence,
    make_nav,
    public_entity_description,
    public_signal_items,
    render_amount,
    top_claims_for_case,
    write_clean_text,
)


STALE_PUBLIC_FILES = {
    "case_dossier.json",
    "case_dossier.md",
    "publication_manifest.json",
    "source_ledger.json",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def prune_stale_case_exports(cases_dir: Path) -> None:
    if not cases_dir.exists():
        return
    for child in cases_dir.iterdir():
        if not child.is_dir():
            continue
        for name in STALE_PUBLIC_FILES:
            path = child / name
            if path.exists():
                path.unlink()


def page(title: str, body: str, prefix: str = "../", body_class: str = "route-page") -> str:
    return f"""{head(title, f"{prefix}styles.css")}
<body class="{esc(body_class)}">
{make_nav(prefix)}
  <main id="main" class="story-route">
    {body}
  </main>
  <script src="{prefix}app.js"></script>
</body>
</html>"""


def source_link(source: dict[str, Any]) -> str:
    url = source.get("url") or ""
    if url:
        return f'<a href="{esc(url)}" target="_blank" rel="noreferrer">Open source</a>'
    return "<span>Record still needed</span>"


def render_claim_cards(claims: list[dict[str, Any]], source_by_claim: dict[str, dict[str, Any]]) -> str:
    cards = []
    for claim in claims:
        source = source_by_claim.get(claim.get("claim_id"), {})
        card_link = source_link(source) if source else "<span>Source listed in ledger</span>"
        cards.append(
            f"""
            <article class="finding-card">
              <p>{esc(claim.get('entity') or 'Case record')}</p>
              <h3>{esc(compact_sentence(claim.get('plain_language_sentence') or claim.get('public_sentence'), 220))}</h3>
              <div class="finding-card__meta">
                <span>{esc(compact_sentence(claim.get('source_family') or source.get('source_family') or 'Public record', 80))}</span>
                {card_link}
              </div>
            </article>
            """
        )
    return "".join(cards)


def render_case_page(
    case: dict[str, Any],
    claims: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    entities: list[dict[str, Any]],
    money_rows: list[dict[str, Any]],
    output_dir: Path,
) -> None:
    case_id = case["case_id"]
    visual = case_visual(case_id)
    case_claims = top_claims_for_case(claims, case_id, 7)
    case_sources = [source for source in sources if source.get("case_id") == case_id]
    source_by_id = {source["source_id"]: source for source in case_sources}
    source_by_claim = {
        claim_id: source
        for source in case_sources
        for claim_id in source.get("claim_ids", [])
    }
    case_entities = [entity for entity in entities if case_id in entity.get("case_ids", [])]
    case_money = [row for row in money_rows if row.get("case_id") == case_id]

    found_rows = []
    for claim in case_claims[:4]:
        found_rows.append(
            f"""
            <li>
              <b>{esc(claim.get('entity') or 'Case record')}</b>
              <span>{esc(compact_sentence(claim.get('plain_language_sentence') or claim.get('public_sentence'), 240))}</span>
            </li>
            """
        )

    money_cards = []
    for row in case_money[:8]:
        source = source_by_id.get(row.get("source_id"), {})
        amount = render_amount(str(row.get("amount", "")), str(source.get("supports", "")))
        money_cards.append(
            f"""
            <article class="mini-receipt">
              <span>{esc(amount)}</span>
              <p>{esc(compact_sentence(source.get('title') or row.get('amount_type'), 120))}</p>
              {source_link(source)}
            </article>
            """
        )

    entity_cards = []
    for entity in case_entities[:12]:
        signals = public_signal_items(entity, 3)
        entity_cards.append(
            f"""
            <details class="entity-folder case-entity">
              <summary><span>{esc(entity['display_name'])}</span><small>{len(entity.get('source_ids', []))} receipts</small></summary>
              <div>
                <p>{esc(public_entity_description(entity.get('what_it_claims_to_do')))}</p>
                <ul>{''.join(f'<li>{esc(signal)}</li>' for signal in signals) or '<li>No public red-flag sentence was exported for this organization.</li>'}</ul>
              </div>
            </details>
            """
        )

    source_rows = "".join(
        f"""
        <tr data-source-id="{esc(source['source_id'])}">
          <td>{esc(source.get('source_family'))}</td>
          <td>{esc(compact_sentence(source.get('title'), 120))}</td>
          <td>{esc(source.get('archive_status'))}</td>
          <td>{source_link(source)}</td>
        </tr>
        """
        for source in case_sources
    )

    body = f"""
    <header class="case-hero" style="--case-color:{esc(visual['ink'])}">
      <div class="case-hero__art tone-{esc(visual['tone'])}" aria-hidden="true"></div>
      <div class="case-hero__copy">
        <p class="type-stamp">{esc(case.get('geography'))} / {esc(case.get('issue_area'))}</p>
        <h1>{esc(case.get('title'))}</h1>
        <p>{esc(clean_public_summary(case))}</p>
        <div class="case-hero__status">
          <span>Red flag, not a verdict</span>
          <span>{esc(case_status(case))}</span>
          <span>{len(case_sources)} public receipts</span>
        </div>
      </div>
    </header>

    <section class="story-brief">
      <div>
        <p class="type-stamp">Briefing</p>
        <h2>What CalDS found</h2>
      </div>
      <ul class="found-list">{''.join(found_rows) or '<li><b>Records found</b><span>No public claim cards were exported for this case.</span></li>'}</ul>
    </section>

    <section class="case-money">
      <div class="chapter-copy">
        <p class="type-stamp">Money trail</p>
        <h2>Dollar amounts named in public records.</h2>
        <p>These amounts are partial unless the source itself says it is a full total.</p>
      </div>
      <div class="mini-receipt-grid">{''.join(money_cards) or '<p class="empty-money is-visible">No dollar rows were exported for this case yet.</p>'}</div>
    </section>

    <section class="case-findings">
      <div class="chapter-copy">
        <p class="type-stamp">Why this was selected</p>
        <h2>The records point to questions, not final answers.</h2>
        <p>CalDS selected these organizations for closer human review because public records show money exposure, official record signals, missing oversight records, or outcome questions.</p>
      </div>
      <div class="finding-stack">{render_claim_cards(case_claims, source_by_claim)}</div>
    </section>

    <section class="case-entities">
      <div class="chapter-copy">
        <p class="type-stamp">Organizations named in the run</p>
        <h2>Open a folder before you form an opinion.</h2>
      </div>
      <div class="folder-grid">{''.join(entity_cards)}</div>
    </section>

    <section class="source-room case-source-room">
      <div class="source-room__intro">
        <p class="type-stamp">Receipts</p>
        <h2>Check the records yourself.</h2>
        <p>The source list is public. Missing records are shown as records still needed, not as proof.</p>
      </div>
      <div class="source-cabinet">
        <table class="source-table">
          <thead><tr><th>Record type</th><th>Title</th><th>Status</th><th>Receipt</th></tr></thead>
          <tbody>{source_rows}</tbody>
        </table>
      </div>
    </section>

    <section class="method-wall case-caveat">
      <p class="type-stamp">What this does not prove</p>
      <h2>This page does not decide guilt, intent, or legal liability.</h2>
      <p>It shows public records that deserve human review. A stronger conclusion would require the missing contracts, invoices, monitoring letters, outcome records, and official findings listed in the sources.</p>
      <a class="paper-link" href="../../sources/">Open all sources</a>
    </section>
    """
    write_clean_text(output_dir / "cases" / case_id / "index.html", page(case.get("short_title") or case.get("title"), body, "../../", "case-page"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    cases = read_json(args.data_dir / "case-summaries.json")["cases"]
    claims = read_json(args.data_dir / "claim-ledger.json")
    sources = read_json(args.data_dir / "source-ledger.json")["sources"]
    entities = read_json(args.data_dir / "entities.json")["entities"]
    money_rows = read_json(args.data_dir / "money-trail.json")["money_trail"]

    cases_dir = args.output_dir / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)
    prune_stale_case_exports(cases_dir)

    cards = []
    for case in cases:
        visual = case_visual(case["case_id"])
        cards.append(
            f"""
            <article class="case-panel" style="--case-color:{esc(visual['ink'])}">
              <div class="case-panel__mark tone-{esc(visual['tone'])}" aria-hidden="true"></div>
              <div class="case-panel__header"><p>{esc(case['geography'])}</p><h3>{esc(case['title'])}</h3></div>
              <p class="case-summary">{esc(clean_public_summary(case))}</p>
              <div class="case-panel__facts"><span>{len(case.get('entities', []))} orgs</span><span>{case.get('source_link_count', 0)} links</span><span>{case.get('source_blocker_count', 0)} records needed</span></div>
              <a class="case-link" href="{esc(case['case_id'])}/">Open case</a>
            </article>
            """
        )
        render_case_page(case, claims, sources, entities, money_rows, args.output_dir)

    cases_body = f"""
    <section class="route-hero">
      <p class="type-stamp">Case map</p>
      <h1>All current CalDS public cases</h1>
      <p>Each case starts with public records, not a verdict. Open a case to see what was found, what is missing, and where the source links point.</p>
    </section>
    <div class="case-accordion">{''.join(cards)}</div>
    """
    write_clean_text(cases_dir / "index.html", page("Cases", cases_body))

    method_dir = args.output_dir / "method"
    method_body = """
    <section class="route-hero">
      <p class="type-stamp">Method</p>
      <h1>How CalDS keeps the public story tied to records.</h1>
      <p>CalDS publishes review leads. That means public records raised a question. It does not mean CalDS has proved wrongdoing.</p>
    </section>
    <div class="method-grid">
      <article><strong>Claims need records.</strong><p>No public claim ships unless it maps to a source record.</p></article>
      <article><strong>Links are checked.</strong><p>Sources must be live, archived, or visibly listed as records still needed.</p></article>
      <article><strong>Legal words are limited.</strong><p>Charges, violations, settlements, or convictions appear only when an official source supports the word.</p></article>
      <article><strong>Private data stays private.</strong><p>The public app is built from sanitized JSON, not raw work files.</p></article>
    </div>
    """
    write_clean_text(method_dir / "index.html", page("Method", method_body))

    sources_dir = args.output_dir / "sources"
    rows = "".join(
        f"<tr><td>{esc(source['case_id'])}</td><td>{esc(source['source_family'])}</td><td>{esc(compact_sentence(source['title'], 120))}</td><td>{esc(source['archive_status'])}</td><td>{source_link(source)}</td></tr>"
        for source in sources
    )
    source_body = f"""
    <section class="route-hero">
      <p class="type-stamp">Source room</p>
      <h1>Public source receipts</h1>
      <p>Search the records behind the public pages. If a record is missing, the page says what still needs to be checked.</p>
    </section>
    <div class="source-table-wrap"><table class="source-table"><thead><tr><th>Case</th><th>Record type</th><th>Title</th><th>Status</th><th>Receipt</th></tr></thead><tbody>{rows}</tbody></table></div>
    """
    write_clean_text(sources_dir / "index.html", page("Sources", source_body))

    for folder in (cases_dir, method_dir, sources_dir):
        for asset in ("styles.css", "app.js"):
            src = args.output_dir / asset
            if src.exists():
                shutil.copy2(src, folder / asset)
    print("routes=cases,case-details,method,sources")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
