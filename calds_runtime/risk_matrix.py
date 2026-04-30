from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Iterable

from .contracts import (
    CanonicalRecord,
    CaseRequest,
    EvidenceBundle,
    OversightRiskIndicator,
    OversightRiskMatrix,
    stable_id,
)


class OversightRiskMatrixService:
    """Deterministic waste, fraud, abuse, and mismanagement screening matrix built from source records."""

    SCORE_SCALE = (
        "Indicator levels: High=immediate reviewer follow-up, Medium=review queue, "
        "Low=context only, Data gap=required source missing or not parsed. Levels are "
        "screening priorities, not findings or allegations."
    )

    METHODOLOGY = (
        "Waste, fraud, abuse, and mismanagement risk-screening matrix generated from parsed IRS Form 990 and ProPublica Nonprofit Explorer API summaries, "
        "Federal Audit Clearinghouse, DHCS facility-status, HCD Homekey/Homekey+ state-award, official enforcement/docket records, county/document index, and retrieved "
        "service-page records. The matrix tests observable risk proxies: year-over-year financial "
        "growth, spending growth, public-funds concentration, executive compensation, payroll scale, "
        "political/lobbying indicators, audit-control flags, enforcement/docket source flags including connected-party official charges, award concentration, facility closure "
        "patterns, homelessness-scope web-language checks, official county/CoC outcome context, "
        "and remaining provider-attributable outcome gaps."
    )

    HOMELESSNESS_SCOPE_HIGH_TERMS = [
        "voter registration",
        "get out the vote",
        "voter engagement",
        "citizenship",
        "naturalization",
        "immigration legal services",
        "ice enforcement",
        "block ice",
        "deportation defense",
        "immigration enforcement",
        "power building",
        "political action",
        "campaign contribution",
        "ballot measure",
        "electioneering",
        "campaign activity",
    ]

    HOMELESSNESS_SCOPE_MEDIUM_TERMS = [
        "policy advocacy",
        "community organizing",
        "lobbying",
        "lobbyist",
        "public affairs",
        "know your rights",
        "asylum",
        "refugee resettlement",
    ]

    def build(
        self,
        request: CaseRequest,
        records: Iterable[CanonicalRecord],
        bundle: EvidenceBundle,
    ) -> OversightRiskMatrix:
        self.records = list(records)
        self.records_by_id = {record.record_id: record for record in self.records}
        self.items_by_record = {item.record_id: item for item in bundle.items}
        irs = self._load_json_for_type("source_extraction_irs_990_table") or {}
        irs_raw = self._load_json_for_type("source_extraction_irs_990_raw_artifact_table") or {}
        fac = self._load_json_for_type("source_extraction_fac_audit_table") or {}
        dhcs = self._load_json_for_type("source_extraction_dhcs_status_table") or {}
        spend_join = self._load_json_for_type("source_extraction_spend_vs_results_table") or {}
        outcome_manifest = self._load_json_for_type("source_extraction_official_outcome_table") or {}
        state_awards = self._load_json_for_type("source_extraction_state_homeless_award_table") or {}
        enforcement = self._load_json_for_type("source_extraction_enforcement_docket_table") or {}

        irs_rows = list(irs.get("rows", [])) if isinstance(irs, dict) else []
        raw_irs_rows = list(irs_raw.get("rows", [])) if isinstance(irs_raw, dict) else []
        irs_rows = self._merge_irs_raw_rows(irs_rows, raw_irs_rows)
        fac_rows = list(fac.get("audit_summary", [])) if isinstance(fac, dict) else []
        award_rows = list(fac.get("award_summary", [])) if isinstance(fac, dict) else []
        dhcs_rows = list(dhcs.get("rows", [])) if isinstance(dhcs, dict) else []
        state_award_rows = list(state_awards.get("entity_award_summary", [])) if isinstance(state_awards, dict) else []
        enforcement_rows = list(enforcement.get("rows", [])) if isinstance(enforcement, dict) else []

        entities = self._entities(request, irs_rows, fac_rows, dhcs_rows)
        indicators: list[OversightRiskIndicator] = []
        for entity in entities:
            indicators.extend(self._enforcement_docket_indicators(request, entity, enforcement_rows))
            indicators.extend(self._state_homeless_award_indicators(request, entity, state_award_rows))
            indicators.extend(self._irs_indicators(request, entity, irs_rows))
            indicators.extend(self._fac_indicators(request, entity, fac_rows, award_rows))
            indicators.extend(self._dhcs_indicators(request, entity, dhcs_rows))
            indicators.extend(self._service_page_indicators(request, entity))
            indicators.extend(self._public_statement_indicators(request, entity))

        indicators.extend(self._spend_vs_results_indicators(request, spend_join))
        indicators.extend(self._outcome_source_gap_indicators(request, outcome_manifest))
        indicators.extend(self._case_wide_gap_indicators(request, spend_join))
        indicators = sorted(
            indicators,
            key=lambda item: (
                {"High": 0, "Medium": 1, "Data gap": 2, "Low": 3}.get(item.risk_level, 4),
                item.risk_area,
                item.entity,
                item.test_name,
            ),
        )
        return OversightRiskMatrix(
            matrix_id=stable_id("risk_matrix", request.case_id, str(len(indicators))),
            case_id=request.case_id,
            methodology=self.METHODOLOGY,
            score_scale=self.SCORE_SCALE,
            indicators=indicators,
        )

    def _load_json_for_type(self, source_type: str) -> dict[str, Any] | None:
        for record in self.records:
            if record.source_type != source_type:
                continue
            candidates = [record.attributes.get("table_path"), record.source_uri]
            for candidate in candidates:
                if not candidate:
                    continue
                path = Path(str(candidate))
                if path.exists():
                    return json.loads(path.read_text(encoding="utf-8"))
        return None

    def _merge_irs_raw_rows(self, irs_rows: list[dict[str, Any]], raw_irs_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged = [dict(row) for row in irs_rows]
        by_key = {(str(row.get("entity") or ""), str(row.get("tax_period_year") or "")): row for row in merged}
        for raw_row in raw_irs_rows:
            entity = str(raw_row.get("entity") or "")
            year = str(raw_row.get("tax_period_year") or "")
            if not entity or not year:
                continue
            row = by_key.get((entity, year))
            if row is None:
                row = {
                    "entity": entity,
                    "ein": raw_row.get("ein"),
                    "tax_period": raw_row.get("tax_period"),
                    "tax_period_year": raw_row.get("tax_period_year"),
                    "downloaded": bool(raw_row.get("xml_downloaded") or raw_row.get("pdf_downloaded")),
                    "source": "Official IRS raw Form 990 artifact extraction",
                }
                merged.append(row)
                by_key[(entity, year)] = row
            parsed = dict(raw_row.get("parsed_detail_fields") or {})
            for key, value in parsed.items():
                if value is not None and value != "":
                    row[key] = value
            row["raw_irs_xml_downloaded"] = bool(raw_row.get("xml_downloaded"))
            row["raw_irs_xml_local_path"] = raw_row.get("xml_local_path") or ""
            row["raw_irs_xml_sha256"] = raw_row.get("xml_sha256") or ""
        return merged

    def _entities(
        self,
        request: CaseRequest,
        irs_rows: list[dict[str, Any]],
        fac_rows: list[dict[str, Any]],
        dhcs_rows: list[dict[str, Any]],
    ) -> list[str]:
        seen: list[str] = []
        for entity in [*request.entities, *[str(row.get("entity", "")) for row in irs_rows], *[str(row.get("entity", "")) for row in fac_rows], *[str(row.get("entity", "")) for row in dhcs_rows]]:
            entity = entity.strip()
            if entity and entity not in seen:
                seen.append(entity)
        return seen

    def _irs_indicators(self, request: CaseRequest, entity: str, rows: list[dict[str, Any]]) -> list[OversightRiskIndicator]:
        entity_rows = sorted(
            [row for row in rows if row.get("entity") == entity],
            key=lambda row: int(row.get("tax_period_year") or 0),
        )
        record_ids = self._record_ids_for_source_types("source_extraction_irs_990_table", "source_extraction_irs_990_raw_artifact_table")
        indicators: list[OversightRiskIndicator] = []

        indicators.append(
            self._growth_indicator(
                request,
                entity,
                entity_rows,
                "Financial growth",
                "Year-over-year total revenue growth",
                "total_revenue",
                "revenue",
                [(50.0, "High"), (25.0, "Medium")],
                record_ids,
                "Compare the growth to contract amendments, new grants, acquisitions, service volume, and program outcomes before escalation.",
            )
        )
        indicators.append(
            self._growth_indicator(
                request,
                entity,
                entity_rows,
                "Spending growth",
                "Year-over-year total expense growth",
                "total_expenses",
                "expenses",
                [(50.0, "High"), (20.0, "Medium")],
                record_ids,
                "Check whether expense growth maps to funded scope, staffing, facilities, and documented service results.",
            )
        )
        indicators.append(self._grant_concentration_indicator(request, entity, entity_rows, record_ids))
        indicators.append(self._compensation_indicator(request, entity, entity_rows, record_ids))
        indicators.append(self._payroll_growth_indicator(request, entity, entity_rows, record_ids))
        indicators.append(self._political_lobbying_indicator(request, entity, entity_rows, record_ids))
        return indicators

    def _enforcement_docket_indicators(
        self,
        request: CaseRequest,
        entity: str,
        rows: list[dict[str, Any]],
    ) -> list[OversightRiskIndicator]:
        entity_rows = [row for row in rows if row.get("entity") == entity]
        record_ids = self._record_ids_for_entity_and_source_types(
            entity,
            "source_extraction_enforcement_docket_table",
            "enforcement_or_docket_source",
            "court_docket_manifest",
        )
        if not entity_rows:
            return [
                self._indicator(
                    request,
                    "Enforcement and docket history",
                    entity,
                    "Official enforcement, prosecution, violation, and docket source coverage",
                    "No official enforcement, prosecution, violation, or docket row is present for this entity in the current corpus.",
                    "Data gap",
                    "missing_source",
                    "Run official enforcement and docket source acquisition before clearing or downgrading this source family.",
                    record_ids,
                    ["No recovered row is not a clearance; it only states current corpus coverage."],
                )
            ]
        indicators: list[OversightRiskIndicator] = []
        for row in entity_rows:
            level = str(row.get("risk_level") or "Medium")
            if level not in {"High", "Medium", "Low", "Data gap"}:
                level = "Medium"
            source_status = str(row.get("legal_status") or row.get("data_status") or "observed")
            official = bool(row.get("official_source"))
            connected_party = bool(row.get("connected_party_entity_trigger"))
            observed = str(row.get("observed_fact") or "")
            caveats = list(row.get("caveats") or [])
            if official:
                caveats.append("Use exact legal status from the official source; do not convert third-party charges into entity-level findings.")
            if connected_party:
                caveats.append("A connected-party charge is a mandatory deep-review trigger, not a finding that the nonprofit was charged or liable.")
            indicators.append(
                self._indicator(
                    request,
                    "Connected-party enforcement exposure" if connected_party else "Enforcement and docket history",
                    entity,
                    str(row.get("test_name") or "Official enforcement or docket source screen"),
                    observed,
                    level,
                    source_status,
                    str(
                        row.get("reviewer_action")
                        or "Open the official source and verify legal status, case posture, named parties, dates, project relationship, payment flow, and nonprofit connection before escalation."
                    ),
                    record_ids,
                    caveats,
                )
            )
        return indicators

    def _growth_indicator(
        self,
        request: CaseRequest,
        entity: str,
        rows: list[dict[str, Any]],
        risk_area: str,
        test_name: str,
        field: str,
        label: str,
        thresholds: list[tuple[float, str]],
        record_ids: list[str],
        reviewer_action: str,
    ) -> OversightRiskIndicator:
        pair = self._latest_numeric_pair(rows, field)
        if not pair:
            years = self._available_years(rows, field)
            return self._indicator(
                request,
                risk_area,
                entity,
                test_name,
                f"No two downloaded IRS returns with numeric {label} are available for this entity. Available parsed years: {years or 'none'}.",
                "Data gap",
                "missing_source_or_field",
                reviewer_action,
                record_ids,
                ["A missing year is not an adverse signal by itself, but it prevents the growth test."],
            )
        previous, current = pair
        previous_value = self._number(previous.get(field)) or 0.0
        current_value = self._number(current.get(field)) or 0.0
        pct = self._pct_change(previous_value, current_value)
        level = "Low"
        for threshold, candidate in thresholds:
            if pct >= threshold:
                level = candidate
                break
        return self._indicator(
            request,
            risk_area,
            entity,
            test_name,
            (
                f"IRS parsed {label} moved from {self._money(previous_value)} in {previous.get('tax_period_year')} "
                f"to {self._money(current_value)} in {current.get('tax_period_year')} ({pct:+.1f}%)."
            ),
            level,
            "observed",
            reviewer_action,
            record_ids,
            ["Growth can be legitimate; it becomes useful only when compared with scope, staffing, service volume, and outcome data."],
        )

    def _grant_concentration_indicator(
        self,
        request: CaseRequest,
        entity: str,
        rows: list[dict[str, Any]],
        record_ids: list[str],
    ) -> OversightRiskIndicator:
        row = self._latest_row_with(rows, "government_grants", "total_revenue")
        if not row:
            return self._indicator(
                request,
                "Public-funds concentration",
                entity,
                "Government grants as share of Form 990 revenue",
                "No downloaded IRS row in the current corpus contains both government grants and total revenue for this entity.",
                "Data gap",
                "missing_source_or_field",
                "Recover the full return or schedule detail before ranking public-funds concentration.",
                record_ids,
                ["Blank government-grant fields may reflect parser coverage or return presentation; verify against raw XML/PDF."],
            )
        grants = self._number(row.get("government_grants")) or 0.0
        revenue = self._number(row.get("total_revenue")) or 0.0
        ratio = grants / revenue if revenue else 0.0
        level = "High" if ratio >= 0.80 else "Medium" if ratio >= 0.50 else "Low"
        return self._indicator(
            request,
            "Public-funds concentration",
            entity,
            "Government grants as share of Form 990 revenue",
            f"Latest parsed IRS row with both fields is {row.get('tax_period_year')}: government grants {self._money(grants)} / total revenue {self._money(revenue)} = {ratio:.1%}.",
            level,
            "observed",
            "Prioritize tracing grant terms, allowable costs, subawards, and reported service outputs for high public-funds exposure.",
            record_ids,
            ["Public-funds concentration is an oversight-priority signal, not an allegation."],
        )

    def _compensation_indicator(
        self,
        request: CaseRequest,
        entity: str,
        rows: list[dict[str, Any]],
        record_ids: list[str],
    ) -> OversightRiskIndicator:
        row = self._latest_row_with(rows, "top_compensation_total") or self._latest_row_with(rows, "officer_compensation_total")
        if not row:
            return self._indicator(
                request,
                "Executive compensation",
                entity,
                "Highest officer/key employee compensation from Form 990 Part VII",
                "No parsed Part VII compensation total is available in the current IRS table for this entity.",
                "Data gap",
                "missing_parser_or_source_field",
                "Parse Part VII from the raw return and compare officer/key-employee pay against peers, program scale, and compensation-policy disclosures.",
                record_ids,
                ["The current test does not infer reasonableness; it only flags pay levels for reviewer comparison."],
            )
        top_total = self._number(row.get("top_compensation_total")) or self._number(row.get("officer_compensation_total")) or 0.0
        expenses = self._number(row.get("total_expenses")) or 0.0
        expense_ratio = top_total / expenses if expenses else 0.0
        level = "High" if top_total >= 1_000_000 or expense_ratio >= 0.02 else "Medium" if top_total >= 500_000 or expense_ratio >= 0.01 else "Low"
        aggregate = bool(row.get("compensation_is_aggregate"))
        if aggregate:
            test_name = "Aggregate officer/director compensation from Form 990 extract"
            subject = "aggregate current officer/director/trustee compensation"
            caveat = "The current row is aggregate compensation from the API/extract; raw Part VII parsing is required before naming individual pay."
        else:
            test_name = "Highest officer/key employee compensation from Form 990 Part VII"
            person = row.get("top_compensation_person") or "top compensated person"
            title = row.get("top_compensation_title") or "title not parsed"
            subject = f"{person} ({title})"
            caveat = "High compensation can be explainable by size, clinical complexity, related-organization structures, or one-time items."
        return self._indicator(
            request,
            "Executive compensation",
            entity,
            test_name,
            f"Latest parsed return {row.get('tax_period_year')} reports {subject} of {self._money(top_total)}, equal to {expense_ratio:.2%} of parsed expenses.",
            level,
            "observed",
            "Compare compensation to board approval process, market survey disclosure, related-organization pay, and peer organizations before any conclusion.",
            record_ids,
            [caveat],
        )

    def _payroll_growth_indicator(
        self,
        request: CaseRequest,
        entity: str,
        rows: list[dict[str, Any]],
        record_ids: list[str],
    ) -> OversightRiskIndicator:
        pair = self._latest_numeric_pair(rows, "salaries_comp_benefits_current_year")
        if not pair:
            return self._indicator(
                request,
                "Payroll and wages",
                entity,
                "Year-over-year salaries, compensation, and benefits growth",
                "No two downloaded IRS returns with parsed salaries/compensation/benefits totals are available for this entity.",
                "Data gap",
                "missing_source_or_field",
                "Parse the salaries/compensation/benefits line and compare payroll growth to headcount, contract scope, and service volume.",
                record_ids,
                ["Payroll growth alone does not show misuse; it is a spend-versus-output review trigger."],
            )
        previous, current = pair
        previous_value = self._number(previous.get("salaries_comp_benefits_current_year")) or 0.0
        current_value = self._number(current.get("salaries_comp_benefits_current_year")) or 0.0
        pct = self._pct_change(previous_value, current_value)
        employees = self._number(current.get("total_employee_count"))
        per_employee = current_value / employees if employees else None
        level = "High" if pct >= 35.0 else "Medium" if pct >= 20.0 else "Low"
        tail = f"; {self._money(per_employee)} per employee using {int(employees)} employees" if per_employee is not None else ""
        return self._indicator(
            request,
            "Payroll and wages",
            entity,
            "Year-over-year salaries, compensation, and benefits growth",
            f"Parsed salaries/compensation/benefits moved from {self._money(previous_value)} in {previous.get('tax_period_year')} to {self._money(current_value)} in {current.get('tax_period_year')} ({pct:+.1f}%{tail}).",
            level,
            "observed",
            "Compare payroll growth with staffing changes, wage requirements, vacancy rates, service units, and contract deliverables.",
            record_ids,
            ["This is a spending efficiency trigger, not a compensation reasonableness finding."],
        )

    def _political_lobbying_indicator(
        self,
        request: CaseRequest,
        entity: str,
        rows: list[dict[str, Any]],
        record_ids: list[str],
    ) -> OversightRiskIndicator:
        row = self._latest_row_with_any(rows, "political_campaign_activity", "lobbying_activities")
        if not row:
            return self._indicator(
                request,
                "Off-scope activity",
                entity,
                "Form 990 political campaign and lobbying indicators",
                "No parsed PoliticalCampaignActyInd or LobbyingActivitiesInd field is available in the current IRS table for this entity.",
                "Data gap",
                "missing_source_or_field",
                "Parse the latest full return and review related schedules before judging whether dollars were used outside funded scope.",
                record_ids,
                ["This check only covers return-level indicators; it does not inspect every program expenditure."],
            )
        political = self._boolish(row.get("political_campaign_activity"))
        lobbying = self._boolish(row.get("lobbying_activities"))
        level = "High" if political else "Medium" if lobbying else "Low"
        return self._indicator(
            request,
            "Off-scope activity",
            entity,
            "Form 990 political campaign and lobbying indicators",
            f"Latest parsed return {row.get('tax_period_year')} reports PoliticalCampaignActyInd={self._yn(political)} and LobbyingActivitiesInd={self._yn(lobbying)}.",
            level,
            "observed",
            "If either indicator is yes, inspect the full return, schedules, funding restrictions, and cost allocation before escalation.",
            record_ids,
            ["A yes indicator can reflect disclosed permissible activity; the reviewer must test allowability and funding source."],
        )

    def _fac_indicators(
        self,
        request: CaseRequest,
        entity: str,
        rows: list[dict[str, Any]],
        award_rows: list[dict[str, Any]],
    ) -> list[OversightRiskIndicator]:
        record_ids = self._record_ids_for_source_types("source_extraction_fac_audit_table", "source_extraction_fac_award_table")
        row = next((item for item in rows if item.get("entity") == entity), None)
        if not row:
            return [
                self._indicator(
                    request,
                    "Audit controls",
                    entity,
                    "FAC control flags and findings",
                    "No FAC audit-control summary row is present for this entity in the current corpus.",
                    "Data gap",
                    "missing_source",
                    "Recover FAC general, findings, awards, and audit PDF records before audit-control ranking.",
                    record_ids,
                    [],
                )
            ]

        material = list(row.get("material_weakness_years") or [])
        deficiencies = list(row.get("internal_control_deficiency_years") or [])
        not_low = list(row.get("not_low_risk_years") or [])
        findings = int(self._number(row.get("fac_findings_row_count")) or 0)
        if material:
            level = "High"
        elif deficiencies or findings or len(not_low) >= 3:
            level = "Medium"
        else:
            level = "Low"
        indicators = [
            self._indicator(
                request,
                "Audit controls",
                entity,
                "FAC control flags and findings",
                f"FAC summary reports material weakness years={self._list_text(material)}, internal-control deficiency years={self._list_text(deficiencies)}, not-low-risk years={self._list_text(not_low)}, findings rows={findings}.",
                level,
                "observed",
                "Open the audit PDFs and row-level FAC findings to verify finding status, program, agency, questioned costs, repeat status, and corrective-action response.",
                record_ids,
                ["FAC flags are audit-context signals; they must be interpreted at report year and program level."],
            )
        ]

        total = self._number(row.get("fac_award_amount_total")) or 0.0
        top_award = next((item for item in award_rows if item.get("entity") == entity), None)
        level = "High" if total >= 150_000_000 else "Medium" if total >= 50_000_000 else "Low"
        program_text = ""
        if top_award:
            program_text = f" Top parsed program: {top_award.get('federal_program_name')} at {self._money(self._number(top_award.get('amount_expended_total')) or 0)}."
        indicators.append(
            self._indicator(
                request,
                "Federal award exposure",
                entity,
                "FAC cumulative award amount in retrieved reports",
                f"Parsed FAC award amount total across retrieved reports is {self._money(total)}.{program_text}",
                level,
                "observed",
                "Use large award totals to prioritize allowable-cost, subrecipient, and deliverable testing; do not infer performance from amount alone.",
                record_ids,
                ["Award exposure is a materiality signal, not an adverse finding."],
            )
        )
        return indicators

    def _dhcs_indicators(self, request: CaseRequest, entity: str, rows: list[dict[str, Any]]) -> list[OversightRiskIndicator]:
        record_ids = self._record_ids_for_source_types("source_extraction_dhcs_status_table")
        row = next((item for item in rows if item.get("entity") == entity), None)
        if not row:
            return [
                self._indicator(
                    request,
                    "Facility status",
                    entity,
                    "DHCS active/closed facility-status ratio",
                    "No parsed DHCS facility-status summary row is present for this entity.",
                    "Data gap",
                    "missing_source",
                    "Recover DHCS facility rows and adverse-status/licensing history before facility-level ranking.",
                    record_ids,
                    [],
                )
            ]
        status_counts = dict(row.get("status_counts") or {})
        total = int(self._number(row.get("facility_rows")) or 0)
        closed = int(self._number(status_counts.get("Closed")) or 0)
        active = int(self._number(status_counts.get("Active")) or 0)
        ratio = closed / total if total else 0.0
        level = "High" if total and ratio >= 0.50 else "Medium" if total and ratio >= 0.30 else "Low"
        return [
            self._indicator(
                request,
                "Facility status",
                entity,
                "DHCS active/closed facility-status ratio",
                f"Parsed DHCS status rows show {active} active and {closed} closed facilities out of {total} matched rows ({ratio:.1%} closed).",
                level,
                "observed",
                "Review closed facility IDs, dates, license histories, probation/suspension/revocation records, and contract coverage before entity-level use.",
                record_ids,
                ["Closed status can be routine, historical, or administrative; facility-level records control."],
            )
        ]

    def _state_homeless_award_indicators(
        self,
        request: CaseRequest,
        entity: str,
        rows: list[dict[str, Any]],
    ) -> list[OversightRiskIndicator]:
        record_ids = self._record_ids_for_entity_and_source_types(
            entity,
            "source_extraction_state_homeless_award_table",
            "state_homelessness_award",
        )
        row = next((item for item in rows if item.get("entity") == entity), None)
        if not row:
            return [
                self._indicator(
                    request,
                    "State homelessness award exposure",
                    entity,
                    "Homekey/Homekey+ co-applicant project-award exposure",
                    "No parsed HCD Homekey or Homekey+ state award row is present for this entity in the current corpus.",
                    "Data gap",
                    "missing_source",
                    "Recover official HCD award rows before ranking state homelessness award exposure.",
                    record_ids,
                    ["Absence of a parsed row is not evidence that the entity lacked state funding exposure."],
                )
            ]

        total = self._number(row.get("total_award_exposure")) or 0.0
        project_count = int(self._number(row.get("project_count")) or 0)
        programs = self._list_text(list(row.get("programs") or []))
        projects = self._list_text(list(row.get("projects") or []))
        counties = self._list_text(list(row.get("counties") or []))
        years = self._list_text(list(row.get("award_years") or []))
        level = "High" if total >= 50_000_000 else "Medium" if total >= 25_000_000 else "Low"
        return [
            self._indicator(
                request,
                "State homelessness award exposure",
                entity,
                "Homekey/Homekey+ co-applicant project-award exposure",
                (
                    f"HCD award lists name {entity} as a co-applicant or project partner on {project_count} "
                    f"Homekey/Homekey+ project row(s), with total project-award exposure of {self._money(total)}. "
                    f"Programs: {programs}. Award year(s): {years}. Counties: {counties}. Projects: {projects}."
                ),
                level,
                "observed",
                "Verify HCD source rows, standard agreements, eligible applicant, co-applicant role, draw records, and any subrecipient allocation before treating project-award exposure as direct receipt.",
                record_ids,
                [
                    "This is project-award exposure assigned to source-listed co-applicants; allocation among co-applicants is not stated in the award lists.",
                    "The screen prioritizes materiality and follow-up, not a finding that funds were mishandled.",
                ],
            ),
            self._indicator(
                request,
                "Direct funding verification",
                entity,
                "State award direct-recipient and subrecipient allocation coverage",
                (
                    f"The HCD award list identifies eligible public applicant(s) and co-applicant(s) for {entity}, "
                    "but this run does not recover the standard agreement, payment ledger, subrecipient ledger, or operating-cost draw records needed to verify the exact dollars received by the nonprofit."
                ),
                "Data gap",
                "missing_source_or_field",
                "Pull the state standard agreement, draw/payment records, and local subrecipient contracts before making direct-recipient or cost-allowability claims.",
                record_ids,
                ["The award-list role field supports exposure ranking but not direct-payment allocation."],
            ),
        ]

    def _service_page_indicators(self, request: CaseRequest, entity: str) -> list[OversightRiskIndicator]:
        records = [record for record in self.records if record.source_type == "org_service_page" and entity in record.entities]
        record_ids = [record.record_id for record in records]
        if not records:
            return [
                self._indicator(
                    request,
                    "Homelessness scope mismatch",
                    entity,
                    "Retrieved website/service-page keyword screen",
                    "No organization service page was retrieved for this entity, so the run cannot screen web language for voter registration, citizenship, immigration enforcement, power building, political action, or similar terms that may need homelessness-funding scope review.",
                    "Data gap",
                    "missing_source",
                    "Add official-site pages and social/traffic sources before judging public messaging or scope alignment.",
                    [],
                    ["Absence of a retrieved page is not evidence that off-scope activity exists or does not exist."],
                )
            ]
        text = "\n".join(record.body for record in records).lower()
        high_terms = self.HOMELESSNESS_SCOPE_HIGH_TERMS
        medium_terms = self.HOMELESSNESS_SCOPE_MEDIUM_TERMS
        found_high = [term for term in high_terms if term in text]
        found_medium = [term for term in medium_terms if term in text]
        if found_high:
            level = "High"
            found = found_high
        elif found_medium:
            level = "Medium"
            found = found_medium
        else:
            level = "Low"
            found = []
        observed = (
            f"Retrieved official/service pages screened for homelessness funding-scope exact phrases. Matched phrases: {', '.join(found) if found else 'none from configured list'}."
        )
        return [
            self._indicator(
                request,
                "Homelessness scope mismatch",
                entity,
                "Retrieved website/service-page keyword screen",
                observed,
                level,
                "observed",
                "If matches exist, compare page context to homelessness grant scope, contract restrictions, cost allocation, and funding source before drawing conclusions.",
                record_ids,
                [
                    "A 501(c)(3) may conduct some voter, civic, citizenship, immigration, advocacy, or education work depending on facts and law; the CalDS test is whether a homelessness-funded entity's activity is in-scope and correctly funded.",
                    "Keyword screening does not replace expenditure testing or full website/social review.",
                ],
            )
        ]

    def _spend_vs_results_indicators(self, request: CaseRequest, spend_join: dict[str, Any]) -> list[OversightRiskIndicator]:
        rows = list(spend_join.get("entity_outcome_rows", [])) if isinstance(spend_join, dict) else []
        record_ids = self._record_ids_for_source_types("source_extraction_spend_vs_results_table", "source_extraction_official_outcome_table")
        indicators: list[OversightRiskIndicator] = []
        for row in rows:
            flags = list(row.get("outcome_flags") or [])
            if not flags:
                continue
            level = str(row.get("risk_level") or "Medium")
            entity = str(row.get("entity") or "unknown")
            county = str(row.get("county") or "unknown county")
            spending = row.get("spending_growth_pct")
            revenue = row.get("revenue_growth_pct")
            grants = row.get("government_grant_growth_pct")
            state_award_exposure = self._number(row.get("state_award_exposure"))
            state_award_text = f" State project-award exposure={self._money(state_award_exposure)}." if state_award_exposure is not None else ""
            geography_phrase = "state-award project geography" if state_award_exposure is not None else "matched service geography"
            observed = (
                f"{entity} has {geography_phrase} in {county}; official county/CoC context flags {', '.join(flags)}. "
                f"Parsed entity growth context: spending={self._pct_text(spending)}, revenue={self._pct_text(revenue)}, government grants={self._pct_text(grants)}.{state_award_text}"
            )
            indicators.append(
                self._indicator(
                    request,
                    "Spend-versus-results",
                    entity,
                    f"County outcome movement and entity spending context: {county}",
                    observed,
                    level if level in {"High", "Medium", "Low"} else "Medium",
                    "observed_contextual_join",
                    "Review underlying county/CoC outcome rows, state-award project geography, contract geography, and provider-specific outcome records before drawing any conclusion.",
                    record_ids,
                    list(row.get("join_caveats") or ["County outcomes are not provider-attributable without direct program outcome data."]),
                )
            )
        return indicators

    def _public_statement_indicators(self, request: CaseRequest, entity: str) -> list[OversightRiskIndicator]:
        records = [record for record in self.records if record.source_type == "public_statement_source" and entity in record.entities]
        if not records:
            return []
        record_ids = [record.record_id for record in records]
        body = "\n".join(record.body for record in records).lower()
        high_terms = self.HOMELESSNESS_SCOPE_HIGH_TERMS
        medium_terms = self.HOMELESSNESS_SCOPE_MEDIUM_TERMS
        found_high = [term for term in high_terms if term in body]
        found_medium = [term for term in medium_terms if term in body]
        if found_high:
            level = "High"
            found = found_high
        elif found_medium:
            level = "Medium"
            found = found_medium
        else:
            level = "Low"
            found = []
        return [
            self._indicator(
                request,
                "Homelessness scope mismatch",
                entity,
                "Official/public page term screen",
                f"Configured public statement pages were harvested. Matched review terms: {', '.join(found) if found else 'none from configured high/medium list'}.",
                level,
                "observed",
                "If terms are present, inspect the archived page context, speaker attribution, homelessness funding restrictions, contract scope, and cost allocation; statements alone do not establish spending outside scope.",
                record_ids,
                [
                    "A 501(c)(3) may conduct some voter, civic, citizenship, immigration, advocacy, or education work depending on facts and law; the CalDS test is whether a homelessness-funded entity's activity is in-scope and correctly funded.",
                    "Website language is context only and must be tied to funding/expenditure records before escalation.",
                ],
            )
        ]

    def _outcome_source_gap_indicators(self, request: CaseRequest, manifest: dict[str, Any]) -> list[OversightRiskIndicator]:
        if not isinstance(manifest, dict) or not manifest:
            return []
        record_ids = self._record_ids_for_source_types("source_extraction_official_outcome_table")
        indicators: list[OversightRiskIndicator] = []
        caloms = manifest.get("dhcs_caloms", {})
        if caloms and (not caloms.get("fetched") or int(caloms.get("text_chars") or 0) == 0):
            indicators.append(
                self._indicator(
                    request,
                    "Treatment completion",
                    "Case-wide",
                    "Direct CalOMS/DATAR treatment completion coverage",
                    "The DHCS CalOMS/DATAR public page was probed, but this run did not recover a machine-readable provider/county treatment completion table.",
                    "Data gap",
                    "restricted_or_non_machine_readable_source",
                    "Use public reports or a governed data request before judging spend-versus-treatment-completion performance.",
                    record_ids,
                    ["MAT membership and county outcomes are context; direct treatment completion data remains unavailable in this run."],
                )
            )
        adverse = [manifest.get("dhcs_suspension_revocation", {}), manifest.get("dhcs_sus_rev_nov", {})]
        if adverse and all(int(item.get("text_chars") or 0) == 0 for item in adverse if item):
            indicators.append(
                self._indicator(
                    request,
                    "License/adverse-action history",
                    "Case-wide",
                    "DHCS adverse-action page machine readability",
                    "DHCS adverse-action pages were fetched but did not expose machine-readable target rows in static text during this run.",
                    "Data gap",
                    "non_machine_readable_source",
                    "Archive the pages and pursue a row export or page-specific parser before ranking probation, suspension, revocation, or NOV history.",
                    record_ids,
                    ["Existing DHCS Active/Closed facility status remains available, but it is not the same as adverse-action history."],
                )
            )
        return indicators

    def _case_wide_gap_indicators(self, request: CaseRequest, spend_join: dict[str, Any] | None = None) -> list[OversightRiskIndicator]:
        rows = list((spend_join or {}).get("entity_outcome_rows", [])) if isinstance(spend_join, dict) else []
        indicators: list[OversightRiskIndicator] = []
        if not rows:
            indicators.append(
                self._indicator(
                    request,
                    "Spend-versus-results",
                    "Case-wide",
                    "Outcome-denominator coverage for homelessness, drug use, crime, and treatment results",
                    "No homelessness, overdose/substance-use, crime, treatment completion, recurrence, or county outcome denominator dataset is ingested in this run; the matrix cannot test whether spending increased while outcomes worsened.",
                    "Data gap",
                    "missing_required_outcome_sources",
                    "Ingest official outcome series and align them by county, service line, year, and funding stream before ranking spend-versus-results concerns.",
                    [],
                    ["The current run can flag spending growth but cannot measure program results."],
                )
            )
        else:
            indicators.append(
                self._indicator(
                    request,
                    "Spend-versus-results",
                    "Case-wide",
                    "Outcome-denominator coverage for homelessness, drug use, crime, and treatment results",
                    f"Official outcome series are ingested and joined into {len(rows)} entity/county context rows. These rows remain contextual and are not provider-attributable results.",
                    "Low",
                    "observed",
                    "Use entity/county rows below to prioritize follow-up; do not treat county outcomes as proof of provider performance.",
                    self._record_ids_for_source_types("source_extraction_official_outcome_table", "source_extraction_spend_vs_results_table"),
                    ["The join is contextual; direct program outcome data is still required for attribution."],
                )
            )
        indicators.extend([
            self._indicator(
                request,
                "Public attention and traffic",
                "Case-wide",
                "Social media and website traffic coverage",
                "No social media account metrics, website analytics, ad-library records, or third-party traffic estimates are ingested in this run.",
                "Data gap",
                "missing_required_attention_sources",
                "Add a governed source policy for traffic/social metrics and preserve collection timestamps before using attention patterns as risk proxies.",
                [],
                ["Traffic and social metrics are volatile and can be misleading without source timestamps and normalization."],
            ),
        ])
        return indicators

    def _indicator(
        self,
        request: CaseRequest,
        risk_area: str,
        entity: str,
        test_name: str,
        observed_fact: str,
        risk_level: str,
        data_status: str,
        reviewer_action: str,
        record_ids: list[str],
        caveats: list[str],
    ) -> OversightRiskIndicator:
        record_ids = [record_id for record_id in dict.fromkeys(record_ids) if record_id in self.records_by_id]
        evidence_ids = [self.items_by_record[record_id].item_id for record_id in record_ids if record_id in self.items_by_record]
        source_uris = [self.records_by_id[record_id].source_uri for record_id in record_ids]
        return OversightRiskIndicator(
            indicator_id=stable_id("risk", request.case_id, risk_area, entity, test_name, observed_fact),
            case_id=request.case_id,
            risk_area=risk_area,
            entity=entity,
            test_name=test_name,
            observed_fact=observed_fact,
            risk_level=risk_level,
            data_status=data_status,
            reviewer_action=reviewer_action,
            evidence_ids=evidence_ids,
            record_ids=record_ids,
            source_uris=source_uris,
            caveats=caveats,
        )

    def _record_ids_for_source_types(self, *source_types: str) -> list[str]:
        return [record.record_id for record in self.records if record.source_type in source_types]

    def _record_ids_for_entity_and_source_types(self, entity: str, *source_types: str) -> list[str]:
        entity_lower = entity.lower()
        return [
            record.record_id
            for record in self.records
            if record.source_type in source_types
            and (
                entity in record.entities
                or entity_lower in record.title.lower()
                or entity_lower in record.record_id.lower()
            )
        ]

    def _latest_numeric_pair(self, rows: list[dict[str, Any]], field: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
        numeric_rows = [row for row in rows if row.get("downloaded") and self._number(row.get(field)) is not None]
        numeric_rows = sorted(numeric_rows, key=lambda row: int(row.get("tax_period_year") or 0))
        if len(numeric_rows) < 2:
            return None
        return numeric_rows[-2], numeric_rows[-1]

    def _latest_row_with(self, rows: list[dict[str, Any]], *fields: str) -> dict[str, Any] | None:
        candidates = [row for row in rows if row.get("downloaded") and all(self._number(row.get(field)) is not None for field in fields)]
        return sorted(candidates, key=lambda row: int(row.get("tax_period_year") or 0))[-1] if candidates else None

    def _latest_row_with_any(self, rows: list[dict[str, Any]], *fields: str) -> dict[str, Any] | None:
        candidates = [row for row in rows if row.get("downloaded") and any(field in row for field in fields)]
        return sorted(candidates, key=lambda row: int(row.get("tax_period_year") or 0))[-1] if candidates else None

    def _available_years(self, rows: list[dict[str, Any]], field: str) -> str:
        years = [str(row.get("tax_period_year")) for row in rows if row.get("downloaded") and self._number(row.get(field)) is not None]
        return ", ".join(years)

    def _number(self, value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(str(value).replace(",", ""))
        except Exception:
            return None

    def _pct_change(self, previous: float, current: float) -> float:
        if previous == 0:
            return 0.0 if current == 0 else 100.0
        return ((current - previous) / abs(previous)) * 100.0

    def _boolish(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "y", "x"}

    def _yn(self, value: bool) -> str:
        return "yes" if value else "no"

    def _money(self, value: float | None) -> str:
        if value is None:
            return "not parsed"
        return "$" + f"{value:,.0f}"

    def _pct_text(self, value: Any) -> str:
        number = self._number(value)
        if number is None:
            return "not parsed"
        return f"{number:+.1f}%"

    def _list_text(self, values: list[Any]) -> str:
        return ", ".join(str(value) for value in values) if values else "none"


