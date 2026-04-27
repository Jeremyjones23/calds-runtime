from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
from typing import Any
import xml.etree.ElementTree as ET

import pdfplumber
from pypdf import PdfReader


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STAGE2_CORPUS = PROJECT_ROOT / "data" / "live_corpus" / "ca_recovery_ngos_2026_04_24_stage2"
DEFAULT_STAGE3_CORPUS = PROJECT_ROOT / "data" / "live_corpus" / "ca_recovery_ngos_2026_04_24_stage3"
DEFAULT_ARTIFACTS = PROJECT_ROOT / "artifacts" / "live_recovery_sources_2026_04_24"
DEFAULT_PARSED = DEFAULT_ARTIFACTS / "parsed"

TARGETS = {
    "942219349": {"slug": "tarzana", "name": "Tarzana Treatment Centers Inc"},
    "946129071": {"slug": "healthright", "name": "HealthRIGHT 360"},
    "237368450": {"slug": "westcare", "name": "WestCare California Inc"},
    "952838006": {"slug": "bhs", "name": "Behavioral Health Services Inc"},
    "952758951": {"slug": "crihelp", "name": "CRI-Help Inc"},
    "954079133": {"slug": "socialmodel", "name": "Social Model Recovery Systems Inc"},
    "943015376": {"slug": "phoenix", "name": "Phoenix Houses Of California Inc"},
}

KEY_TERMS = [
    "material weakness",
    "significant deficiency",
    "questioned costs",
    "repeat finding",
    "corrective action",
    "prior finding",
    "low-risk",
    "finding",
    "contract",
    "monitoring",
    "recovery bridge housing",
    "substance abuse prevention and control",
    "HealthRIGHT 360",
    "Tarzana",
    "Behavioral Health Services",
    "CRI-Help",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", "replace")).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def copy_corpus(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    if source.exists() and source.resolve() == destination.resolve():
        return
    for existing in destination.glob("*.json"):
        existing.unlink()
    for path in sorted(source.glob("*.json")):
        shutil.copy2(path, destination / path.name)


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def first_value(values: dict[str, list[str]], *keys: str) -> str:
    for key in keys:
        found = values.get(key)
        if found:
            return found[0]
    return ""


def child_text(elem: ET.Element, name: str) -> str:
    for child in list(elem):
        if local_name(child.tag) == name:
            return (child.text or "").strip()
    return ""


def number_text(value: str) -> int:
    try:
        return int(float(str(value).replace(",", "")))
    except Exception:
        return 0


def bool_indicator(value: str) -> bool | str:
    if value == "":
        return ""
    return str(value).strip().lower() in {"1", "true", "yes", "y", "x"}


def parse_part_vii_compensation(root: ET.Element) -> dict[str, Any]:
    people: list[dict[str, Any]] = []
    for elem in root.iter():
        if local_name(elem.tag) != "Form990PartVIISectionAGrp":
            continue
        reportable_org = number_text(child_text(elem, "ReportableCompFromOrgAmt"))
        reportable_related = number_text(child_text(elem, "ReportableCompFromRltdOrgAmt"))
        other = number_text(child_text(elem, "OtherCompensationAmt"))
        total = reportable_org + reportable_related + other
        people.append(
            {
                "person": child_text(elem, "PersonNm") or child_text(elem, "BusinessNameLine1Txt"),
                "title": child_text(elem, "TitleTxt"),
                "officer": bool(child_text(elem, "OfficerInd")),
                "key_employee": bool(child_text(elem, "KeyEmployeeInd")),
                "highest_compensated_employee": bool(child_text(elem, "HighestCompensatedEmployeeInd")),
                "reportable_comp_from_org": reportable_org,
                "reportable_comp_from_related_org": reportable_related,
                "other_compensation": other,
                "total_compensation": total,
            }
        )
    people = [person for person in people if person["person"] or person["total_compensation"]]
    ranked = sorted(people, key=lambda item: item["total_compensation"], reverse=True)
    top = ranked[0] if ranked else {}
    officer_key = [person for person in ranked if person.get("officer") or person.get("key_employee") or person.get("highest_compensated_employee")]
    return {
        "top_compensation_person": top.get("person", ""),
        "top_compensation_title": top.get("title", ""),
        "top_compensation_total": top.get("total_compensation", ""),
        "top_compensation_from_org": top.get("reportable_comp_from_org", ""),
        "top_compensation_from_related_org": top.get("reportable_comp_from_related_org", ""),
        "top_compensation_other": top.get("other_compensation", ""),
        "top_five_compensation_total": sum(person["total_compensation"] for person in ranked[:5]),
        "officer_key_employee_compensation_total": sum(person["total_compensation"] for person in officer_key),
        "part_vii_person_count": len(people),
    }


def parse_irs_xml(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    root = ET.fromstring(raw)
    values: dict[str, list[str]] = defaultdict(list)
    for elem in root.iter():
        text = (elem.text or "").strip()
        if text:
            values[local_name(elem.tag)].append(text)

    tag_names = set(values)
    parsed = {
        "local_xml_path": str(path),
        "xml_sha256": hashlib.sha256(raw).hexdigest(),
        "ein": first_value(values, "EIN"),
        "tax_year": first_value(values, "TaxYr"),
        "tax_period_begin": first_value(values, "TaxPeriodBeginDt"),
        "tax_period_end": first_value(values, "TaxPeriodEndDt"),
        "return_type": first_value(values, "ReturnTypeCd"),
        "business_name": " ".join(
            part for part in [first_value(values, "BusinessNameLine1Txt"), first_value(values, "BusinessNameLine2Txt")] if part
        ),
        "gross_receipts": first_value(values, "GrossReceiptsAmt"),
        "total_revenue": first_value(values, "CYTotalRevenueAmt", "TotalRevenueAmt"),
        "total_expenses": first_value(values, "CYTotalExpensesAmt", "TotalFunctionalExpensesAmt"),
        "total_assets_eoy": first_value(values, "TotalAssetsEOYAmt"),
        "net_assets_eoy": first_value(values, "NetAssetsOrFundBalancesEOYAmt"),
        "government_grants": first_value(values, "GovernmentGrantsAmt"),
        "program_service_revenue": first_value(values, "ProgramServiceRevenueAmt"),
        "salaries_comp_benefits_current_year": first_value(values, "CYSalariesCompEmpBnftPaidAmt", "SalariesOtherCompEmplBnftAmt"),
        "total_employee_count": first_value(values, "TotalEmployeeCnt", "EmployeeCnt"),
        "political_campaign_activity": bool_indicator(first_value(values, "PoliticalCampaignActyInd")),
        "lobbying_activities": bool_indicator(first_value(values, "LobbyingActivitiesInd")),
        "compensation_process_ceo": bool_indicator(first_value(values, "CompensationProcessCEOInd")),
        "compensation_process_other": bool_indicator(first_value(values, "CompensationProcessOtherInd")),
        "schedule_l_present": any("ScheduleL" in name for name in tag_names),
        "schedule_r_present": any("ScheduleR" in name for name in tag_names),
        "nonempty_tag_count": len(values),
    }
    parsed.update(parse_part_vii_compensation(root))
    return parsed


def build_irs_table(artifacts: Path) -> tuple[list[dict[str, Any]], list[str]]:
    manifest = read_json(artifacts / "irs_xml_download_manifest.json")
    rows: list[dict[str, Any]] = []
    notes: list[str] = []
    for item in manifest:
        row = {
            "entity": item.get("target", ""),
            "ein": item.get("ein", ""),
            "tax_period": item.get("tax_period", ""),
            "tax_period_year": item.get("tax_period_year") or str(item.get("tax_period", ""))[:4],
            "object_id": item.get("object_id", ""),
            "xml_batch_id": item.get("xml_batch_id", ""),
            "downloaded": bool(item.get("local_xml_path")),
        }
        xml_path = item.get("local_xml_path")
        if xml_path and Path(xml_path).exists():
            row.update(parse_irs_xml(Path(xml_path)))
        else:
            row["parse_status"] = "missing_xml_object"
            notes.append(f"IRS XML missing for {row['entity']} object {row['object_id']}.")
        rows.append(row)
    return rows, notes


def yes(value: Any) -> bool:
    return str(value).strip().lower() in {"y", "yes", "true", "1"}


def intish(value: Any) -> int:
    try:
        return int(float(str(value).replace(",", "")))
    except Exception:
        return 0


def build_fac_tables(artifacts: Path) -> dict[str, Any]:
    general = read_json(artifacts / "fac_general_matches.json")
    findings = read_json(artifacts / "fac_findings_matches.json")["rows"]
    awards = read_json(artifacts / "fac_federal_awards_matches.json")["rows"]
    pdf_manifest = read_json(artifacts / "fac_audit_pdf_manifest.json")
    pdf_by_report = {item.get("report_id"): item for item in pdf_manifest}
    findings_by_report: dict[str, list[dict[str, Any]]] = defaultdict(list)
    awards_by_report: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in findings:
        findings_by_report[row.get("report_id", "")].append(row)
    for row in awards:
        awards_by_report[row.get("report_id", "")].append(row)

    entity_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in general:
        entity_rows[(row.get("auditee_ein") or "").zfill(9)].append(row)

    audit_summary: list[dict[str, Any]] = []
    for ein, rows in sorted(entity_rows.items()):
        rows = sorted(rows, key=lambda item: (item.get("audit_year", ""), item.get("report_id", "")))
        target = TARGETS.get(ein, {"name": rows[-1].get("auditee_name", ein)})
        report_ids = [row.get("report_id", "") for row in rows]
        all_findings = [finding for report_id in report_ids for finding in findings_by_report.get(report_id, [])]
        all_awards = [award for report_id in report_ids for award in awards_by_report.get(report_id, [])]
        audit_summary.append(
            {
                "entity": target["name"],
                "ein": ein,
                "audit_years": sorted({row.get("audit_year", "") for row in rows}),
                "report_count": len(rows),
                "latest_report_id": rows[-1].get("report_id", ""),
                "latest_audit_year": rows[-1].get("audit_year", ""),
                "latest_total_amount_expended": intish(rows[-1].get("total_amount_expended")),
                "audit_pdf_downloaded_count": sum(1 for report_id in report_ids if pdf_by_report.get(report_id, {}).get("downloaded")),
                "not_low_risk_years": sorted(
                    {row.get("audit_year", "") for row in rows if str(row.get("is_low_risk_auditee", "")).lower() in {"no", "n"}}
                ),
                "material_weakness_years": sorted(
                    {
                        row.get("audit_year", "")
                        for row in rows
                        if yes(row.get("is_internal_control_material_weakness_disclosed")) or yes(row.get("is_material_weakness"))
                    }
                ),
                "internal_control_deficiency_years": sorted(
                    {
                        row.get("audit_year", "")
                        for row in rows
                        if yes(row.get("is_internal_control_deficiency_disclosed")) or yes(row.get("is_significant_deficiency"))
                    }
                ),
                "prior_finding_agencies": sorted({row.get("agencies_with_prior_findings", "") for row in rows if row.get("agencies_with_prior_findings")}),
                "fac_findings_row_count": len(all_findings),
                "fac_award_row_count": len(all_awards),
                "fac_award_amount_total": sum(intish(row.get("amount_expended")) for row in all_awards),
            }
        )

    awards_by_entity_program: dict[tuple[str, str], int] = defaultdict(int)
    report_to_ein = {row.get("report_id", ""): (row.get("auditee_ein") or "").zfill(9) for row in general}
    for row in awards:
        ein = report_to_ein.get(row.get("report_id", ""), "")
        entity = TARGETS.get(ein, {"name": ein})["name"]
        program = row.get("federal_program_name") or row.get("cluster_name") or "unknown"
        awards_by_entity_program[(entity, program)] += intish(row.get("amount_expended"))
    award_summary = [
        {"entity": entity, "federal_program_name": program, "amount_expended_total": amount}
        for (entity, program), amount in sorted(awards_by_entity_program.items(), key=lambda item: (-item[1], item[0][0], item[0][1]))[:60]
    ]
    return {"audit_summary": audit_summary, "award_summary": award_summary, "findings": findings}


def build_dhcs_table(artifacts: Path) -> list[dict[str, Any]]:
    rows = read_json(artifacts / "dhcs_lcd_status_matches.json")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row.get("_target_name", "unknown")].append(row)
    summary = []
    for entity, items in sorted(grouped.items()):
        status_counts = Counter(str(item.get("FACILITY_STATUS", "unknown")) for item in items)
        service_counts = Counter(str(item.get("Service_Type", "unknown")) for item in items)
        counties = sorted({str(item.get("CountyName", "")) for item in items if item.get("CountyName")})
        summary.append(
            {
                "entity": entity,
                "facility_rows": len(items),
                "status_counts": dict(sorted(status_counts.items())),
                "service_type_counts": dict(sorted(service_counts.items())),
                "counties": counties,
                "closed_record_ids": sorted(str(item.get("Record_ID", "")) for item in items if str(item.get("FACILITY_STATUS", "")).lower() == "closed"),
            }
        )
    return summary


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def snippet(text: str, term: str, radius: int = 180) -> str | None:
    lowered = text.lower()
    idx = lowered.find(term.lower())
    if idx < 0:
        return None
    start = max(0, idx - radius)
    end = min(len(text), idx + len(term) + radius)
    prefix = "..." if start else ""
    suffix = "..." if end < len(text) else ""
    return prefix + text[start:end].strip() + suffix


def ocr_engine_status() -> dict[str, Any]:
    tesseract = shutil.which("tesseract")
    return {
        "engine": "tesseract",
        "available": bool(tesseract),
        "path": tesseract or "",
    }


def extract_layout_profile(path: Path, max_table_samples: int = 8) -> dict[str, Any]:
    profile: dict[str, Any] = {
        "layout_engine": "pdfplumber",
        "layout_text_char_count": 0,
        "layout_text_sha256": "",
        "pdfplumber_table_count": 0,
        "pdfplumber_table_samples": [],
        "layout_error": "",
    }
    layout_parts: list[str] = []
    table_samples: list[dict[str, Any]] = []
    table_count = 0
    try:
        with pdfplumber.open(str(path)) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                layout_parts.append(page.extract_text(layout=True) or "")
                try:
                    tables = page.extract_tables() or []
                except Exception:
                    tables = []
                table_count += len(tables)
                for table in tables:
                    if len(table_samples) >= max_table_samples:
                        break
                    rows = []
                    for row in table[:8]:
                        cleaned = [normalize_text(str(cell or "")) for cell in row]
                        if any(cleaned):
                            rows.append(cleaned[:8])
                    if rows:
                        table_samples.append({"page": page_number, "rows": rows})
    except Exception as exc:
        profile["layout_error"] = repr(exc)
        return profile

    layout_text = normalize_text("\n".join(layout_parts))
    profile.update(
        {
            "layout_text_char_count": len(layout_text),
            "layout_text_sha256": sha256_text(layout_text),
            "pdfplumber_table_count": table_count,
            "pdfplumber_table_samples": table_samples,
        }
    )
    return profile


def extract_pdf_index(manifest_items: list[dict[str, Any]], document_kind: str) -> list[dict[str, Any]]:
    index: list[dict[str, Any]] = []
    for item in manifest_items:
        local_path = item.get("local_pdf_path")
        if not local_path or not Path(local_path).exists():
            index.append({"document_kind": document_kind, "source_id": item.get("report_id") or item.get("record_id"), "extracted": False})
            continue
        path = Path(local_path)
        try:
            reader = PdfReader(str(path))
            page_texts = []
            for page in reader.pages:
                try:
                    page_texts.append(page.extract_text() or "")
                except Exception:
                    page_texts.append("")
            text = normalize_text("\n".join(page_texts))
            snippets = {term: found for term in KEY_TERMS if (found := snippet(text, term))}
            layout_profile = extract_layout_profile(path)
            ocr_status = ocr_engine_status()
            index.append(
                {
                    "document_kind": document_kind,
                    "source_id": item.get("report_id") or item.get("record_id"),
                    "local_pdf_path": str(path),
                    "page_count": len(reader.pages),
                    "text_sha256": sha256_text(text),
                    "extracted_char_count": len(text),
                    "keyword_snippets": snippets,
                    "extracted": True,
                    "layout_extracted": not bool(layout_profile.get("layout_error")),
                    "ocr_status": "not_run_text_layer_present" if text else ("available_not_run" if ocr_status["available"] else "not_run_no_ocr_engine"),
                    "ocr_engine": ocr_status,
                    **layout_profile,
                }
            )
        except Exception as exc:
            index.append(
                {
                    "document_kind": document_kind,
                    "source_id": item.get("report_id") or item.get("record_id"),
                    "local_pdf_path": str(path),
                    "extracted": False,
                    "error": repr(exc),
                }
            )
    return index


def markdown_table(rows: list[dict[str, Any]], columns: list[str], limit: int = 50) -> str:
    clipped = rows[:limit]
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    body = []
    for row in clipped:
        cells = []
        for column in columns:
            value = row.get(column, "")
            if isinstance(value, list):
                value = ", ".join(str(item) for item in value)
            elif isinstance(value, dict):
                value = ", ".join(f"{key}:{val}" for key, val in value.items())
            cells.append(str(value).replace("|", "/")[:180])
        body.append("| " + " | ".join(cells) + " |")
    if len(rows) > limit:
        body.append(f"| ... | {len(rows) - limit} additional rows omitted from packet view |" + " |" * max(0, len(columns) - 2))
    return "\n".join([header, separator, *body])


def corpus_record(
    record_id: str,
    title: str,
    source_uri: str,
    source_type: str,
    body: str,
    entities: list[str],
    signals: dict[str, Any],
    attributes: dict[str, Any],
) -> dict[str, Any]:
    return {
        "record_id": record_id,
        "title": title,
        "source_uri": source_uri,
        "source_type": source_type,
        "published_at": "2026-04-24",
        "collected_at": utc_now(),
        "entities": entities,
        "attributes": {"signals": signals, **attributes},
        "body": body,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract deterministic reviewer tables from live source artifacts.")
    parser.add_argument("--stage2-corpus", type=Path, default=DEFAULT_STAGE2_CORPUS)
    parser.add_argument("--stage3-corpus", type=Path, default=DEFAULT_STAGE3_CORPUS)
    parser.add_argument("--artifacts-dir", type=Path, default=DEFAULT_ARTIFACTS)
    parser.add_argument("--parsed-dir", type=Path, default=DEFAULT_PARSED)
    args = parser.parse_args()

    args.parsed_dir.mkdir(parents=True, exist_ok=True)
    copy_corpus(args.stage2_corpus, args.stage3_corpus)

    irs_rows, irs_notes = build_irs_table(args.artifacts_dir)
    fac_tables = build_fac_tables(args.artifacts_dir)
    dhcs_rows = build_dhcs_table(args.artifacts_dir)
    fac_pdf_index = extract_pdf_index(read_json(args.artifacts_dir / "fac_audit_pdf_manifest.json"), "fac_audit_pdf")
    county_pdf_index = extract_pdf_index(read_json(args.artifacts_dir / "county_contract_monitoring_manifest.json"), "county_contract_or_monitoring_pdf")

    write_json(args.parsed_dir / "irs_990_financials.json", {"rows": irs_rows, "notes": irs_notes})
    write_json(args.parsed_dir / "fac_audit_summary.json", fac_tables)
    write_json(args.parsed_dir / "dhcs_facility_status_summary.json", {"rows": dhcs_rows})
    write_json(args.parsed_dir / "pdf_text_index.json", {"fac_audit_pdfs": fac_pdf_index, "county_contract_pdfs": county_pdf_index})

    entities = [target["name"] for target in TARGETS.values()]
    records = [
        corpus_record(
            "source_table_irs_990_financials",
            "Parsed IRS Form 990 XML financial fields for target entities",
            str(args.parsed_dir / "irs_990_financials.json"),
            "source_extraction_irs_990_table",
            "\n".join(
                [
                    "Deterministic parser output from downloaded IRS Form 990 XML files. Raw XML remains the controlling source.",
                    markdown_table(
                        irs_rows,
                        [
                            "entity",
                            "ein",
                            "tax_period",
                            "tax_period_year",
                            "total_revenue",
                            "total_expenses",
                            "total_assets_eoy",
                            "net_assets_eoy",
                            "government_grants",
                            "top_compensation_person",
                            "top_compensation_title",
                            "top_compensation_total",
                            "salaries_comp_benefits_current_year",
                            "total_employee_count",
                            "political_campaign_activity",
                            "lobbying_activities",
                            "schedule_l_present",
                            "downloaded",
                        ],
                    ),
                    "Notes: " + ("; ".join(irs_notes) if irs_notes else "none"),
                ]
            ),
            entities,
            {"source_extraction_table": True, "full_990_xml_parsed": True, "missing_data": bool(irs_notes)},
            {"table_path": str(args.parsed_dir / "irs_990_financials.json"), "row_count": len(irs_rows)},
        ),
        corpus_record(
            "source_table_fac_audit_controls",
            "Parsed FAC audit-control and findings table for target entities",
            str(args.parsed_dir / "fac_audit_summary.json"),
            "source_extraction_fac_audit_table",
            "\n".join(
                [
                    "Deterministic parser output from FAC general, findings, federal_awards CSVs, with downloaded audit PDF presence. Audit PDFs and FAC CSV rows remain the controlling sources.",
                    markdown_table(
                        fac_tables["audit_summary"],
                        [
                            "entity",
                            "ein",
                            "audit_years",
                            "report_count",
                            "latest_report_id",
                            "audit_pdf_downloaded_count",
                            "not_low_risk_years",
                            "material_weakness_years",
                            "internal_control_deficiency_years",
                            "fac_findings_row_count",
                            "fac_award_amount_total",
                        ],
                    ),
                ]
            ),
            entities,
            {"source_extraction_table": True, "fac_table_parsed": True, "fac_audit_pdf_indexed": True},
            {"table_path": str(args.parsed_dir / "fac_audit_summary.json"), "row_count": len(fac_tables["audit_summary"])},
        ),
        corpus_record(
            "source_table_fac_award_programs",
            "Parsed FAC federal award program totals for target entities",
            str(args.parsed_dir / "fac_audit_summary.json"),
            "source_extraction_fac_award_table",
            "\n".join(
                [
                    "Deterministic parser output from FAC federal_awards rows filtered to matched reports. Amount totals support funding-trace review only.",
                    markdown_table(fac_tables["award_summary"], ["entity", "federal_program_name", "amount_expended_total"], limit=40),
                ]
            ),
            entities,
            {"source_extraction_table": True, "fac_award_table_parsed": True},
            {"table_path": str(args.parsed_dir / "fac_audit_summary.json"), "row_count": len(fac_tables["award_summary"])},
        ),
        corpus_record(
            "source_table_dhcs_facility_status",
            "Parsed DHCS facility-status summary for target entities",
            str(args.parsed_dir / "dhcs_facility_status_summary.json"),
            "source_extraction_dhcs_status_table",
            "\n".join(
                [
                    "Deterministic parser output from DHCS SUD Facilities LCD status rows. Facility rows are facility-level context, not entity-level findings.",
                    markdown_table(dhcs_rows, ["entity", "facility_rows", "status_counts", "service_type_counts", "counties", "closed_record_ids"]),
                ]
            ),
            entities,
            {"source_extraction_table": True, "dhcs_facility_table_parsed": True, "dhcs_facility_closed_status": any(row.get("closed_record_ids") for row in dhcs_rows)},
            {"table_path": str(args.parsed_dir / "dhcs_facility_status_summary.json"), "row_count": len(dhcs_rows)},
        ),
        corpus_record(
            "source_table_pdf_text_index",
            "Parsed PDF text index for FAC audits and county monitoring records",
            str(args.parsed_dir / "pdf_text_index.json"),
            "source_extraction_pdf_text_index",
            "\n".join(
                [
                    "Deterministic text extraction index from downloaded FAC audit PDFs and county monitoring or contract PDFs. Snippets are navigation aids; raw PDFs remain controlling sources.",
                    f"FAC audit PDFs indexed: {sum(1 for row in fac_pdf_index if row.get('extracted'))} of {len(fac_pdf_index)}.",
                    f"County PDFs indexed: {sum(1 for row in county_pdf_index if row.get('extracted'))} of {len(county_pdf_index)}.",
                    f"FAC audit PDFs with layout extraction: {sum(1 for row in fac_pdf_index if row.get('layout_extracted'))} of {len(fac_pdf_index)}.",
                    f"County PDFs with layout extraction: {sum(1 for row in county_pdf_index if row.get('layout_extracted'))} of {len(county_pdf_index)}.",
                    f"OCR engine available: {ocr_engine_status()['available']}.",
                    markdown_table(
                        [
                            {
                                "document_kind": row.get("document_kind"),
                                "source_id": row.get("source_id"),
                                "page_count": row.get("page_count"),
                                "extracted_char_count": row.get("extracted_char_count"),
                                "keyword_count": len(row.get("keyword_snippets", {})),
                                "layout_tables": row.get("pdfplumber_table_count", 0),
                            }
                            for row in [*fac_pdf_index[:12], *county_pdf_index]
                        ],
                        ["document_kind", "source_id", "page_count", "extracted_char_count", "keyword_count", "layout_tables"],
                        limit=25,
                    ),
                ]
            ),
            entities,
            {
                "source_extraction_table": True,
                "pdf_text_extracted": True,
                "pdf_layout_extracted": True,
                "ocr_engine_available": ocr_engine_status()["available"],
            },
            {"table_path": str(args.parsed_dir / "pdf_text_index.json"), "fac_pdf_count": len(fac_pdf_index), "county_pdf_count": len(county_pdf_index)},
        ),
    ]

    for record in records:
        write_json(args.stage3_corpus / f"{record['record_id']}.json", record)

    summary = {
        "completed_at": utc_now(),
        "stage3_corpus": str(args.stage3_corpus),
        "stage3_record_count": len(list(args.stage3_corpus.glob("*.json"))),
        "parsed_dir": str(args.parsed_dir),
        "source_table_records": [record["record_id"] for record in records],
        "irs_rows": len(irs_rows),
        "fac_audit_summary_rows": len(fac_tables["audit_summary"]),
        "fac_award_summary_rows": len(fac_tables["award_summary"]),
        "dhcs_summary_rows": len(dhcs_rows),
        "fac_pdfs_indexed": sum(1 for row in fac_pdf_index if row.get("extracted")),
        "county_pdfs_indexed": sum(1 for row in county_pdf_index if row.get("extracted")),
        "fac_pdfs_layout_indexed": sum(1 for row in fac_pdf_index if row.get("layout_extracted")),
        "county_pdfs_layout_indexed": sum(1 for row in county_pdf_index if row.get("layout_extracted")),
        "ocr_engine": ocr_engine_status(),
    }
    write_json(args.parsed_dir / "extract_summary.json", summary)
    print(f"stage3_corpus={args.stage3_corpus}")
    print(f"records={summary['stage3_record_count']}")
    print(f"source_table_records={len(records)}")
    print(f"fac_pdfs_indexed={summary['fac_pdfs_indexed']}/{len(fac_pdf_index)}")
    print(f"county_pdfs_indexed={summary['county_pdfs_indexed']}/{len(county_pdf_index)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


