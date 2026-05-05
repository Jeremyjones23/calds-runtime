from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from .contracts import read_json, stable_id, utc_now, write_json


CASE_METADATA: dict[str, dict[str, str]] = {
    "live_ca_homelessness_top15_2026_04_29": {
        "title": "California homelessness nonprofit triage",
        "short_title": "Statewide homelessness",
        "issue_area": "Homelessness services",
        "geography": "California",
    },
    "live_ca_sf_homelessness_complex": {
        "title": "San Francisco homelessness nonprofit complex",
        "short_title": "San Francisco homelessness",
        "issue_area": "Homelessness services",
        "geography": "San Francisco",
    },
    "live_ca_recovery_ngos_2026_04_24": {
        "title": "California recovery and treatment nonprofits",
        "short_title": "Recovery and treatment",
        "issue_area": "Recovery and treatment services",
        "geography": "California",
    },
}

LEGAL_TERMS = (
    "fraud",
    "abuse",
    "criminal",
    "illegal",
    "convicted",
    "violation",
    "settlement",
    "prosecution",
    "indictment",
    "charged",
)

PUBLIC_INTERNAL_PHRASES = (
    "row count",
    "source table",
    "source dataset",
    "parser",
    "workflow state",
    "sentinel",
    "risk matrix",
    "source completeness",
    "low-linkage",
    "publication confidence",
    "review packet",
    "WFA",
)

SECRET_OR_PRIVATE_RE = re.compile(
    r"(github_pat_[A-Za-z0-9_]{20,}|ghp_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}|C:\\Users\\|data\\live_corpus\\|runs\\)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class EditorialExport:
    output_dir: str
    files: dict[str, str]
    verification_manifest: dict[str, Any]


def _clean_text(value: str) -> str:
    text = re.sub(r"`([^`]+)`", r"\1", value)
    text = text.replace("CalDS flags", "CalDS found a red flag for")
    text = text.replace("sentinel posture", "legal-language check")
    text = text.replace("Sentinel posture", "Legal-language check")
    text = text.replace("workflow state", "case status")
    text = text.replace("Workflow state", "Case status")
    text = text.replace("review packet", "public case story")
    text = text.replace("risk matrix", "red flags")
    text = text.replace("source completeness", "records we still could not get")
    text = text.replace("publication confidence", "how safe this is to publish")
    text = text.replace("WFA", "possible fraud, waste, or abuse")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _first_sentence(value: str, max_chars: int = 320) -> str:
    cleaned = _clean_text(value)
    if len(cleaned) <= max_chars:
        return cleaned
    match = re.search(r"(?<=[.!?])\s+", cleaned[: max_chars + 80])
    if match:
        return cleaned[: match.start()].strip()
    return cleaned[:max_chars].rstrip(" ,;:") + "..."


def _extract_section(markdown: str, heading: str) -> str:
    pattern = re.compile(rf"^##\s+\d+\.\s+{re.escape(heading)}\s*$", re.MULTILINE)
    match = pattern.search(markdown)
    if not match:
        return ""
    rest = markdown[match.end() :]
    next_match = re.search(r"^##\s+\d+\.\s+", rest, re.MULTILINE)
    return rest[: next_match.start()] if next_match else rest


def _extract_bullets(section: str, limit: int = 8) -> list[str]:
    bullets: list[str] = []
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            text = _clean_text(stripped[2:])
            if text and len(text) > 12:
                bullets.append(text)
        if len(bullets) >= limit:
            break
    return bullets


def _extract_deep_review_entities(markdown: str) -> list[str]:
    entities: list[str] = []
    in_deep_review = False
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped == "### Deep-Review Entities":
            in_deep_review = True
            continue
        if in_deep_review and stripped.startswith("### ") and stripped != "### Deep-Review Entities":
            break
        if in_deep_review and stripped.startswith("#### "):
            entities.append(_clean_text(stripped[5:]))
    return entities


def _case_summary_from_markdown(case_id: str, markdown: str, manifest: dict[str, Any], ledger: dict[str, Any]) -> dict[str, Any]:
    metadata = CASE_METADATA.get(
        case_id,
        {
            "title": case_id.replace("_", " ").title(),
            "short_title": case_id.replace("_", " ").title(),
            "issue_area": "Public oversight",
            "geography": "California",
        },
    )
    snapshot = _extract_section(markdown, "Executive Snapshot")
    one_page = _extract_section(markdown, "Case In One Page")
    does_not_prove = _extract_section(markdown, "What This Does Not Prove") or snapshot
    bullets = _extract_bullets(snapshot, 12)
    found_first = [item for item in bullets if item.startswith("E")][:3]
    selected_entities = _extract_deep_review_entities(markdown)
    if not selected_entities:
        for bullet in bullets:
            if bullet.lower().startswith("entities selected"):
                selected_entities = [item.strip(" .") for item in bullet.split(":", 1)[-1].split(",") if item.strip()]
                break
    public_summary = _first_sentence(one_page or snapshot, 380)
    blockers = manifest.get("source_access", {}).get("total_source_blocker_count", 0)
    link_count = manifest.get("public_link_access", {}).get("checked_url_count") or manifest.get("link_integrity", {}).get("checked_url_count", 0)
    return {
        "case_id": case_id,
        "title": metadata["title"],
        "short_title": metadata["short_title"],
        "issue_area": metadata["issue_area"],
        "geography": metadata["geography"],
        "public_summary": public_summary,
        "strongest_supported_flags": found_first or _extract_bullets(one_page, 3),
        "what_this_does_not_prove": _extract_bullets(does_not_prove, 5),
        "source_link_count": link_count,
        "source_blocker_count": blockers,
        "entities": selected_entities,
        "case_url": f"cases/{case_id}/",
        "legal_language_check": str(manifest.get("sentinel_decision", "not provided")).replace("_", " ").title(),
        "citation_status": manifest.get("citation_verification", {}).get("status", "not checked"),
        "link_status": manifest.get("link_integrity", {}).get("status", "not checked"),
        "evidence_count": len(ledger.get("evidence", [])),
    }


def _claim_type_for_evidence(item: dict[str, Any]) -> str:
    text = f"{item.get('source_type', '')} {item.get('source_type_label', '')} {item.get('excerpt', '')}".lower()
    if any(term in text for term in ("not recover", "gap", "blocker", "missing", "did not parse")):
        return "gap"
    if any(term in text for term in ("charged", "violation", "audit", "finding", "material weakness", "deficiency")):
        return "verified fact"
    if any(term in text for term in ("increased", "decreased", "$", "revenue", "expenses", "award")):
        return "measured comparison"
    return "verified fact"


def _legal_status_for_claim(sentence: str, urls: list[str]) -> str:
    lower = sentence.lower()
    used = [term for term in LEGAL_TERMS if term in lower]
    if not used:
        return "No legal term used"
    official = any("justice.gov" in url or "sf.gov" in url or "fhfaoig.gov" in url for url in urls)
    if official:
        return "Legal term appears with official-source link"
    return "Legal term requires review before stronger wording"


def _extract_entity_from_item(item: dict[str, Any], case_entities: list[str]) -> str:
    text = f"{item.get('title', '')} {item.get('excerpt', '')}"
    for entity in sorted(case_entities, key=len, reverse=True):
        if entity and entity.lower() in text.lower():
            return entity
    title = str(item.get("title", ""))
    if ":" in title:
        return _clean_text(title.split(":", 1)[-1].split("(")[0])
    return ""


def _build_claims_and_sources(case_summaries: list[dict[str, Any]], ledgers: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    claims: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    entities: dict[str, dict[str, Any]] = {}
    money_rows: list[dict[str, Any]] = []

    for summary in case_summaries:
        case_id = summary["case_id"]
        case_entities = list(summary.get("entities", []))
        for entity in case_entities:
            entity_id = stable_id("entity", entity)
            entities.setdefault(
                entity_id,
                {
                    "entity_id": entity_id,
                    "display_name": entity,
                    "case_ids": [],
                    "issue_area": summary["issue_area"],
                    "geography": summary["geography"],
                    "what_it_claims_to_do": "CalDS shows only source-backed service descriptions. If no public service page was recovered, the public story says so.",
                    "public_money_found": [],
                    "official_records_found": [],
                    "red_flags": [],
                    "caveats": [],
                    "source_ids": [],
                },
            )
            if case_id not in entities[entity_id]["case_ids"]:
                entities[entity_id]["case_ids"].append(case_id)

        for item in ledgers[case_id].get("evidence", []):
            urls = [str(url) for url in item.get("source_urls", []) if str(url).startswith("http")]
            sentence = _first_sentence(str(item.get("excerpt", "")), 360)
            claim_id = stable_id("claim", case_id, str(item.get("ref", "")), sentence)
            source_id = stable_id("source", case_id, str(item.get("record_id", "")), str(item.get("source_reference", "")))
            entity = _extract_entity_from_item(item, case_entities)
            claim = {
                "claim_id": claim_id,
                "public_sentence": sentence,
                "plain_language_sentence": sentence,
                "claim_type": _claim_type_for_evidence(item),
                "case_id": case_id,
                "entity": entity,
                "source_family": item.get("source_type_label") or item.get("source_type", "Public record"),
                "evidence_ids": [item.get("ref", ""), item.get("internal_evidence_id", "")],
                "source_urls": urls,
                "source_excerpt": _first_sentence(str(item.get("excerpt", "")), 520),
                "date_of_source": item.get("published_at", ""),
                "retrieval_date": item.get("published_at", ""),
                "confidence": "source-backed" if urls else "blocked-source",
                "public_language_allowed": bool(urls or item.get("link_note")),
                "legal_language_status": _legal_status_for_claim(sentence, urls),
                "meaning_preservation_status": "plain sentence is derived from evidence excerpt",
                "legal_language_notes": "Red flag, not verdict. Do not treat this claim as a legal finding.",
            }
            claims.append(claim)
            source = {
                "source_id": source_id,
                "case_id": case_id,
                "evidence_ids": claim["evidence_ids"],
                "claim_ids": [claim_id],
                "title": item.get("title", ""),
                "source_type": item.get("source_type", ""),
                "source_family": item.get("source_type_label") or item.get("source_type", "Public record"),
                "url": urls[0] if urls else "",
                "final_url": urls[0] if urls else "",
                "http_status": "verified in publication manifest" if urls else "blocked",
                "content_type": "",
                "retrieval_date": item.get("published_at", ""),
                "checksum": item.get("checksum", ""),
                "archive_status": "Live" if urls else "Blocked",
                "blocker_reason": item.get("link_note", "") if not urls else "",
                "supports": sentence,
            }
            sources.append(source)
            if entity:
                entity_id = stable_id("entity", entity)
                entities.setdefault(
                    entity_id,
                    {
                        "entity_id": entity_id,
                        "display_name": entity,
                        "case_ids": [case_id],
                        "issue_area": summary["issue_area"],
                        "geography": summary["geography"],
                        "what_it_claims_to_do": "",
                        "public_money_found": [],
                        "official_records_found": [],
                        "red_flags": [],
                        "caveats": [],
                        "source_ids": [],
                    },
                )
                entities[entity_id]["source_ids"].append(source_id)
                if "$" in sentence:
                    entities[entity_id]["public_money_found"].append(sentence)
                if any(term in sentence.lower() for term in ("audit", "charged", "violation", "finding", "official")):
                    entities[entity_id]["official_records_found"].append(sentence)
                if claim["claim_type"] in {"gap", "measured comparison"} or "red flag" in sentence.lower():
                    entities[entity_id]["red_flags"].append(sentence)
                if claim["claim_type"] == "gap":
                    entities[entity_id]["caveats"].append(sentence)
            amounts = re.findall(r"\$[0-9][0-9,]*(?:\.[0-9]+)?", sentence)
            years = re.findall(r"\b(20[0-9]{2})\b", sentence)
            for amount in amounts[:3]:
                money_rows.append(
                    {
                        "case_id": case_id,
                        "entity_id": stable_id("entity", entity) if entity else "",
                        "year": years[0] if years else "",
                        "amount": amount,
                        "amount_type": "public amount or filing amount named in cited record",
                        "source_id": source_id,
                        "claim_id": claim_id,
                        "calculation_note": "Amount is published only as it appears in the cited evidence excerpt.",
                        "is_partial": True,
                        "missing_records_note": "Treat as partial unless the case source says it is a full total.",
                    }
                )
            if not urls:
                blockers.append(
                    {
                        "blocker_id": stable_id("blocker", case_id, str(item.get("ref", "")), sentence),
                        "case_id": case_id,
                        "entity": entity,
                        "source_family": source["source_family"],
                        "what_was_sought": item.get("title", ""),
                        "why_it_matters": "This record affects what CalDS can safely say in public.",
                        "status": "Blocked",
                        "next_human_step": item.get("link_note", "Request or recover a public source before relying on this claim."),
                    }
                )
    return claims, sources, list(entities.values()), money_rows, blockers


def _readability_summary(texts: list[str]) -> dict[str, Any]:
    sentences = 0
    words = 0
    long_sentences = 0
    for text in texts:
        sentence_parts = [part.strip() for part in re.split(r"[.!?]+", text) if part.strip()]
        for part in sentence_parts:
            count = len(re.findall(r"\b[A-Za-z0-9$][A-Za-z0-9,$'-]*\b", part))
            if count:
                sentences += 1
                words += count
                if count > 28:
                    long_sentences += 1
    avg = round(words / max(sentences, 1), 2)
    return {
        "target": "fifth_sixth_grade_plain_language",
        "sentence_count": sentences,
        "word_count": words,
        "average_words_per_sentence": avg,
        "long_sentence_count": long_sentences,
        "status": "PASS" if avg <= 24 and long_sentences <= max(8, sentences // 8) else "PASS_WITH_WARNINGS",
    }


def _scan_public_payload(payloads: dict[str, Any]) -> dict[str, Any]:
    text = "\n".join(str(value) for value in payloads.values())
    banned_hits = sorted({phrase for phrase in PUBLIC_INTERNAL_PHRASES if phrase.lower() in text.lower()})
    private_hits = sorted(set(SECRET_OR_PRIVATE_RE.findall(text)))
    return {
        "banned_internal_phrase_hits": banned_hits,
        "private_or_secret_hits": private_hits,
        "status": "PASS" if not private_hits and not banned_hits else "FAIL",
    }


def export_editorial_public_data(site_dir: Path, output_dir: Path) -> EditorialExport:
    cases_dir = site_dir / "cases"
    if not cases_dir.exists():
        raise FileNotFoundError(f"Missing cases directory: {cases_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    case_summaries: list[dict[str, Any]] = []
    ledgers: dict[str, dict[str, Any]] = {}
    manifest_status: list[dict[str, Any]] = []
    for case_path in sorted(path for path in cases_dir.iterdir() if path.is_dir()):
        case_id = case_path.name
        dossier_path = case_path / "case_dossier.md"
        ledger_path = case_path / "source_ledger.json"
        manifest_path = case_path / "publication_manifest.json"
        if not dossier_path.exists() or not ledger_path.exists() or not manifest_path.exists():
            continue
        markdown = dossier_path.read_text(encoding="utf-8")
        ledger = read_json(ledger_path)
        manifest = read_json(manifest_path)
        summary = _case_summary_from_markdown(case_id, markdown, manifest, ledger)
        case_summaries.append(summary)
        ledgers[case_id] = ledger
        manifest_status.append(
            {
                "case_id": case_id,
                "citation_status": manifest.get("citation_verification", {}).get("status"),
                "link_status": manifest.get("link_integrity", {}).get("status"),
                "safety_passed": manifest.get("safety", {}).get("passed"),
                "source_blocker_count": manifest.get("source_access", {}).get("total_source_blocker_count", 0),
            }
        )

    claims, sources, entities, money_rows, blockers = _build_claims_and_sources(case_summaries, ledgers)
    evidence_by_case = Counter(claim["case_id"] for claim in claims)
    public_cases = {
        "publication_id": stable_id("editorial_publication", utc_now(), str(len(claims))),
        "generated_at": utc_now(),
        "title": "The California Case File",
        "dek": "CalDS checked public records across homelessness, recovery, and treatment nonprofit cases. The records raise questions about money, outcomes, missing oversight records, and public accountability. This is a red flag, not a verdict.",
        "cases": case_summaries,
        "site_language_level": "fifth_sixth_grade_plain_language",
        "public_policy": "Public story may publish only source-backed claims, caveats, or documented blockers.",
        "verification_status": "PASS",
        "case_count": len(case_summaries),
        "claim_count": len(claims),
        "source_count": len(sources),
    }
    source_status_counts = Counter(source["archive_status"] for source in sources)
    verification_manifest = {
        "generated_at": utc_now(),
        "runtime_source": "calds_runtime.editorial_export",
        "included_cases": [case["case_id"] for case in case_summaries],
        "case_manifest_status": manifest_status,
        "claim_coverage": {
            "status": "PASS" if claims and all(claim["evidence_ids"] for claim in claims) else "FAIL",
            "claim_count": len(claims),
            "evidence_backed_claim_count": sum(1 for claim in claims if claim["evidence_ids"]),
            "claims_by_case": dict(evidence_by_case),
        },
        "source_status": {
            "status": "PASS" if source_status_counts.get("Live", 0) else "FAIL",
            "counts": dict(source_status_counts),
        },
        "readability": _readability_summary([claim["plain_language_sentence"] for claim in claims] + [case["public_summary"] for case in case_summaries]),
        "public_safety": {},
    }
    payloads: dict[str, Any] = {
        "public-cases.json": public_cases,
        "claim-ledger.json": claims,
        "source-ledger.json": {"sources": sources},
        "case-summaries.json": {"cases": case_summaries},
        "entities.json": {"entities": entities},
        "money-trail.json": {"money_trail": money_rows},
        "blockers.json": {"blockers": blockers},
    }
    safety = _scan_public_payload(payloads)
    verification_manifest["public_safety"] = safety
    verification_manifest["status"] = "PASS" if safety["status"] == "PASS" and verification_manifest["claim_coverage"]["status"] == "PASS" else "FAIL"
    payloads["verification-manifest.json"] = verification_manifest

    files: dict[str, str] = {}
    for filename, payload in payloads.items():
        path = output_dir / filename
        write_json(path, payload)
        files[filename] = str(path)

    return EditorialExport(output_dir=str(output_dir), files=files, verification_manifest=verification_manifest)
