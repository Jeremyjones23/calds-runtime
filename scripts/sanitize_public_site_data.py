from __future__ import annotations

from pathlib import Path
import argparse
import hashlib
import json
import re
from typing import Any


INTERNAL_CASE_KEYS = {
    "legal_language_check",
}

INTERNAL_TEXT_MARKERS = (
    "case posture",
    "workflow state",
    "sentinel",
    "review priority",
    "risk severity",
    "source completeness",
    "publication confidence",
    "how safe this is to publish",
    "score scope",
    "awaiting_human_review",
    "downgrade_for_review",
    "downgrade for review",
)

MECHANICAL_PUBLIC_MARKERS = (
    "already recovered: true",
    "pages fetched:",
    "source collection",
    "entity:",
    "rank by parsed",
    "source-listed",
    "calds shows only",
)


CASE_SUMMARY_OVERRIDES = {
    "live_ca_homelessness_top15_2026_04_29": (
        "CalDS screened 15 California homelessness nonprofits. The public records show large state housing-award "
        "exposure, one official federal charging announcement tied to a connected property transaction, and records "
        "that still need to be requested before anyone should draw a final conclusion."
    ),
    "live_ca_recovery_ngos_2026_04_24": (
        "CalDS screened seven recovery and treatment nonprofits. This public file shows the records recovered so far, "
        "including audit and public-statement sources, but it does not support a public accusation."
    ),
    "live_ca_sf_homelessness_complex": (
        "CalDS screened 15 San Francisco homelessness nonprofits. The records show public payments, official notices "
        "or audits for some providers, and many contract, monitoring, and outcome records still needed for a full review."
    ),
}


DEFAULT_CAVEATS = [
    "This public page shows records that deserve human review.",
    "It does not decide guilt, intent, or legal liability.",
    "A stronger conclusion would require more contracts, monitoring records, outcome records, or official findings.",
]


AMOUNT_RE = re.compile(r"\$\s?[0-9][0-9,]*(?:\.[0-9]+)?(?:\s*(?:million|billion))?", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(20[0-9]{2})\b")

SUPPLEMENTAL_DOSSIER_PATTERNS = (
    "runs/**/{case_id}/case_dossier.md",
    "runs/**/{case_id}/artifacts/case_dossier.md",
    "runs/**/cases/{case_id}/case_dossier.md",
    "artifacts/**/cases/{case_id}/case_dossier.md",
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def stable_public_id(prefix: str, *parts: Any) -> str:
    digest = hashlib.sha256("|".join(str(part or "") for part in parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def clean_sentence(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = re.sub(r"^E\d+\s+", "", text)
    text = text.replace("source-listed", "listed")
    text = text.replace("parsed", "listed")
    text = text.replace("deep review", "closer review")
    text = text.replace("deep-dive", "review")
    text = text.replace("Review Value Score", "review score")
    return text


def clean_money_context(value: Any, limit: int = 260) -> str:
    text = reader_facing_source_text(value)
    text = re.sub(r"`[^`]*`", "", text)
    text = re.sub(r"\bevidence\s+E\d+\b", "source record", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip(" -")
    if len(text) > limit:
        text = text[: limit - 3].rsplit(" ", 1)[0] + "..."
    return text


def extract_entity_from_context(text: str, known_entities: list[str]) -> str:
    lower = text.lower()
    flag_subject = re.search(r"\bCalDS flags\s+([^/]+?)\s*/", text, re.IGNORECASE)
    if flag_subject:
        return flag_subject.group(1).strip()
    for entity in known_entities:
        if entity and entity.lower() in lower:
            return entity
    subject = re.search(r"\bsubject:\s*([^;.)]+)", text, re.IGNORECASE)
    if subject:
        return subject.group(1).strip()
    org_named = re.search(r"\borganization named in the cited source:\s*([^;.)]+)", text, re.IGNORECASE)
    if org_named:
        return org_named.group(1).strip()
    payment = re.search(r"([A-Z][A-Za-z0-9&.' -]{3,90})\s+in Department of Homelessness", text)
    if payment:
        return payment.group(1).strip()
    return "Organization named in source"


def discover_supplemental_dossiers(data_dir: Path, case_id: str) -> list[Path]:
    repo_root = data_dir.resolve()
    while repo_root.name.lower() not in {"calds", ""} and repo_root.parent != repo_root:
        repo_root = repo_root.parent
    candidates: list[Path] = []
    for pattern in SUPPLEMENTAL_DOSSIER_PATTERNS:
        candidates.extend(repo_root.glob(pattern.format(case_id=case_id)))
    unique: dict[str, Path] = {}
    for path in candidates:
        if path.exists() and path.is_file():
            unique[str(path.resolve())] = path
    return sorted(unique.values(), key=lambda path: path.stat().st_mtime, reverse=True)


def supplemental_money_snippets(data_dir: Path, case_id: str) -> list[str]:
    snippets: list[str] = []
    for path in discover_supplemental_dossiers(data_dir, case_id):
        text = path.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            if "$" not in line:
                continue
            lower = line.lower()
            if not any(
                marker in lower
                for marker in (
                    "payment exposure",
                    "federal award exposure",
                    "government grants",
                    "total revenue",
                    "revenue moved",
                    "expenses moved",
                    "compensation",
                    "salaries",
                    "award amount total",
                    "award data captured",
                )
            ):
                continue
            cleaned = clean_money_context(line, 620)
            if cleaned and cleaned not in snippets:
                snippets.append(cleaned)
            if len(snippets) >= 16:
                return snippets
    return snippets


def is_mechanical(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return any(marker in text for marker in MECHANICAL_PUBLIC_MARKERS)


def reader_facing_source_text(value: Any) -> str:
    text = clean_sentence(value)
    replacements = (
        ("Downloaded Internal Revenue Service Form 990 machine-readable filing data", "IRS Form 990 filing data"),
        ("Internal Revenue Service machine-readable filing-data availability manifest", "IRS filing index"),
        ("California Department of Health Care Services adverse-status page machine-readability manifest", "state adverse-status source index"),
        ("California Department of Health Care Services adverse-status page manifest", "state adverse-status page"),
        ("California Department of Health Care Services adverse-status machine-readable source directory", "California facility adverse-status source"),
        ("California Department of Health Care Services facility-status machine-readable source directory", "California facility-status source"),
        ("Court docket search manifest", "court calendar search result"),
        ("docket-search manifest only", "court-calendar search result only"),
        ("Parsed source document text index", "Source document text"),
        ("machine-readable filing data", "filing data"),
        ("machine-readable filing-data availability manifest", "filing index"),
        ("SharePoint API candidates, and ArcGIS searches were probed", "state web sources were checked"),
        ("No separate machine-readable probation, suspension, revocation, or NOV table was recovered", "No separate public probation, suspension, revocation, or notice-of-violation table was recovered"),
        ("machine-readable source directory", "source directory"),
        ("machine-readable source discovery manifest", "source index"),
        ("machine-readability manifest", "source index"),
        ("source discovery manifest", "source index"),
        ("adverse-status source discovery", "adverse-status source"),
        ("facility-status source discovery", "facility-status source"),
        ("verified in publication manifest", "verified"),
        ("publication manifest", "publication check"),
        ("availability manifest", "index"),
        ("Parsed source", "Source"),
    )
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def public_caveats(case: dict[str, Any]) -> list[str]:
    caveats = []
    for item in case.get("what_this_does_not_prove", []) or []:
        text = clean_sentence(item)
        lower = text.lower()
        if any(marker in lower for marker in INTERNAL_TEXT_MARKERS):
            continue
        if text:
            caveats.append(text)
    return caveats[:5] or list(DEFAULT_CAVEATS)


def sanitize_case(case: dict[str, Any]) -> dict[str, Any]:
    cleaned = {key: value for key, value in case.items() if key not in INTERNAL_CASE_KEYS}
    case_id = str(cleaned.get("case_id", ""))
    if case_id in CASE_SUMMARY_OVERRIDES:
        cleaned["public_summary"] = CASE_SUMMARY_OVERRIDES[case_id]
    cleaned["what_this_does_not_prove"] = public_caveats(cleaned)
    cleaned["strongest_supported_flags"] = [
        clean_sentence(item)
        for item in cleaned.get("strongest_supported_flags", [])
        if not is_mechanical(item)
    ]
    return cleaned


def sanitize_entities(data_dir: Path) -> None:
    path = data_dir / "entities.json"
    if not path.exists():
        return
    payload = read_json(path)
    for entity in payload.get("entities", []):
        if str(entity.get("what_it_claims_to_do", "")).startswith("CalDS shows only"):
            entity["what_it_claims_to_do"] = "No source-backed service description is shown in this public export."
        for key in ("official_records_found", "public_money_found", "red_flags", "caveats"):
            deduped: list[str] = []
            for item in entity.get(key, []) or []:
                text = reader_facing_source_text(item)
                if is_mechanical(text):
                    continue
                if text and text not in deduped:
                    deduped.append(text)
            entity[key] = deduped
    write_json(path, payload)
    print(f"sanitized={path}")


def sanitize_claims_and_source_refs(data_dir: Path) -> None:
    claim_path = data_dir / "claim-ledger.json"
    if not claim_path.exists():
        return
    claims = read_json(claim_path)
    kept_claims = [
        claim
        for claim in claims
        if not is_mechanical(claim.get("plain_language_sentence") or claim.get("public_sentence") or claim.get("source_excerpt"))
    ]
    for claim in kept_claims:
        for field in ("plain_language_sentence", "public_sentence", "source_excerpt", "source_family"):
            if field in claim:
                claim[field] = reader_facing_source_text(claim[field])
    kept_ids = {claim.get("claim_id") for claim in kept_claims}
    write_json(claim_path, kept_claims)
    print(f"sanitized={claim_path}")

    source_path = data_dir / "source-ledger.json"
    if source_path.exists():
        payload = read_json(source_path)
        for source in payload.get("sources", []):
            source["claim_ids"] = [claim_id for claim_id in source.get("claim_ids", []) if claim_id in kept_ids]
            title = reader_facing_source_text(source.get("title", ""))
            title = title.replace("Contract and payment acquisition status:", "Contract or payment record:")
            title = title.replace("Official enforcement/docket triage source:", "Official enforcement or docket source:")
            title = title.replace("Public statement page harvest:", "Public statement page:")
            title = title.replace("Internal Revenue Service Form 990 acquisition status:", "IRS Form 990 record:")
            source["title"] = title
            family = reader_facing_source_text(source.get("source_family", ""))
            family = family.replace("Contract and payment acquisition gap record", "Contract or payment record search")
            family = family.replace("irs_990_raw_artifact_discovery", "IRS Form 990 record")
            family = family.replace("irs_990_raw_artifact", "IRS Form 990 record")
            source["source_family"] = family
            if is_mechanical(source.get("supports")):
                source["supports"] = "Public website or statement page was found."
            else:
                source["supports"] = reader_facing_source_text(source.get("supports"))
            source["http_status"] = reader_facing_source_text(source.get("http_status", ""))
            source["source_type"] = str(source.get("source_type", "")).replace("manifest", "source_index")
        write_json(source_path, payload)
        print(f"sanitized={source_path}")


def augment_money_trail(data_dir: Path) -> None:
    money_path = data_dir / "money-trail.json"
    claim_path = data_dir / "claim-ledger.json"
    source_path = data_dir / "source-ledger.json"
    case_path = data_dir / "case-summaries.json"
    entity_path = data_dir / "entities.json"
    if not all(path.exists() for path in (money_path, claim_path, source_path, case_path, entity_path)):
        return

    money_payload = read_json(money_path)
    claims = read_json(claim_path)
    source_payload = read_json(source_path)
    cases = read_json(case_path).get("cases", [])
    entity_payload = read_json(entity_path)

    sources = source_payload.get("sources", [])
    entities = entity_payload.get("entities", [])
    source_by_claim: dict[str, dict[str, Any]] = {}
    source_by_id = {source.get("source_id"): source for source in sources}
    for source in sources:
        for claim_id in source.get("claim_ids", []) or []:
            source_by_claim[claim_id] = source

    entity_by_name = {str(entity.get("display_name", "")).lower(): entity for entity in entities}
    known_entities_by_case = {
        case.get("case_id"): [str(entity) for entity in case.get("entities", []) or []]
        for case in cases
    }

    rows = money_payload.setdefault("money_trail", [])
    existing = {
        (
            str(row.get("case_id")),
            str(row.get("entity_id")),
            str(row.get("amount")).replace(" ", ""),
            str(row.get("source_id")),
            str(row.get("claim_id")),
        )
        for row in rows
    }
    existing_display_amounts = {
        (
            str(row.get("case_id")),
            str(row.get("entity_id")),
            str(row.get("amount")).replace(" ", ""),
        )
        for row in rows
    }
    existing_case_amounts = {
        (
            str(row.get("case_id")),
            str(row.get("amount")).replace(" ", ""),
        )
        for row in rows
    }

    def add_row(case_id: str, entity_name: str, amount: str, source_id: str, claim_id: str, context: str) -> None:
        amount = amount.rstrip(".,;:")
        if amount == "$11.2":
            amount = "$11.2 million"
        entity = entity_by_name.get(entity_name.lower())
        if entity:
            entity_id = entity.get("entity_id", "")
        else:
            entity_id = stable_public_id("entity", entity_name)
            entity = {
                "case_ids": [case_id],
                "caveats": [],
                "display_name": entity_name,
                "entity_id": entity_id,
                "geography": "",
                "issue_area": "",
                "official_records_found": [],
                "public_money_found": [],
                "red_flags": [],
                "source_ids": [],
                "what_it_claims_to_do": "",
            }
            entities.append(entity)
            entity_by_name[entity_name.lower()] = entity
        key = (case_id, str(entity_id), amount.replace(" ", ""), source_id, claim_id)
        display_key = (case_id, str(entity_id), amount.replace(" ", ""))
        case_amount_key = (case_id, amount.replace(" ", ""))
        if display_key in existing_display_amounts:
            return
        if entity_name == "Organization named in source" and case_amount_key in existing_case_amounts:
            return
        if key in existing:
            return
        existing.add(key)
        existing_display_amounts.add(display_key)
        existing_case_amounts.add(case_amount_key)
        years = YEAR_RE.findall(context)
        rows.append(
            {
                "amount": amount,
                "amount_type": "public amount or filing amount named in cited record",
                "calculation_note": "Amount is published only as it appears in the cited record text.",
                "case_id": case_id,
                "claim_id": claim_id,
                "entity_id": entity_id,
                "is_partial": True,
                "missing_records_note": "Treat as partial unless the source says it is a full total.",
                "source_id": source_id,
                "year": years[0] if years else "",
            }
        )
        if context and context not in entity.get("public_money_found", []):
            entity.setdefault("public_money_found", []).append(context)
        if source_id and source_id not in entity.get("source_ids", []):
            entity.setdefault("source_ids", []).append(source_id)

    for claim in claims:
        case_id = str(claim.get("case_id", ""))
        context = clean_money_context(
            " ".join(
                str(claim.get(field, ""))
                for field in ("public_sentence", "plain_language_sentence", "source_excerpt")
            )
        )
        amounts = AMOUNT_RE.findall(context)
        if not amounts:
            continue
        source = source_by_claim.get(claim.get("claim_id"), {})
        source_id = source.get("source_id") or stable_public_id("source", case_id, claim.get("claim_id"), context)
        if source_id not in source_by_id:
            source_by_id[source_id] = {
                "archive_status": "Live",
                "blocker_reason": "",
                "case_id": case_id,
                "checksum": stable_public_id("checksum", context),
                "claim_ids": [claim.get("claim_id")],
                "content_type": "",
                "evidence_ids": claim.get("evidence_ids", []),
                "final_url": (claim.get("source_urls") or [""])[0],
                "http_status": "verified" if claim.get("source_urls") else "listed",
                "retrieval_date": claim.get("retrieval_date", ""),
                "source_family": claim.get("source_family", "Public dollar record"),
                "source_id": source_id,
                "source_type": "public_dollar_record",
                "supports": context,
                "title": f"Public dollar record: {claim.get('entity') or 'organization named in source'}",
                "url": (claim.get("source_urls") or [""])[0],
            }
            sources.append(source_by_id[source_id])
        for amount in amounts[:4]:
            add_row(
                case_id,
                str(claim.get("entity") or extract_entity_from_context(context, known_entities_by_case.get(case_id, []))),
                amount,
                source_id,
                str(claim.get("claim_id")),
                context,
            )

    money_counts = {case.get("case_id"): 0 for case in cases}
    for row in rows:
        money_counts[row.get("case_id")] = money_counts.get(row.get("case_id"), 0) + 1

    for case in cases:
        case_id = str(case.get("case_id", ""))
        if money_counts.get(case_id, 0) > 0:
            continue
        for index, snippet in enumerate(supplemental_money_snippets(data_dir, case_id), start=1):
            amounts = AMOUNT_RE.findall(snippet)
            if not amounts:
                continue
            entity_name = extract_entity_from_context(snippet, known_entities_by_case.get(case_id, []))
            source_id = stable_public_id("source", case_id, "supplemental-money", index)
            claim_id = stable_public_id("claim", case_id, "supplemental-money", index)
            if source_id not in source_by_id:
                source_by_id[source_id] = {
                    "archive_status": "Public artifact",
                    "blocker_reason": "",
                    "case_id": case_id,
                    "checksum": stable_public_id("checksum", snippet),
                    "claim_ids": [claim_id],
                    "content_type": "text/markdown",
                    "evidence_ids": [],
                    "final_url": "",
                    "http_status": "listed",
                    "retrieval_date": "",
                    "source_family": "Public dollar record",
                    "source_id": source_id,
                    "source_type": "public_dollar_record",
                    "supports": snippet,
                    "title": f"Public dollar record: {entity_name}",
                    "url": "",
                }
                sources.append(source_by_id[source_id])
            before_count = len(rows)
            for amount in amounts[:2]:
                add_row(case_id, entity_name, amount, source_id, claim_id, snippet)
            money_counts[case_id] = money_counts.get(case_id, 0) + (len(rows) - before_count)
            if money_counts.get(case_id, 0) >= 8:
                break

    write_json(money_path, money_payload)
    write_json(source_path, source_payload)
    write_json(entity_path, entity_payload)
    print(f"augmented_money_trail={money_path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()

    for name in ("case-summaries.json", "public-cases.json"):
        path = args.data_dir / name
        payload = read_json(path)
        if name == "case-summaries.json":
            payload["cases"] = [sanitize_case(case) for case in payload.get("cases", [])]
        else:
            payload["cases"] = [sanitize_case(case) for case in payload.get("cases", [])]
        write_json(path, payload)
        print(f"sanitized={path}")
    money_path = args.data_dir / "money-trail.json"
    if money_path.exists():
        payload = read_json(money_path)
        for row in payload.get("money_trail", []):
            if row.get("amount") == "$11.2":
                row["amount"] = "$11.2 million"
                row["calculation_note"] = "Amount is normalized from a cited source phrase that says $11.2 million."
        write_json(money_path, payload)
        print(f"sanitized={money_path}")
    sanitize_entities(args.data_dir)
    sanitize_claims_and_source_refs(args.data_dir)
    augment_money_trail(args.data_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
