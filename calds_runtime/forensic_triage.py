from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
from typing import Iterable

from .contracts import (
    CanonicalRecord,
    CaseRequest,
    ContextHandoffLedger,
    EntityTriageResult,
    ForensicFinding,
    ForensicInvestigationPlan,
    TriageFinding,
    stable_id,
)
from .truth import tokenize


SOURCE_FAMILIES = [
    "state_awards",
    "irs_990",
    "audit",
    "enforcement_or_docket",
    "county_contract_monitoring",
    "web_and_social",
    "outcomes",
]


class HomelessnessTriageService:
    """Deterministic first-pass triage over all named homelessness entities."""

    def build(
        self,
        request: CaseRequest,
        records: Iterable[CanonicalRecord],
    ) -> list[EntityTriageResult]:
        self.records = list(records)
        results = []
        for entity in request.entities:
            entity_records = self._records_for_entity(entity)
            findings = self._findings_for_entity(request, entity, entity_records)
            missing = self._missing_source_families(entity_records)
            priority, deep_dive, rationale = self._priority(findings, missing)
            results.append(
                EntityTriageResult(
                    result_id=stable_id("triage", request.case_id, entity, priority),
                    case_id=request.case_id,
                    entity=entity,
                    triage_priority=priority,
                    deep_dive_recommended=deep_dive,
                    rationale=rationale,
                    findings=findings,
                    missing_source_families=missing,
                )
            )
        return results

    def build_plan(
        self,
        request: CaseRequest,
        results: list[EntityTriageResult],
    ) -> ForensicInvestigationPlan:
        selected = [
            result.entity
            for result in results
            if result.deep_dive_recommended
        ]
        rationales = {result.entity: result.rationale for result in results if result.entity in selected}
        return ForensicInvestigationPlan(
            plan_id=stable_id("forensic_plan", request.case_id, *selected),
            case_id=request.case_id,
            selected_entities=selected,
            selection_rule=(
                "Deep dive when an entity has at least one High triage finding, "
                "or two or more Medium findings from independent source families. "
                "Data gaps alone do not upgrade an entity."
            ),
            source_families=SOURCE_FAMILIES,
            entity_rationales=rationales,
        )

    def build_forensic_findings(
        self,
        request: CaseRequest,
        results: list[EntityTriageResult],
        plan: ForensicInvestigationPlan,
    ) -> list[ForensicFinding]:
        findings = []
        selected = set(plan.selected_entities)
        for result in results:
            if result.entity not in selected:
                continue
            substantive = [item for item in result.findings if item.risk_level in {"High", "Medium"}]
            if not substantive:
                continue
            source_families = ", ".join(sorted({item.source_family for item in substantive}))
            basis = " ".join(item.observed_fact for item in substantive[:4])
            findings.append(
                ForensicFinding(
                    finding_id=stable_id("forensic", request.case_id, result.entity, basis),
                    case_id=request.case_id,
                    entity=result.entity,
                    hypothesis=(
                        f"CalDS should investigate {result.entity} for possible public-funds oversight risk "
                        f"because the triage stage found {source_families} signals."
                    ),
                    basis=basis,
                    confidence="High" if any(item.risk_level == "High" for item in substantive) else "Medium",
                    evidence_record_ids=self._dedupe(record_id for item in substantive for record_id in item.record_ids),
                    source_uris=self._dedupe(uri for item in substantive for uri in item.source_uris),
                    caveats=self._dedupe(caveat for item in substantive for caveat in item.caveats),
                    next_steps=self._next_steps_for(result),
                )
            )
        return findings

    def build_handoff(
        self,
        request: CaseRequest,
        from_step: str,
        to_step: str,
        artifact_refs: list[str],
        present_fields: list[str] | None = None,
    ) -> ContextHandoffLedger:
        required = [
            "case_id",
            "entities",
            "source_families",
            "triage_results",
            "selected_entities",
            "evidence_record_ids",
            "source_uris",
            "caveats",
            "next_steps",
        ]
        derived_fields = self._derive_handoff_present_fields(request, artifact_refs)
        present = derived_fields or list(present_fields or [])
        missing = [field for field in required if field not in present]
        return ContextHandoffLedger(
            ledger_id=stable_id("handoff", request.case_id, from_step, to_step, *artifact_refs),
            case_id=request.case_id,
            from_step=from_step,
            to_step=to_step,
            required_fields=required,
            present_fields=present,
            missing_fields=missing,
            artifact_refs=artifact_refs,
            status="PASS" if not missing else "REPAIR_REQUIRED",
        )

    def _derive_handoff_present_fields(self, request: CaseRequest, artifact_refs: list[str]) -> list[str]:
        artifacts = {Path(ref).name: self._load_json(Path(ref)) for ref in artifact_refs}
        triage = artifacts.get("entity_triage_results.json", {})
        plan = artifacts.get("forensic_investigation_plan.json", {})
        forensic = artifacts.get("forensic_findings.json", {})
        results = list(triage.get("results", [])) if isinstance(triage, dict) else []
        findings = list(forensic.get("findings", [])) if isinstance(forensic, dict) else []
        selected = list(plan.get("selected_entities", [])) if isinstance(plan, dict) else []
        triage_findings = [finding for result in results for finding in result.get("findings", [])]

        present: list[str] = []
        if request.case_id and (
            plan.get("case_id") == request.case_id
            or any(result.get("case_id") == request.case_id for result in results)
            or any(finding.get("case_id") == request.case_id for finding in findings)
        ):
            present.append("case_id")
        if request.entities and {item.get("entity") for item in results} & set(request.entities):
            present.append("entities")
        if isinstance(plan, dict) and plan.get("source_families"):
            present.append("source_families")
        if results:
            present.append("triage_results")
        if "selected_entities" in plan:
            present.append("selected_entities")
        if not selected:
            present.extend(["evidence_record_ids", "source_uris", "caveats", "next_steps"])
            return present
        if any(finding.get("evidence_record_ids") for finding in findings) or any(finding.get("record_ids") for finding in triage_findings):
            present.append("evidence_record_ids")
        if any(finding.get("source_uris") for finding in findings) or any(finding.get("source_uris") for finding in triage_findings):
            present.append("source_uris")
        if any(finding.get("caveats") for finding in findings) or any(finding.get("caveats") for finding in triage_findings):
            present.append("caveats")
        if any(finding.get("next_steps") for finding in findings):
            present.append("next_steps")
        return present

    def _load_json(self, path: Path) -> dict[str, object]:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def priority_record_ids(self, results: list[EntityTriageResult]) -> list[str]:
        priority = []
        for result in results:
            if not result.deep_dive_recommended:
                continue
            for finding in result.findings:
                if finding.risk_level in {"High", "Medium"}:
                    priority.extend(finding.record_ids)
        return self._dedupe(priority)

    def _records_for_entity(self, entity: str) -> list[CanonicalRecord]:
        entity_norm = self._norm(entity)
        entity_tokens = set(tokenize(entity)) - {"inc", "the", "of", "association", "center"}
        records = []
        for record in self.records:
            haystack = self._norm(" ".join([record.record_id, record.title, " ".join(record.entities)]))
            record_tokens = set(tokenize(" ".join([record.record_id, record.title, " ".join(record.entities)])))
            if entity_norm in haystack or (entity_tokens and len(entity_tokens & record_tokens) >= min(2, len(entity_tokens))):
                records.append(record)
        return records

    def _findings_for_entity(
        self,
        request: CaseRequest,
        entity: str,
        records: list[CanonicalRecord],
    ) -> list[TriageFinding]:
        findings: list[TriageFinding] = []
        for record in records:
            signals = dict(record.attributes.get("signals", {}))
            if signals.get("official_enforcement_or_docket_flag"):
                connected_party = bool(signals.get("connected_party_enforcement_exposure"))
                findings.append(
                    self._finding(
                        request,
                        entity,
                        "enforcement_or_docket",
                        "connected-party official charge trigger" if connected_party else "official enforcement or docket linkage",
                        self._enforcement_fact(record),
                        "High",
                        "observed",
                        (
                            "An official charge or indictment tied to a public-funded project, counterparty, operator, or transaction chain is a mandatory deep-dive trigger while preserving named-party legal distinctions."
                            if connected_party
                            else "Official enforcement or court-source records create an immediate deep-dive trigger."
                        ),
                        [record],
                        [
                            "Use exact legal status from the source. A charge against a third party is not a finding against the nonprofit unless the source says so.",
                            "Connected-party exposure is a triage trigger, not an entity-level legal conclusion.",
                            "All defendants are presumed innocent unless and until proven guilty in court.",
                        ],
                    )
                )
            if signals.get("third_party_enforcement_pointer"):
                findings.append(
                    self._finding(
                        request,
                        entity,
                        "enforcement_or_docket",
                        "secondary enforcement pointer",
                        self._short_body(record),
                        "Medium",
                        "observed_contextual_pointer",
                        "Secondary-source enforcement pointers should be verified against official docket or agency records.",
                        [record],
                        ["Secondary media or watchdog material is not controlling source evidence."],
                    )
                )
            if record.source_type == "state_homelessness_award":
                exposure = self._number(record.attributes.get("total_award_exposure"))
                if exposure is not None:
                    level = "High" if exposure >= 50_000_000 else "Medium" if exposure >= 25_000_000 else "Low"
                    if level in {"High", "Medium"}:
                        findings.append(
                            self._finding(
                                request,
                                entity,
                                "state_awards",
                                "material state project-award exposure",
                                f"Official California housing award rows attach {self._money(exposure)} in project-award exposure to {entity}.",
                                level,
                                "observed",
                                "Material public-funds exposure should be traced to standard agreements, subrecipient allocations, payment ledgers, and deliverables.",
                                [record],
                                ["Project-award exposure is not direct-payment proof."],
                            )
                        )
                if signals.get("direct_payment_allocation_missing"):
                    findings.append(
                        self._finding(
                            request,
                            entity,
                            "state_awards",
                            "direct payment allocation gap",
                            "The current corpus does not recover the agreement, draw, payment, or subrecipient allocation records needed to prove exact nonprofit receipt.",
                            "Data gap",
                            "missing_source_or_field",
                            "Do not treat project-award exposure as direct receipt until payment allocation is verified.",
                            [record],
                            ["This is a source gap, not an adverse finding."],
                        )
                    )
            if record.source_type in {"org_service_page", "public_statement_source"} and signals.get("off_scope_keyword_match"):
                matched_terms = list(record.attributes.get("matched_terms") or [])
                high_terms = {
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
                }
                level = "Medium"
                funding_nexus = self._has_scope_funding_nexus(record)
                if any(term in high_terms for term in matched_terms) and funding_nexus:
                    level = "High"
                trigger_reason = (
                    "Public language is tied to a specific funding-source, contract-scope, or cost-allocation nexus in the record."
                    if funding_nexus
                    else "Keyword-only scope language requires funding-source, contract-scope, or cost-allocation evidence before high-priority escalation."
                )
                findings.append(
                    self._finding(
                        request,
                        entity,
                        "web_and_social",
                        "homelessness scope-mismatch public language",
                        self._short_body(record),
                        level,
                        "observed_with_funding_nexus" if funding_nexus else "observed_keyword_only",
                        trigger_reason,
                        [record],
                        [
                            "Website language alone does not prove money was spent outside scope.",
                            "The triage question is funding and scope alignment for a homelessness-funded entity, not whether the activity is categorically unlawful for a 501(c)(3).",
                        ],
                    )
                )
        return sorted(findings, key=lambda item: ({"High": 0, "Medium": 1, "Low": 2}.get(item.risk_level, 3), item.source_family, item.finding_type))

    def _priority(
        self,
        findings: list[TriageFinding],
        missing: list[str],
    ) -> tuple[str, bool, str]:
        levels = Counter(item.risk_level for item in findings)
        medium_families = {item.source_family for item in findings if item.risk_level == "Medium"}
        if levels.get("High"):
            return "High", True, "At least one official or high-materiality source trigger fired."
        if len(medium_families) >= 2:
            return "Medium", True, "Two or more independent medium triage source families fired."
        if levels.get("Medium"):
            return "Medium-watch", False, "One medium signal fired; hold for broader source collection before deep dive."
        if missing:
            return "Source-gap", False, "No substantive triage trigger fired, but required source families remain missing."
        return "Low", False, "No configured triage trigger fired from the current corpus."

    def _missing_source_families(self, records: list[CanonicalRecord]) -> list[str]:
        present = {self._source_family(record) for record in records if not self._is_source_gap_only(record)}
        present.discard("")
        return [family for family in SOURCE_FAMILIES if family not in present]

    def _is_source_gap_only(self, record: CanonicalRecord) -> bool:
        signals = dict(record.attributes.get("signals", {}))
        source_type = str(record.source_type).lower()
        return bool(
            signals.get("discovery_only_source_gap")
            or signals.get("not_citation_ready")
            or signals.get("source_gap_only")
            or source_type.endswith("_discovery")
            or "discovery_gap" in source_type
        )

    def _has_scope_funding_nexus(self, record: CanonicalRecord) -> bool:
        signals = dict(record.attributes.get("signals", {}))
        return any(
            bool(signals.get(key) or record.attributes.get(key))
            for key in (
                "funding_scope_linked",
                "cost_allocation_evidence",
                "grant_scope_linked",
                "contract_scope_linked",
                "homelessness_funding_nexus",
                "funding_source_nexus",
                "public_funds_nexus",
            )
        )

    def _source_family(self, record: CanonicalRecord) -> str:
        source_type = record.source_type
        value = f"{record.source_type} {record.record_id} {record.title}".lower()
        if source_type in {"state_homelessness_award", "source_extraction_state_homeless_award_table"} or "homekey" in value:
            return "state_awards"
        if "irs_990" in value or source_type.startswith("irs_990") or source_type == "source_extraction_irs_990_table":
            return "irs_990"
        if "fac_" in value or source_type.startswith("fac_") or source_type in {"source_extraction_fac_audit_table", "source_extraction_fac_award_table"}:
            return "audit"
        if "enforcement" in value or "docket" in value or "court" in value:
            return "enforcement_or_docket"
        if "county" in value or "contract" in value or "monitoring" in value:
            return "county_contract_monitoring"
        if source_type in {"org_service_page", "public_statement_source", "social_media_source", "source_extraction_social_web_table"}:
            return "web_and_social"
        if "outcome" in value or "spend_vs_results" in value:
            return "outcomes"
        return ""

    def _finding(
        self,
        request: CaseRequest,
        entity: str,
        source_family: str,
        finding_type: str,
        observed_fact: str,
        risk_level: str,
        data_status: str,
        trigger_reason: str,
        records: list[CanonicalRecord],
        caveats: list[str],
    ) -> TriageFinding:
        return TriageFinding(
            finding_id=stable_id("triage_finding", request.case_id, entity, source_family, finding_type, observed_fact),
            case_id=request.case_id,
            entity=entity,
            source_family=source_family,
            finding_type=finding_type,
            observed_fact=observed_fact,
            risk_level=risk_level,
            data_status=data_status,
            trigger_reason=trigger_reason,
            source_uris=self._dedupe(record.source_uri for record in records),
            record_ids=self._dedupe(record.record_id for record in records),
            caveats=caveats,
        )

    def _next_steps_for(self, result: EntityTriageResult) -> list[str]:
        steps = [
            "Open every official source cited by the triage result and verify the source wording before escalation.",
            "Pull raw Form 990 filings, audit reports, payment ledgers, contracts, standard agreements, deliverables, and monitoring or corrective-action records for the selected entity.",
        ]
        if any(item.source_family == "enforcement_or_docket" for item in result.findings):
            steps.append("Verify the official docket or agency case status directly and distinguish third-party charges from entity-level findings.")
        if any(item.source_family == "state_awards" for item in result.findings):
            steps.append("Trace project-award exposure to exact recipient, subrecipient, draw, and operating-cost records.")
        if any(item.source_family == "web_and_social" for item in result.findings):
            steps.append("Archive public website and social-media pages, then compare voter, citizenship, immigration, advocacy, and political-language matches to homelessness grant scope, contract restrictions, funding source, and cost allocation.")
        return self._dedupe(steps)

    def _enforcement_fact(self, record: CanonicalRecord) -> str:
        text = self._short_body(record)
        if text:
            return text
        return f"Official enforcement or docket source retrieved: {record.title}."

    def _short_body(self, record: CanonicalRecord, limit: int = 520) -> str:
        body = " ".join(record.body.split())
        if len(body) <= limit:
            return body
        return body[: limit - 3].rstrip() + "..."

    def _number(self, value: object) -> float | None:
        try:
            text = str(value).replace(",", "").replace("$", "").strip()
            if not text:
                return None
            return float(text)
        except Exception:
            return None

    def _money(self, value: float) -> str:
        return "$" + f"{value:,.0f}"

    def _norm(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", value.lower())

    def _dedupe(self, values: Iterable[str]) -> list[str]:
        seen = set()
        result = []
        for value in values:
            if value and value not in seen:
                seen.add(value)
                result.append(value)
        return result
