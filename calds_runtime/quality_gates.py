from __future__ import annotations

from collections import Counter
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request

from .contracts import (
    AcquisitionSearchRun,
    CanonicalRecord,
    CaseRequest,
    CitationCheck,
    CitationVerificationResult,
    CompletionGuardResult,
    EvidenceBundle,
    LinkIntegrityReport,
    OversightRiskMatrix,
    SourceLinkCheck,
    stable_id,
)


REQUIRED_SOURCE_FAMILIES = [
    "state_awards",
    "irs_990",
    "audit",
    "enforcement_or_docket",
    "county_contract_monitoring",
    "web_and_social",
    "outcomes",
]

SOURCE_FAMILY_TARGETS = {
    "state_awards": [
        "California Department of Housing and Community Development award lists",
        "state standard agreements",
        "draw or payment records",
    ],
    "irs_990": ["Internal Revenue Service Form 990 XML", "full Form 990 PDF or rendered return"],
    "audit": ["Federal Audit Clearinghouse general data", "audit findings", "audit report PDF"],
    "enforcement_or_docket": ["official agency enforcement pages", "court or docket records", "inspector-general releases"],
    "county_contract_monitoring": ["county contracts", "monitoring letters", "corrective-action records"],
    "web_and_social": ["official service pages", "public statements", "social or web pages"],
    "outcomes": ["official homelessness outcomes", "provider-attributable outcomes", "capacity or completion records"],
}

LEGAL_STATUS_TERMS = re.compile(r"\b(charged|convicted|settled|settlement|violation|prosecuted|indicted)\b", re.IGNORECASE)
MONEY_OR_DATE_RE = re.compile(r"(\$[0-9][0-9,]*(?:\.[0-9]+)?|\b20[0-9]{2}\b|\b19[0-9]{2}\b)")
EVIDENCE_REF_RE = re.compile(r"`(E\d{2})`")


class CompletionGuardService:
    """Deterministic anti-laziness gate for source-family acquisition coverage."""

    def build_acquisition_ledger(
        self,
        request: CaseRequest,
        records: list[CanonicalRecord],
        selected_entities: list[str],
        source_families: list[str] | None = None,
    ) -> list[AcquisitionSearchRun]:
        families = source_families or REQUIRED_SOURCE_FAMILIES
        entities = selected_entities or request.entities
        runs: list[AcquisitionSearchRun] = []
        for entity in entities:
            for family in families:
                matched = [
                    record
                    for record in records
                    if self._record_mentions_entity(record, entity) and self.source_family(record) == family
                ]
                query = self._query_for(entity, family)
                status = "hit" if matched else "miss"
                blocker = "" if matched else f"No citation-ready {family} record was recovered for {entity} in the current corpus."
                runs.append(
                    AcquisitionSearchRun(
                        search_id=stable_id("acquisition", request.case_id, entity, family),
                        case_id=request.case_id,
                        entity=entity,
                        source_family=family,
                        query=query,
                        attempted_sources=list(SOURCE_FAMILY_TARGETS.get(family, [family])),
                        matched_record_ids=sorted({record.record_id for record in matched}),
                        source_uris=self._dedupe(record.source_uri for record in matched),
                        status=status,
                        confidence="High" if matched else "Blocked",
                        blocker_reason=blocker,
                    )
                )
        return runs

    def guard(
        self,
        request: CaseRequest,
        ledger: list[AcquisitionSearchRun],
        selected_entities: list[str],
        source_families: list[str] | None = None,
    ) -> CompletionGuardResult:
        families = source_families or REQUIRED_SOURCE_FAMILIES
        entities = selected_entities or request.entities
        missing_required: list[str] = []
        by_key = {(run.entity, run.source_family): run for run in ledger}
        for entity in entities:
            for family in families:
                run = by_key.get((entity, family))
                if run is None or run.status != "hit":
                    missing_required.append(f"{entity}: {family}")
        counts = Counter(run.status for run in ledger)
        status = "PASS" if not missing_required else "PASS_WITH_BLOCKERS"
        if not ledger or not entities:
            status = "FAIL"
        notes = [
            "Completion guard records both hits and misses; misses are blockers, not clearance.",
            "Dossier compilation may proceed only because unresolved source gaps are preserved for human review.",
        ]
        if status == "FAIL":
            notes.append("No selected entities or acquisition rows were available; the workflow should not be treated as complete.")
        return CompletionGuardResult(
            guard_id=stable_id("completion_guard", request.case_id, str(len(ledger)), status),
            case_id=request.case_id,
            status=status,
            required_source_families=families,
            selected_entities=entities,
            total_searches=len(ledger),
            hit_count=counts.get("hit", 0),
            miss_count=counts.get("miss", 0),
            blocker_count=len(missing_required),
            missing_required=missing_required,
            notes=notes,
        )

    def source_family(self, record: CanonicalRecord) -> str:
        value = f"{record.source_type} {record.record_id}".lower()
        if record.source_type in {"state_homelessness_award", "source_extraction_state_homeless_award_table"} or "homekey" in value or "state_homeless" in value:
            return "state_awards"
        if "irs_990" in value or record.source_type.startswith("irs_990") or record.source_type == "source_extraction_irs_990_table":
            return "irs_990"
        if "fac_" in value or record.source_type.startswith("fac_") or record.source_type in {"source_extraction_fac_audit_table", "source_extraction_fac_award_table"}:
            return "audit"
        if "enforcement" in value or "docket" in value or "court" in value or "prosecution" in value:
            return "enforcement_or_docket"
        if "county" in value or "contract" in value or "monitoring" in value:
            return "county_contract_monitoring"
        if record.source_type in {"org_service_page", "public_statement_source", "social_media_source", "source_extraction_social_web_table"}:
            return "web_and_social"
        if "outcome" in value or "spend_vs_results" in value:
            return "outcomes"
        return ""

    def _record_mentions_entity(self, record: CanonicalRecord, entity: str) -> bool:
        wanted = self._norm(entity)
        return any(self._norm(candidate) == wanted for candidate in record.entities)

    def _query_for(self, entity: str, family: str) -> str:
        targets = ", ".join(SOURCE_FAMILY_TARGETS.get(family, [family]))
        return f"{entity} California {family} official sources: {targets}"

    def _norm(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

    def _dedupe(self, values) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            if value and value not in seen:
                seen.add(value)
                result.append(value)
        return result


class CitationVerifierService:
    """Checks that dossier claims remain tied to cited evidence and do not overstate source facts."""

    def verify(
        self,
        request: CaseRequest,
        dossier_text: str,
        bundle: EvidenceBundle,
        risk_matrix: OversightRiskMatrix,
    ) -> CitationVerificationResult:
        checks: list[CitationCheck] = []
        label_to_item = {f"E{index:02d}": item for index, item in enumerate(bundle.items, start=1)}
        item_ids = {item.item_id for item in bundle.items}
        referenced = sorted(set(EVIDENCE_REF_RE.findall(dossier_text)))

        for ref in referenced:
            if ref not in label_to_item:
                checks.append(self._check(request, "evidence_ref_resolution", "ERROR", f"{ref} is cited but absent from the evidence bundle.", [ref]))
        for label, item in label_to_item.items():
            if not item.source_uri or not item.provenance.checksum:
                checks.append(self._check(request, "evidence_traceability", "ERROR", f"{label} lacks source URI or checksum.", [label], [item.record_id]))

        for indicator in risk_matrix.indicators:
            if indicator.risk_level in {"High", "Medium"} and not (set(indicator.evidence_ids) & item_ids or indicator.record_ids or indicator.source_uris):
                checks.append(
                    self._check(
                        request,
                        "indicator_support",
                        "ERROR",
                        f"{indicator.entity or 'case'} / {indicator.risk_area} has no evidence IDs, record IDs, or source URIs.",
                        record_ids=indicator.record_ids,
                    )
                )

        checked_claim_count = 0
        for line_number, line in enumerate(dossier_text.splitlines(), start=1):
            text = line.strip()
            if not text or text.startswith("|") or text.startswith("#"):
                continue
            claim_like = (
                "CalDS flags" in text
                or "Bottom line:" in text
                or "Evidence:" in text
                or LEGAL_STATUS_TERMS.search(text)
                or MONEY_OR_DATE_RE.search(text)
            )
            if not claim_like:
                continue
            checked_claim_count += 1
            refs = EVIDENCE_REF_RE.findall(text)
            has_source_pointer = "Source:" in text or "Evidence:" in text or "evidence " in text.lower()
            if (MONEY_OR_DATE_RE.search(text) or LEGAL_STATUS_TERMS.search(text) or "CalDS flags" in text) and not refs and not has_source_pointer:
                checks.append(
                    self._check(
                        request,
                        "claim_citation",
                        "WARNING",
                        f"Line {line_number} contains a substantive claim without an inline evidence/source pointer.",
                    )
                )
            if re.search(r"\bcaus(?:e|ed|es|ing)\b", text, re.IGNORECASE) and re.search(r"\b(county|continuum of care|provider-attributable)\b", text, re.IGNORECASE):
                checks.append(
                    self._check(
                        request,
                        "provider_attribution",
                        "ERROR",
                        f"Line {line_number} risks treating geography-level outcome context as provider causation.",
                        refs,
                    )
                )
            if (
                LEGAL_STATUS_TERMS.search(text)
                and "Weingart" in text
                and "Taylor" not in text
                and "not Weingart" not in text
                and "whether any official source names" not in text
                and "or only as transaction" not in text
            ):
                checks.append(
                    self._check(
                        request,
                        "named_party_legal_status",
                        "ERROR",
                        f"Line {line_number} mentions Weingart with legal-status language without preserving the named-party distinction.",
                        refs,
                    )
                )

        errors = [check for check in checks if check.status == "ERROR"]
        warnings = [check for check in checks if check.status == "WARNING"]
        status = "PASS" if not errors else "FAIL"
        if not errors and warnings:
            status = "PASS_WITH_WARNINGS"
        return CitationVerificationResult(
            verification_id=stable_id("citation_verification", request.case_id, status, str(len(checks))),
            case_id=request.case_id,
            status=status,
            checked_claim_count=checked_claim_count,
            error_count=len(errors),
            warning_count=len(warnings),
            checks=checks,
        )

    def _check(
        self,
        request: CaseRequest,
        check_type: str,
        status: str,
        message: str,
        evidence_refs: list[str] | None = None,
        record_ids: list[str] | None = None,
    ) -> CitationCheck:
        return CitationCheck(
            check_id=stable_id("citation_check", request.case_id, check_type, status, message),
            case_id=request.case_id,
            check_type=check_type,
            status=status,
            message=message,
            evidence_refs=evidence_refs or [],
            record_ids=record_ids or [],
        )


class LinkIntegrityService:
    """Public-link verification gate for source citations."""

    def check_source_ledger(self, source_ledger: list[dict[str, object]], timeout: int = 12) -> LinkIntegrityReport:
        urls: list[str] = []
        warnings = 0
        for entry in source_ledger:
            entry_urls = [str(url) for url in entry.get("source_urls", [])]
            if not entry_urls and not entry.get("link_note"):
                warnings += 1
            urls.extend(entry_urls)
        unique_urls = self._dedupe(urls)
        checks = [self._check_url(url, timeout) for url in unique_urls]
        errors = [check for check in checks if check.status == "ERROR"]
        status = "PASS" if not errors else "FAIL"
        if not errors and warnings:
            status = "PASS_WITH_WARNINGS"
        return LinkIntegrityReport(
            report_id=stable_id("link_integrity", str(len(unique_urls)), status),
            status=status,
            checked_url_count=len(unique_urls),
            error_count=len(errors),
            warning_count=warnings,
            checks=checks,
        )

    def _check_url(self, url: str, timeout: int) -> SourceLinkCheck:
        headers = {"User-Agent": "CalDS link integrity checker/1.0"}
        request = urllib.request.Request(url, headers=headers, method="GET")
        context = ssl.create_default_context()
        try:
            with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
                status = int(getattr(response, "status", response.getcode()))
                final_url = response.geturl()
                content_type = response.headers.get("content-type", "")
                response.read(2048)
            check_status = "PASS" if 200 <= status < 400 else "ERROR"
            error = "" if check_status == "PASS" else f"HTTP {status}"
            return SourceLinkCheck(
                check_id=stable_id("link_check", url, str(status), final_url),
                url=url,
                status=check_status,
                http_status=status,
                final_url=final_url,
                content_type=content_type,
                error=error,
            )
        except Exception as exc:
            return SourceLinkCheck(
                check_id=stable_id("link_check", url, "error", str(exc)),
                url=url,
                status="ERROR",
                http_status=None,
                final_url="",
                content_type="",
                error=str(exc),
            )

    def _dedupe(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            if value and value not in seen:
                seen.add(value)
                result.append(value)
        return result
