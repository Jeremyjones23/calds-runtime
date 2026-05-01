from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import html
import json
import re
from typing import Any, Iterable

from .case_compiler import (
    _archive_path_remaps,
    compile_dossier_from_run,
    evidence_bundle_from_dict,
    risk_matrix_from_dict,
    sentinel_result_from_dict,
)
from .contracts import CaseRequest, EvidenceBundle, EvidenceItem, read_json, stable_id, to_jsonable, utc_now, write_json
from .plain_language import expand_reviewer_acronyms
from .quality_gates import CitationVerifierService, LinkIntegrityService
from .review import SOURCE_TYPE_LABELS


URL_RE = re.compile(r"https?://[^\s\\|)\]}\"']+", re.IGNORECASE)
WINDOWS_PATH_RE = re.compile(r"[A-Za-z]:\\[^\s|)]+")
RELATIVE_LOCAL_PATH_RE = re.compile(r"(?<![A-Za-z0-9_/-])(?:artifacts|runs|data\\live_corpus)\\[^\s|)]+", re.IGNORECASE)
ARCHIVED_COPY_RE = re.compile(r" \(archived local copy: [A-Za-z]:\\[^)]*\)")
SECRET_RE = re.compile(r"(github_pat_[A-Za-z0-9_]{20,}|ghp_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,})")
EVIDENCE_REF_RE = re.compile(r"`(E\d{2})`")
PROTECTED_CODE_RE = re.compile(r"`([^`]+)`")
NON_BROWSABLE_PUBLIC_URLS = (
    "https://data.ca.gov/api/3/action/datastore_search",
)
PUBLIC_URL_REPAIRS = {
    "https://data.chhs.ca.gov/api/3/action": "https://data.chhs.ca.gov/",
    "https://data.ca.gov/api/3/action": "https://lab.data.ca.gov/",
    "https://data.chhs.ca.gov/dataset/medication-assisted-treatment-in-medi-cal-for-opioid-use-disorders-by-county": "https://lab.data.ca.gov/dataset/medication-assisted-treatment-in-medi-cal-for-opioid-use-disorders-by-county",
    "https://www.tarzanatc.org/news-events/": "https://www.tarzanatc.org/treatment-news/",
    "https://socialmodelrecovery.org/annual-report/": "https://socialmodelrecovery.org/annual-report/?amp",
    "https://www.socialmodelrecovery.org/about-us/": "https://socialmodelrecovery.org/services/",
    "https://www.socialmodelrecovery.org/programs/": "https://socialmodelrecovery.org/services/",
}


@dataclass(frozen=True)
class PublicCaseSite:
    case_id: str
    output_dir: str
    index_html: str
    case_dossier_markdown: str
    case_dossier_json: str
    source_ledger_json: str
    publication_manifest_json: str
    safety_passed: bool


def publish_case_site_from_run(run_dir: Path, output_dir: Path) -> PublicCaseSite:
    """Compile a run into a public-safe static case viewer."""

    run_dir = run_dir.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    compiled = compile_dossier_from_run(run_dir, output_dir)
    artifacts_dir = run_dir / "artifacts"
    request = CaseRequest.from_dict(read_json(artifacts_dir / "case_request.json"))
    bundle = evidence_bundle_from_dict(read_json(artifacts_dir / "evidence_bundle.json"))
    sentinel = sentinel_result_from_dict(read_json(artifacts_dir / "sentinel_decision.json"))
    risk_matrix = risk_matrix_from_dict(read_json(artifacts_dir / "oversight_risk_matrix.json"))

    labels = evidence_labels(bundle)
    remaps = _archive_path_remaps(run_dir)
    source_ledger = build_source_ledger(bundle, labels, remaps)

    compiled_markdown = Path(compiled.markdown_path).read_text(encoding="utf-8")
    citation_verification = CitationVerifierService().verify(request, compiled_markdown, bundle, risk_matrix)
    if citation_verification.status != "PASS":
        raise ValueError(
            f"public case-site citation validation failed: {citation_verification.status} "
            f"({citation_verification.warning_count} warnings, {citation_verification.error_count} errors)"
        )

    public_markdown = sanitize_public_text(compiled_markdown)
    public_markdown_path = output_dir / "case_dossier.md"
    public_markdown_path.write_text(public_markdown, encoding="utf-8", newline="\n")

    source_ledger, link_repair = repair_public_source_urls(source_ledger)
    link_integrity = LinkIntegrityService().check_source_ledger(source_ledger)

    source_ledger_path = output_dir / "source_ledger.json"
    write_json(source_ledger_path, {"case_id": request.case_id, "evidence": source_ledger})

    html_text = render_public_html(request, public_markdown, source_ledger, sentinel.decision.value)
    index_path = output_dir / "index.html"
    index_path.write_text(html_text, encoding="utf-8", newline="\n")

    public_dossier = {
        "dossier_id": compiled.dossier_id,
        "case_id": compiled.case_id,
        "markdown_path": "case_dossier.md",
        "source_ledger_path": "source_ledger.json",
        "sentinel_decision": compiled.sentinel_decision.value,
        "compiler_role": compiled.compiler_role.value,
        "created_at": compiled.created_at,
        "publication_note": "Public-safe dossier metadata. Internal local artifact paths are intentionally omitted.",
    }
    public_dossier_path = output_dir / "case_dossier.json"
    write_json(public_dossier_path, public_dossier)

    link_integrity = LinkIntegrityService().check_source_ledger(source_ledger)
    safety = validate_publication(output_dir, public_markdown, html_text, source_ledger, link_integrity)
    manifest = {
        "publication_id": stable_id("publication", request.case_id, utc_now()),
        "case_id": request.case_id,
        "generated_at": utc_now(),
        "source_run_label": run_dir.name,
        "sentinel_decision": sentinel.decision.value,
        "human_review_required": True,
        "files": {
            "index_html": "index.html",
            "case_dossier_markdown": "case_dossier.md",
            "case_dossier_json": "case_dossier.json",
            "source_ledger_json": "source_ledger.json",
        },
        "safety": safety,
        "link_integrity": to_jsonable(link_integrity),
        "link_repair": link_repair,
        "citation_verification": to_jsonable(citation_verification),
    }
    manifest_path = output_dir / "publication_manifest.json"
    write_json(manifest_path, manifest)

    if not safety["passed"]:
        raise ValueError("public case-site safety validation failed: " + "; ".join(safety["errors"]))

    return PublicCaseSite(
        case_id=request.case_id,
        output_dir=str(output_dir),
        index_html=str(index_path),
        case_dossier_markdown=str(public_markdown_path),
        case_dossier_json=str(public_dossier_path),
        source_ledger_json=str(source_ledger_path),
        publication_manifest_json=str(manifest_path),
        safety_passed=True,
    )


def evidence_labels(bundle: EvidenceBundle) -> dict[str, str]:
    return {item.item_id: f"E{index:02d}" for index, item in enumerate(bundle.items, start=1)}


def build_source_ledger(bundle: EvidenceBundle, labels: dict[str, str], path_remaps: dict[str, str]) -> list[dict[str, Any]]:
    source_type_counts = Counter(item.source_type for item in bundle.items)
    entries: list[dict[str, Any]] = []
    for item in bundle.items:
        direct_urls = public_browsable_urls(extract_urls(item.source_uri))
        derived_urls = [] if direct_urls else public_browsable_urls(infer_external_urls(item, bundle, path_remaps))
        source_urls = unique_preserve_order([*direct_urls, *derived_urls])
        link_status = "external_source_linked" if direct_urls else "derived_external_source_linked" if derived_urls else "not_externally_linkable"
        link_note = ""
        if link_status == "derived_external_source_linked":
            link_note = "This evidence item is a parsed local artifact; external links point to upstream official or public sources used by the run."
        elif link_status == "not_externally_linkable":
            link_note = "Not externally linkable in this run; the public packet preserves the internal evidence ID, record ID, source type, checksum, and title for audit follow-up."

        entries.append(
            {
                "ref": labels[item.item_id],
                "anchor": f"evidence-{labels[item.item_id]}",
                "internal_evidence_id": item.item_id,
                "record_id": item.record_id,
                "title": expand_reviewer_acronyms(item.title),
                "source_type": item.source_type,
                "source_type_label": expand_reviewer_acronyms(SOURCE_TYPE_LABELS.get(item.source_type, item.source_type)),
                "source_reference": public_source_reference(item),
                "source_urls": source_urls,
                "link_status": link_status,
                "link_note": link_note,
                "published_at": item.published_at or "not provided",
                "checksum": item.provenance.checksum,
                "retrieval_relevance": item.relevance_score,
                "active_signal_count": len([key for key, value in item.signals.items() if value]),
                "source_type_count_in_bundle": source_type_counts[item.source_type],
                "excerpt": sanitize_public_text(shorten(item.excerpt, 600)),
            }
        )
    return entries


def repair_public_source_urls(source_ledger: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    affected_refs: list[str] = []
    replacements: list[dict[str, str]] = []
    updated: list[dict[str, Any]] = []
    for entry in source_ledger:
        row = dict(entry)
        urls = [str(url) for url in row.get("source_urls", [])]
        repaired_urls: list[str] = []
        row_replacements: list[tuple[str, str]] = []
        for url in urls:
            repaired = repair_public_url(url)
            repaired_urls.append(repaired)
            if repaired != url:
                row_replacements.append((url, repaired))
                replacements.append(
                    {
                        "ref": str(row.get("ref", "")),
                        "old_unlinked_reference": unlinked_url_reference(url),
                        "new_url": repaired,
                    }
                )
        if row_replacements:
            affected_refs.append(str(row.get("ref", "")))
            existing_note = str(row.get("link_note", "")).strip()
            repair_note = (
                f"Publication link repair replaced {len(row_replacements)} stale or renamed public URL(s) with working public source page(s)."
            )
            row["link_note"] = " ".join(part for part in [existing_note, repair_note] if part)
            row["source_urls"] = unique_preserve_order(repaired_urls)
            row["source_reference"] = repair_public_source_reference(str(row.get("source_reference", "")))
            row["link_status"] = "external_source_linked" if row["source_urls"] else "not_externally_linkable"
        updated.append(row)

    return updated, {
        "repaired_public_links": len(replacements),
        "affected_evidence_refs": [ref for ref in affected_refs if ref],
        "replacements": replacements,
        "note": "Stale or renamed public URLs are repaired to working source pages before publication. Links are not removed as a substitute for repair.",
    }


def repair_public_urls(urls: Iterable[str]) -> list[str]:
    return unique_preserve_order(repair_public_url(url) for url in urls)


def repair_public_url(url: str) -> str:
    return PUBLIC_URL_REPAIRS.get(str(url).strip(), str(url).strip())


def repair_public_source_reference(value: str) -> str:
    repaired = value
    for old, new in PUBLIC_URL_REPAIRS.items():
        repaired = repaired.replace(old, new)
    return repaired


def unlinked_url_reference(url: str) -> str:
    return re.sub(r"^https?://", "", str(url).strip())


def infer_external_urls(item: EvidenceItem, bundle: EvidenceBundle, path_remaps: dict[str, str]) -> list[str]:
    urls = urls_from_local_artifact(item.source_uri, path_remaps)
    if urls:
        return urls[:30]

    family = source_family(item.source_type, item.record_id)
    if not family:
        return []
    candidates: list[str] = []
    for other in bundle.items:
        if other.item_id == item.item_id:
            continue
        if source_family(other.source_type, other.record_id) == family:
            candidates.extend(extract_urls(other.source_uri))
    return unique_preserve_order(candidates)[:30]


def source_family(source_type: str, record_id: str) -> str:
    value = f"{source_type} {record_id}".lower()
    if source_type.startswith("dhcs") or "dhcs" in value:
        return "dhcs"
    if source_type.startswith("irs") or "_irs_" in value or "irs_" in value:
        return "irs"
    if source_type.startswith("fac") or "_fac_" in value or "fac_" in value:
        return "fac"
    if "outcome" in value or "spend_vs_results" in value:
        return "outcome"
    if "homekey" in value or "hcd" in value or "state_homeless" in value:
        return "state_homelessness_award"
    if "enforcement" in value or "docket" in value or "court" in value or "prosecution" in value:
        return "enforcement_or_docket"
    if "public_statement" in value or "service_page" in value:
        return "public_statement"
    if "social_media" in value or "website_traffic" in value:
        return "social_web"
    if "county" in value:
        return "county"
    return ""


def urls_from_local_artifact(source_uri: str, path_remaps: dict[str, str]) -> list[str]:
    path = resolve_local_path(source_uri, path_remaps)
    if not path or not path.exists() or path.stat().st_size > 5_000_000:
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    return unique_preserve_order(extract_urls(text))


def resolve_local_path(source_uri: str, path_remaps: dict[str, str]) -> Path | None:
    if extract_urls(source_uri):
        return None
    text = str(source_uri).strip()
    if not text:
        return None
    candidate = Path(text)
    if candidate.exists():
        return candidate
    for original, replacement in path_remaps.items():
        if text.startswith(original):
            mapped = Path(replacement + text[len(original):])
            if mapped.exists():
                return mapped
    return None


def public_source_reference(item: EvidenceItem) -> str:
    raw_urls = extract_urls(item.source_uri)
    urls = public_browsable_urls(raw_urls)
    if urls:
        return "; ".join(urls)
    if raw_urls:
        return f"non-browsable machine source reference: {item.record_id}"
    name = Path(str(item.source_uri)).name if item.source_uri else item.record_id
    if str(item.source_uri).startswith("local://"):
        return f"local source reference: {item.record_id}"
    return f"derived local artifact: {name or item.record_id}"


def extract_urls(value: object) -> list[str]:
    return unique_preserve_order(match.group(0).rstrip(".,;") for match in URL_RE.finditer(str(value)))


def public_browsable_urls(urls: Iterable[str]) -> list[str]:
    return unique_preserve_order(
        url for url in urls if not any(url.startswith(prefix) for prefix in NON_BROWSABLE_PUBLIC_URLS)
    )


def unique_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def sanitize_public_text(value: object) -> str:
    text = str(value)
    text = ARCHIVED_COPY_RE.sub("", text)
    text = WINDOWS_PATH_RE.sub("[internal local artifact]", text)
    text = RELATIVE_LOCAL_PATH_RE.sub("[internal local artifact]", text)
    return text


def public_case_css() -> str:
    return """
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,700&family=IBM+Plex+Mono:wght@400;500;600&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600;8..60,700&display=swap');
:root {
  color-scheme: light;
  --paper: #f3ead8;
  --paper-2: #fff9ed;
  --paper-3: #e6d7bb;
  --ink: #19150f;
  --muted: #665f52;
  --quiet: #867866;
  --charcoal: #121615;
  --charcoal-2: #1e2925;
  --civic-blue: #214f72;
  --civic-blue-2: #2d6f8f;
  --docket-red: #9e2f2b;
  --audit-amber: #d89d28;
  --ledger-green: #2f6d55;
  --line: rgba(25, 21, 15, .18);
  --line-dark: rgba(255, 249, 237, .18);
  --shadow: 0 24px 65px rgba(25, 21, 15, .18);
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  color: var(--ink);
  background:
    linear-gradient(90deg, rgba(25, 21, 15, .035) 1px, transparent 1px) 0 0 / 38px 38px,
    linear-gradient(180deg, rgba(25, 21, 15, .028) 1px, transparent 1px) 0 0 / 38px 38px,
    radial-gradient(circle at 10% 0%, rgba(216, 157, 40, .22), transparent 34%),
    linear-gradient(145deg, #f6ecd7 0%, #efe0c2 38%, #f8f1e2 100%);
  font-family: "Source Serif 4", Georgia, serif;
  line-height: 1.58;
}
a { color: var(--civic-blue); text-decoration-thickness: 1px; text-underline-offset: 3px; }
code, pre, .mono, .evidence-ref {
  font-family: "IBM Plex Mono", Consolas, monospace;
  letter-spacing: 0;
}
code {
  background: rgba(255, 249, 237, .82);
  border: 1px solid var(--line);
  border-radius: 4px;
  padding: 1px 5px;
}
.case-hero {
  position: relative;
  overflow: hidden;
  background:
    linear-gradient(135deg, rgba(18, 22, 21, .97), rgba(30, 41, 37, .95)),
    repeating-linear-gradient(90deg, rgba(255,255,255,.04) 0 1px, transparent 1px 32px);
  color: var(--paper-2);
  border-bottom: 7px solid var(--docket-red);
}
.case-hero::before {
  content: "";
  position: absolute;
  inset: 0;
  background:
    linear-gradient(120deg, transparent 0 56%, rgba(216,157,40,.18) 56% 58%, transparent 58%),
    repeating-linear-gradient(135deg, rgba(255,255,255,.035) 0 1px, transparent 1px 18px);
  pointer-events: none;
}
.case-hero__inner {
  position: relative;
  max-width: 1220px;
  margin: 0 auto;
  padding: 44px 24px 34px;
}
.eyebrow {
  margin: 0 0 12px;
  color: var(--audit-amber);
  font-family: "IBM Plex Mono", Consolas, monospace;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0;
  text-transform: uppercase;
}
.case-hero h1 {
  margin: 0;
  max-width: 940px;
  font-family: "Fraunces", Georgia, serif;
  font-size: clamp(38px, 7vw, 86px);
  line-height: .92;
  letter-spacing: 0;
}
.case-title {
  max-width: 860px;
  margin: 18px 0 0;
  color: rgba(255, 249, 237, .88);
  font-size: 20px;
}
.status-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin: 30px 0 0;
}
.status-tile {
  min-height: 108px;
  padding: 14px;
  border: 1px solid var(--line-dark);
  background: rgba(255, 249, 237, .08);
  box-shadow: inset 0 1px 0 rgba(255,255,255,.08);
}
.status-tile strong {
  display: block;
  color: #fff9ed;
  font-family: "IBM Plex Mono", Consolas, monospace;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
}
.status-tile span {
  display: block;
  margin-top: 8px;
  color: rgba(255, 249, 237, .82);
  font-size: 18px;
}
.case-nav {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 24px;
}
.case-nav a {
  color: var(--paper-2);
  border: 1px solid rgba(255, 249, 237, .35);
  background: rgba(255, 249, 237, .08);
  padding: 8px 11px;
  text-decoration: none;
  font-family: "IBM Plex Mono", Consolas, monospace;
  font-size: 12px;
  text-transform: uppercase;
}
.case-shell {
  display: grid;
  grid-template-columns: 252px minmax(0, 1fr);
  gap: 28px;
  max-width: 1220px;
  margin: 0 auto;
  padding: 30px 24px 72px;
}
.case-rail {
  position: sticky;
  top: 18px;
  align-self: start;
  padding: 18px;
  background: rgba(255, 249, 237, .82);
  border: 1px solid var(--line);
  box-shadow: 8px 8px 0 rgba(158, 47, 43, .12);
}
.case-rail h2 {
  margin: 0 0 10px;
  font-family: "Fraunces", Georgia, serif;
  font-size: 24px;
  line-height: 1;
}
.case-rail a {
  display: block;
  margin: 7px 0;
  color: var(--charcoal);
  font-family: "IBM Plex Mono", Consolas, monospace;
  font-size: 12px;
  text-decoration: none;
  text-transform: uppercase;
}
.case-main { min-width: 0; }
.notice {
  display: grid;
  grid-template-columns: 10px 1fr;
  gap: 14px;
  margin: 0 0 24px;
  padding: 18px;
  background: var(--paper-2);
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
}
.notice::before { content: ""; background: var(--audit-amber); }
.notice strong { color: var(--docket-red); }
.dossier, #source-ledger {
  background: rgba(255, 249, 237, .9);
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
}
.dossier {
  padding: 28px;
}
#source-ledger {
  margin-top: 28px;
  padding: 28px;
}
h1, h2, h3, h4 {
  font-family: "Fraunces", Georgia, serif;
  line-height: 1.12;
  letter-spacing: 0;
}
.dossier h1 {
  margin-top: 0;
  font-size: clamp(34px, 4vw, 52px);
}
.dossier h2, #source-ledger h2 {
  margin-top: 38px;
  padding-top: 18px;
  border-top: 2px solid rgba(158, 47, 43, .28);
  color: var(--charcoal);
}
.dossier h3 { color: var(--civic-blue); }
.dossier p, .dossier li { font-size: 18px; }
.dossier ul, .dossier ol { padding-left: 26px; }
.table-block {
  overflow: auto;
  margin: 18px 0;
  padding: 14px;
  color: #f9edd4;
  background:
    linear-gradient(90deg, rgba(216, 157, 40, .1), transparent 26%),
    #18201d;
  border: 1px solid rgba(25, 21, 15, .42);
  box-shadow: inset 0 0 0 1px rgba(255,255,255,.04);
  white-space: pre;
}
.evidence-ref {
  display: inline-block;
  color: var(--paper-2);
  background: var(--docket-red);
  border: 1px solid rgba(25, 21, 15, .22);
  border-radius: 3px;
  padding: 0 5px;
  font-size: .78em;
  font-weight: 600;
  text-decoration: none;
  transform: translateY(-1px);
}
.evidence-card {
  position: relative;
  margin: 16px 0;
  padding: 18px 18px 18px 26px;
  border: 1px solid var(--line);
  background:
    linear-gradient(90deg, rgba(47, 109, 85, .12), transparent 32%),
    #fffaf0;
}
.evidence-card::before {
  content: "";
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 8px;
  background: var(--ledger-green);
}
.evidence-card--not-externally-linkable::before { background: var(--audit-amber); }
.evidence-card--external-source-linked::before { background: var(--ledger-green); }
.evidence-card--derived-external-source-linked::before { background: var(--civic-blue-2); }
.evidence-card h3 {
  margin: 0 0 10px;
  font-size: 24px;
}
.meta, .link-status, footer {
  color: var(--muted);
  font-size: 14px;
}
.source-list {
  margin: 8px 0 0;
  padding-left: 22px;
  overflow-wrap: anywhere;
}
.source-list a { word-break: break-word; }
footer {
  max-width: 1220px;
  margin: 0 auto;
  padding: 22px 24px 38px;
}
@media (prefers-reduced-motion: no-preference) {
  .case-hero__inner, .notice, .dossier, #source-ledger, .evidence-card {
    animation: rise-in .7s ease both;
  }
  .notice { animation-delay: .08s; }
  .dossier { animation-delay: .14s; }
  #source-ledger { animation-delay: .2s; }
  .evidence-card:nth-of-type(2n) { animation-delay: .05s; }
  @keyframes rise-in {
    from { opacity: 0; transform: translateY(16px); }
    to { opacity: 1; transform: translateY(0); }
  }
}
@media (max-width: 880px) {
  .status-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .case-shell { grid-template-columns: 1fr; }
  .case-rail { position: static; }
}
@media (max-width: 560px) {
  .case-hero__inner, .case-shell { padding-left: 16px; padding-right: 16px; }
  .status-strip { grid-template-columns: 1fr; }
  .dossier, #source-ledger { padding: 18px; }
  .dossier p, .dossier li { font-size: 16px; }
}
@media print {
  body { background: #fff; color: #000; }
  .case-hero, .case-rail, .case-nav { background: #fff; color: #000; border: 0; }
  .case-shell { display: block; max-width: none; padding: 0; }
  .dossier, #source-ledger, .notice { box-shadow: none; border-color: #999; }
}
"""


def render_public_html(request: CaseRequest, markdown_text: str, source_ledger: list[dict[str, Any]], sentinel_decision: str) -> str:
    body = render_markdown_fragment(markdown_text)
    cards = "\n".join(render_evidence_card(entry) for entry in source_ledger)
    title = html.escape(request.title)
    generated = html.escape(utc_now())
    css = public_case_css()
    evidence_count = len(source_ledger)
    linked_count = sum(1 for entry in source_ledger if entry.get("source_urls"))
    not_linked_count = evidence_count - linked_count
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>{title} | CalDS Public Case Viewer</title>
  <style>
{css}
  </style>
</head>
<body>
<header class=\"case-hero\">
  <div class=\"case-hero__inner\">
    <p class=\"eyebrow\">California Evidence Room</p>
    <h1>CalDS Public Case Viewer</h1>
    <p class=\"case-title\">{title}</p>
    <div class=\"status-strip\" aria-label=\"Case publication status\">
      <div class=\"status-tile\"><strong>Sentinel posture</strong><span>{html.escape(sentinel_decision)}</span></div>
      <div class=\"status-tile\"><strong>Human posture</strong><span>Review required</span></div>
      <div class=\"status-tile\"><strong>Evidence ledger</strong><span>{evidence_count} records</span></div>
      <div class=\"status-tile\"><strong>Internet links</strong><span>{linked_count} linked / {not_linked_count} marked</span></div>
    </div>
    <nav class=\"case-nav\" aria-label=\"Case links\">
      <a href=\"#dossier\">Briefing</a>
      <a href=\"#source-ledger\">Source Ledger</a>
      <a href=\"case_dossier.md\">Markdown</a>
      <a href=\"source_ledger.json\">Source JSON</a>
    </nav>
  </div>
</header>
<main class=\"case-shell\">
  <aside class=\"case-rail\" aria-label=\"Case navigation\">
    <h2>Read Order</h2>
    <a href=\"#dossier\">Start With The Brief</a>
    <a href=\"#source-ledger\">Audit The Sources</a>
    <a href=\"case_dossier.md\">Open Markdown</a>
    <a href=\"case_dossier.json\">Open Metadata</a>
    <a href=\"source_ledger.json\">Open Source JSON</a>
  </aside>
  <div class=\"case-main\">
  <section class=\"notice\">
    <div><strong>Publication safety note:</strong> This page is a public-safe review aid, not a formal finding. Local file paths are omitted. Evidence labels jump to source-ledger cards; source rows either link to recovered internet sources or state why the record is not externally linkable in this run.</div>
  </section>
  <section id=\"dossier\" class=\"dossier\">{body}</section>
  <section id=\"source-ledger\">
    <h2>Source Ledger</h2>
    <p>Every evidence label used in the dossier resolves here. Original URLs are linked when available; otherwise the row states why the source is not externally linkable in this run.</p>
{cards}
  </section>
  </div>
</main>
<footer>Generated {generated}. Human review remains required before outside-facing use.</footer>
</body>
</html>
"""


def render_markdown_fragment(markdown_text: str) -> str:
    lines = markdown_text.splitlines()
    output: list[str] = []
    in_ul = False
    in_ol = False
    table_lines: list[str] = []

    def close_lists() -> None:
        nonlocal in_ul, in_ol
        if in_ul:
            output.append("</ul>")
            in_ul = False
        if in_ol:
            output.append("</ol>")
            in_ol = False

    def flush_table() -> None:
        nonlocal table_lines
        if table_lines:
            close_lists()
            output.append(f'<pre class="table-block">{html.escape("\n".join(table_lines))}</pre>')
            table_lines = []

    for raw in lines:
        line = raw.rstrip()
        if line.startswith("|"):
            table_lines.append(line)
            continue
        flush_table()
        if not line:
            close_lists()
            continue
        if line.startswith("#"):
            close_lists()
            level = min(len(line) - len(line.lstrip("#")), 4)
            text = line[level:].strip()
            output.append(f'<h{level} id="{slugify(text)}">{format_inline(text)}</h{level}>')
        elif line.startswith("- "):
            if not in_ul:
                close_lists()
                output.append("<ul>")
                in_ul = True
            output.append(f"<li>{format_inline(line[2:])}</li>")
        elif re.match(r"^\d+\. ", line):
            if not in_ol:
                close_lists()
                output.append("<ol>")
                in_ol = True
            output.append(f"<li>{format_inline(re.sub(r'^\d+\. ', '', line))}</li>")
        else:
            close_lists()
            output.append(f"<p>{format_inline(line)}</p>")
    flush_table()
    close_lists()
    return "\n".join(output)


def format_inline(text: str) -> str:
    escaped = html.escape(text)

    def code_or_ref(match: re.Match[str]) -> str:
        value = match.group(1)
        if re.fullmatch(r"E\d{2}", value):
            return f'<a class="evidence-ref" href="#evidence-{value}">{value}</a>'
        return f"<code>{html.escape(value)}</code>"

    escaped = PROTECTED_CODE_RE.sub(code_or_ref, escaped)
    escaped = URL_RE.sub(lambda match: f'<a href="{html.escape(match.group(0))}">{html.escape(match.group(0))}</a>', escaped)
    return escaped


def render_evidence_card(entry: dict[str, Any]) -> str:
    urls = entry.get("source_urls", [])
    if urls:
        source_items = "".join(f'<li><a href="{html.escape(url)}">{html.escape(url)}</a></li>' for url in urls[:20])
        if len(urls) > 20:
            source_items += f"<li>+{len(urls) - 20} additional source URL(s) in source_ledger.json</li>"
    else:
        source_items = f"<li>{html.escape(entry.get('link_note', 'No external source URL recovered.'))}</li>"
    excerpt = html.escape(str(entry.get("excerpt", "")))
    link_status = html.escape(str(entry.get("link_status", "not_externally_linkable")).replace("_", "-"))
    link_status_text = html.escape(str(entry.get("link_status", "not_externally_linkable")).replace("_", " "))
    return f"""
<article class=\"evidence-card evidence-card--{link_status}\" id=\"{html.escape(entry['anchor'])}\">
  <h3>{html.escape(entry['ref'])}: {html.escape(entry['title'])}</h3>
  <p class=\"link-status mono\">Link status: {link_status_text}</p>
  <p class=\"meta\"><strong>Record:</strong> <code>{html.escape(entry['record_id'])}</code> | <strong>Source type:</strong> {html.escape(entry['source_type_label'])} | <strong>Published:</strong> {html.escape(entry['published_at'])}</p>
  <p><strong>Source reference:</strong> {html.escape(entry['source_reference'])}</p>
  <p><strong>Checksum:</strong> <code>{html.escape(entry['checksum'])}</code></p>
  <p><strong>External source links:</strong></p>
  <ul class=\"source-list\">{source_items}</ul>
  <p><strong>Excerpt:</strong> {excerpt}</p>
</article>
"""


def validate_publication(
    output_dir: Path,
    markdown_text: str,
    html_text: str,
    source_ledger: list[dict[str, Any]],
    link_integrity=None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    ledger_refs = {entry["ref"] for entry in source_ledger}
    referenced = set(EVIDENCE_REF_RE.findall(markdown_text))
    missing_refs = sorted(ref for ref in referenced if ref not in ledger_refs)
    if missing_refs:
        errors.append("missing source-ledger targets for evidence refs: " + ", ".join(missing_refs))
    for entry in source_ledger:
        if not entry.get("source_urls") and not entry.get("link_note"):
            errors.append(f"{entry['ref']} lacks external source URL or explicit not-linkable note")
    safety_files = {
        "case_dossier.md": markdown_text,
        "index.html": html_text,
        "source_ledger.json": json.dumps({"evidence": source_ledger}, sort_keys=True),
    }
    for name, text in safety_files.items():
        if WINDOWS_PATH_RE.search(text) or RELATIVE_LOCAL_PATH_RE.search(text):
            errors.append(f"{name} contains a local filesystem path")
        if SECRET_RE.search(text):
            errors.append(f"{name} contains a token-like secret")
    if "Human Review Required" not in markdown_text:
        errors.append("case dossier is missing explicit human-review pause")
    if "Sentinel" not in markdown_text:
        errors.append("case dossier is missing sentinel posture")
    if not (output_dir / "index.html").exists():
        errors.append("index.html was not created")
    if link_integrity and link_integrity.status == "FAIL":
        errors.append(
            f"link integrity check failed for {link_integrity.error_count} URL(s); see publication_manifest.json"
        )
    return {
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "checked_files": sorted(safety_files),
        "evidence_refs_checked": len(referenced),
        "source_ledger_entries": len(source_ledger),
    }


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "section"


def shorten(value: str, limit: int) -> str:
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."
