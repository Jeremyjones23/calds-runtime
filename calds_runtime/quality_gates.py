from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
import ssl
import time
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
    RunReadinessResult,
    SourceLinkCheck,
    read_json,
    stable_id,
    write_json,
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
        "San Francisco HSH nonprofit spending and completed-payment rows",
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
OPINION_CLAIM_PREFIXES = (
    "Briefing judgment:",
    "Reviewer readout:",
    "Why this matters:",
    "System opinion:",
    "What this flags:",
    "What CalDS found:",
    "How this triggered review:",
    "Why CalDS flagged it:",
    "Recommended human next step:",
)
SAFETY_CAVEAT_RE = re.compile(
    r"\b(does not prove|does not mean|not a formal finding|not a formal conclusion|not a finding|"
    r"not charged or liable|not legal clearance|not provider attribution|source access required|"
    r"human review required|pending explicit human review)\b",
    re.IGNORECASE,
)


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
                candidates = [
                    record
                    for record in records
                    if self._record_mentions_entity(record, entity) and self.source_family(record) == family
                ]
                no_public_record = [record for record in candidates if self._is_official_no_public_record(record)]
                matched = [record for record in candidates if not self._is_source_gap_record(record) and not self._is_official_no_public_record(record)]
                query = self._query_for(entity, family)
                status = "hit" if matched else "searched_no_public_official_record" if no_public_record else "miss"
                attempted_sources = list(SOURCE_FAMILY_TARGETS.get(family, [family]))
                attempted_sources.extend(self._dedupe(record.source_uri for record in candidates if self._is_source_gap_record(record) or self._is_official_no_public_record(record)))
                if matched:
                    blocker = ""
                elif no_public_record:
                    blocker = (
                        f"Configured public official {family} searches completed for {entity} with no public adverse record recovered; "
                        "this remains unresolved source access, not legal clearance. Manual PACER, local court, and records-request work may still be required."
                    )
                elif candidates:
                    blocker = (
                        f"Only discovery/source-gap {family} records were recovered for {entity}; "
                        "no citation-ready source record is available in the current corpus."
                    )
                else:
                    blocker = f"No citation-ready {family} record was recovered for {entity} in the current corpus."
                runs.append(
                    AcquisitionSearchRun(
                        search_id=stable_id("acquisition", request.case_id, entity, family),
                        case_id=request.case_id,
                        entity=entity,
                        source_family=family,
                        query=query,
                        attempted_sources=attempted_sources,
                        matched_record_ids=sorted({record.record_id for record in matched or no_public_record}),
                        source_uris=self._dedupe(record.source_uri for record in matched or no_public_record),
                        status=status,
                        confidence="High" if matched else "PublicNoRecord" if no_public_record else "Blocked",
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
        acceptable_statuses = {"hit", "searched_no_public_official_record"}
        for entity in entities:
            for family in families:
                run = by_key.get((entity, family))
                if run is None or run.status not in acceptable_statuses:
                    missing_required.append(f"{entity}: {family}")
        counts = Counter(run.status for run in ledger)
        status = "PASS" if not missing_required else "PASS_WITH_BLOCKERS"
        if not ledger or not entities:
            status = "FAIL"
        notes = [
            "Completion guard records hits, public official no-record searches, and misses; anything short of a citation-ready hit remains a source-access blocker, not clearance.",
            "A completed public official no-record search means configured public official sources were searched without recovering a public adverse record; it is not legal clearance and still leaves manual PACER, local court, records-request, or credentialed-source work unresolved.",
            "Dossier compilation may proceed as a review packet only because unresolved source-access blockers are preserved for human review.",
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
        if record.source_type in {
            "state_homelessness_award",
            "source_extraction_state_homeless_award_table",
            "sf_hsh_payment_exposure",
            "source_extraction_sf_hsh_payment_table",
        } or "homekey" in value or "state_homeless" in value or "sf_hsh_payment" in value:
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

    def _is_source_gap_record(self, record: CanonicalRecord) -> bool:
        signals = dict(record.attributes.get("signals", {}))
        return bool(
            signals.get("discovery_only_source_gap")
            or signals.get("not_citation_ready")
            or signals.get("source_gap_only")
            or str(record.source_type).endswith("_discovery")
            or "discovery_gap" in str(record.source_type).lower()
        )

    def _is_official_no_public_record(self, record: CanonicalRecord) -> bool:
        signals = dict(record.attributes.get("signals", {}))
        return bool(
            signals.get("official_source_search_completed_no_hit")
            or signals.get("searched_no_public_official_record")
            or record.source_type == "enforcement_docket_official_no_record_search"
        )

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


class RunReadinessService:
    """Compare a new case run against a baseline before treating it as deeper evidence work."""

    def compare(
        self,
        current_run_dir: Path,
        baseline_run_dir: Path,
        output_file: Path | None = None,
    ) -> RunReadinessResult:
        current = self.collect_metrics(Path(current_run_dir))
        baseline = self.collect_metrics(Path(baseline_run_dir))
        material_changes = self._material_changes(current, baseline)
        blockers = self._blockers(current)
        if blockers:
            status = "NEEDS_REPAIR"
            recommendation = "Do not publish or rely on this rerun until the blockers are resolved."
        elif material_changes:
            status = "MATERIAL_CHANGE_READY"
            recommendation = "This rerun appears materially deeper than the baseline and is ready for reviewer comparison."
        else:
            status = "NO_MATERIAL_CHANGE"
            recommendation = "This rerun does not materially improve source depth over the baseline."
        case_id = str(current.get("case_id") or baseline.get("case_id") or "unknown_case")
        result = RunReadinessResult(
            readiness_id=stable_id("run_readiness", case_id, str(current_run_dir), str(baseline_run_dir), status),
            case_id=case_id,
            status=status,
            current_run_dir=str(current_run_dir),
            baseline_run_dir=str(baseline_run_dir),
            current_metrics=current,
            baseline_metrics=baseline,
            material_changes=material_changes,
            blockers=blockers,
            recommendation=recommendation,
        )
        if output_file:
            write_json(Path(output_file), result)
        return result

    def collect_metrics(self, run_dir: Path) -> dict[str, object]:
        artifacts_dir = run_dir / "artifacts"
        state = self._load_json(run_dir / "workflow_state.json")
        bundle = self._load_json(artifacts_dir / "evidence_bundle.json")
        risk = self._load_json(artifacts_dir / "oversight_risk_matrix.json")
        guard = self._load_json(artifacts_dir / "completion_guard.json")
        acquisition = self._load_json(artifacts_dir / "acquisition_ledger.json")
        citation = self._load_json(artifacts_dir / "citation_verification.json")
        forensic_plan = self._load_json(artifacts_dir / "forensic_investigation_plan.json")
        manifest = self._load_json(run_dir / "public_site" / "publication_manifest.json")

        items = list(bundle.get("items") or [])
        indicators = list(risk.get("indicators") or [])
        searches = list(acquisition.get("searches") or [])
        source_types = Counter(str(item.get("source_type") or "") for item in items if item.get("source_type"))
        high_rows = [row for row in indicators if row.get("risk_level") == "High"]
        medium_rows = [row for row in indicators if row.get("risk_level") == "Medium"]
        data_gap_rows = [row for row in indicators if row.get("data_status") == "Data gap"]
        acquisition_hits = [row for row in searches if row.get("status") == "hit"]
        return {
            "run_dir": str(run_dir),
            "case_id": state.get("case_id") or bundle.get("case_id") or risk.get("case_id"),
            "workflow_status": state.get("status"),
            "evidence_count": len(items),
            "source_type_counts": dict(sorted(source_types.items())),
            "source_type_count": len(source_types),
            "risk_indicator_count": len(indicators),
            "high_risk_count": len(high_rows),
            "medium_risk_count": len(medium_rows),
            "data_gap_count": len(data_gap_rows),
            "completion_guard_status": guard.get("status"),
            "completion_guard_hit_count": int(guard.get("hit_count") or 0),
            "completion_guard_blocker_count": int(guard.get("blocker_count") or 0),
            "completion_guard_missing_required": list(guard.get("missing_required") or []),
            "acquisition_hit_count": len(acquisition_hits),
            "selected_entities": list(forensic_plan.get("selected_entities") or []),
            "citation_status": citation.get("status"),
            "citation_error_count": int(citation.get("error_count") or 0),
            "citation_warning_count": int(citation.get("warning_count") or 0),
            "publication_safety_passed": manifest.get("passed"),
            "publication_manifest_present": bool(manifest),
        }

    def _load_json(self, path: Path) -> dict[str, object]:
        if not path.exists():
            return {}
        try:
            return read_json(path)
        except Exception as exc:
            return {"load_error": repr(exc), "path": str(path)}

    def _material_changes(self, current: dict[str, object], baseline: dict[str, object]) -> list[str]:
        changes: list[str] = []
        numeric_fields = [
            ("evidence_count", "evidence item count"),
            ("source_type_count", "source-type diversity"),
            ("risk_indicator_count", "risk indicator count"),
            ("high_risk_count", "high-risk review item count"),
            ("completion_guard_hit_count", "completion-guard hit count"),
        ]
        for field, label in numeric_fields:
            current_value = int(current.get(field) or 0)
            baseline_value = int(baseline.get(field) or 0)
            if current_value > baseline_value:
                changes.append(f"{label} increased from {baseline_value} to {current_value}.")

        current_blockers = int(current.get("completion_guard_blocker_count") or 0)
        baseline_blockers = int(baseline.get("completion_guard_blocker_count") or 0)
        if baseline_blockers and current_blockers < baseline_blockers:
            changes.append(f"Completion-guard blockers decreased from {baseline_blockers} to {current_blockers}.")

        current_types = set((current.get("source_type_counts") or {}).keys())
        baseline_types = set((baseline.get("source_type_counts") or {}).keys())
        new_types = sorted(current_types - baseline_types)
        if new_types:
            changes.append(f"New evidence source types appeared: {', '.join(new_types)}.")

        current_entities = set(current.get("selected_entities") or [])
        baseline_entities = set(baseline.get("selected_entities") or [])
        if current_entities != baseline_entities:
            changes.append(
                "Deep-dive entity selection changed: "
                f"added {sorted(current_entities - baseline_entities)}, removed {sorted(baseline_entities - current_entities)}."
            )
        current_warnings = int(current.get("citation_warning_count") or 0)
        baseline_warnings = int(baseline.get("citation_warning_count") or 0)
        if baseline_warnings and current_warnings < baseline_warnings:
            changes.append(f"Citation warnings decreased from {baseline_warnings} to {current_warnings}.")
        if baseline.get("citation_status") != "PASS" and current.get("citation_status") == "PASS":
            changes.append(f"Citation status improved from {baseline.get('citation_status')} to PASS.")
        return changes

    def _blockers(self, current: dict[str, object]) -> list[str]:
        blockers: list[str] = []
        if current.get("workflow_status") != "AWAITING_HUMAN_REVIEW":
            blockers.append(f"Workflow status is {current.get('workflow_status')}; expected AWAITING_HUMAN_REVIEW.")
        if current.get("citation_status") not in {"PASS", None} or int(current.get("citation_error_count") or 0) > 0:
            blockers.append(f"Citation verifier is not clean: {current.get('citation_status')}.")
        if current.get("publication_manifest_present") and current.get("publication_safety_passed") is False:
            blockers.append("Publication safety manifest did not pass.")
        if int(current.get("completion_guard_blocker_count") or 0) > 0:
            blockers.append(f"Completion guard still has {current.get('completion_guard_blocker_count')} source-access blocker(s).")
        if int(current.get("evidence_count") or 0) == 0:
            blockers.append("No evidence bundle items were produced.")
        return blockers


class CitationVerifierService:
    """Checks that dossier claims remain tied to cited evidence and do not overstate source facts."""

    def verify(
        self,
        request: CaseRequest,
        dossier_text: str,
        bundle: EvidenceBundle,
        risk_matrix: OversightRiskMatrix,
        max_warning_count: int = 0,
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
            if text.startswith("- Test:") or text.startswith("Test:") or text.startswith("- Objective:"):
                continue
            if text in OPINION_CLAIM_PREFIXES:
                continue
            claim_like = (
                text.startswith(OPINION_CLAIM_PREFIXES)
                or "CalDS flags" in text
                or "Bottom line:" in text
                or "Evidence:" in text
                or LEGAL_STATUS_TERMS.search(text)
                or MONEY_OR_DATE_RE.search(text)
            )
            if not claim_like:
                continue
            checked_claim_count += 1
            if SAFETY_CAVEAT_RE.search(text):
                continue
            refs = EVIDENCE_REF_RE.findall(text)
            has_source_pointer = "Source:" in text or "Source URI" in text or "Evidence:" in text or "evidence " in text.lower()
            if (
                MONEY_OR_DATE_RE.search(text)
                or LEGAL_STATUS_TERMS.search(text)
                or "CalDS flags" in text
                or text.startswith(OPINION_CLAIM_PREFIXES)
            ) and not refs and not has_source_pointer:
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
        if not errors and len(warnings) > max_warning_count:
            status = "REPAIR_REQUIRED"
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
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CalDS-link-integrity-checker/1.0",
            "Accept": "text/html,application/xhtml+xml,application/pdf,application/json,text/csv,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        context = ssl.create_default_context()
        last_error = ""
        for attempt in range(3):
            request = urllib.request.Request(url, headers=headers, method="GET")
            try:
                with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
                    status = int(getattr(response, "status", response.getcode()))
                    final_url = response.geturl()
                    content_type = response.headers.get("content-type", "")
                    response.read(2048)
                check_status = "PASS" if 200 <= status < 400 else "ERROR"
                error = "" if check_status == "PASS" else f"HTTP {status}"
                if check_status == "ERROR" and status in {403, 408, 429, 500, 502, 503, 504} and attempt < 2:
                    time.sleep(0.75 * (attempt + 1))
                    continue
                return SourceLinkCheck(
                    check_id=stable_id("link_check", url, str(status), final_url),
                    url=url,
                    status=check_status,
                    http_status=status,
                    final_url=final_url,
                    content_type=content_type,
                    error=error,
                )
            except urllib.error.HTTPError as exc:
                last_error = f"HTTP Error {exc.code}: {exc.reason}"
                if exc.code in {403, 408, 429, 500, 502, 503, 504} and attempt < 2:
                    time.sleep(0.75 * (attempt + 1))
                    continue
                return SourceLinkCheck(
                    check_id=stable_id("link_check", url, "error", last_error),
                    url=url,
                    status="ERROR",
                    http_status=None,
                    final_url="",
                    content_type="",
                    error=last_error,
                )
            except Exception as exc:
                last_error = str(exc)
                if attempt < 2:
                    time.sleep(0.75 * (attempt + 1))
                    continue
                return SourceLinkCheck(
                    check_id=stable_id("link_check", url, "error", last_error),
                    url=url,
                    status="ERROR",
                    http_status=None,
                    final_url="",
                    content_type="",
                    error=last_error,
                )
        return SourceLinkCheck(
            check_id=stable_id("link_check", url, "error", last_error),
            url=url,
            status="ERROR",
            http_status=None,
            final_url="",
            content_type="",
            error=last_error,
        )

    def _dedupe(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            if value and value not in seen:
                seen.add(value)
                result.append(value)
        return result
