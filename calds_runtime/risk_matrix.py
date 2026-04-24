from __future__ import annotations

import json
from pathlib import Path
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
    """Deterministic WFA screening matrix built from source records, not model memory."""

    SCORE_SCALE = (
        "Indicator levels: High=immediate reviewer follow-up, Medium=review queue, "
        "Low=context only, Data gap=required source missing or not parsed. Levels are "
        "screening priorities, not findings or allegations."
    )

    METHODOLOGY = (
        "Waste, fraud, and abuse risk-screening matrix generated from parsed IRS, "
        "FAC, DHCS, county/document, public-statement, and outcome-join records. "
        "Rows are reviewer prompts only and cannot be treated as conclusions."
    )

    def build(
        self,
        request: CaseRequest,
        records: Iterable[CanonicalRecord],
        bundle: EvidenceBundle,
    ) -> OversightRiskMatrix:
        self.records = list(records)
        self.records_by_id = {record.record_id: record for record in self.records}
        self.items_by_record = {item.record_id: item for item in bundle.items}
        indicators: list[OversightRiskIndicator] = []

        spend_join = self._load_json_for_type("source_extraction_spend_vs_results_table") or {}
        spend_rows = list(spend_join.get("entity_outcome_rows", [])) if isinstance(spend_join, dict) else []
        indicators.extend(self._spend_vs_results_rows(request, spend_rows))

        entities = self._entities(request)
        for entity in entities:
            indicators.extend(self._entity_financial_rows(request, entity))
            indicators.extend(self._entity_source_rows(request, entity))

        if not spend_rows:
            indicators.append(
                self._indicator(
                    request,
                    "Spend-versus-results",
                    "Case-wide",
                    "Outcome-denominator coverage for homelessness, drug use, crime, and treatment results",
                    "No joined outcome-denominator rows are available in this source tree until the live outcome ingestor is run or the bundled source is rehydrated.",
                    "Data gap",
                    "missing_required_outcome_sources",
                    "Run the official outcome ingestor and align by county, year, and service footprint before ranking spend-versus-results concerns.",
                    [],
                    ["This data gap blocks provider-attributable outcome conclusions."],
                )
            )

        indicators.append(
            self._indicator(
                request,
                "Public attention and traffic",
                "Case-wide",
                "Social media and website traffic coverage",
                "No governed social media metrics, website analytics, ad-library records, or third-party traffic estimates are present in the source tree.",
                "Data gap",
                "missing_required_attention_sources",
                "Add a governed source policy for traffic/social metrics before using attention patterns as risk proxies.",
                [],
                ["Traffic and social metrics are volatile and require timestamps, normalization, and source caveats."],
            )
        )

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
            for candidate in [record.attributes.get("table_path"), record.source_uri]:
                if not candidate:
                    continue
                path = Path(str(candidate))
                if path.exists():
                    return json.loads(path.read_text(encoding="utf-8"))
        return None

    def _entities(self, request: CaseRequest) -> list[str]:
        seen: list[str] = []
        for entity in request.entities:
            if entity and entity not in seen:
                seen.append(entity)
        for record in self.records:
            for entity in record.entities:
                if entity and entity not in seen:
                    seen.append(entity)
        return seen or ["Case-wide"]

    def _spend_vs_results_rows(self, request: CaseRequest, rows: list[dict[str, Any]]) -> list[OversightRiskIndicator]:
        indicators: list[OversightRiskIndicator] = []
        record_ids = self._record_ids_for_source_types(
            "source_extraction_spend_vs_results_table",
            "source_extraction_official_outcome_table",
        )
        for row in rows:
            flags = list(row.get("outcome_flags") or [])
            if not flags:
                continue
            entity = str(row.get("entity") or "unknown entity")
            county = str(row.get("county") or "unknown county")
            level = str(row.get("risk_level") or "Medium")
            if level not in {"High", "Medium", "Low"}:
                level = "Medium"
            observed = (
                f"{entity} has DHCS facility footprint in {county}; official county/CoC context flags "
                f"{', '.join(flags)}. Entity growth context: spending={self._pct_text(row.get('spending_growth_pct'))}, "
                f"revenue={self._pct_text(row.get('revenue_growth_pct'))}, government grants={self._pct_text(row.get('government_grant_growth_pct'))}."
            )
            indicators.append(
                self._indicator(
                    request,
                    "Spend-versus-results",
                    entity,
                    f"County outcome movement and entity spending context: {county}",
                    observed,
                    level,
                    "observed_contextual_join",
                    "Review county/CoC outcome rows, facility footprint, contract geography, and provider-specific outcome records before drawing any conclusion.",
                    record_ids,
                    list(row.get("join_caveats") or ["County outcomes are not provider-attributable without direct program outcome data."]),
                )
            )
        return indicators

    def _entity_financial_rows(self, request: CaseRequest, entity: str) -> list[OversightRiskIndicator]:
        record_ids = self._record_ids_for_entity(entity, "irs_990_xml", "source_extraction_irs_990_table", "irs_990_full_text_fallback")
        if record_ids:
            return [
                self._indicator(
                    request,
                    "Financial growth",
                    entity,
                    "IRS return coverage for growth, compensation, payroll, and off-scope indicators",
                    "IRS return or parser records are present for this entity. Use raw XML/PDF and parsed tables to compute year-over-year growth, compensation, payroll, grant concentration, and political/lobbying indicators.",
                    "Low",
                    "source_available",
                    "Run the full parser or inspect the raw return before ranking the entity on financial-growth or compensation tests.",
                    record_ids,
                    ["Presence of a return is not an adverse signal."],
                )
            ]
        return [
            self._indicator(
                request,
                "Financial growth",
                entity,
                "IRS return coverage for growth, compensation, payroll, and off-scope indicators",
                "No parsed or downloaded IRS return record is available in the current visible source tree for this entity.",
                "Data gap",
                "missing_source_or_field",
                "Recover full IRS XML/PDF and parse financial fields before ranking this entity.",
                [],
                ["The full source bundle may contain additional live-ingest scripts and artifacts after rehydration."],
            )
        ]

    def _entity_source_rows(self, request: CaseRequest, entity: str) -> list[OversightRiskIndicator]:
        rows: list[OversightRiskIndicator] = []
        fac_ids = self._record_ids_for_entity(entity, "fac_audit_pdf", "fac_findings", "fac_federal_awards", "source_extraction_fac_audit_table")
        dhcs_ids = self._record_ids_for_entity(entity, "dhcs_facility_status", "source_extraction_dhcs_status_table")
        statement_ids = self._record_ids_for_entity(entity, "public_statement_source", "org_service_page")
        rows.append(
            self._indicator(
                request,
                "Audit controls",
                entity,
                "FAC audit and award coverage",
                "FAC audit, findings, or award records are present." if fac_ids else "No FAC audit/findings/award records are visible for this entity in the current source tree.",
                "Low" if fac_ids else "Data gap",
                "source_available" if fac_ids else "missing_source",
                "Open FAC PDFs and award rows to verify findings, award concentration, and management response status.",
                fac_ids,
                ["Audit records require year-specific and finding-specific review."],
            )
        )
        rows.append(
            self._indicator(
                request,
                "License/adverse-action history",
                entity,
                "DHCS facility status and adverse-action coverage",
                "DHCS facility-status records are present." if dhcs_ids else "No DHCS facility-status/adverse-action records are visible for this entity in the current source tree.",
                "Low" if dhcs_ids else "Data gap",
                "source_available" if dhcs_ids else "missing_source",
                "Verify facility-level status and adverse-action history directly against DHCS before entity-level use.",
                dhcs_ids,
                ["Active/closed facility status is not the same as probation, suspension, revocation, or NOV history."],
            )
        )
        rows.append(
            self._indicator(
                request,
                "Public statements",
                entity,
                "Official/public page term screen",
                "Public statement or service-page records are present." if statement_ids else "No harvested public statement or service-page records are visible for this entity in the current source tree.",
                "Low" if statement_ids else "Data gap",
                "source_available" if statement_ids else "missing_source",
                "Use statement pages only as context; tie any off-scope concern to funding restrictions and expenditure records.",
                statement_ids,
                ["Website language does not establish spending outside scope by itself."],
            )
        )
        return rows

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

    def _record_ids_for_entity(self, entity: str, *source_types: str) -> list[str]:
        return [
            record.record_id
            for record in self.records
            if record.source_type in source_types and entity in record.entities
        ]

    def _pct_text(self, value: Any) -> str:
        try:
            return f"{float(value):+.1f}%"
        except Exception:
            return "not parsed"
