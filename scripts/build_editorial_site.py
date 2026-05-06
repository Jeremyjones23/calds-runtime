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
        "headline": "Big housing awards. Thin answers.",
        "ink": "#9f3d2f",
        "tone": "civic",
    },
    "live_ca_recovery_ngos_2026_04_24": {
        "label": "Recovery",
        "headline": "Treatment promises. Public records.",
        "ink": "#4e6f42",
        "tone": "field",
    },
    "live_ca_sf_homelessness_complex": {
        "label": "San Francisco",
        "headline": "City spending. Provider questions.",
        "ink": "#245b72",
        "tone": "bay",
    },
}

MECHANICAL_PUBLIC_MARKERS = (
    "already recovered: true",
    "pages fetched:",
    "source collection",
    "entity:",
    "rank by parsed",
    "source-listed",
    "calds shows only",
)

BRIEFING_EXCLUDED_SOURCE_FAMILIES = {
    "Organization service page",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def write_clean_text(path: Path, text: str) -> None:
    cleaned = "\n".join(line.rstrip() for line in text.splitlines()) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(cleaned, encoding="utf-8", newline="\n")


def compact_sentence(value: Any, limit: int = 230) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = re.sub(r"^E\d+\s+", "", text)
    text = text.replace("source-listed", "listed")
    text = text.replace("parsed", "listed")
    text = text.replace("deep review", "closer review")
    text = text.replace("deep-dive", "review")
    text = text.replace("Review Value Score", "review score")
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0].rstrip(".,;:") + "..."


def clean_public_summary(case: dict[str, Any]) -> str:
    case_id = case.get("case_id")
    if case_id == "live_ca_homelessness_top15_2026_04_29":
        return (
            "CalDS screened 15 California homelessness nonprofits. The public records show large state housing-award "
            "exposure, one official federal charging announcement tied to a connected property transaction, and records "
            "that still need to be requested before anyone should draw a final conclusion."
        )
    if case_id == "live_ca_recovery_ngos_2026_04_24":
        return (
            "CalDS screened seven recovery and treatment nonprofits. This public file shows the records recovered so far, "
            "including audit and public-statement sources, but it does not support a public accusation."
        )
    if case_id == "live_ca_sf_homelessness_complex":
        return (
            "CalDS screened 15 San Francisco homelessness nonprofits. The records show public payments, official notices "
            "or audits for some providers, and many contract, monitoring, and outcome records still needed for a full review."
        )
    return compact_sentence(case.get("public_summary") or case.get("title") or "CalDS reviewed public records for this case.")


def is_mechanical_public_sentence(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return any(marker in text for marker in MECHANICAL_PUBLIC_MARKERS)


def public_entity_description(value: Any) -> str:
    text = compact_sentence(value, 160)
    if not text or "CalDS shows only source-backed" in text:
        return "No source-backed service description is shown in this public export."
    return text


def public_signal_items(entity: dict[str, Any], limit: int = 3) -> list[str]:
    items: list[str] = []
    for item in (
        entity.get("official_records_found", [])
        + entity.get("public_money_found", [])
        + entity.get("red_flags", [])
        + entity.get("caveats", [])
    ):
        if is_mechanical_public_sentence(item):
            continue
        text = compact_sentence(item, 170)
        if text and text not in items:
            items.append(text)
        if len(items) >= limit:
            break
    return items


def case_visual(case_id: str) -> dict[str, str]:
    return CASE_VISUALS.get(
        case_id,
        {"label": "Case", "headline": "Records raised questions.", "ink": "#8b6728", "tone": "archive"},
    )


def amount_value(amount: str) -> float:
    cleaned = re.sub(r"[^0-9.]", "", str(amount or ""))
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def render_amount(amount: str, source_supports: str = "") -> str:
    if amount == "$11.2" and "million" in source_supports.lower():
        return "$11.2 million"
    return amount


def case_status(case: dict[str, Any]) -> str:
    blockers = int(case.get("source_blocker_count", 0) or 0)
    if blockers:
        return f"Needs records: {blockers} public-record gaps remain."
    return "Records checked: no missing public-record gaps in this export."


def top_claims_for_case(claims: list[dict[str, Any]], case_id: str, count: int = 5) -> list[dict[str, Any]]:
    candidates = [
        claim
        for claim in claims
        if claim.get("case_id") == case_id
        and claim.get("public_language_allowed", True)
        and claim.get("source_family") not in BRIEFING_EXCLUDED_SOURCE_FAMILIES
        and not is_mechanical_public_sentence(claim.get("plain_language_sentence") or claim.get("public_sentence"))
    ]

    def sort_key(claim: dict[str, Any]) -> tuple[int, int]:
        text = " ".join(
            str(claim.get(key, "")) for key in ("plain_language_sentence", "source_excerpt", "source_family", "legal_language_status")
        ).lower()
        official = int(any(word in text for word in ("official", "audit", "charged", "violation", "controller", "district attorney")))
        money = int("$" in text or "award" in text or "payment" in text or "contract" in text)
        return official + money, len(text)

    return sorted(candidates, key=sort_key, reverse=True)[:count]


def make_nav(prefix: str = "") -> str:
    return f"""
  <a class="skip-link" href="#main">Skip to story</a>
  <nav class="record-rail" aria-label="Primary navigation">
    <a class="brand" href="{prefix}index.html">CalDS</a>
    <div class="rail-links">
      <a href="{prefix}index.html#pattern">Pattern</a>
      <a href="{prefix}cases/">Cases</a>
      <a href="{prefix}index.html#money">Money trail</a>
      <a href="{prefix}sources/">Sources</a>
      <a href="{prefix}method/">Method</a>
    </div>
    <p>Public records. Public interest.</p>
  </nav>
"""


def head(title: str, stylesheet: str = "styles.css") -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)} | CalDS</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,800;9..144,900&family=Geist:wght@400;520;650;760;900&family=IBM+Plex+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="{stylesheet}">
</head>"""


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
        flag = clean_public_summary(case)
        case_cards.append(
            f"""
            <article class="case-ticket reveal" data-case="{esc(case['case_id'])}" style="--case-color:{esc(visual['ink'])}">
              <a class="case-ticket__photo tone-{esc(visual['tone'])}" href="cases/{esc(case['case_id'])}/" aria-label="Open {esc(case['short_title'])}"></a>
              <div class="case-ticket__body">
                <p class="case-ticket__label">{esc(visual['label'])}</p>
                <h3>{esc(visual['headline'])}</h3>
                <p>{esc(flag)}</p>
                <div class="case-ticket__meta">
                  <span>{len(case.get('entities', []))} orgs</span>
                  <span>{len(case_claims)} public claims</span>
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
        entity_name = entity.get("display_name") or "Organization named in source"
        amount = render_amount(str(row.get("amount", "")), str(source.get("supports", "")))
        money_cards.append(
            f"""
            <article class="receipt-card reveal" data-case="{esc(row['case_id'])}">
              <div class="receipt-card__stub">Public record</div>
              <strong class="receipt-card__amount">{esc(amount)}</strong>
              <p>{esc(entity_name)}</p>
              <small>{esc(source_title)}</small>
              <button class="source-jump" type="button" data-source="{esc(row['source_id'])}">Open receipt row</button>
            </article>
            """
        )

    top_entities = sorted(
        entities,
        key=lambda item: len(item.get("official_records_found", [])) * 3
        + len(item.get("public_money_found", [])) * 2
        + len(item.get("red_flags", [])),
        reverse=True,
    )[:12]
    entity_cards = []
    for entity in top_entities:
        flags = public_signal_items(entity, 3)
        flag_html = "".join(f"<li>{esc(flag)}</li>" for flag in flags)
        entity_cards.append(
            f"""
            <details class="entity-folder reveal">
              <summary>
                <span>{esc(entity['display_name'])}</span>
                <small>{len(entity.get('source_ids', []))} receipts</small>
              </summary>
              <div>
                <p>{esc(public_entity_description(entity.get('what_it_claims_to_do')))}</p>
                <ul>{flag_html or '<li>CalDS did not export a public red-flag sentence for this organization.</li>'}</ul>
              </div>
            </details>
            """
        )

    source_rows = []
    for source in sources:
        url = source.get("url") or ""
        if url:
            link = f'<a href="{esc(url)}" target="_blank" rel="noreferrer">Open receipt</a>'
        elif source.get("archive_status") == "Public artifact":
            link = "<span>Public artifact row</span>"
        else:
            link = "<span>Record still needed</span>"
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
        f"<li>{esc(item['case_id'])}: source links {esc(item['link_status'])}, citations {esc(item['citation_status'])}, records still needed {esc(item['source_blocker_count'])}</li>"
        for item in verification.get("case_manifest_status", [])
    )

    html_doc = f"""{head("Follow the Receipts")}
<body>
{make_nav()}
  <main id="main">
    <header class="poster-hero" id="top">
      <div class="sun-strip" aria-hidden="true"></div>
      <section class="poster-sheet">
        <div class="capitol-rail" aria-hidden="true"></div>
        <div class="paper-stamp" aria-hidden="true">California<br>public file</div>
        <div class="poster-copy">
          <p class="type-stamp">Public records / public power</p>
          <h1><span>Follow</span><span class="receipt-line"><span>the</span> <span>receipts.</span></span></h1>
          <p class="dek">We dig through the records so you do not have to. Explore the cases. Check the money. See what is proven, what is missing, and why it matters.</p>
          <div class="hero-actions" aria-label="Primary actions">
            <a href="cases/">Open the case files</a>
            <a href="#money">Trace the money</a>
          </div>
        </div>
        <aside class="tip-note">
          <span>See something worth checking?</span>
          <p>Send records, links, or a lead. We only publish what the receipts support.</p>
          <a href="#sources">Check the sources</a>
        </aside>
        <section class="latest-wall" aria-label="Latest cases">
          <p class="wall-label">Latest cases</p>
          <div class="case-strip">{''.join(case_cards)}</div>
        </section>
        <aside class="recent-source">
          <span>Source pulse</span>
          <p>{esc(compact_sentence(recent_source.get('title', 'Public source receipt'), 125))}</p>
          <strong>{live_sources}/{total_sources}</strong>
          <small>live public links</small>
        </aside>
        <p class="verdict-note">Red flag, not a verdict.</p>
        <div class="public-service">Journalism is a public service</div>
        <aside class="loop-note receipt-note">
          <b>Recent source</b>
          <span>{esc(compact_sentence(recent_source.get('title', 'Public source receipt'), 90))}</span>
          <i>{live_sources}/{total_sources} live public links</i>
        </aside>
        <aside class="curiosity-card" aria-hidden="true">
          <b>California counts on curiosity</b>
        </aside>
        <div class="marquee" aria-hidden="true"><span>New records added</span><span>IRS 990s</span><span>Contracts</span><span>City grants</span><span>Audits</span><span>Open questions</span></div>
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
        <article><b>{total_claims}</b><span>public claims tied to records</span></article>
        <article><b>{source_blockers}</b><span>records still needed</span></article>
        <article><b>{live_sources}</b><span>live public receipts</span></article>
      </div>
    </section>

    <section class="chapter money-machine" id="money">
      <div class="machine-copy">
        <p class="type-stamp">Money trail</p>
        <h2>Follow the dollar rows.</h2>
        <p>These dollar amounts come from public records. Some are partial. We say so when a record does not show the full total.</p>
        <div class="filter-tabs" aria-label="Filter money trail by case">{''.join(filter_buttons)}</div>
      </div>
      <div class="receipt-machine">
        <div class="machine-counter"><span id="receiptCount">{len(money_rows)}</span><small>visible receipts</small></div>
        <div class="receipt-roll">{''.join(money_cards)}</div>
        <p class="empty-money" hidden>No dollar records are shown for this case yet. Open the sources to see the public records we have.</p>
      </div>
    </section>

    <section class="chapter entity-board" id="cases">
      <div class="chapter-copy">
        <p class="type-stamp">Named review leads</p>
        <h2>Open the folders. Read what triggered review.</h2>
        <p>This page shows only public records, source links, open questions, and caveats. Draft notes and unreviewed leads stay off the public site.</p>
      </div>
      <div class="folder-grid">{''.join(entity_cards)}</div>
    </section>

    <section class="chapter source-room" id="sources">
      <div class="source-room__intro">
        <p class="type-stamp">Source room</p>
        <h2>Every public claim needs a receipt.</h2>
        <p>Public means linked records, plain caveats, and a clear list of what still needs to be checked.</p>
        <input id="sourceSearch" class="source-search" type="search" placeholder="Search receipts, agencies, cases, or record types" aria-label="Search sources">
      </div>
      <div class="source-cabinet">
        <table class="source-table">
          <thead><tr><th>Case</th><th>Record type</th><th>Title</th><th>Status</th><th>Receipt</th></tr></thead>
          <tbody>{''.join(source_rows)}</tbody>
        </table>
      </div>
      <aside class="private-lock">
        <b>Private stays private</b>
        <p>Draft notes and unchecked leads stay off public pages.</p>
      </aside>
    </section>

    <section class="chapter method-wall" id="method">
      <p class="type-stamp">How this stays honest</p>
      <h2>Possible fraud, waste, or abuse means the records show a red flag.</h2>
      <p>It does not mean CalDS has proved a crime. We publish source-backed review leads, legal-status caveats, and what still needs to be checked.</p>
      <div class="method-cards">
        <article><b>Receipts first</b><span>No public claim ships without a source.</span></article>
        <article><b>Plain words</b><span>We write for readers, not for internal tools.</span></article>
        <article><b>Gaps are not proof</b><span>Missing records are shown as records still needed.</span></article>
        <article><b>Red flag, not verdict</b><span>Human review comes before conclusions.</span></article>
      </div>
      <details class="gate-detail">
        <summary>What this build checked</summary>
        <ul>{manifest_rows}</ul>
      </details>
    </section>
  </main>

  <footer class="final-poster">
    <h2>Follow the receipts.</h2>
    <p>Public records are not paperwork. They are receipts.</p>
    <p>Read the case. Check the source. Ask the next question.</p>
    <a href="#top">Back to top</a>
  </footer>

  <script src="app.js"></script>
</body>
</html>"""
    output_dir.mkdir(parents=True, exist_ok=True)
    write_clean_text(output_dir / "index.html", html_doc.replace("<head>", f"<head>\n  <meta name=\"calds-build\" content=\"{build_marker}\">"))
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
