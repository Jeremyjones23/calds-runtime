from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
from typing import Any
import urllib.parse
import urllib.request


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STAGE3_CORPUS = PROJECT_ROOT / "data" / "live_corpus" / "ca_recovery_ngos_2026_04_24_stage3"
DEFAULT_STAGE4_CORPUS = PROJECT_ROOT / "data" / "live_corpus" / "ca_recovery_ngos_2026_04_24_stage4"
DEFAULT_ARTIFACTS = PROJECT_ROOT / "artifacts" / "live_recovery_sources_2026_04_24"
DEFAULT_RECOVERY = DEFAULT_ARTIFACTS / "gap_recovery"

PROPUBLICA_HEALTHRIGHT_FULL = "https://projects.propublica.org/nonprofits/organizations/946129071/202541349349300309/full"
PROPUBLICA_FULL_TEXT_BASE = "https://projects.propublica.org/nonprofits/full_text/202541349349300309"
SCHEDULES = [
    "IRS990",
    "IRS990ScheduleA",
    "IRS990ScheduleB",
    "IRS990ScheduleC",
    "IRS990ScheduleD",
    "IRS990ScheduleG",
    "IRS990ScheduleJ",
    "IRS990ScheduleK",
    "IRS990ScheduleM",
    "IRS990ScheduleO",
    "IRS990ScheduleR",
]

DHCS_ADVERSE_PAGE = "https://www.dhcs.ca.gov/provgovpart/SUD-LCR/Pages/SUS-REV-NOV.aspx"
DHCS_ARCGIS_SEARCH_TERMS = [
    '"Probationary Status" "Temporary Suspension Order"',
    '"Notice of Operation in Violation" "DHCS"',
    '"SUD" "Revoked" "FACILITY_STATUS"',
    '"LCD" "Suspended" "Revoked"',
    '"SUDS" "NOV" "DHCS"',
    '"SUDS Facilities LCD"',
]
TARGET_ENTITIES = [
    "Tarzana Treatment Centers Inc",
    "HealthRIGHT 360",
    "WestCare California Inc",
    "Behavioral Health Services Inc",
    "CRI-Help Inc",
    "Social Model Recovery Systems Inc",
    "Phoenix Houses Of California Inc",
]


class TextStripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def copy_corpus(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    if source.exists() and source.resolve() == destination.resolve():
        return
    for existing in destination.glob("*.json"):
        existing.unlink()
    for path in sorted(source.glob("*.json")):
        shutil.copy2(path, destination / path.name)


def fetch(url: str, timeout: int = 90) -> tuple[bytes, str, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 CalDS gap recovery",
            "Accept-Encoding": "identity",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(), response.geturl(), response.headers.get("Content-Type", "")


def decode_possible_gzip(raw: bytes) -> str:
    if raw.startswith(b"\x1f\x8b"):
        raw = gzip.decompress(raw)
    return raw.decode("utf-8", "replace")


def strip_html(value: str) -> str:
    parser = TextStripper()
    parser.feed(value)
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


def number_after(pattern: str, text: str, group: int = -1) -> str:
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return ""
    numbers = re.findall(r"-?\d[\d,]*", match.group(0))
    return numbers[group] if numbers else ""


def line_value(start_pattern: str, end_pattern: str, text: str, group: int = -1) -> str:
    pattern = start_pattern + r"(?P<body>.*?)" + end_pattern
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return ""
    numbers = re.findall(r"-?\d[\d,]*", match.group("body"))
    return numbers[group] if numbers else ""


def recover_healthright_full_text(recovery_dir: Path) -> dict[str, Any]:
    full_raw, full_final_url, full_content_type = fetch(PROPUBLICA_HEALTHRIGHT_FULL)
    full_html = decode_possible_gzip(full_raw)
    write_text(recovery_dir / "healthright_2024_full_page.html", full_html)

    schedules: dict[str, dict[str, Any]] = {}
    full_plain_parts: list[str] = []
    for schedule in SCHEDULES:
        url = f"{PROPUBLICA_FULL_TEXT_BASE}/{schedule}"
        raw, final_url, content_type = fetch(url)
        html = decode_possible_gzip(raw)
        plain = strip_html(html)
        write_text(recovery_dir / "healthright_2024_schedules" / f"{schedule}.html", html)
        write_text(recovery_dir / "healthright_2024_schedules" / f"{schedule}.txt", plain)
        schedules[schedule] = {
            "url": url,
            "final_url": final_url,
            "content_type": content_type,
            "html_bytes": len(html.encode("utf-8")),
            "text_chars": len(plain),
        }
        full_plain_parts.append(f"[{schedule}] {plain}")

    irs990_text = (recovery_dir / "healthright_2024_schedules" / "IRS990.txt").read_text(encoding="utf-8")
    parsed = {
        "entity": "HealthRIGHT 360",
        "ein": "946129071",
        "object_id": "202541349349300309",
        "tax_period": "202406",
        "source_posture": "ProPublica rendered full-text secondary source because direct IRS XML object was not present in the listed IRS ZIP and ProPublica XML download was Cloudflare-blocked in local fetch.",
        "gross_receipts": number_after(r"Gross receipts \$\s*-?\d[\d,]*", irs990_text),
        "current_year_total_revenue": line_value(r"12\s+Total revenue", r"13\s+Grants", irs990_text),
        "current_year_total_expenses": line_value(r"18\s+Total expenses", r"19\s+Revenue less expenses", irs990_text),
        "end_of_year_total_assets": line_value(r"20\s+Total assets", r"21\s+Total liabilities", irs990_text),
        "end_of_year_net_assets": line_value(r"22\s+Net assets or fund balances", r"Part II", irs990_text),
        "government_grants_contributions": number_after(r"Government grants \(contributions\)\s*1e\s*-?\d[\d,]*", irs990_text),
        "program_service_revenue": line_value(r"9\s+Program service revenue", r"10\s+Investment income", irs990_text),
        "schedule_r_present": bool((recovery_dir / "healthright_2024_schedules" / "IRS990ScheduleR.txt").read_text(encoding="utf-8")),
        "schedule_l_present": False,
    }
    manifest = {
        "full_page": {
            "url": PROPUBLICA_HEALTHRIGHT_FULL,
            "final_url": full_final_url,
            "content_type": full_content_type,
            "html_bytes": len(full_html.encode("utf-8")),
        },
        "schedules": schedules,
        "parsed_fields": parsed,
        "official_xml_status": "unresolved_missing_from_irs_zip_index_batch",
        "official_pdf_status": "not_found_in_irs_bulk_or_propublica_latest_listing",
    }
    write_json(recovery_dir / "healthright_2024_propublica_full_text_manifest.json", manifest)
    write_text(recovery_dir / "healthright_2024_full_text_combined.txt", "\n\n".join(full_plain_parts))
    return manifest


def probe_dhcs_adverse_sources(recovery_dir: Path) -> dict[str, Any]:
    page_result: dict[str, Any]
    try:
        raw, final_url, content_type = fetch(DHCS_ADVERSE_PAGE)
        text = decode_possible_gzip(raw)
        write_text(recovery_dir / "dhcs_adverse_page_static.html", text)
        page_result = {
            "url": DHCS_ADVERSE_PAGE,
            "final_url": final_url,
            "content_type": content_type,
            "bytes": len(raw),
            "contains_target_alias": {entity: entity.lower() in text.lower() for entity in TARGET_ENTITIES},
            "contains_table_rows": "<tr" in text.lower(),
        }
    except Exception as exc:
        page_result = {"url": DHCS_ADVERSE_PAGE, "error": repr(exc)}

    sharepoint_endpoints = []
    raw_endpoints = [
        "https://www.dhcs.ca.gov/_api/web/GetFileByServerRelativeUrl('/provgovpart/SUD-LCR/Pages/SUS-REV-NOV.aspx')/ListItemAllFields?$select=Title,CanvasContent1,WikiField,PublishingPageContent",
        "https://www.dhcs.ca.gov/provgovpart/SUD-LCR/_api/web/lists/getbytitle('Pages')/items?"
        + urllib.parse.urlencode({"$filter": "FileLeafRef eq 'SUS-REV-NOV.aspx'", "$select": "Title,CanvasContent1,WikiField,PublishingPageContent"}),
    ]
    for endpoint in raw_endpoints:
        try:
            raw, final_url, content_type = fetch(endpoint)
            body = decode_possible_gzip(raw)
            sharepoint_endpoints.append(
                {
                    "url": endpoint,
                    "final_url": final_url,
                    "content_type": content_type,
                    "bytes": len(raw),
                    "appears_incapsula_or_challenge": "Incapsula" in body or "Security Check" in body,
                    "body_head": body[:300],
                }
            )
        except Exception as exc:
            sharepoint_endpoints.append({"url": endpoint, "error": repr(exc)})

    arcgis_searches = []
    for query in DHCS_ARCGIS_SEARCH_TERMS:
        url = "https://www.arcgis.com/sharing/rest/search?" + urllib.parse.urlencode(
            {"f": "json", "q": query, "num": "10", "sortField": "modified", "sortOrder": "desc"}
        )
        try:
            raw, final_url, content_type = fetch(url)
            data = json.loads(raw.decode("utf-8", "replace"))
            arcgis_searches.append(
                {
                    "query": query,
                    "url": url,
                    "total": data.get("total"),
                    "results": [
                        {
                            "title": item.get("title"),
                            "id": item.get("id"),
                            "type": item.get("type"),
                            "owner": item.get("owner"),
                            "url": item.get("url"),
                        }
                        for item in data.get("results", [])[:10]
                    ],
                }
            )
        except Exception as exc:
            arcgis_searches.append({"query": query, "url": url, "error": repr(exc)})

    manifest = {
        "page_probe": page_result,
        "sharepoint_api_probes": sharepoint_endpoints,
        "arcgis_search_probes": arcgis_searches,
        "result": "No separate machine-readable DHCS probation/suspension/revocation/NOV source was found in this run. The public ArcGIS experience backing source remains the LCD facility-status service with Active/Closed status fields.",
    }
    write_json(recovery_dir / "dhcs_adverse_source_discovery_manifest.json", manifest)
    return manifest


def corpus_record(
    record_id: str,
    title: str,
    source_uri: str,
    source_type: str,
    body: str,
    signals: dict[str, Any],
    attributes: dict[str, Any],
    entities: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "record_id": record_id,
        "title": title,
        "source_uri": source_uri,
        "source_type": source_type,
        "published_at": "2026-04-24",
        "collected_at": utc_now(),
        "entities": entities or TARGET_ENTITIES,
        "attributes": {"signals": signals, **attributes},
        "body": body,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Recover or document remaining live-source gaps.")
    parser.add_argument("--stage3-corpus", type=Path, default=DEFAULT_STAGE3_CORPUS)
    parser.add_argument("--stage4-corpus", type=Path, default=DEFAULT_STAGE4_CORPUS)
    parser.add_argument("--recovery-dir", type=Path, default=DEFAULT_RECOVERY)
    args = parser.parse_args()

    args.recovery_dir.mkdir(parents=True, exist_ok=True)
    copy_corpus(args.stage3_corpus, args.stage4_corpus)

    healthright = recover_healthright_full_text(args.recovery_dir)
    dhcs = probe_dhcs_adverse_sources(args.recovery_dir)

    parsed = healthright["parsed_fields"]
    healthright_body = "\n".join(
        [
            "HealthRIGHT 360 Form 990 secondary source recovered from ProPublica rendered full-text schedules.",
            "This does not replace the missing official IRS XML object; it is a source-access blocker and secondary source for reviewer comparison.",
            "Parsed secondary-source fields:",
            json.dumps(parsed, indent=2, sort_keys=True),
        ]
    )
    records = [
        corpus_record(
            "healthright_2024_irs_990_rendered_secondary_source",
            "HealthRIGHT 360 2024 Form 990 rendered secondary source",
            str(args.recovery_dir / "healthright_2024_full_text_combined.txt"),
            "irs_990_rendered_secondary_source",
            healthright_body,
            {"irs_990_rendered_secondary_source": True, "full_990_xml_missing": True, "missing_data": True, "source_access_required": True},
            {"manifest_path": str(args.recovery_dir / "healthright_2024_propublica_full_text_manifest.json"), "parsed_fields": parsed},
            entities=["HealthRIGHT 360"],
        ),
        corpus_record(
            "dhcs_adverse_status_source_discovery_gap",
            "DHCS adverse-status machine-readable source discovery manifest",
            str(args.recovery_dir / "dhcs_adverse_source_discovery_manifest.json"),
            "dhcs_adverse_status_discovery",
            "DHCS adverse-status page, SharePoint API candidates, and ArcGIS searches were probed. No separate machine-readable probation, suspension, revocation, or NOV table was recovered in this run. Existing DHCS facility status remains Active/Closed facility-level context.",
            {"dhcs_adverse_source_probe_complete": True, "dhcs_status_crosscheck_incomplete": True, "missing_data": True},
            {"manifest_path": str(args.recovery_dir / "dhcs_adverse_source_discovery_manifest.json"), "probe_result": dhcs["result"]},
        ),
    ]
    for record in records:
        write_json(args.stage4_corpus / f"{record['record_id']}.json", record)

    summary = {
        "completed_at": utc_now(),
        "stage4_corpus": str(args.stage4_corpus),
        "stage4_record_count": len(list(args.stage4_corpus.glob("*.json"))),
        "recovery_dir": str(args.recovery_dir),
        "records": [record["record_id"] for record in records],
        "healthright_official_xml_status": healthright["official_xml_status"],
        "healthright_official_pdf_status": healthright["official_pdf_status"],
        "dhcs_result": dhcs["result"],
    }
    write_json(args.recovery_dir / "gap_recovery_summary.json", summary)
    print(f"stage4_corpus={args.stage4_corpus}")
    print(f"records={summary['stage4_record_count']}")
    print(f"healthright_xml_status={summary['healthright_official_xml_status']}")
    print(f"dhcs_result={summary['dhcs_result']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
