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
    sentinel_result_from_dict,
)
from .contracts import CaseRequest, EvidenceBundle, EvidenceItem, read_json, stable_id, utc_now, write_json
from .plain_language import expand_reviewer_acronyms
from .review import SOURCE_TYPE_LABELS


URL_RE = re.compile(r"https?://[^\s|)\]}\"']+", re.IGNORECASE)
WINDOWS_PATH_RE = re.compile(r"[A-Za-z]:\\[^\s|)]+")
RELATIVE_LOCAL_PATH_RE = re.compile(r"(?<![A-Za-z0-9_/-])(?:artifacts|runs|data\\live_corpus)\\[^\s|)]+", re.IGNORECASE)
ARCHIVED_COPY_RE = re.compile(r" \(archived local copy: [A-Za-z]:\\[^)]*\)")
SECRET_RE = re.compile(r"(github_pat_[A-Za-z0-9_]{20,}|ghp_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,})")
EVIDENCE_REF_RE = re.compile(r"`(E\d{2})`")
PROTECTED_CODE_RE = re.compile(r"`([^`]+)`")


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

    labels = evidence_labels(bundle)
    remaps = _archive_path_remaps(run_dir)
    source_ledger = build_source_ledger(bundle, labels, remaps)

    public_markdown = sanitize_public_text(Path(compiled.markdown_path).read_text(encoding="utf-8"))
    public_markdown_path = output_dir / "case_dossier.md"
    public_markdown_path.write_text(public_markdown, encoding="utf-8")

    source_ledger_path = output_dir / "source_ledger.json"
    write_json(source_ledger_path, {"case_id": request.case_id, "evidence": source_ledger})

    html_text = render_public_html(request, public_markdown, source_ledger, sentinel.decision.value)
    index_path = output_dir / "index.html"
    index_path.write_text(html_text, encoding="utf-8")

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

    safety = validate_publication(output_dir, public_markdown, html_text, source_ledger)
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
        direct_urls = extract_urls(item.source_uri)
        derived_urls = [] if direct_urls else infer_external_urls(item, bundle, path_remaps)
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
    if "public_statement" in value or "service_page" in value:
        return "public_statement"
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
    urls = extract_urls(item.source_uri)
    if urls:
        return "; ".join(urls)
    name = Path(str(item.source_uri)).name if item.source_uri else item.record_id
    if str(item.source_uri).startswith("local://"):
        return f"local source reference: {item.record_id}"
    return f"derived local artifact: {name or item.record_id}"


def extract_urls(value: object) -> list[str]:
    return unique_preserve_order(match.group(0).rstrip(".,;") for match in URL_RE.finditer(str(value)))


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


def render_public_html(request: CaseRequest, markdown_text: str, source_ledger: list[dict[str, Any]], sentinel_decision: str) -> str:
    body = render_markdown_fragment(markdown_text)
    cards = "\n".join(render_evidence_card(entry) for entry in source_ledger)
    title = html.escape(request.title)
    generated = html.escape(utc_now())
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>{title} | CalDS Public Case Viewer</title>
  <style>
    :root {{ color-scheme: light; --ink:#172026; --muted:#59666f; --line:#d8dee4; --soft:#f6f8fa; --accent:#0b5cad; --warn:#8a4b00; }}
    body {{ margin:0; font-family: Arial, Helvetica, sans-serif; color:var(--ink); background:#fff; line-height:1.5; }}
    header {{ background:#102a43; color:#fff; padding:28px 36px; }}
    header h1 {{ margin:0 0 8px; font-size:28px; }}
    header p {{ margin:4px 0; max-width:960px; }}
    main {{ max-width:1120px; margin:0 auto; padding:28px 24px 64px; }}
    nav {{ display:flex; flex-wrap:wrap; gap:12px; margin:18px 0 0; }}
    nav a {{ color:#fff; border:1px solid rgba(255,255,255,.5); padding:6px 10px; text-decoration:none; }}
    h1, h2, h3, h4 {{ line-height:1.25; }}
    h2 {{ margin-top:34px; padding-top:14px; border-top:1px solid var(--line); }}
    a {{ color:var(--accent); }}
    code {{ background:var(--soft); border:1px solid var(--line); padding:1px 4px; border-radius:4px; }}
    .notice {{ border-left:4px solid var(--warn); background:#fff8ec; padding:12px 14px; margin:18px 0; }}
    .dossier {{ margin-top:24px; }}
    .table-block {{ overflow:auto; background:var(--soft); border:1px solid var(--line); padding:12px; white-space:pre; }}
    .evidence-ref {{ font-weight:700; text-decoration:none; }}
    .evidence-card {{ border:1px solid var(--line); padding:16px; margin:14px 0; border-radius:6px; }}
    .evidence-card h3 {{ margin-top:0; }}
    .meta {{ color:var(--muted); font-size:14px; }}
    .source-list {{ margin:8px 0 0; padding-left:20px; }}
    footer {{ color:var(--muted); border-top:1px solid var(--line); margin-top:42px; padding-top:18px; font-size:14px; }}
  </style>
</head>
<body>
<header>
  <h1>CalDS Public Case Viewer</h1>
  <p>{title}</p>
  <p>Sentinel posture: <strong>{html.escape(sentinel_decision)}</strong>. This is an internal-review aid, not a formal finding.</p>
  <nav><a href=\"#dossier\">Dossier</a><a href=\"#source-ledger\">Source Ledger</a><a href=\"case_dossier.md\">Markdown</a><a href=\"source_ledger.json\">Source JSON</a></nav>
</header>
<main>
  <section class=\"notice\">
    <strong>Publication safety note:</strong> local file paths are omitted. Evidence labels link to source-ledger cards with official internet source links where recovered. Items without an internet source are marked explicitly.
  </section>
  <section id=\"dossier\" class=\"dossier\">{body}</section>
  <section id=\"source-ledger\">
    <h2>Source Ledger</h2>
    <p>Every evidence label used in the dossier resolves here. Original URLs are linked when available; otherwise the row states why the source is not externally linkable in this run.</p>
    {cards}
  </section>
  <footer>Generated {generated}. Human review remains required before outside-facing use.</footer>
</main>
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
    return f"""
<article class=\"evidence-card\" id=\"{html.escape(entry['anchor'])}\">
  <h3>{html.escape(entry['ref'])}: {html.escape(entry['title'])}</h3>
  <p class=\"meta\"><strong>Record:</strong> <code>{html.escape(entry['record_id'])}</code> | <strong>Source type:</strong> {html.escape(entry['source_type_label'])} | <strong>Published:</strong> {html.escape(entry['published_at'])}</p>
  <p><strong>Source reference:</strong> {html.escape(entry['source_reference'])}</p>
  <p><strong>Checksum:</strong> <code>{html.escape(entry['checksum'])}</code></p>
  <p><strong>External source links:</strong></p>
  <ul class=\"source-list\">{source_items}</ul>
  <p><strong>Excerpt:</strong> {excerpt}</p>
</article>
"""


def validate_publication(output_dir: Path, markdown_text: str, html_text: str, source_ledger: list[dict[str, Any]]) -> dict[str, Any]:
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
