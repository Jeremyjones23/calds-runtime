from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import time
from typing import Any
import urllib.parse
import urllib.request
import zlib
import xml.etree.ElementTree as ET


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STAGE1_CORPUS = PROJECT_ROOT / "data" / "live_corpus" / "ca_recovery_ngos_2026_04_24"
DEFAULT_STAGE2_CORPUS = PROJECT_ROOT / "data" / "live_corpus" / "ca_recovery_ngos_2026_04_24_stage2"
DEFAULT_ARTIFACTS = PROJECT_ROOT / "artifacts" / "live_recovery_sources_2026_04_24"

IRS_XML_BASE = "https://apps.irs.gov/pub/epostcard/990/xml"
DEFAULT_TAX_PERIOD_YEARS = [2023, 2024, 2025]

FAC_CSVS = {
    "general": "https://app.fac.gov/dissemination/public-data/gsa/full/general.csv",
    "findings": "https://app.fac.gov/dissemination/public-data/gsa/full/findings.csv",
    "findings_text": "https://app.fac.gov/dissemination/public-data/gsa/full/findings_text.csv",
    "federal_awards": "https://app.fac.gov/dissemination/public-data/gsa/full/federal_awards.csv",
    "corrective_action_plans": "https://app.fac.gov/dissemination/public-data/gsa/full/corrective_action_plans.csv",
}

DHCS_CURRENT_FACILITIES = (
    "https://services7.arcgis.com/7MUwsS9z05YumJRZ/arcgis/rest/services/"
    "SUD_Recovery_Treatment_Facilities/FeatureServer/0"
)
DHCS_LCD_STATUS = (
    "https://services7.arcgis.com/7MUwsS9z05YumJRZ/arcgis/rest/services/"
    "SUDS_Facilities_LCD_view/FeatureServer/7"
)
DHCS_ADVERSE_PAGE = "https://www.dhcs.ca.gov/provgovpart/SUD-LCR/Pages/SUS-REV-NOV.aspx"


@dataclass(frozen=True)
class Target:
    slug: str
    name: str
    ein: str
    aliases: tuple[str, ...]


TARGETS = [
    Target(
        "tarzana",
        "Tarzana Treatment Centers Inc",
        "942219349",
        ("Tarzana Treatment Centers", "TARZANA TREATMENT CENTERS, INC."),
    ),
    Target(
        "healthright",
        "HealthRIGHT 360",
        "946129071",
        ("HealthRight 360", "HEALTHRIGHT 360"),
    ),
    Target(
        "westcare",
        "WestCare California Inc",
        "237368450",
        ("WestCare California", "WESTCARE CALIFORNIA, INC."),
    ),
    Target(
        "bhs",
        "Behavioral Health Services Inc",
        "952838006",
        ("Behavioral Health Services", "BEHAVIORAL HEALTH SERVICES, INC."),
    ),
    Target(
        "crihelp",
        "CRI-Help Inc",
        "952758951",
        ("CRI-Help", "CRI-HELP, INC."),
    ),
    Target(
        "socialmodel",
        "Social Model Recovery Systems Inc",
        "954079133",
        ("Social Model Recovery Systems", "SOCIAL MODEL RECOVERY SYSTEMS, INC."),
    ),
    Target(
        "phoenix",
        "Phoenix Houses Of California Inc",
        "943015376",
        ("Phoenix Houses", "PHOENIX HOUSES OF CALIFORNIA", "PHOENIX HOUSES OF LOS ANGELES"),
    ),
]


COUNTY_AND_CONTRACT_DOCS = [
    {
        "record_id": "county_monitoring_tarzana_sapc_2021",
        "title": "Los Angeles County Auditor-Controller fiscal compliance review: Tarzana SAPC programs",
        "url": "https://file.lacounty.gov/SDSInter/auditor/cmr/1112050_2021-09-07TarzanaTreatmentCentersInc.-aDPHSAPCDrug-FiscalComplianceReview.pdf",
        "entities": ["Tarzana Treatment Centers Inc"],
        "published_at": "2021-09-07",
        "signals": {"county_monitoring_report": True, "county_monitoring_priority": True},
    },
    {
        "record_id": "county_monitoring_tarzana_dmh_2022",
        "title": "Los Angeles County Auditor-Controller fiscal compliance review: Tarzana DMH programs",
        "url": "https://file.lacounty.gov/SDSInter/auditor/cmr/1124357_2022-05-13TarzanaTreatmentCentersInc-ADepartmentofMentalHealthProgramServicesProvider-FiscalComplianceReview.pdf",
        "entities": ["Tarzana Treatment Centers Inc"],
        "published_at": "2022-05-13",
        "signals": {"county_monitoring_report": True, "county_monitoring_priority": True},
    },
    {
        "record_id": "county_monitoring_bhs_sapc_2023",
        "title": "Los Angeles County Auditor-Controller fiscal compliance review: BHS SAPC provider",
        "url": "https://file.lacounty.gov/SDSInter/auditor/cmr/1141106_2023-04-26BehavioralHealthServicesInc-ADPHSAPCServiceProvider-FiscalComplianceReview.pdf",
        "entities": ["Behavioral Health Services Inc"],
        "published_at": "2023-04-26",
        "signals": {"county_monitoring_report": True, "county_monitoring_priority": True},
    },
    {
        "record_id": "county_monitoring_bhs_sapc_2025",
        "title": "Los Angeles County Auditor-Controller fiscal compliance review: BHS current SAPC contracts",
        "url": "https://file.lacounty.gov/SDSInter/auditor/cmr/1190330_2025-08-18BehavioralHealthServices_Inc.-ADPHSAPCServiceProvider-FiscalComplianceReview.pdf",
        "entities": ["Behavioral Health Services Inc"],
        "published_at": "2025-08-18",
        "signals": {"county_monitoring_report": True, "county_monitoring_priority": True},
    },
    {
        "record_id": "county_grant_ledger_crihelp_rbh_2025_11",
        "title": "Los Angeles County Recovery Bridge Housing paid-claims ledger: CRI-Help November 2025",
        "url": "https://file.lacounty.gov/SDSInter/ceo/asp/1202205_Cri-HelpInc.-RecoveryBridgeHousing-November2025.pdf",
        "entities": ["CRI-Help Inc"],
        "published_at": "2026-02-09",
        "signals": {"county_grant_ledger_present": True},
    },
    {
        "record_id": "county_grant_ledger_crihelp_rbh_2024_03",
        "title": "Los Angeles County Recovery Bridge Housing paid-claims ledger: CRI-Help March 2024",
        "url": "https://file.lacounty.gov/SDSInter/ceo/asp/1165582_CRI-HelpInc.-RecoveryBridgeHousing-Mar.2024.pdf",
        "entities": ["CRI-Help Inc"],
        "published_at": "2024-05",
        "signals": {"county_grant_ledger_present": True},
    },
    {
        "record_id": "sf_contract_healthright_2025_05",
        "title": "San Francisco Health Commission monthly contracts report: HealthRIGHT 360 May 2025",
        "url": "https://media.api.sf.gov/documents/HC_Monthly_May_Report.pdf",
        "entities": ["HealthRIGHT 360"],
        "published_at": "2025-05-05",
        "signals": {"county_contract_source_match": True},
    },
    {
        "record_id": "sf_contract_healthright_2024_09",
        "title": "San Francisco Health Commission monthly contracts report: HealthRIGHT 360 September 2024",
        "url": "https://media.api.sf.gov/documents/HC_Monthly_Report_Sept_3_2024_Final.pdf",
        "entities": ["HealthRIGHT 360"],
        "published_at": "2024-09-03",
        "signals": {"county_contract_source_match": True},
    },
]


COURT_SEARCH_MANIFESTS = [
    {
        "record_id": "court_manifest_healthright_santa_barbara_calendar_2025",
        "title": "Santa Barbara Superior Court calendar search hit: HealthRIGHT 360",
        "url": (
            "https://www.santabarbara.courts.ca.gov/es/online-services/court-calendars/"
            "search-court-calendars/calendarios-judiciales-civil?case_type=All&hearing_type=All"
            "&keyword=&order=field_party_name&page=56&sort=asc"
        ),
        "entities": ["HealthRIGHT 360"],
        "published_at": "2025",
        "body": (
            "Official court website calendar page surfaced a HealthRIGHT 360 party-name hit for case "
            "VENCI00555357. This is a docket-search manifest only; it is not a merits finding and the "
            "court page itself states calendar information is not the official court record."
        ),
        "signals": {"court_docket_manifest": True, "missing_data": True},
    }
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def safe_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def find_7z() -> Path | None:
    path = shutil.which("7z") or shutil.which("7za")
    if path:
        return Path(path)
    candidates = [
        Path(r"C:\Program Files\7-Zip\7z.exe"),
        Path(r"C:\Program Files (x86)\7-Zip\7z.exe"),
        Path(r"C:\Program Files\NVIDIA Corporation\NVIDIA app\7z.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def fetch_bytes(url: str, timeout: int = 90) -> tuple[bytes, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "CalDS-local-ingest/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(), response.geturl()


def head_info(url: str, timeout: int = 60) -> dict[str, str]:
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "CalDS-local-ingest/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return {
            "status": str(response.status),
            "final_url": response.geturl(),
            "content_length": response.headers.get("Content-Length", ""),
            "content_type": response.headers.get("Content-Type", ""),
        }


class RemoteZip:
    def __init__(self, url: str) -> None:
        self.url = url
        info = head_info(url)
        self.size = int(info["content_length"])
        self.entries = self._read_entries()

    def _range_get(self, start: int, end: int) -> bytes:
        request = urllib.request.Request(
            self.url,
            headers={
                "Range": f"bytes={start}-{end}",
                "User-Agent": "CalDS-local-ingest/0.1",
            },
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.read()

    def _read_entries(self) -> dict[str, dict[str, Any]]:
        tail_start = max(0, self.size - 70000)
        tail = self._range_get(tail_start, self.size - 1)
        eocd_pos = tail.rfind(b"PK\x05\x06")
        if eocd_pos < 0:
            raise ValueError(f"Could not locate ZIP end-of-central-directory for {self.url}")
        eocd = struct.unpack_from("<4s4H2LH", tail, eocd_pos)
        cd_size = eocd[5]
        cd_offset = eocd[6]
        central = self._range_get(cd_offset, cd_offset + cd_size - 1)
        entries: dict[str, dict[str, Any]] = {}
        offset = 0
        while offset < len(central):
            if central[offset : offset + 4] != b"PK\x01\x02":
                break
            fields = struct.unpack_from("<4s6H3L5H2L", central, offset)
            compression = fields[4]
            crc32 = fields[7]
            compressed_size = fields[8]
            uncompressed_size = fields[9]
            name_length = fields[10]
            extra_length = fields[11]
            comment_length = fields[12]
            local_offset = fields[16]
            name = central[offset + 46 : offset + 46 + name_length].decode("utf-8")
            entries[name] = {
                "compression": compression,
                "crc32": crc32,
                "compressed_size": compressed_size,
                "uncompressed_size": uncompressed_size,
                "local_offset": local_offset,
            }
            offset += 46 + name_length + extra_length + comment_length
        return entries

    def extract(self, name: str) -> bytes:
        entry = self.entries[name]
        header = self._range_get(entry["local_offset"], entry["local_offset"] + 30 - 1)
        local = struct.unpack_from("<4s5H3L2H", header, 0)
        if local[0] != b"PK\x03\x04":
            raise ValueError(f"Bad local header for {name}")
        name_length = local[9]
        extra_length = local[10]
        data_start = entry["local_offset"] + 30 + name_length + extra_length
        compressed = self._range_get(data_start, data_start + entry["compressed_size"] - 1)
        if entry["compression"] == 0:
            return compressed
        if entry["compression"] == 8:
            return zlib.decompress(compressed, -15)
        if entry["compression"] == 9:
            return self._extract_deflate64_with_7z(name, entry, compressed)
        raise ValueError(f"Unsupported ZIP compression method {entry['compression']} for {name}")

    def _extract_deflate64_with_7z(self, name: str, entry: dict[str, Any], compressed: bytes) -> bytes:
        seven_zip = find_7z()
        if seven_zip is None:
            raise ValueError("ZIP method 9 requires 7-Zip fallback, but 7z.exe was not found")
        filename = name.encode("utf-8")
        local_header = (
            struct.pack(
                "<4s5H3L2H",
                b"PK\x03\x04",
                20,
                0,
                entry["compression"],
                0,
                0,
                entry["crc32"],
                entry["compressed_size"],
                entry["uncompressed_size"],
                len(filename),
                0,
            )
            + filename
        )
        central_offset = len(local_header) + len(compressed)
        central = (
            struct.pack(
                "<4s6H3L5H2L",
                b"PK\x01\x02",
                45,
                20,
                0,
                entry["compression"],
                0,
                0,
                entry["crc32"],
                entry["compressed_size"],
                entry["uncompressed_size"],
                len(filename),
                0,
                0,
                0,
                0,
                0,
                0,
            )
            + filename
        )
        eocd = struct.pack("<4s4H2LH", b"PK\x05\x06", 0, 0, 1, 1, len(central), central_offset, 0)
        with tempfile.TemporaryDirectory(prefix="calds_irs_zip_") as temp:
            temp_dir = Path(temp)
            zip_path = temp_dir / "single-entry.zip"
            zip_path.write_bytes(local_header + compressed + central + eocd)
            result = subprocess.run(
                [str(seven_zip), "x", "-y", str(zip_path), f"-o{temp_dir}"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                raise ValueError(f"7-Zip fallback failed for {name}: {result.stderr.strip()}")
            return (temp_dir / name).read_bytes()


def copy_stage1_corpus(stage1: Path, stage2: Path) -> None:
    stage2.mkdir(parents=True, exist_ok=True)
    if stage1.exists() and stage1.resolve() == stage2.resolve():
        return
    for existing in stage2.glob("*.json"):
        existing.unlink()
    if not stage1.exists():
        return
    for source in sorted(stage1.glob("*.json")):
        shutil.copy2(source, stage2 / source.name)


def build_record(
    record_id: str,
    title: str,
    source_uri: str,
    source_type: str,
    published_at: str,
    entities: list[str],
    body: str,
    signals: dict[str, Any] | None = None,
    attributes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    attrs = dict(attributes or {})
    attrs["signals"] = dict(signals or {})
    return {
        "record_id": record_id,
        "title": title,
        "source_uri": source_uri,
        "source_type": source_type,
        "published_at": published_at,
        "collected_at": utc_now(),
        "entities": entities,
        "attributes": attrs,
        "body": body,
    }


def csv_rows(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": "CalDS-local-ingest/0.1"})
    with urllib.request.urlopen(request, timeout=180) as response:
        text = (line.decode("utf-8-sig", "replace") for line in response)
        yield from csv.DictReader(text)


def irs_index_url(index_year: int) -> str:
    return f"{IRS_XML_BASE}/{index_year}/index_{index_year}.csv"


def irs_zip_url(batch: str) -> str:
    normalized = batch.upper()
    year = normalized[:4]
    return f"{IRS_XML_BASE}/{year}/{normalized}.zip"


def tax_period_year(row: dict[str, Any]) -> int | None:
    value = str(row.get("TAX_PERIOD", ""))
    if len(value) < 4 or not value[:4].isdigit():
        return None
    return int(value[:4])


def resolve_zip_member_name(entries: dict[str, dict[str, Any]], filename: str) -> str | None:
    if filename in entries:
        return filename
    suffix = "/" + filename
    matches = [name for name in entries if name.endswith(suffix)]
    if len(matches) == 1:
        return matches[0]
    return None


def ingest_irs_xml(artifacts: Path, corpus: Path, tax_period_years: list[int]) -> dict[str, Any]:
    target_by_ein = {target.ein: target for target in TARGETS}
    wanted_years = sorted(set(tax_period_years))
    index_years = list(range(min(wanted_years) + 1, max(wanted_years) + 2)) if wanted_years else []
    matches: list[dict[str, Any]] = []
    rows_by_target_year: dict[tuple[str, int], dict[str, Any]] = {}
    index_probe_manifest: list[dict[str, Any]] = []

    for index_year in index_years:
        url = irs_index_url(index_year)
        year_matches: list[dict[str, Any]] = []
        try:
            for row in csv_rows(url):
                ein = (row.get("EIN") or row.get("ein") or "").zfill(9)
                if ein not in target_by_ein:
                    continue
                year = tax_period_year(row)
                if year not in wanted_years:
                    continue
                normalized = dict(row)
                normalized["_index_year"] = index_year
                normalized["_index_url"] = url
                normalized["_tax_period_year"] = year
                matches.append(normalized)
                year_matches.append(normalized)
                key = (ein, year)
                current = rows_by_target_year.get(key)
                if current is None or str(normalized.get("TAX_PERIOD", "")) > str(current.get("TAX_PERIOD", "")):
                    rows_by_target_year[key] = normalized
            index_probe_manifest.append({"index_year": index_year, "url": url, "matched_rows": len(year_matches), "status": "ok"})
            write_json(artifacts / f"irs_{index_year}_index_matches.json", year_matches)
        except Exception as exc:
            index_probe_manifest.append({"index_year": index_year, "url": url, "matched_rows": 0, "status": "error", "error": repr(exc)})

    write_json(artifacts / "irs_index_probe_manifest.json", index_probe_manifest)
    write_json(artifacts / "irs_index_matches.json", matches)

    by_zip: dict[str, RemoteZip] = {}
    xml_dir = artifacts / "irs_xml"
    manifest: list[dict[str, Any]] = []
    for target in TARGETS:
        for year in wanted_years:
            row = rows_by_target_year.get((target.ein, year))
            if row is None:
                source_record = {
                    "target": target.name,
                    "ein": target.ein,
                    "tax_period_year": year,
                    "downloaded": False,
                    "status": "irs_index_row_missing",
                    "note": f"No IRS XML index row was found for {target.name} tax period year {year} in probed IRS indexes {index_years}.",
                }
                manifest.append(source_record)
                record = build_record(
                    record_id=f"irs_990_xml_manifest_missing_{target.slug}_{year}",
                    title=f"IRS Form 990 XML manifest gap: {target.name} tax period {year}",
                    source_uri="; ".join(irs_index_url(index_year) for index_year in index_years),
                    source_type="irs_990_download_manifest",
                    published_at=str(year),
                    entities=[target.name, *target.aliases],
                    body=source_record["note"],
                    signals={"missing_data": True, "full_990_xml_missing": True, "irs_index_row_missing": True},
                    attributes={"tax_period_year": year, "probed_index_years": index_years},
                )
                write_json(corpus / f"{record['record_id']}.json", record)
                continue

            object_id = row.get("OBJECT_ID") or row.get("object_id")
            batch = row.get("XML_BATCH_ID") or row.get("xml_batch_id")
            if not object_id or not batch:
                source_record = {
                    "target": target.name,
                    "ein": target.ein,
                    "tax_period": row.get("TAX_PERIOD", ""),
                    "tax_period_year": year,
                    "object_id": object_id or "",
                    "xml_batch_id": batch or "",
                    "downloaded": False,
                    "status": "irs_index_row_missing_batch",
                    "note": "The IRS index row was found, but no XML batch was provided.",
                }
                manifest.append(source_record)
                record = build_record(
                    record_id=f"irs_990_xml_manifest_missing_{target.slug}_{year}",
                    title=f"IRS Form 990 XML manifest gap: {target.name} tax period {year}",
                    source_uri=str(row.get("_index_url", "")),
                    source_type="irs_990_download_manifest",
                    published_at=str(row.get("TAX_PERIOD", year)),
                    entities=[target.name, *target.aliases],
                    body=source_record["note"],
                    signals={"missing_data": True, "full_990_xml_missing": True, "irs_index_row_found": True},
                    attributes={"irs_index_row": row},
                )
                write_json(corpus / f"{record['record_id']}.json", record)
                continue

            zip_url = irs_zip_url(str(batch))
            filename = f"{object_id}_public.xml"
            try:
                if zip_url not in by_zip:
                    by_zip[zip_url] = RemoteZip(zip_url)
                zip_entries = by_zip[zip_url].entries
            except Exception as exc:
                zip_entries = {}
                zip_error = repr(exc)
            else:
                zip_error = ""

            member_name = resolve_zip_member_name(zip_entries, filename)
            if member_name is None:
                source_record = {
                    "target": target.name,
                    "ein": target.ein,
                    "object_id": object_id,
                    "tax_period": row.get("TAX_PERIOD", ""),
                    "tax_period_year": year,
                    "xml_batch_id": batch,
                    "zip_url": zip_url,
                    "xml_filename": filename,
                    "downloaded": False,
                    "status": "xml_object_missing_from_zip",
                    "note": "The IRS index row was found, but the named XML object was not present in the listed ZIP central directory during this run.",
                    "zip_error": zip_error,
                }
                manifest.append(source_record)
                record = build_record(
                    record_id=f"irs_990_xml_manifest_missing_{target.slug}_{year}",
                    title=f"IRS Form 990 XML manifest gap: {target.name} tax period {year}",
                    source_uri=f"{zip_url}#{filename}",
                    source_type="irs_990_download_manifest",
                    published_at=str(row.get("TAX_PERIOD", "")),
                    entities=[target.name, *target.aliases],
                    body=source_record["note"],
                    signals={"missing_data": True, "full_990_xml_missing": True, "irs_index_row_found": True},
                    attributes={"irs_index_row": row, "tax_period_year": year, "zip_error": zip_error},
                )
                write_json(corpus / f"{record['record_id']}.json", record)
                continue

            xml_bytes = by_zip[zip_url].extract(member_name)
            xml_path = xml_dir / str(year) / filename
            xml_path.parent.mkdir(parents=True, exist_ok=True)
            xml_path.write_bytes(xml_bytes)
            summary = parse_990_xml(xml_bytes)
            checksum = sha256_bytes(xml_bytes)
            xml_uri = f"{zip_url}#{member_name}"
            source_record = {
                "target": target.name,
                "ein": target.ein,
                "object_id": object_id,
                "tax_period": row.get("TAX_PERIOD", ""),
                "tax_period_year": year,
                "xml_batch_id": batch,
                "zip_url": zip_url,
                "xml_filename": filename,
                "xml_member_name": member_name,
                "local_xml_path": str(xml_path),
                "sha256": checksum,
                "summary": summary,
                "downloaded": True,
                "status": "downloaded",
            }
            manifest.append(source_record)
            signals = {
                "full_990_xml_downloaded": True,
                "schedule_l_present": summary.get("schedule_l_present", False),
                "schedule_r_present": summary.get("schedule_r_present", False),
                "irs_990_pdf_unavailable": True,
            }
            body = "\n".join(
                [
                    f"IRS Form 990 XML downloaded for {target.name}.",
                    f"EIN: {target.ein}",
                    f"Tax period year: {year}",
                    f"Tax period: {row.get('TAX_PERIOD', '')}",
                    f"Object ID: {object_id}",
                    f"ZIP batch: {batch}",
                    f"Local XML path: {xml_path}",
                    f"SHA256: {checksum}",
                    "Selected XML fields:",
                    json.dumps(summary, indent=2, sort_keys=True),
                    "Official IRS bulk source currently exposes the return as XML; no official bulk PDF was available from this IRS page during this run.",
                ]
            )
            record = build_record(
                record_id=f"irs_990_xml_{target.slug}_{year}",
                title=f"IRS Form 990 XML: {target.name} tax period {year}",
                source_uri=xml_uri,
                source_type="irs_990_xml",
                published_at=str(row.get("TAX_PERIOD", "")),
                entities=[target.name, *target.aliases],
                body=body,
                signals=signals,
                attributes={"irs_index_row": row, "xml_sha256": checksum, "local_xml_path": str(xml_path), "tax_period_year": year},
            )
            write_json(corpus / f"{record['record_id']}.json", record)

    write_json(artifacts / "irs_xml_download_manifest.json", manifest)
    return {"matches": matches, "downloads": manifest, "index_probes": index_probe_manifest, "tax_period_years": wanted_years}


def parse_990_xml(xml_bytes: bytes) -> dict[str, Any]:
    root = ET.fromstring(xml_bytes)

    def local_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    values: dict[str, list[str]] = {}
    for elem in root.iter():
        text = (elem.text or "").strip()
        if not text:
            continue
        values.setdefault(local_name(elem.tag), []).append(text)

    wanted = [
        "ReturnTypeCd",
        "TaxYr",
        "TaxPeriodBeginDt",
        "TaxPeriodEndDt",
        "EIN",
        "BusinessNameLine1Txt",
        "BusinessNameLine2Txt",
        "GrossReceiptsAmt",
        "CYTotalRevenueAmt",
        "TotalRevenueAmt",
        "CYTotalExpensesAmt",
        "TotalFunctionalExpensesAmt",
        "TotalAssetsEOYAmt",
        "NetAssetsOrFundBalancesEOYAmt",
        "GovernmentGrantsAmt",
        "AllOtherContributionsAmt",
        "ProgramServiceRevenueAmt",
    ]
    summary = {key: values.get(key, [""])[0] for key in wanted if values.get(key)}
    tag_names = set(values)
    summary["schedule_l_present"] = any("ScheduleL" in key for key in tag_names)
    summary["schedule_r_present"] = any("ScheduleR" in key for key in tag_names)
    summary["nonempty_tag_count"] = len(values)
    return summary


def ingest_fac(artifacts: Path, corpus: Path, include_federal_awards: bool = True) -> dict[str, Any]:
    target_by_ein = {target.ein: target for target in TARGETS}
    general_rows: list[dict[str, Any]] = []
    for row in csv_rows(FAC_CSVS["general"]):
        ein = (row.get("auditee_ein") or "").zfill(9)
        if ein in target_by_ein:
            general_rows.append(row)

    write_json(artifacts / "fac_general_matches.json", general_rows)
    report_ids = sorted({row["report_id"] for row in general_rows if row.get("report_id")})

    findings = filter_fac_table("findings", report_ids, artifacts)
    findings_text = filter_fac_table("findings_text", report_ids, artifacts)
    corrective = filter_fac_table("corrective_action_plans", report_ids, artifacts)
    awards: list[dict[str, Any]] = []
    if include_federal_awards:
        awards = filter_fac_table("federal_awards", report_ids, artifacts)

    findings_by_report: dict[str, list[dict[str, Any]]] = {}
    for row in findings:
        findings_by_report.setdefault(row.get("report_id", ""), []).append(row)

    awards_by_report: dict[str, list[dict[str, Any]]] = {}
    for row in awards:
        awards_by_report.setdefault(row.get("report_id", ""), []).append(row)

    pdf_dir = artifacts / "fac_audit_pdfs"
    pdf_manifest: list[dict[str, Any]] = []
    latest_by_ein: dict[str, dict[str, Any]] = {}
    for row in general_rows:
        ein = (row.get("auditee_ein") or "").zfill(9)
        current = latest_by_ein.get(ein)
        if current is None or str(row.get("audit_year", "")) > str(current.get("audit_year", "")):
            latest_by_ein[ein] = row
    significant_reports = {
        row["report_id"]
        for row in general_rows
        if row.get("is_material_weakness") == "Y"
        or row.get("is_material_weakness") is True
        or row.get("is_significant_deficiency") == "Y"
        or row.get("is_internal_control_material_weakness_disclosed") == "Yes"
        or row.get("is_internal_control_deficiency_disclosed") == "Yes"
        or row.get("is_low_risk_auditee") == "No"
        or row.get("is_low_risk_auditee") == "N"
    }
    pdf_report_ids = report_ids
    for report_id in pdf_report_ids:
        url = f"https://app.fac.gov/dissemination/report/pdf/{report_id}"
        pdf_path = pdf_dir / f"{report_id}.pdf"
        try:
            pdf_bytes, final_url = fetch_bytes(url, timeout=120)
            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            pdf_path.write_bytes(pdf_bytes)
            pdf_manifest.append(
                {
                    "report_id": report_id,
                    "url": url,
                    "final_url": final_url,
                    "local_pdf_path": str(pdf_path),
                    "sha256": sha256_bytes(pdf_bytes),
                    "bytes": len(pdf_bytes),
                    "downloaded": True,
                }
            )
        except Exception as exc:
            pdf_manifest.append({"report_id": report_id, "url": url, "downloaded": False, "error": repr(exc)})
    write_json(artifacts / "fac_audit_pdf_manifest.json", pdf_manifest)

    general_by_report = {row.get("report_id", ""): row for row in general_rows}
    for row in general_rows:
        report_id = row.get("report_id", "")
        ein = (row.get("auditee_ein") or "").zfill(9)
        target = target_by_ein.get(ein)
        if not target or not report_id:
            continue
        report_findings = findings_by_report.get(report_id, [])
        report_awards = awards_by_report.get(report_id, [])
        pdf = next((item for item in pdf_manifest if item.get("report_id") == report_id), None)
        signals = fac_signals(row, report_findings)
        if pdf and pdf.get("downloaded"):
            signals["fac_audit_pdf_downloaded"] = True
        if report_awards:
            signals["fac_federal_awards_present"] = True
        body = "\n".join(
            [
                f"FAC general-table record for {target.name}.",
                f"Report ID: {report_id}",
                f"Audit year: {row.get('audit_year', '')}",
                f"FAC accepted date: {row.get('fac_accepted_date', '')}",
                f"Auditee name: {row.get('auditee_name', '')}",
                f"Auditee EIN: {ein}",
                f"Audit type: {row.get('audit_type', '') or row.get('audit_report_type', '')}",
                f"Total amount expended: {row.get('total_amount_expended', '')}",
                f"Low-risk auditee: {row.get('is_low_risk_auditee', '')}",
                f"Prior findings agency prefixes: {row.get('agencies_with_prior_findings', '') or row.get('prior_findings', '')}",
                f"Matching findings rows: {len(report_findings)}",
                f"Matching federal award rows: {len(report_awards)}",
                f"Audit PDF path: {pdf.get('local_pdf_path') if pdf else 'not downloaded'}",
                "Selected FAC general row:",
                json.dumps(row, indent=2, sort_keys=True),
            ]
        )
        record = build_record(
            record_id=f"fac_general_{safe_slug(report_id)}",
            title=f"FAC audit record: {target.name} {row.get('audit_year', '')}",
            source_uri=f"https://app.fac.gov/dissemination/report/pdf/{report_id}",
            source_type="fac_audit_pdf",
            published_at=str(row.get("fac_accepted_date") or row.get("audit_year", "")),
            entities=[target.name, *target.aliases],
            body=body,
            signals=signals,
            attributes={
                "fac_general_row": row,
                "fac_findings_rows": report_findings,
                "fac_federal_award_rows": report_awards[:50],
                "fac_pdf_manifest": pdf or {},
            },
        )
        write_json(corpus / f"{record['record_id']}.json", record)

    if findings:
        record = build_record(
            record_id="fac_findings_filtered_targets",
            title="FAC findings rows filtered to target EIN reports",
            source_uri=FAC_CSVS["findings"],
            source_type="fac_findings",
            published_at="2016-present",
            entities=[target.name for target in TARGETS],
            body=f"Filtered FAC findings table rows for target report IDs. Row count: {len(findings)}.",
            signals={"fac_current_year_findings": True},
            attributes={"rows": findings},
        )
        write_json(corpus / f"{record['record_id']}.json", record)
    if awards:
        record = build_record(
            record_id="fac_federal_awards_filtered_targets",
            title="FAC federal award ledger rows filtered to target EIN reports",
            source_uri=FAC_CSVS["federal_awards"],
            source_type="fac_federal_awards",
            published_at="2016-present",
            entities=[target.name for target in TARGETS],
            body=f"Filtered FAC federal_awards table rows for target report IDs. Row count: {len(awards)}.",
            signals={"fac_federal_awards_present": True},
            attributes={"row_count": len(awards), "sample_rows": awards[:100]},
        )
        write_json(corpus / f"{record['record_id']}.json", record)

    return {
        "general_rows": general_rows,
        "findings": findings,
        "findings_text": findings_text,
        "corrective_action_plans": corrective,
        "federal_awards": awards,
        "pdfs": pdf_manifest,
    }


def filter_fac_table(table: str, report_ids: list[str], artifacts: Path) -> list[dict[str, Any]]:
    wanted = set(report_ids)
    rows: list[dict[str, Any]] = []
    if not wanted:
        return rows
    start = time.time()
    for row in csv_rows(FAC_CSVS[table]):
        if row.get("report_id") in wanted:
            rows.append(row)
    write_json(
        artifacts / f"fac_{table}_matches.json",
        {
            "source_url": FAC_CSVS[table],
            "elapsed_seconds": round(time.time() - start, 2),
            "row_count": len(rows),
            "rows": rows,
        },
    )
    return rows


def fac_signals(general: dict[str, Any], findings: list[dict[str, Any]]) -> dict[str, Any]:
    def yes(value: Any) -> bool:
        return str(value).strip().lower() in {"y", "yes", "true", "1"}

    signals: dict[str, Any] = {}
    if (
        yes(general.get("is_material_weakness"))
        or yes(general.get("is_internal_control_material_weakness_disclosed"))
        or any(yes(row.get("is_material_weakness")) for row in findings)
    ):
        signals["fac_material_weakness"] = True
    if yes(general.get("is_significant_deficiency")) or yes(general.get("is_internal_control_deficiency_disclosed")):
        signals["fac_significant_deficiency"] = True
    if str(general.get("is_low_risk_auditee", "")).strip().lower() in {"n", "no", "false"}:
        signals["fac_low_risk_no"] = True
    if general.get("prior_findings") or general.get("agencies_with_prior_findings"):
        signals["fac_prior_findings"] = True
    if findings:
        signals["fac_current_year_findings"] = True
    if any(yes(row.get("is_questioned_costs")) for row in findings):
        signals["fac_questioned_costs"] = True
    if any(yes(row.get("is_repeat_finding")) for row in findings):
        signals["fac_repeat_finding"] = True
    return signals


def ingest_dhcs(artifacts: Path, corpus: Path) -> dict[str, Any]:
    current_records: list[dict[str, Any]] = []
    status_records: list[dict[str, Any]] = []
    for target in TARGETS:
        current_records.extend(query_dhcs_service(DHCS_CURRENT_FACILITIES, target, ("Legal_Entity_Name", "Facility_Name"), limit=200))
        status_records.extend(query_dhcs_service(DHCS_LCD_STATUS, target, ("LENAME", "NAME"), limit=200))

    write_json(artifacts / "dhcs_current_facility_matches.json", current_records)
    write_json(artifacts / "dhcs_lcd_status_matches.json", status_records)

    adverse_page_bytes, final_url = fetch_bytes(DHCS_ADVERSE_PAGE, timeout=60)
    adverse_manifest = {
        "source_uri": DHCS_ADVERSE_PAGE,
        "final_url": final_url,
        "bytes": len(adverse_page_bytes),
        "sha256": sha256_bytes(adverse_page_bytes),
        "contains_target_alias": {
            target.name: any(alias.lower().encode() in adverse_page_bytes.lower() for alias in (target.name, *target.aliases))
            for target in TARGETS
        },
        "note": "The DHCS page identifies an adverse-status list, but the page did not expose table rows in the static HTML fetched during this run.",
    }
    write_json(artifacts / "dhcs_adverse_status_page_manifest.json", adverse_manifest)

    for target in TARGETS:
        target_status = [
            row for row in status_records if row.get("_target_slug") == target.slug
        ]
        if not target_status:
            continue
        statuses = sorted({str(row.get("FACILITY_STATUS", "")).strip() for row in target_status if row.get("FACILITY_STATUS")})
        closed_count = sum(1 for row in target_status if str(row.get("FACILITY_STATUS", "")).lower() == "closed")
        active_count = sum(1 for row in target_status if str(row.get("FACILITY_STATUS", "")).lower() == "active")
        signals = {
            "dhcs_facility_status_crosscheck": True,
            "dhcs_adverse_status_page_checked": True,
            "dhcs_status_crosscheck_incomplete": True,
        }
        if closed_count:
            signals["dhcs_facility_closed_status"] = True
        body = "\n".join(
            [
                f"DHCS facility-status cross-check for {target.name}.",
                f"LCD status rows matched: {len(target_status)}",
                f"Active rows: {active_count}",
                f"Closed rows: {closed_count}",
                f"Statuses observed: {', '.join(statuses)}",
                "The separate DHCS adverse-status page was checked, but static HTML did not expose a machine-readable table in this run.",
                "Facility-level status rows are licensing/certification context; closed rows are not entity-level adverse findings without source-specific follow-up.",
            ]
        )
        record = build_record(
            record_id=f"dhcs_facility_status_{target.slug}",
            title=f"DHCS SUD facility-status matches: {target.name}",
            source_uri=DHCS_LCD_STATUS,
            source_type="dhcs_facility_status",
            published_at="2026-04-15",
            entities=[target.name, *target.aliases],
            body=body,
            signals=signals,
            attributes={
                "matched_status_rows": target_status,
                "dhcs_adverse_status_page_manifest": adverse_manifest,
            },
        )
        write_json(corpus / f"{record['record_id']}.json", record)

    manifest_record = build_record(
        record_id="dhcs_adverse_status_page_manifest",
        title="DHCS adverse-status page machine-readability manifest",
        source_uri=DHCS_ADVERSE_PAGE,
        source_type="dhcs_adverse_status_manifest",
        published_at="2025-10-16",
        entities=[target.name for target in TARGETS],
        body=adverse_manifest["note"],
        signals={"missing_data": True, "dhcs_status_crosscheck_incomplete": True},
        attributes=adverse_manifest,
    )
    write_json(corpus / f"{manifest_record['record_id']}.json", manifest_record)
    return {"current": current_records, "status": status_records, "adverse_manifest": adverse_manifest}


def query_dhcs_service(service_url: str, target: Target, fields: tuple[str, str], limit: int) -> list[dict[str, Any]]:
    clauses = []
    for alias in (target.name, *target.aliases):
        escaped = alias.upper().replace("'", "''")
        for field in fields:
            clauses.append(f"UPPER({field}) LIKE '%{escaped}%'")
    params = {
        "f": "json",
        "where": " OR ".join(clauses),
        "outFields": "*",
        "returnGeometry": "false",
        "resultRecordCount": str(limit),
    }
    url = f"{service_url}/query?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": "CalDS-local-ingest/0.1"})
    with urllib.request.urlopen(request, timeout=90) as response:
        data = json.load(response)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for feature in data.get("features", []):
        attrs = dict(feature.get("attributes", {}))
        key = json.dumps(attrs, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        attrs["_target_slug"] = target.slug
        attrs["_target_name"] = target.name
        rows.append(attrs)
    return rows


def ingest_county_and_contract_docs(artifacts: Path, corpus: Path) -> dict[str, Any]:
    doc_dir = artifacts / "county_contract_monitoring_docs"
    manifest: list[dict[str, Any]] = []
    for doc in COUNTY_AND_CONTRACT_DOCS:
        pdf_path = doc_dir / f"{doc['record_id']}.pdf"
        try:
            pdf_bytes, final_url = fetch_bytes(doc["url"], timeout=120)
            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            pdf_path.write_bytes(pdf_bytes)
            checksum = sha256_bytes(pdf_bytes)
            downloaded = True
            error = ""
        except Exception as exc:
            final_url = doc["url"]
            checksum = ""
            downloaded = False
            error = repr(exc)
        manifest.append(
            {
                "record_id": doc["record_id"],
                "url": doc["url"],
                "final_url": final_url,
                "local_pdf_path": str(pdf_path) if downloaded else "",
                "sha256": checksum,
                "downloaded": downloaded,
                "error": error,
            }
        )
        body = "\n".join(
            [
                doc["title"],
                f"Source URI: {doc['url']}",
                f"Local PDF path: {pdf_path if downloaded else 'not downloaded'}",
                f"SHA256: {checksum or 'not available'}",
                "This is a source document for reviewer triage only; the workflow must not convert monitoring or contract records into an entity-level conclusion without human review.",
            ]
        )
        record = build_record(
            record_id=doc["record_id"],
            title=doc["title"],
            source_uri=doc["url"],
            source_type="county_contract_or_monitoring",
            published_at=doc["published_at"],
            entities=doc["entities"],
            body=body,
            signals=doc["signals"],
            attributes={"local_pdf_path": str(pdf_path) if downloaded else "", "sha256": checksum, "downloaded": downloaded},
        )
        write_json(corpus / f"{record['record_id']}.json", record)
    write_json(artifacts / "county_contract_monitoring_manifest.json", manifest)
    return {"docs": manifest}


def ingest_litigation_manifest(artifacts: Path, corpus: Path) -> dict[str, Any]:
    write_json(artifacts / "litigation_search_manifest.json", COURT_SEARCH_MANIFESTS)
    for item in COURT_SEARCH_MANIFESTS:
        record = build_record(
            record_id=item["record_id"],
            title=item["title"],
            source_uri=item["url"],
            source_type="court_docket_manifest",
            published_at=item["published_at"],
            entities=item["entities"],
            body=item["body"],
            signals=item["signals"],
            attributes={"manifest_kind": "official-court-calendar-search-hit"},
        )
        write_json(corpus / f"{record['record_id']}.json", record)
    return {"manifests": COURT_SEARCH_MANIFESTS}


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest live California recovery-treatment source artifacts.")
    parser.add_argument("--stage1-corpus", type=Path, default=DEFAULT_STAGE1_CORPUS)
    parser.add_argument("--stage2-corpus", type=Path, default=DEFAULT_STAGE2_CORPUS)
    parser.add_argument("--artifacts-dir", type=Path, default=DEFAULT_ARTIFACTS)
    parser.add_argument("--skip-federal-awards", action="store_true")
    parser.add_argument("--tax-period-years", type=int, nargs="+", default=DEFAULT_TAX_PERIOD_YEARS)
    args = parser.parse_args()

    args.stage2_corpus.mkdir(parents=True, exist_ok=True)
    args.artifacts_dir.mkdir(parents=True, exist_ok=True)
    copy_stage1_corpus(args.stage1_corpus, args.stage2_corpus)

    summary: dict[str, Any] = {
        "started_at": utc_now(),
        "stage1_corpus": str(args.stage1_corpus),
        "stage2_corpus": str(args.stage2_corpus),
        "artifacts_dir": str(args.artifacts_dir),
        "targets": [target.__dict__ for target in TARGETS],
    }
    summary["tax_period_years"] = sorted(set(args.tax_period_years))
    summary["irs"] = ingest_irs_xml(args.artifacts_dir, args.stage2_corpus, summary["tax_period_years"])
    summary["fac"] = ingest_fac(args.artifacts_dir, args.stage2_corpus, include_federal_awards=not args.skip_federal_awards)
    summary["dhcs"] = ingest_dhcs(args.artifacts_dir, args.stage2_corpus)
    summary["county_contracts"] = ingest_county_and_contract_docs(args.artifacts_dir, args.stage2_corpus)
    summary["litigation"] = ingest_litigation_manifest(args.artifacts_dir, args.stage2_corpus)
    summary["completed_at"] = utc_now()
    summary["stage2_corpus_record_count"] = len(list(args.stage2_corpus.glob("*.json")))
    write_json(args.artifacts_dir / "ingest_summary.json", summary)
    print(f"stage2_corpus={args.stage2_corpus}")
    print(f"artifacts_dir={args.artifacts_dir}")
    print(f"records={summary['stage2_corpus_record_count']}")
    print(f"irs_xml_manifest_entries={len(summary['irs']['downloads'])}")
    print(f"fac_general_rows={len(summary['fac']['general_rows'])}")
    print(f"fac_findings_rows={len(summary['fac']['findings'])}")
    print(f"fac_federal_awards_rows={len(summary['fac']['federal_awards'])}")
    print(f"dhcs_status_rows={len(summary['dhcs']['status'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

