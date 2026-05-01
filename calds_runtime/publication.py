from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import html
import json
import re
import urllib.parse
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
    "https://socialmodelrecovery.org/annual-report/": "https://socialmodelrecovery.org/",
    "https://socialmodelrecovery.org/annual-report/?amp": "https://socialmodelrecovery.org/",
    "https://www.socialmodelrecovery.org/about-us/": "https://socialmodelrecovery.org/services/",
    "https://www.socialmodelrecovery.org/programs/": "https://socialmodelrecovery.org/services/",
}
IRS_LOOSE_XML_RE = re.compile(r"^(https://apps\.irs\.gov/pub/epostcard/990/xml/(\d{4})/).+_public\.xml$", re.IGNORECASE)
PROPUBLICA_DOWNLOAD_EIN_RE = re.compile(r"projects\.propublica\.org/nonprofits/download-filing\?path=.*?([0-9]{2})-?([0-9]{7})_", re.IGNORECASE)


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


def load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = read_json(path)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


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
    lead_candidate = load_optional_json(artifacts_dir / "lead_candidate.json")
    completion_guard = load_optional_json(artifacts_dir / "completion_guard.json")
    review_decision = load_optional_json(artifacts_dir / "review_decision.json")
    workflow_state = load_optional_json(run_dir / "workflow_state.json")

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
    source_ledger, unverified_link_access = mark_unverified_source_urls(source_ledger, link_integrity)
    link_integrity = LinkIntegrityService().check_source_ledger(source_ledger)
    public_link_access = public_link_access_report(source_ledger, link_integrity)
    source_access = source_access_report(source_ledger, completion_guard)
    publication_context = build_publication_context(
        run_dir=run_dir,
        lead_candidate=lead_candidate,
        completion_guard=completion_guard,
        review_decision=review_decision,
        workflow_state=workflow_state,
        link_integrity=link_integrity,
        public_link_access=public_link_access,
        source_access=source_access,
        source_ledger=source_ledger,
    )

    source_ledger_path = output_dir / "source_ledger.json"
    write_json(source_ledger_path, {"case_id": request.case_id, "evidence": source_ledger})

    html_text = render_public_html(request, public_markdown, source_ledger, sentinel.decision.value, publication_context)
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

    safety = validate_publication(output_dir, public_markdown, html_text, source_ledger, link_integrity, completion_guard)
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
        "unverified_link_access": unverified_link_access,
        "public_link_access": public_link_access,
        "source_access": source_access,
        "publication_context": publication_context,
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
        link_status = "external_source_linked" if direct_urls else "derived_external_source_linked" if derived_urls else "source_access_required"
        link_note = ""
        if link_status == "derived_external_source_linked":
            link_note = "This evidence item is a parsed local artifact; external links point to upstream official or public sources used by the run."
        elif link_status == "source_access_required":
            link_note = "Source access required: this evidence item did not expose a working public URL during publication. The public packet preserves the internal evidence ID, record ID, source type, checksum, and title so a reviewer can request or attach the raw source artifact."

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
                "source_role": source_role_text(item, link_status),
                "source_exactness": source_exactness_text(link_status),
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
            row["link_status"] = "external_source_linked" if row["source_urls"] else "source_access_required"
        updated.append(row)

    return updated, {
        "repaired_public_links": len(replacements),
        "affected_evidence_refs": [ref for ref in affected_refs if ref],
        "replacements": replacements,
        "note": "Stale or renamed public URLs are repaired to working source pages before publication. Links are not removed as a substitute for repair.",
    }


def source_role_text(item: EvidenceItem, link_status: str) -> str:
    label = expand_reviewer_acronyms(SOURCE_TYPE_LABELS.get(item.source_type, item.source_type))
    if link_status == "derived_external_source_linked":
        return f"Upstream public source for a parsed {label} evidence row."
    if link_status == "source_access_required":
        return f"Source-access repair target for a {label} evidence row."
    return f"Direct public source for a {label} evidence row."


def source_exactness_text(link_status: str) -> str:
    if link_status == "derived_external_source_linked":
        return "Upstream source: the link opens the official/public dataset or document family used to create the parsed row, not necessarily the exact local row file."
    if link_status == "source_access_required":
        return "Source access required: no verified public URL is attached yet, so a reviewer must attach a working official/source-owner URL or archived source copy."
    return "Exact source link: the URL is the evidence item's direct public source reference."


def repair_public_urls(urls: Iterable[str]) -> list[str]:
    return unique_preserve_order(repair_public_url(url) for url in urls)


def repair_public_url(url: str) -> str:
    candidate = str(url).strip()
    if candidate in PUBLIC_URL_REPAIRS:
        return PUBLIC_URL_REPAIRS[candidate]
    irs_match = IRS_LOOSE_XML_RE.match(candidate)
    if irs_match:
        year = irs_match.group(2)
        return f"https://apps.irs.gov/pub/epostcard/990/xml/{year}/index_{year}.csv"
    propublica_match = PROPUBLICA_DOWNLOAD_EIN_RE.search(urllib.parse.unquote(candidate))
    if propublica_match:
        ein = f"{propublica_match.group(1)}{propublica_match.group(2)}"
        return f"https://projects.propublica.org/nonprofits/organizations/{ein}"
    return candidate


def mark_unverified_source_urls(source_ledger: list[dict[str, Any]], link_integrity) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    failed = {
        str(check.url)
        for check in getattr(link_integrity, "checks", [])
        if getattr(check, "status", "") == "ERROR"
    }
    if not failed:
        return source_ledger, {
            "unverified_public_links": 0,
            "affected_evidence_refs": [],
            "note": "All public source URLs passed link verification after deterministic repairs.",
            "items": [],
        }

    updated: list[dict[str, Any]] = []
    affected_refs: list[str] = []
    items: list[dict[str, Any]] = []
    for entry in source_ledger:
        row = dict(entry)
        urls = [str(url) for url in row.get("source_urls", [])]
        unverified = [url for url in urls if url in failed]
        if not unverified:
            updated.append(row)
            continue
        verified = [url for url in urls if url not in failed]
        affected_refs.append(str(row.get("ref", "")))
        unlinked_refs = [unlinked_url_reference(url) for url in unverified]
        existing_note = str(row.get("link_note", "")).strip()
        access_note = (
            "Source access required for unverified public URL reference(s): "
            f"{'; '.join(unlinked_refs[:6])}. These references are preserved without live hyperlinks until a working official/source-owner URL or archived copy is attached."
        )
        row["source_urls"] = verified
        row["source_reference"] = remove_unverified_urls_from_reference(str(row.get("source_reference", "")), unverified)
        row["unverified_source_references"] = unlinked_refs
        row["link_note"] = " ".join(part for part in [existing_note, access_note] if part)
        row["link_status"] = "external_source_linked" if verified else "source_access_required"
        items.append(
            {
                "ref": row.get("ref"),
                "title": row.get("title"),
                "unverified_source_references": unlinked_refs,
                "remaining_verified_url_count": len(verified),
            }
        )
        updated.append(row)
    return updated, {
        "unverified_public_links": sum(len(item["unverified_source_references"]) for item in items),
        "affected_evidence_refs": [ref for ref in affected_refs if ref],
        "items": items,
        "note": "Broken or blocked public URLs are not published as live links. They are preserved as unlinked source-access references, and the evidence row remains visible for reviewer repair.",
    }


def remove_unverified_urls_from_reference(value: str, urls: Iterable[str]) -> str:
    updated = value
    for url in urls:
        updated = updated.replace(url, unlinked_url_reference(url))
    return updated


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

    table_urls = infer_table_upstream_urls(item, bundle)
    if table_urls:
        return table_urls[:30]

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


def infer_table_upstream_urls(item: EvidenceItem, bundle: EvidenceBundle) -> list[str]:
    value = f"{item.source_type} {item.record_id} {item.title}".lower()
    if "source_extraction" not in value and "source_table" not in value:
        return []
    if "spend_vs_results" in value or "outcome_join" in value:
        wanted = {"state_homelessness_award", "outcome", "irs", "dhcs", "facility", "county"}
    elif "pdf_text_index" in value:
        wanted = {"fac", "audit", "county", "contract", "monitoring", "pdf"}
    else:
        wanted = {"fac", "audit", "irs", "state_homelessness_award", "outcome", "county", "contract", "dhcs"}
    urls: list[str] = []
    for other in bundle.items:
        if other.item_id == item.item_id:
            continue
        haystack = f"{other.source_type} {other.record_id} {other.title}".lower()
        if any(token in haystack for token in wanted):
            urls.extend(extract_urls(other.source_uri))
            urls.extend(extract_urls(other.excerpt))
    return unique_preserve_order(public_browsable_urls(urls))


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
    return f"derived private source artifact: {friendly_source_name(name or item.record_id)}"


def friendly_source_name(value: object) -> str:
    text = str(value or "source artifact")
    text = re.sub(r"\bsource_table_[A-Za-z0-9_./-]+", "source table", text)
    text = text.replace("_", " ").strip()
    return text or "source artifact"


def extract_urls(value: object) -> list[str]:
    return unique_preserve_order(match.group(0).rstrip(".,;:") for match in URL_RE.finditer(str(value)))


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
    text = WINDOWS_PATH_RE.sub("[private source artifact]", text)
    text = RELATIVE_LOCAL_PATH_RE.sub("[private source artifact]", text)
    text = re.sub(r"\bsource_table_[A-Za-z0-9_./-]+", "source table", text)
    return text


def build_publication_context(
    *,
    run_dir: Path,
    lead_candidate: dict[str, Any],
    completion_guard: dict[str, Any],
    review_decision: dict[str, Any],
    workflow_state: dict[str, Any],
    link_integrity,
    public_link_access: dict[str, Any],
    source_access: dict[str, Any],
    source_ledger: list[dict[str, Any]],
) -> dict[str, Any]:
    score_inputs = lead_candidate.get("score_inputs") if isinstance(lead_candidate.get("score_inputs"), dict) else {}
    review_value = review_decision.get("decision") or review_decision.get("status") or "PENDING"
    workflow_value = workflow_state.get("status") or "AWAITING_HUMAN_REVIEW"
    return {
        "run_label": run_dir.name,
        "workflow_state": workflow_value,
        "human_decision": review_value,
        "review_priority": lead_candidate.get("score") or score_inputs.get("final_score") or "not computed",
        "risk_severity": score_inputs.get("risk_severity_score", "not computed"),
        "source_completeness": score_inputs.get("source_completeness_score", "not computed"),
        "publication_confidence": score_inputs.get("publication_confidence_score", "not computed"),
        "completion_guard_status": completion_guard.get("status", "not computed"),
        "completion_guard_blocker_count": int(completion_guard.get("blocker_count") or 0),
        "completion_guard_hit_count": int(completion_guard.get("hit_count") or 0),
        "completion_guard_total": int(completion_guard.get("total_searches") or 0),
        "completion_guard_missing_required": list(completion_guard.get("missing_required") or []),
        "public_link_status": getattr(link_integrity, "status", "not checked"),
        "public_link_checked_count": getattr(link_integrity, "checked_url_count", 0),
        "public_link_error_count": getattr(link_integrity, "error_count", 0),
        "public_link_access": public_link_access,
        "source_access": source_access,
        "evidence_count": len(source_ledger),
        "verified_linked_evidence_count": sum(1 for entry in source_ledger if entry.get("source_urls")),
    }


def score_display(value: object) -> str:
    if isinstance(value, (int, float)):
        return f"{float(value):g} / 100"
    text = str(value or "not computed")
    return text if "/" in text or text == "not computed" else f"{text} / 100"


def source_access_status_text(context: dict[str, Any]) -> str:
    blockers = int(context.get("completion_guard_blocker_count") or 0)
    checked = int(context.get("public_link_checked_count") or 0)
    link_errors = int(context.get("public_link_error_count") or 0)
    guard_status = str(context.get("completion_guard_status", "not computed"))
    if blockers:
        return f"{checked} verified URLs; {blockers} source blocker(s)"
    if guard_status == "not computed":
        return f"{checked} verified URLs; guard not computed"
    if link_errors:
        return f"{checked} URLs checked; {link_errors} broken"
    return f"{checked} verified URLs"


def render_reviewer_panel(context: dict[str, Any]) -> str:
    missing = list(context.get("completion_guard_missing_required") or [])
    missing_items = ""
    if missing:
        visible = "".join(f"<li>{html.escape(item)}</li>" for item in missing[:6])
        if len(missing) > 6:
            visible += f"<li>+{len(missing) - 6} additional blocker(s) in the manifest.</li>"
        missing_items = f"<details><summary>Open source blockers</summary><ul>{visible}</ul></details>"
    return f"""
<section class=\"reviewer-panel\" aria-label=\"Reviewer control panel\">
  <div>
    <strong>How to use this case page</strong>
    <p>Start with the briefing, click each <span class=\"mono\">E##</span> evidence label, and verify the linked source card before relying on a claim. This page is a review aid, not a formal finding.</p>
  </div>
  <div class=\"reviewer-panel__grid\">
    <div><span>Workflow state</span><strong>{html.escape(str(context.get('workflow_state', 'AWAITING_HUMAN_REVIEW')))}</strong></div>
    <div><span>Human decision</span><strong>{html.escape(str(context.get('human_decision', 'PENDING')))}</strong></div>
    <div><span>Public links</span><strong>{html.escape(str(context.get('public_link_status', 'not checked')))} / {int(context.get('public_link_checked_count') or 0)} checked</strong></div>
    <div><span>Completion guard</span><strong>{html.escape(str(context.get('completion_guard_status', 'not computed')))} / {int(context.get('completion_guard_blocker_count') or 0)} blocker(s)</strong></div>
  </div>
{missing_items}
</section>
"""


def render_toc(markdown_text: str) -> str:
    preferred = []
    for raw in markdown_text.splitlines():
        if not raw.startswith("##"):
            continue
        level = min(len(raw) - len(raw.lstrip("#")), 3)
        if level > 3:
            continue
        text = raw[level:].strip()
        if not text or text.startswith("6.") or text.startswith("7.") or text.startswith("8."):
            continue
        preferred.append((level, text, slugify(text)))
        if len(preferred) >= 12:
            break
    links = [f'<a class=\"toc-level-{level}\" href=\"#{html.escape(slug)}\">{html.escape(text)}</a>' for level, text, slug in preferred]
    links.extend(
        [
            '<a href=\"#source-ledger\">Source Ledger</a>',
            '<a href=\"publication_manifest.json\">Publication Manifest</a>',
            '<a href=\"case_dossier.md\">Open Markdown</a>',
            '<a href=\"source_ledger.json\">Open Source JSON</a>',
        ]
    )
    return "\n".join(links)


def source_domain(urls: list[str]) -> str:
    if not urls:
        return "source access required"
    try:
        return urllib.parse.urlparse(urls[0]).netloc or urls[0]
    except Exception:
        return urls[0]


def render_source_ledger_digest(source_ledger: list[dict[str, Any]]) -> str:
    rows = []
    for entry in source_ledger[:120]:
        urls = [str(url) for url in entry.get("source_urls", [])]
        rows.append(
            "<tr>"
            f"<td><a class=\"evidence-ref\" href=\"#{html.escape(str(entry.get('anchor', '')))}\">{html.escape(str(entry.get('ref', '')))}</a></td>"
            f"<td>{html.escape(shorten(str(entry.get('title', '')), 96))}</td>"
            f"<td>{html.escape(str(entry.get('source_type_label', entry.get('source_type', ''))))}</td>"
            f"<td>{html.escape(source_domain(urls))}</td>"
            f"<td>{html.escape(str(entry.get('link_status', '')).replace('_', ' '))}</td>"
            "</tr>"
        )
    more = ""
    if len(source_ledger) > 120:
        more = f"<p class=\"ledger-note\">Showing the first 120 evidence rows; full details remain in source_ledger.json.</p>"
    return f"""
<div class=\"ledger-digest\" aria-label=\"Source ledger digest\">
  <h3>Source Ledger Digest</h3>
  <p>This scan layer shows what each evidence card opens before the full audit cards below.</p>
  <div class=\"table-scroll\">
    <table>
      <thead><tr><th>Ref</th><th>Evidence</th><th>Source type</th><th>Opens to</th><th>Status</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
  </div>
{more}
</div>
"""


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
a:focus-visible, button:focus-visible, summary:focus-visible {
  outline: 3px solid var(--audit-amber);
  outline-offset: 3px;
}
.skip-link {
  position: absolute;
  left: 16px;
  top: -60px;
  z-index: 10;
  padding: 10px 12px;
  color: var(--ink);
  background: var(--audit-amber);
  font-family: "IBM Plex Mono", Consolas, monospace;
  font-size: 12px;
}
.skip-link:focus { top: 12px; }
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
.case-id {
  margin: 14px 0 0;
  color: rgba(255, 249, 237, .72);
  font-family: "IBM Plex Mono", Consolas, monospace;
  font-size: 12px;
  overflow-wrap: anywhere;
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
  overflow-wrap: anywhere;
}
.print-button {
  border: 1px solid rgba(255, 249, 237, .35);
  background: rgba(255, 249, 237, .12);
  color: var(--paper-2);
  cursor: pointer;
  padding: 8px 11px;
  font-family: "IBM Plex Mono", Consolas, monospace;
  font-size: 12px;
  text-transform: uppercase;
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
.reviewer-panel {
  margin: 0 0 24px;
  padding: 20px;
  background: #fffdf5;
  border: 2px solid rgba(47, 109, 85, .35);
  box-shadow: 8px 8px 0 rgba(47, 109, 85, .12);
}
.reviewer-panel p { margin: 8px 0 0; }
.reviewer-panel__grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}
.reviewer-panel__grid div {
  padding: 10px;
  background: rgba(243, 234, 216, .72);
  border: 1px solid var(--line);
}
.reviewer-panel__grid span {
  display: block;
  color: var(--muted);
  font-family: "IBM Plex Mono", Consolas, monospace;
  font-size: 11px;
  text-transform: uppercase;
}
.reviewer-panel__grid strong { overflow-wrap: anywhere; }
.reviewer-panel details {
  margin-top: 12px;
  border-top: 1px solid var(--line);
  padding-top: 10px;
}
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
.ledger-digest {
  margin: 18px 0 26px;
  padding: 16px;
  background: rgba(243, 234, 216, .7);
  border: 1px solid var(--line);
}
.ledger-digest h3 { margin-top: 0; }
.table-scroll { overflow-x: auto; }
.ledger-digest table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}
.ledger-digest th, .ledger-digest td {
  padding: 8px;
  border-bottom: 1px solid var(--line);
  text-align: left;
  vertical-align: top;
}
.ledger-digest th {
  font-family: "IBM Plex Mono", Consolas, monospace;
  font-size: 11px;
  text-transform: uppercase;
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
.evidence-card--source-access-required::before { background: var(--audit-amber); }
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
.source-role {
  margin: 8px 0;
  padding: 10px;
  background: rgba(33, 79, 114, .08);
  border-left: 4px solid var(--civic-blue);
}
.repro-details {
  margin: 12px 0;
  padding: 10px;
  background: rgba(25, 21, 15, .04);
  border: 1px solid var(--line);
}
.repro-details summary {
  cursor: pointer;
  font-family: "IBM Plex Mono", Consolas, monospace;
  font-size: 12px;
  text-transform: uppercase;
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
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  *, *::before, *::after {
    animation-duration: .001ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: .001ms !important;
  }
}
@media (max-width: 880px) {
  .status-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .case-shell { grid-template-columns: 1fr; }
  .case-rail { position: static; }
  .reviewer-panel__grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 560px) {
  .case-hero__inner, .case-shell { padding-left: 16px; padding-right: 16px; }
  .status-strip { grid-template-columns: 1fr; }
  .reviewer-panel__grid { grid-template-columns: 1fr; }
  .dossier, #source-ledger { padding: 18px; }
  .dossier p, .dossier li { font-size: 16px; }
}
@media print {
  body { background: #fff; color: #000; }
  .case-hero, .case-rail, .case-nav { background: #fff; color: #000; border: 0; }
  .case-nav, .print-button, .skip-link { display: none; }
  .case-shell { display: block; max-width: none; padding: 0; }
  .dossier, #source-ledger, .notice { box-shadow: none; border-color: #999; }
  .reviewer-panel, .evidence-card { break-inside: avoid; box-shadow: none; }
  a[href^="http"]::after { content: " (" attr(href) ")"; font-size: 10px; }
}
"""


def render_public_html(
    request: CaseRequest,
    markdown_text: str,
    source_ledger: list[dict[str, Any]],
    sentinel_decision: str,
    context: dict[str, Any] | None = None,
) -> str:
    context = context or {}
    body = render_markdown_fragment(markdown_text)
    reviewer_panel = render_reviewer_panel(context)
    toc_links = render_toc(markdown_text)
    ledger_digest = render_source_ledger_digest(source_ledger)
    cards = "\n".join(render_evidence_card(entry) for entry in source_ledger)
    title = html.escape(request.title)
    generated = html.escape(utc_now())
    css = public_case_css()
    evidence_count = len(source_ledger)
    case_id = html.escape(request.case_id)
    access_status = source_access_status_text(context)
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
<a class=\"skip-link\" href=\"#dossier\">Skip to case briefing</a>
<header class=\"case-hero\">
  <div class=\"case-hero__inner\">
    <p class=\"eyebrow\">California Evidence Room</p>
    <h1>{title}</h1>
    <p class=\"case-title\">Public-safe source-cited review packet. Human review required; not a formal finding.</p>
    <p class=\"case-id\">Case ID: {case_id} | Generated: {generated} | Run: {html.escape(str(context.get('run_label', 'not provided')))}</p>
    <div class=\"status-strip\" aria-label=\"Case publication status\">
      <div class=\"status-tile\"><strong>Sentinel posture</strong><span>{html.escape(sentinel_decision)}</span></div>
      <div class=\"status-tile\"><strong>Review priority</strong><span>{html.escape(score_display(context.get('review_priority')))}</span></div>
      <div class=\"status-tile\"><strong>Evidence ledger</strong><span>{evidence_count} records</span></div>
      <div class=\"status-tile\"><strong>Source status</strong><span>{html.escape(access_status)}</span></div>
    </div>
    <nav class=\"case-nav\" aria-label=\"Case links\">
      <a href=\"#dossier\">Briefing</a>
      <a href=\"#source-ledger\">Source Ledger</a>
      <a href=\"case_dossier.md\">Markdown</a>
      <a href=\"source_ledger.json\">Source JSON</a>
      <a href=\"publication_manifest.json\">Manifest</a>
      <button class=\"print-button\" type=\"button\" onclick=\"window.print()\">Print / Save PDF</button>
    </nav>
  </div>
</header>
<main id=\"case-main\" class=\"case-shell\">
  <aside class=\"case-rail\" aria-label=\"Case navigation\">
    <h2>Read Order</h2>
    {toc_links}
  </aside>
  <div class=\"case-main\">
{reviewer_panel}
  <section class=\"notice\">
    <div><strong>Publication safety note:</strong> This page is a public-safe review aid, not a formal finding. Local file paths are omitted. Evidence labels jump to source-ledger cards; source rows either link to verified internet sources or state that source access is still required and must be resolved before the packet is treated as complete.</div>
  </section>
  <section id=\"dossier\" class=\"dossier\">{body}</section>
  <section id=\"source-ledger\">
    <h2>Source Ledger</h2>
    <p>Every evidence label used in the dossier resolves here. Original URLs are linked when available. If a row lacks a verified internet source, it is marked as source access required rather than treated as complete.</p>
{ledger_digest}
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
    protected: list[tuple[str, str]] = []

    def code_or_ref(match: re.Match[str]) -> str:
        value = match.group(1)
        if re.fullmatch(r"E\d{2}", value):
            replacement = f'<a class="evidence-ref" href="#evidence-{value}" aria-label="Open evidence {value} in source ledger">{value}</a>'
        else:
            replacement = f"<code>{html.escape(value)}</code>"
        token = f"@@CALDS_CODE_{len(protected)}@@"
        protected.append((token, replacement))
        return token

    escaped = PROTECTED_CODE_RE.sub(code_or_ref, escaped)
    escaped = URL_RE.sub(linkify_public_url, escaped)
    for token, replacement in protected:
        escaped = escaped.replace(token, replacement)
    return escaped


def linkify_public_url(match: re.Match[str]) -> str:
    raw = match.group(0)
    cleaned = raw.rstrip(".,;:")
    suffix = raw[len(cleaned):]
    safe_url = html.escape(cleaned)
    return f'<a href="{safe_url}">{safe_url}</a>{html.escape(suffix)}'


def render_evidence_card(entry: dict[str, Any]) -> str:
    urls = entry.get("source_urls", [])
    link_note = str(entry.get("link_note", "")).strip()
    if urls:
        source_items = "".join(f'<li><a href="{html.escape(url)}">{html.escape(url)}</a></li>' for url in urls[:20])
        if len(urls) > 20:
            source_items += f"<li>+{len(urls) - 20} additional source URL(s) in source_ledger.json</li>"
        if link_note:
            source_items += f"<li>{html.escape(link_note)}</li>"
    else:
        source_items = f"<li>{html.escape(link_note or 'No external source URL recovered.')}</li>"
    excerpt = html.escape(str(entry.get("excerpt", "")))
    link_status = html.escape(str(entry.get("link_status", "source_access_required")).replace("_", "-"))
    link_status_text = html.escape(str(entry.get("link_status", "source_access_required")).replace("_", " "))
    display_record = html.escape(friendly_source_name(entry.get("record_id", "")))
    return f"""
<article class=\"evidence-card evidence-card--{link_status}\" id=\"{html.escape(entry['anchor'])}\">
  <h3>{html.escape(entry['ref'])}: {html.escape(entry['title'])}</h3>
  <p class=\"link-status mono\">Link status: {link_status_text}</p>
  <p class=\"source-role\"><strong>What this opens:</strong> {html.escape(str(entry.get('source_role', 'Public source for this evidence row.')))} {html.escape(str(entry.get('source_exactness', '')))}</p>
  <p class=\"meta\"><strong>Source type:</strong> {html.escape(entry['source_type_label'])} | <strong>Published:</strong> {html.escape(entry['published_at'])}</p>
  <p><strong>External source links:</strong></p>
  <ul class=\"source-list\">{source_items}</ul>
  <details class=\"repro-details\">
    <summary>Audit identifiers</summary>
    <p><strong>Record:</strong> <code>{display_record}</code></p>
    <p><strong>Source reference:</strong> {html.escape(entry['source_reference'])}</p>
    <p><strong>Checksum:</strong> <code>{html.escape(entry['checksum'])}</code></p>
  </details>
  <p><strong>Excerpt:</strong> {excerpt}</p>
</article>
"""


def validate_publication(
    output_dir: Path,
    markdown_text: str,
    html_text: str,
    source_ledger: list[dict[str, Any]],
    link_integrity=None,
    completion_guard: dict[str, Any] | None = None,
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
            errors.append(f"{entry['ref']} lacks external source URL or explicit source-access note")
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
        "source_access": source_access_report(source_ledger, completion_guard),
    }


def public_link_access_report(source_ledger: list[dict[str, Any]], link_integrity=None) -> dict[str, Any]:
    missing = [entry for entry in source_ledger if not entry.get("source_urls")]
    return {
        "complete": not missing and getattr(link_integrity, "status", "PASS") != "FAIL",
        "status": getattr(link_integrity, "status", "not checked"),
        "checked_url_count": getattr(link_integrity, "checked_url_count", 0),
        "error_count": getattr(link_integrity, "error_count", 0),
        "warning_count": getattr(link_integrity, "warning_count", 0),
        "evidence_rows_without_verified_public_link": len(missing),
        "note": "Public link access means every published evidence row has a verified browser-openable URL or a visible source-access note. It is not the same as raw-source or completion-guard access.",
    }


def source_access_report(source_ledger: list[dict[str, Any]], completion_guard: dict[str, Any] | None = None) -> dict[str, Any]:
    completion_guard = completion_guard or {}
    required = [
        {
            "ref": entry.get("ref"),
            "record_id": entry.get("record_id"),
            "source_type": entry.get("source_type"),
            "title": entry.get("title"),
            "reason": entry.get("link_note") or "No verified public source URL is attached.",
        }
        for entry in source_ledger
        if not entry.get("source_urls")
    ]
    partial = [
        {
            "ref": entry.get("ref"),
            "record_id": entry.get("record_id"),
            "source_type": entry.get("source_type"),
            "title": entry.get("title"),
            "unverified_source_references": entry.get("unverified_source_references", []),
            "remaining_verified_url_count": len(entry.get("source_urls", [])),
        }
        for entry in source_ledger
        if entry.get("unverified_source_references")
    ]
    guard_blockers = int(completion_guard.get("blocker_count") or 0)
    guard_missing = list(completion_guard.get("missing_required") or [])
    guard_status = completion_guard.get("status") or "not computed"
    return {
        "complete": not required and guard_blockers == 0 and bool(completion_guard),
        "public_link_access_complete": not required,
        "completion_guard_access_complete": guard_blockers == 0 and bool(completion_guard),
        "completion_guard_status": guard_status,
        "completion_guard_blocker_count": guard_blockers,
        "completion_guard_missing_required": guard_missing,
        "source_access_required_count": len(required),
        "partial_source_access_issue_count": len(partial),
        "affected_evidence_refs": [str(entry["ref"]) for entry in required if entry.get("ref")],
        "items": required,
        "partial_items": partial,
        "note": "Source access combines public-link access with completion-guard access. Verified links do not clear unresolved acquisition blockers, and missing source access is never treated as completion.",
    }


def publish_site_index(site_dir: Path) -> Path:
    site_dir = Path(site_dir).resolve()
    cases_dir = site_dir / "cases"
    case_cards: list[dict[str, Any]] = []
    for manifest_path in sorted(cases_dir.glob("*/publication_manifest.json")):
        case_dir = manifest_path.parent
        manifest = load_optional_json(manifest_path)
        dossier_text = (case_dir / "case_dossier.md").read_text(encoding="utf-8", errors="ignore") if (case_dir / "case_dossier.md").exists() else ""
        case_cards.append(
            {
                "case_id": manifest.get("case_id", case_dir.name),
                "title": extract_case_title(dossier_text, str(manifest.get("case_id", case_dir.name))),
                "bottom_line": extract_bottom_line(dossier_text),
                "href": f"cases/{case_dir.name}/",
                "generated_at": manifest.get("generated_at", "not provided"),
                "sentinel": manifest.get("sentinel_decision", "not provided"),
                "review_required": bool(manifest.get("human_review_required", True)),
                "link_status": (manifest.get("link_integrity") or {}).get("status", "not checked"),
                "checked_urls": (manifest.get("link_integrity") or {}).get("checked_url_count", 0),
                "source_access": manifest.get("source_access") or {},
                "context": manifest.get("publication_context") or {},
            }
        )
    cards_html = "\n".join(render_case_index_card(card) for card in case_cards) or "<p>No published cases found.</p>"
    generated = html.escape(utc_now())
    css = public_case_css() + """
.index-main { max-width: 1220px; margin: 0 auto; padding: 30px 24px 72px; }
.case-index-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 18px; }
.case-index-card { background: rgba(255, 249, 237, .92); border: 1px solid var(--line); box-shadow: var(--shadow); padding: 20px; }
.case-index-card h2 { margin-top: 0; }
.case-index-card__meta { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin: 12px 0; }
.case-index-card__meta div { padding: 8px; background: rgba(243, 234, 216, .72); border: 1px solid var(--line); }
.case-index-card__meta span { display: block; color: var(--muted); font-family: \"IBM Plex Mono\", Consolas, monospace; font-size: 11px; text-transform: uppercase; }
.case-index-card__links { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
.case-index-card__links a { border: 1px solid var(--line); padding: 7px 9px; background: #fffdf5; font-family: \"IBM Plex Mono\", Consolas, monospace; font-size: 12px; text-decoration: none; text-transform: uppercase; }
"""
    html_text = f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>CalDS Public Case Index</title>
  <style>{css}</style>
</head>
<body>
<a class=\"skip-link\" href=\"#cases\">Skip to cases</a>
<header class=\"case-hero\">
  <div class=\"case-hero__inner\">
    <p class=\"eyebrow\">California Evidence Room</p>
    <h1>CalDS Public Case Index</h1>
    <p class=\"case-title\">Source-cited public review packets for state and local government reviewers. Each case remains a review aid, not a formal finding.</p>
    <p class=\"case-id\">Generated: {generated}</p>
  </div>
</header>
<main id=\"cases\" class=\"index-main\">
  <section class=\"notice\"><div><strong>How to read this index:</strong> open a case, read the executive snapshot, then audit the linked evidence labels in the source ledger. Link integrity and source-access status are shown per case.</div></section>
  <section class=\"case-index-grid\">{cards_html}</section>
</main>
<footer>Generated {generated}. Human review remains required before outside-facing use.</footer>
</body>
</html>
"""
    output = site_dir / "index.html"
    output.write_text(html_text, encoding="utf-8", newline="\n")
    return output


def extract_case_title(markdown_text: str, fallback: str) -> str:
    for line in markdown_text.splitlines():
        if line.startswith("# Case Dossier:"):
            return line.split(":", 1)[1].strip()
    return fallback


def extract_bottom_line(markdown_text: str) -> str:
    for line in markdown_text.splitlines():
        if line.startswith("Bottom line:"):
            return shorten(line.replace("Bottom line:", "").strip(), 360)
    return "Open the case packet for the source-cited executive snapshot."


def render_case_index_card(card: dict[str, Any]) -> str:
    source_access = card.get("source_access") or {}
    context = card.get("context") or {}
    blocker_count = source_access.get("completion_guard_blocker_count", context.get("completion_guard_blocker_count", 0))
    source_text = f"{card.get('checked_urls', 0)} verified URL(s); {blocker_count} completion blocker(s)"
    href = str(card.get("href", "#"))
    return f"""
<article class=\"case-index-card\">
  <h2><a href=\"{html.escape(href)}\">{html.escape(str(card.get('title', card.get('case_id', 'Case'))))}</a></h2>
  <p>{html.escape(str(card.get('bottom_line', '')))}</p>
  <div class=\"case-index-card__meta\">
    <div><span>Case ID</span><strong>{html.escape(str(card.get('case_id', '')))}</strong></div>
    <div><span>Generated</span><strong>{html.escape(str(card.get('generated_at', 'not provided')))}</strong></div>
    <div><span>Sentinel</span><strong>{html.escape(str(card.get('sentinel', 'not provided')))}</strong></div>
    <div><span>Links and source access</span><strong>{html.escape(str(card.get('link_status', 'not checked')))} / {html.escape(source_text)}</strong></div>
  </div>
  <p><strong>Public posture:</strong> {'Human review required; not a formal finding.' if card.get('review_required', True) else 'Review state not provided.'}</p>
  <div class=\"case-index-card__links\">
    <a href=\"{html.escape(href)}\">Open Viewer</a>
    <a href=\"{html.escape(href)}case_dossier.md\">Markdown</a>
    <a href=\"{html.escape(href)}source_ledger.json\">Source Ledger</a>
    <a href=\"{html.escape(href)}publication_manifest.json\">Manifest</a>
  </div>
</article>
"""


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "section"


def shorten(value: str, limit: int) -> str:
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."
