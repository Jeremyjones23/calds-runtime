from __future__ import annotations

from collections import Counter
from pathlib import Path
import argparse
import html
import json
import re
from typing import Any


CASE_VISUALS = {
    "live_ca_homelessness_top15_2026_04_29": {
        "label": "Homelessness",
        "headline": "Millions spent. Where did it go?",
        "image": "https://picsum.photos/seed/calds-homelessness-civic-record/900/620",
        "color": "#a94935",
    },
    "live_ca_recovery_ngos_2026_04_24": {
        "label": "Recovery",
        "headline": "Treatment promises. What worked?",
        "image": "https://picsum.photos/seed/calds-recovery-records/900/620",
        "color": "#57774e",
    },
    "live_ca_sf_homelessness_complex": {
        "label": "San Francisco",
        "headline": "Programs on paper. Results in doubt?",
        "image": "https://picsum.photos/seed/calds-san-francisco-civic/900/620",
        "color": "#255d74",
    },
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def first_items(items: list[Any], count: int) -> list[Any]:
    return items[:count] if len(items) > count else items


def write_clean_text(path: Path, text: str) -> None:
    cleaned = "\n".join(line.rstrip() for line in text.splitlines()) + "\n"
    path.write_text(cleaned, encoding="utf-8", newline="\n")


def compact_sentence(value: str, limit: int = 210) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = re.sub(r"^E\d+\s+", "", text)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0].rstrip(".,;:") + "..."


def case_visual(case_id: str) -> dict[str, str]:
    return CASE_VISUALS.get(
        case_id,
        {
            "label": "Case",
            "headline": "Records raised questions.",
            "image": f"https://picsum.photos/seed/{esc(case_id)}/900/620",
            "color": "#8e6b2f",
        },
    )


def render_index(data_dir: Path, output_dir: Path) -> str:
    public_cases = read_json(data_dir / "public-cases.json")
    case_summaries = read_json(data_dir / "case-summaries.json")["cases"]
    claims = read_json(data_dir / "claim-ledger.json")
    sources = read_json(data_dir / "source-ledger.json")["sources"]
    entities = read_json(data_dir / "entities.json")["entities"]
    money_rows = read_json(data_dir / "money-trail.json")["money_trail"]
    verification = read_json(data_dir / "verification-manifest.json")

    claims_by_case: dict[str, list[dict[str, Any]]] = {case["case_id"]: [] for case in case_summaries}
    for claim in claims:
        claims_by_case.setdefault(claim["case_id"], []).append(claim)

    sources_by_case: dict[str, list[dict[str, Any]]] = {case["case_id"]: [] for case in case_summaries}
    source_by_id: dict[str, dict[str, Any]] = {}
    for source in sources:
        sources_by_case.setdefault(source["case_id"], []).append(source)
        source_by_id[source["source_id"]] = source

    entity_by_id = {entity.get("entity_id"): entity for entity in entities}
    money_counts = Counter(row.get("case_id") for row in money_rows)
    total_sources = len(sources)
    live_sources = sum(1 for source in sources if source.get("archive_status") == "Live")
    total_claims = len(claims)
    source_blockers = sum(int(case.get("source_blocker_count", 0) or 0) for case in case_summaries)
    build_marker = esc(public_cases.get("publication_id", "editorial-build"))

    case_cards = []
    for index, case in enumerate(case_summaries, start=1):
        visual = case_visual(case["case_id"])
        case_claims = claims_by_case.get(case["case_id"], [])
        case_sources = sources_by_case.get(case["case_id"], [])
        flag = compact_sentence((case.get("strongest_supported_flags") or ["Records raised questions."])[0])
        case_cards.append(
            f"""
            <article class="case-ticket reveal" data-case="{esc(case['case_id'])}" style="--case-color:{esc(visual['color'])}">
              <a class="case-ticket__photo" href="cases/{esc(case['case_id'])}/" aria-label="Open {esc(case['short_title'])}" style="background-image:url('{esc(visual['image'])}')"></a>
              <div class="case-ticket__body">
                <p class="case-ticket__label">{esc(visual['label'])}</p>
                <h3>{esc(visual['headline'])}</h3>
                <p>{esc(flag)}</p>
                <div class="case-ticket__meta">
                  <span>{len(case.get('entities', []))} orgs</span>
                  <span>{len(case_claims)} claims</span>
                  <span>{len(case_sources)} receipts</span>
                </div>
                <a class="paper-link" href="cases/{esc(case['case_id'])}/">View case</a>
              </div>
              <span class="case-ticket__number">{index:02d}</span>
            </article>
            """
        )

    filter_buttons = [
        f'<button class="filter-tab is-active" type="button" data-money-filter="all"><span>All cases</span><b>{len(money_rows)}</b></button>'
    ]
    for case in case_summaries:
        count = money_counts.get(case["case_id"], 0)
        filter_buttons.append(
            f'<button class="filter-tab" type="button" data-money-filter="{esc(case["case_id"])}"><span>{esc(case["short_title"])}</span><b>{count}</b></button>'
        )

    money_cards = []
    for row in money_rows:
        source = source_by_id.get(row.get("source_id"), {})
        entity = entity_by_id.get(row.get("entity_id"), {})
        source_title = compact_sentence(source.get("title", "Public source receipt"), 90)
        entity_name = entity.get("display_name") or "Entity named in source"
        money_cards.append(
            f"""
            <article class="receipt-card reveal" data-case="{esc(row['case_id'])}">
              <div class="receipt-card__stub">Public record</div>
              <strong>{esc(row['amount'])}</strong>
              <p>{esc(entity_name)}</p>
              <small>{esc(source_title)}</small>
              <button class="source-jump" type="button" data-source="{esc(row['source_id'])}">View receipt</button>
            </article>
            """
        )

    top_entities = sorted(
        entities,
        key=lambda item: len(item.get("red_flags", [])) + len(item.get("official_records_found", [])) + len(item.get("public_money_found", [])),
        reverse=True,
    )[:12]
    entity_cards = []
    for entity in top_entities:
        flags = first_items(entity.get("red_flags", []) + entity.get("official_records_found", []) + entity.get("public_money_found", []), 3)
        flag_html = "".join(f"<li>{esc(compact_sentence(flag, 180))}</li>" for flag in flags)
        entity_cards.append(
            f"""
            <details class="entity-folder reveal">
              <summary>
                <span>{esc(entity['display_name'])}</span>
                <small>{len(entity.get('source_ids', []))} receipts</small>
              </summary>
              <div>
                <p>{esc(entity.get('what_it_claims_to_do') or 'CalDS publishes only source-backed descriptions recovered in the run.')}</p>
                <ul>{flag_html or '<li>No high-priority public sentence was exported for this organization.</li>'}</ul>
              </div>
            </details>
            """
        )

    source_rows = []
    for source in sources:
        url = source.get("url") or ""
        link = f'<a href="{esc(url)}" target="_blank" rel="noreferrer">Open receipt</a>' if url else "<span>Blocked</span>"
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

    recent_source = sources[0] if sources else {}
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
  <title>Follow the Receipts | CalDS</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=Fraunces:opsz,wght@9..144,600;9..144,800;9..144,900&family=IBM+Plex+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <a class="skip-link" href="#cases">Skip to cases</a>
  <nav class="record-rail" aria-label="Primary navigation">
    <a class="brand" href="#top">CalDS</a>
    <div class="rail-links">
      <a href="#pattern">Pattern</a>
      <a href="#cases">Cases</a>
      <a href="#money">Money trail</a>
      <a href="#sources">Sources</a>
      <a href="#method">Method</a>
    </div>
    <p>Public records. Public interest.</p>
  </nav>

  <main id="top">
    <header class="poster-hero">
      <div class="sun-strip" aria-hidden="true"></div>
      <section class="poster-sheet">
        <div class="poster-copy">
          <p class="type-stamp">Public records / power accountability</p>
          <h1><span>Follow</span><span class="receipt-line"><span>the</span> <span>receipts.</span></span></h1>
          <p class="dek">We dig through the records so you do not have to. Explore the cases. Check the money. Help keep California accountable.</p>
        </div>
        <aside class="tip-note">
          <span>See something worth looking into?</span>
          <p>Share documents, data, or details. Your tip could be the next story.</p>
          <a href="mailto:tips@caldoge.ai">Send a tip</a>
        </aside>
        <section class="latest-wall" aria-label="Latest cases">
          <p class="wall-label">Latest cases</p>
          <div class="case-strip">{''.join(case_cards)}</div>
        </section>
        <aside class="recent-source">
          <span>Recent source</span>
          <p>{esc(compact_sentence(recent_source.get('title', 'Public source receipt'), 130))}</p>
          <strong>{live_sources}/{total_sources}</strong>
          <small>live receipts</small>
        </aside>
        <div class="capitol-postcard" aria-hidden="true"></div>
        <div class="curiosity-sign" aria-hidden="true"><span>California counts on curiosity</span></div>
        <div class="public-service">Journalism is a public service</div>
        <p class="verdict-note">This is a red flag, not a verdict.</p>
        <aside class="newsletter-note">
          <b>Stay in the loop</b>
          <p>New case updates and document drops.</p>
          <span>Your email</span>
        </aside>
        <div class="marquee" aria-hidden="true"><span>New records added</span><span>IRS 990s</span><span>Contracts</span><span>City grants</span><span>Audits</span><span>Explore what is new</span></div>
      </section>
    </header>

    <section class="chapter pattern-chapter" id="pattern">
      <div class="chapter-copy">
        <p class="type-stamp">What the public can see</p>
        <h2>The same question keeps coming back: who got paid, and what changed?</h2>
        <p>{esc(public_cases['dek'])}</p>
      </div>
      <div class="record-grid">
        <article><b>{len(case_summaries)}</b><span>case families</span></article>
        <article><b>{total_claims}</b><span>source-backed public claims</span></article>
        <article><b>{source_blockers}</b><span>records still needed</span></article>
        <article><b>{live_sources}</b><span>live public receipts</span></article>
      </div>
    </section>

    <section class="chapter money-machine" id="money">
      <div class="machine-copy">
        <p class="type-stamp">Money trail records machine</p>
        <h2>Filter the receipt roll.</h2>
        <p>The current exported dollar rows are source-backed and partial unless the receipt says they are a full total. Filters now show counts and a clear empty state.</p>
        <div class="filter-tabs" aria-label="Filter money trail by case">{''.join(filter_buttons)}</div>
      </div>
      <div class="receipt-machine">
        <div class="machine-counter"><span id="receiptCount">{len(money_rows)}</span><small>visible receipts</small></div>
        <div class="receipt-roll">{''.join(money_cards)}</div>
        <p class="empty-money" hidden>No exported dollar receipt rows for this case yet. The case still has source receipts in the source room.</p>
      </div>
    </section>

    <section class="chapter entity-board" id="cases">
      <div class="chapter-copy">
        <p class="type-stamp">Named review leads</p>
        <h2>Open the folders. Read what triggered review.</h2>
        <p>These are public-facing review leads. Raw runs, drafts, local files, and internal reasoning stay private unless they are turned into source-backed public claims.</p>
      </div>
      <div class="folder-grid">{''.join(entity_cards)}</div>
    </section>

    <section class="chapter source-room" id="sources">
      <div class="source-room__intro">
        <p class="type-stamp">Source room</p>
        <h2>Every public claim needs a receipt.</h2>
        <p>Public: source links, citation status, blocked-record explanations, caveats. Private: raw runs, local artifact paths, draft reasoning, and unreviewed hypotheses.</p>
        <input id="sourceSearch" class="source-search" type="search" placeholder="Search receipts, agencies, cases, or record types" aria-label="Search sources">
      </div>
      <div class="source-cabinet">
        <table class="source-table">
          <thead><tr><th>Case</th><th>Source family</th><th>Title</th><th>Status</th><th>Receipt</th></tr></thead>
          <tbody>{''.join(source_rows)}</tbody>
        </table>
      </div>
      <aside class="private-lock">
        <b>Private stays private</b>
        <p>Internal notes, drafts, raw files, and work-in-progress analysis are not public.</p>
      </aside>
    </section>

    <section class="chapter method-wall" id="method">
      <p class="type-stamp">How this stays honest</p>
      <h2>Possible fraud, waste, or abuse means the records show a red flag.</h2>
      <p>It does not mean CalDS has proved a crime. We publish source-backed review leads, legal-status caveats, and what still needs to be checked.</p>
      <div class="method-cards">
        <article><b>Receipts first</b><span>No public claim ships without a source row.</span></article>
        <article><b>Plain words</b><span>We avoid internal workflow language on public pages.</span></article>
        <article><b>Human limits</b><span>Missing records are shown as gaps, not proof.</span></article>
        <article><b>Public boundary</b><span>Private notes do not become public by accident.</span></article>
      </div>
      <details class="gate-detail">
        <summary>Publication gates for this build</summary>
        <ul>{manifest_rows}</ul>
      </details>
    </section>
  </main>

  <footer class="final-poster">
    <h2>Follow the receipts.</h2>
    <p>Public records. Public interest. Red flags, not verdicts.</p>
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
