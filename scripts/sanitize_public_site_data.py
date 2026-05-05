from __future__ import annotations

from pathlib import Path
import argparse
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


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def clean_sentence(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = re.sub(r"^E\d+\s+", "", text)
    text = text.replace("source-listed", "listed")
    text = text.replace("parsed", "listed")
    text = text.replace("deep review", "closer review")
    text = text.replace("deep-dive", "review")
    text = text.replace("Review Value Score", "review score")
    return text


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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
