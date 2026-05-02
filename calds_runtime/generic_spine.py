from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import re
from typing import Iterable

from .contracts import (
    CanonicalRecord,
    CaseRequest,
    CitationVerificationResult,
    EntityResolutionAlias,
    EntityResolutionResult,
    EvidenceBundle,
    EvidenceStoreEntry,
    EvidenceStoreManifest,
    ForensicTestDefinition,
    ForensicTestResult,
    HumanActionItem,
    HumanActionPlan,
    InvestigationProfile,
    OversightRiskMatrix,
    ProfileGateAuditResult,
    ReviewValueScore,
    SourceAcquisitionPlan,
    SourceAcquisitionRequirement,
    SourceConnectorSpec,
    TargetCandidate,
    TargetUniverse,
    TriageFinding,
    stable_id,
)
from .investigation_profiles import DEFAULT_DEEP_SOURCE_FAMILIES, DEFAULT_SOURCE_FAMILIES, ReviewValueScoringService
from .quality_gates import CompletionGuardService
from .truth import tokenize


REQUIRED_PROFILE_GATES = [
    "profile",
    "entity_resolution",
    "target_discovery",
    "source",
    "handoff",
    "forensic_tests",
    "evidence_store",
    "citation",
    "link",
    "hallucination",
    "sentinel",
    "presentation",
    "human_action",
    "human_review",
]


class ProfileGateService:
    """Audits whether a profile can drive repeatable investigations across the full spine."""

    def audit(self, profile: InvestigationProfile) -> ProfileGateAuditResult:
        gates = list(profile.completion_gates)
        missing = [gate for gate in REQUIRED_PROFILE_GATES if gate not in gates]
        source_families = list(profile.required_source_families or DEFAULT_SOURCE_FAMILIES)
        deep_families = list(profile.deep_source_families or DEFAULT_DEEP_SOURCE_FAMILIES)
        notes = [
            "Profile gate audit is deterministic configuration review; it does not retrieve evidence.",
            "Deep source families may remain blocked by public-record availability, credentials, or manual records requests.",
        ]
        if not source_families:
            missing.append("required_source_families")
        if not deep_families:
            missing.append("deep_source_families")
        return ProfileGateAuditResult(
            audit_id=stable_id("profile_gate", profile.profile_id, ",".join(gates), ",".join(missing)),
            profile_id=profile.profile_id,
            status="PASS" if not missing else "REPAIR_REQUIRED",
            checked_gates=gates,
            missing_gates=missing,
            required_source_families=source_families,
            deep_source_families=deep_families,
            notes=notes,
        )


class EntityResolutionService:
    """Resolves aliases and old names without making the LLM the source of truth."""

    def resolve(
        self,
        request: CaseRequest,
        profile: InvestigationProfile,
        records: Iterable[CanonicalRecord],
    ) -> EntityResolutionResult:
        canonical = list(dict.fromkeys(request.entities))
        aliases: list[EntityResolutionAlias] = []
        records_by_norm_entity: dict[str, list[CanonicalRecord]] = defaultdict(list)
        for record in records:
            for entity in record.entities:
                records_by_norm_entity[self._norm(entity)].append(record)

        for entity in canonical:
            configured_aliases = list(profile.entity_aliases.get(entity, []))
            for alias in configured_aliases:
                aliases.append(
                    EntityResolutionAlias(
                        alias=alias,
                        canonical_entity=entity,
                        basis="profile configured alias",
                        confidence="High",
                        source_record_ids=[],
                    )
                )
            entity_norm = self._norm(entity)
            for record in records:
                record_aliases = []
                attrs = dict(record.attributes)
                for key in ("aliases", "former_names", "known_as", "dba_names"):
                    value = attrs.get(key)
                    if isinstance(value, list):
                        record_aliases.extend(str(item) for item in value)
                    elif isinstance(value, str):
                        record_aliases.extend(part.strip() for part in value.split(";") if part.strip())
                for candidate in record.entities:
                    if self._norm(candidate) != entity_norm and self._soft_match(entity, candidate):
                        record_aliases.append(candidate)
                for alias in sorted(set(record_aliases)):
                    if self._norm(alias) == entity_norm:
                        continue
                    aliases.append(
                        EntityResolutionAlias(
                            alias=alias,
                            canonical_entity=entity,
                            basis=f"record metadata or entity list from {record.source_type}",
                            confidence="Medium",
                            source_record_ids=[record.record_id],
                        )
                    )

        unresolved = [
            entity
            for entity in canonical
            if self._norm(entity) not in records_by_norm_entity
            and not any(self._norm(alias.alias) in records_by_norm_entity for alias in aliases if alias.canonical_entity == entity)
        ]
        notes = [
            "Entity resolution emits aliases and unresolved names; it does not merge canonical records.",
            "Connected-person and fiscal-sponsor relationships require cited source records before they can affect scoring.",
        ]
        return EntityResolutionResult(
            result_id=stable_id("entity_resolution", request.case_id, ",".join(canonical), str(len(aliases))),
            case_id=request.case_id,
            canonical_entities=canonical,
            aliases=self._dedupe_aliases(aliases),
            unresolved_entities=unresolved,
            notes=notes,
        )

    def _soft_match(self, left: str, right: str) -> bool:
        left_tokens = set(tokenize(left)) - {"inc", "the", "of", "and", "services", "service"}
        right_tokens = set(tokenize(right)) - {"inc", "the", "of", "and", "services", "service"}
        return bool(left_tokens and right_tokens and len(left_tokens & right_tokens) >= min(2, len(left_tokens), len(right_tokens)))

    def _dedupe_aliases(self, aliases: list[EntityResolutionAlias]) -> list[EntityResolutionAlias]:
        seen: set[tuple[str, str]] = set()
        output: list[EntityResolutionAlias] = []
        for alias in aliases:
            key = (self._norm(alias.alias), self._norm(alias.canonical_entity))
            if key in seen:
                continue
            seen.add(key)
            output.append(alias)
        return output

    def _norm(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


class TargetDiscoveryService:
    """Builds the repeatable candidate universe before deep-dive pruning."""

    def __init__(self) -> None:
        self.review_value = ReviewValueScoringService()

    def discover(
        self,
        request: CaseRequest,
        profile: InvestigationProfile,
        records: Iterable[CanonicalRecord],
        triage_findings: dict[str, list[TriageFinding]] | None = None,
    ) -> TargetUniverse:
        record_list = list(records)
        candidate_entities = list(dict.fromkeys([*request.entities, *self._source_discovered_entities(record_list)]))
        candidates: list[TargetCandidate] = []
        for entity in candidate_entities:
            entity_records = self._records_for_entity(entity, record_list)
            findings = list((triage_findings or {}).get(entity, []))
            source_families = {CompletionGuardService().source_family(record) for record in entity_records}
            missing = [family for family in profile.required_source_families if family not in source_families]
            score = self.review_value.score_entity(request, profile, entity, entity_records, findings, missing)
            candidates.append(
                TargetCandidate(
                    candidate_id=stable_id("target", request.case_id, entity, str(score.final_score)),
                    case_id=request.case_id,
                    entity=entity,
                    review_value_score=score,
                    selection_sources=self._selection_sources(score),
                    rationale=score.rationale,
                    source_record_ids=score.source_record_ids,
                    source_uris=score.source_uris,
                )
            )
        ordered = sorted(candidates, key=lambda item: item.review_value_score.final_score, reverse=True)
        selected = [
            candidate.entity
            for candidate in ordered
            if candidate.review_value_score.final_score >= profile.deep_dive_threshold
        ][: profile.max_targets]
        if not selected:
            selected = [candidate.entity for candidate in ordered[: min(profile.max_targets, len(ordered))]]
        return TargetUniverse(
            universe_id=stable_id("target_universe", request.case_id, profile.profile_id, str(len(ordered))),
            case_id=request.case_id,
            profile_id=profile.profile_id,
            candidates=ordered,
            selected_entities=selected,
            discovery_notes=[
                "Target universe uses Review Value Score, not money alone.",
                "Official adverse records, source opacity, scope mismatch, and verifiability can elevate lower-dollar entities.",
            ],
        )

    def _source_discovered_entities(self, records: list[CanonicalRecord]) -> list[str]:
        counts = Counter(entity for record in records for entity in record.entities if entity)
        return [entity for entity, count in counts.items() if count >= 2]

    def _records_for_entity(self, entity: str, records: list[CanonicalRecord]) -> list[CanonicalRecord]:
        wanted = self._norm(entity)
        return [record for record in records if any(self._norm(value) == wanted for value in record.entities)]

    def _selection_sources(self, score: ReviewValueScore) -> list[str]:
        components = [
            key.replace("_", " ")
            for key, value in score.component_scores.items()
            if value >= 50
        ]
        return components or ["low-signal named target"]

    def _norm(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


class SourceAcquisitionPlannerService:
    """Plans deep source acquisition and records exact blockers before any dossier claims."""

    DEFAULT_CONNECTORS = [
        SourceConnectorSpec("irs_raw_xml", "raw_irs_990", "Internal Revenue Service raw XML and return image", "public_http", ["raw XML", "return image or rendered filing"], ["https://apps.irs.gov/"]),
        SourceConnectorSpec("propublica_nonprofit_api", "raw_irs_990", "ProPublica Nonprofit Explorer API", "public_http", ["organization filing summary"], ["https://projects.propublica.org/nonprofits/api"]),
        SourceConnectorSpec("fac_general_api", "audit_pdf", "Federal Audit Clearinghouse general data and audit package", "public_http", ["audit PDF", "finding rows", "federal award rows"], ["https://fac.gov/"]),
        SourceConnectorSpec("county_contract_portal", "county_contracts", "County contract, amendment, monitoring, and corrective-action portal", "public_or_records_request", ["contract", "amendment", "monitoring letter", "corrective action"], []),
        SourceConnectorSpec("payment_ledger", "payment_ledger", "State, county, or city payment ledger", "public_or_records_request", ["payment rows", "invoice or draw ledger"], []),
        SourceConnectorSpec("court_docket", "litigation_docket", "Court and docket systems", "credentialed_or_manual", ["case docket", "complaint", "settlement", "charging document"], [], True, "Court systems may require credentials, fees, or manual search."),
        SourceConnectorSpec("board_files", "board_files", "Board agenda, committee, and procurement files", "public_http", ["agenda item", "staff report", "resolution", "contract approval"], []),
        SourceConnectorSpec("agency_adverse_action", "enforcement_adverse", "Official enforcement, adverse-action, debarment, and inspector-general sources", "public_http", ["official action", "status", "named parties"], []),
        SourceConnectorSpec("web_archive", "web_social_archive", "Organization website and social/web statement snapshots", "public_http", ["current page", "archived snapshot", "statement excerpt"], []),
        SourceConnectorSpec("provider_outcomes", "provider_outcomes", "Provider-attributable outcomes, deliverables, capacity, and completion records", "public_or_records_request", ["outcome report", "deliverable report", "capacity history"], []),
    ]

    def build_plan(
        self,
        request: CaseRequest,
        profile: InvestigationProfile,
        records: Iterable[CanonicalRecord],
        entities: list[str],
    ) -> SourceAcquisitionPlan:
        record_list = list(records)
        connector_specs = self._connector_specs(profile)
        families = list(profile.deep_source_families or DEFAULT_DEEP_SOURCE_FAMILIES)
        requirements: list[SourceAcquisitionRequirement] = []
        for entity in entities:
            for family in families:
                connectors = [spec for spec in connector_specs if spec.source_family == family]
                matched = [record for record in record_list if self._record_matches(record, entity, family)]
                if matched:
                    status = "satisfied"
                    blocker = ""
                    retryable = False
                elif any(spec.credentials_required for spec in connectors):
                    status = "blocked_external"
                    blocker = "; ".join(spec.manual_access_reason for spec in connectors if spec.manual_access_reason) or "Connector requires credentialed or manual access."
                    retryable = False
                elif connectors:
                    status = "needs_ingestor_or_records_request"
                    blocker = "No current corpus record satisfies this deep source family; add connector/parser coverage or perform records request."
                    retryable = True
                else:
                    status = "needs_connector_profile"
                    blocker = "Profile does not define a connector for this source family."
                    retryable = True
                requirements.append(
                    SourceAcquisitionRequirement(
                        requirement_id=stable_id("source_req", request.case_id, entity, family),
                        case_id=request.case_id,
                        entity=entity,
                        source_family=family,
                        connector_ids=[spec.connector_id for spec in connectors],
                        required_artifacts=self._required_artifacts(connectors, family),
                        status=status,
                        matched_record_ids=[record.record_id for record in matched],
                        source_uris=self._dedupe(record.source_uri for record in matched),
                        blocker_reason=blocker,
                        retryable=retryable,
                    )
                )
        counts = Counter(req.status for req in requirements)
        return SourceAcquisitionPlan(
            plan_id=stable_id("source_plan", request.case_id, profile.profile_id, str(len(requirements))),
            case_id=request.case_id,
            profile_id=profile.profile_id,
            requirements=requirements,
            connector_specs=connector_specs,
            satisfied_count=counts.get("satisfied", 0),
            blocked_count=counts.get("blocked_external", 0),
            needs_ingestor_count=counts.get("needs_ingestor_or_records_request", 0) + counts.get("needs_connector_profile", 0),
        )

    def _connector_specs(self, profile: InvestigationProfile) -> list[SourceConnectorSpec]:
        specs = list(self.DEFAULT_CONNECTORS)
        for item in profile.source_connectors:
            specs.append(
                SourceConnectorSpec(
                    connector_id=str(item.get("connector_id") or stable_id("connector", str(item))),
                    source_family=str(item.get("source_family") or ""),
                    name=str(item.get("name") or item.get("connector_id") or "profile connector"),
                    access_mode=str(item.get("access_mode") or "public_http"),
                    required_artifacts=list(item.get("required_artifacts") or []),
                    source_uris=list(item.get("source_uris") or []),
                    credentials_required=bool(item.get("credentials_required") or False),
                    manual_access_reason=str(item.get("manual_access_reason") or ""),
                    parser_version=str(item.get("parser_version") or "profile-v1"),
                )
            )
        return specs

    def _record_matches(self, record: CanonicalRecord, entity: str, family: str) -> bool:
        if not any(self._norm(value) == self._norm(entity) for value in record.entities):
            return False
        value = f"{record.source_type} {record.record_id} {record.title}".lower()
        if family == "raw_irs_990":
            return "irs_990_raw" in value or "irs_990" in value
        if family == "audit_pdf":
            return "fac" in value or "audit" in value
        if family == "county_contracts":
            return "contract" in value or "monitoring" in value or "corrective" in value
        if family == "payment_ledger":
            return "payment" in value or "ledger" in value or "award" in value
        if family == "litigation_docket":
            return "docket" in value or "court" in value or "litigation" in value
        if family == "board_files":
            return "board" in value or "agenda" in value or "resolution" in value
        if family == "enforcement_adverse":
            return "enforcement" in value or "violation" in value or "adverse" in value or "debar" in value
        if family == "web_social_archive":
            return record.source_type in {"org_service_page", "public_statement_source", "social_media_source"}
        if family == "provider_outcomes":
            return "outcome" in value or "deliverable" in value or "capacity" in value
        return family in value

    def _required_artifacts(self, connectors: list[SourceConnectorSpec], family: str) -> list[str]:
        artifacts = self._dedupe(artifact for spec in connectors for artifact in spec.required_artifacts)
        return artifacts or [family.replace("_", " ")]

    def _norm(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

    def _dedupe(self, values: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for value in values:
            if value and value not in seen:
                seen.add(value)
                output.append(value)
        return output


class ForensicTestService:
    """Runs deterministic forensic test readiness checks for selected entities."""

    DEFAULT_TESTS = [
        ForensicTestDefinition("money_to_scope", "money trail", "Do payments, grants, or awards map to contract scope and allowable use?", ["payment_ledger", "county_contracts"], "money without scope", "Trace contract, payment, invoice, and deliverable records."),
        ForensicTestDefinition("compensation_governance", "tax and compensation", "Do Form 990 compensation and payroll trends create governance review questions?", ["raw_irs_990"], "compensation without governance file", "Verify raw return, board approval, comparability, and payroll schedule."),
        ForensicTestDefinition("related_party_vendor", "related party and contractors", "Do related-party or contractor records require follow-up?", ["raw_irs_990", "county_contracts"], "vendor relationship not parsed", "Pull Schedule L, contractor schedules, procurement records, and conflict disclosures."),
        ForensicTestDefinition("audit_corrective_action", "audit controls", "Do audit findings, material weaknesses, or not-low-risk status have documented correction?", ["audit_pdf"], "audit issue without corrective-action status", "Open audit report and corrective-action plan."),
        ForensicTestDefinition("spend_vs_results", "spend versus results", "Did public-dollar exposure rise while geography or provider outcomes moved the wrong direction?", ["provider_outcomes", "payment_ledger"], "geography context without provider attribution", "Pull provider-attributable outcomes for the same contract window."),
        ForensicTestDefinition("legal_status", "enforcement and docket", "Do official adverse records name the entity, a connected party, or a project counterparty?", ["enforcement_adverse", "litigation_docket"], "legal status overstatement risk", "Verify named parties, status, docket, and relationship."),
        ForensicTestDefinition("off_scope_activity", "scope mismatch", "Do public statements suggest activity outside funded scope and is there a funding nexus?", ["web_social_archive", "county_contracts"], "keyword without funding nexus", "Compare web/public statements to contract scope and cost allocation."),
    ]

    def run_tests(
        self,
        request: CaseRequest,
        profile: InvestigationProfile,
        records: Iterable[CanonicalRecord],
        selected_entities: list[str],
        source_plan: SourceAcquisitionPlan,
    ) -> list[ForensicTestResult]:
        tests = self._test_definitions(profile)
        requirements = {
            (req.entity, req.source_family): req
            for req in source_plan.requirements
        }
        record_list = list(records)
        results: list[ForensicTestResult] = []
        for entity in selected_entities:
            entity_records = [record for record in record_list if any(self._norm(value) == self._norm(entity) for value in record.entities)]
            for test in tests:
                missing = [
                    family
                    for family in test.required_source_families
                    if requirements.get((entity, family)) is None or requirements[(entity, family)].status != "satisfied"
                ]
                if missing:
                    status = "BLOCKED_BY_SOURCE_GAP"
                    finding = f"{test.question} The run cannot complete this test because {', '.join(missing)} is unresolved."
                    blockers = missing
                else:
                    status = "READY_FOR_HUMAN_REVIEW"
                    finding = f"{test.question} Required source families are present; reviewer should inspect the cited records for the test question."
                    blockers = []
                results.append(
                    ForensicTestResult(
                        result_id=stable_id("forensic_test", request.case_id, entity, test.test_id, status),
                        case_id=request.case_id,
                        entity=entity,
                        test_id=test.test_id,
                        category=test.category,
                        status=status,
                        finding=finding,
                        evidence_record_ids=[record.record_id for record in entity_records],
                        source_uris=self._dedupe(record.source_uri for record in entity_records),
                        blockers=blockers,
                        human_next_steps=[test.human_next_step],
                    )
                )
        return results

    def _test_definitions(self, profile: InvestigationProfile) -> list[ForensicTestDefinition]:
        tests = list(self.DEFAULT_TESTS)
        for item in profile.forensic_tests:
            tests.append(
                ForensicTestDefinition(
                    test_id=str(item.get("test_id") or stable_id("test", str(item))),
                    category=str(item.get("category") or "profile test"),
                    question=str(item.get("question") or "Profile forensic test."),
                    required_source_families=list(item.get("required_source_families") or []),
                    failure_mode=str(item.get("failure_mode") or "unmapped failure mode"),
                    human_next_step=str(item.get("human_next_step") or "Review source files."),
                )
            )
        return tests

    def _norm(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

    def _dedupe(self, values: Iterable[str]) -> list[str]:
        return list(dict.fromkeys(value for value in values if value))


class EvidenceStoreManifestService:
    """Creates immutable evidence manifest rows for every canonical record used by a run."""

    def build_manifest(
        self,
        request: CaseRequest,
        profile: InvestigationProfile,
        records: Iterable[CanonicalRecord],
        bundle: EvidenceBundle | None = None,
    ) -> EvidenceStoreManifest:
        record_ids = {item.record_id for item in bundle.items} if bundle is not None else set()
        selected = [record for record in records if not record_ids or record.record_id in record_ids]
        entries: list[EvidenceStoreEntry] = []
        missing_snapshots = 0
        for record in selected:
            snapshot_path = self._snapshot_path(record)
            if record.source_uri.startswith("http") and not snapshot_path:
                missing_snapshots += 1
            entries.append(
                EvidenceStoreEntry(
                    entry_id=stable_id("evidence_store", request.case_id, record.record_id),
                    record_id=record.record_id,
                    source_uri=record.source_uri,
                    source_type=record.source_type,
                    checksum=record.provenance.checksum,
                    snapshot_path=snapshot_path,
                    parser_version=str(record.attributes.get("parser_version") or profile.evidence_store_policy.get("parser_version") or "unknown"),
                    immutable_reference=f"sha256:{record.provenance.checksum}",
                    collected_at=record.provenance.collected_at,
                )
            )
        notes = [
            "Manifest records checksums and source URIs for auditability.",
            "A missing snapshot means the runtime has a source URL/checksum but not a durable local copy of the source page or file.",
        ]
        return EvidenceStoreManifest(
            manifest_id=stable_id("evidence_manifest", request.case_id, str(len(entries)), str(missing_snapshots)),
            case_id=request.case_id,
            entry_count=len(entries),
            entries=entries,
            missing_snapshot_count=missing_snapshots,
            notes=notes,
        )

    def _snapshot_path(self, record: CanonicalRecord) -> str:
        for key in ("local_path", "artifact_path", "raw_artifact_path", "table_path"):
            value = record.attributes.get(key)
            if value and Path(str(value)).exists():
                return str(value)
        if record.source_uri and not record.source_uri.startswith("http") and Path(record.source_uri).exists():
            return record.source_uri
        return ""


class HumanActionCompilerService:
    """Compiles concrete human-only next actions from matrix rows, source blockers, and forensic tests."""

    def compile(
        self,
        request: CaseRequest,
        risk_matrix: OversightRiskMatrix,
        source_plan: SourceAcquisitionPlan,
        forensic_tests: list[ForensicTestResult],
        citation: CitationVerificationResult | None = None,
    ) -> HumanActionPlan:
        actions: list[HumanActionItem] = []
        for indicator in risk_matrix.indicators:
            if indicator.risk_level not in {"High", "Medium", "Data gap"}:
                continue
            priority = "High" if indicator.risk_level == "High" else "Medium" if indicator.risk_level == "Medium" else "Source gap"
            actions.append(
                HumanActionItem(
                    action_id=stable_id("human_action", request.case_id, indicator.entity or "case", indicator.risk_area, indicator.reviewer_action),
                    case_id=request.case_id,
                    entity=indicator.entity or "Case-wide",
                    priority=priority,
                    action_type=self._action_type(indicator.risk_area),
                    action=indicator.reviewer_action,
                    rationale=indicator.observed_fact,
                    source_refs=[*indicator.evidence_ids, *indicator.record_ids, *indicator.source_uris],
                )
            )
        for requirement in source_plan.requirements:
            if requirement.status == "satisfied":
                continue
            actions.append(
                HumanActionItem(
                    action_id=stable_id("human_action_source", request.case_id, requirement.entity, requirement.source_family),
                    case_id=request.case_id,
                    entity=requirement.entity,
                    priority="Source gap",
                    action_type="source acquisition",
                    action=f"Acquire {requirement.source_family.replace('_', ' ')} artifacts: {', '.join(requirement.required_artifacts)}.",
                    rationale=requirement.blocker_reason,
                    source_refs=[*requirement.source_uris, *requirement.matched_record_ids],
                    required_authority="authorized records request, credentialed docket access, or public-source collector",
                )
            )
        for result in forensic_tests:
            if result.status != "BLOCKED_BY_SOURCE_GAP":
                continue
            actions.append(
                HumanActionItem(
                    action_id=stable_id("human_action_test", request.case_id, result.entity, result.test_id),
                    case_id=request.case_id,
                    entity=result.entity,
                    priority="Source gap",
                    action_type=f"forensic test: {result.category}",
                    action="; ".join(result.human_next_steps),
                    rationale=result.finding,
                    source_refs=[*result.evidence_record_ids, *result.source_uris],
                )
            )
        if citation and citation.status != "PASS":
            actions.append(
                HumanActionItem(
                    action_id=stable_id("human_action_citation", request.case_id, citation.status),
                    case_id=request.case_id,
                    entity="Case-wide",
                    priority="High",
                    action_type="citation repair",
                    action="Repair citation verifier warnings or errors before any public use.",
                    rationale=f"Citation status {citation.status}; errors={citation.error_count}; warnings={citation.warning_count}.",
                    source_refs=[],
                )
            )
        ordered = self._rank_actions(actions)
        highest = ordered[0].action if ordered else "No human action compiled; rerun after risk matrix generation."
        return HumanActionPlan(
            plan_id=stable_id("human_action_plan", request.case_id, str(len(ordered)), highest),
            case_id=request.case_id,
            actions=ordered,
            highest_leverage_action=highest,
        )

    def _action_type(self, risk_area: str) -> str:
        lower = risk_area.lower()
        if "audit" in lower:
            return "audit verification"
        if "docket" in lower or "enforcement" in lower:
            return "legal-status verification"
        if "funding" in lower or "payment" in lower or "award" in lower:
            return "money-trail verification"
        if "scope" in lower or "statement" in lower:
            return "scope and allowability review"
        if "spend-versus-results" in lower or "outcome" in lower:
            return "outcome attribution review"
        return "source review"

    def _rank_actions(self, actions: list[HumanActionItem]) -> list[HumanActionItem]:
        priority = {"High": 0, "Medium": 1, "Source gap": 2, "Low": 3}
        seen: set[tuple[str, str, str]] = set()
        output: list[HumanActionItem] = []
        for action in sorted(actions, key=lambda item: (priority.get(item.priority, 9), item.entity, item.action_type, item.action)):
            key = (action.entity, action.action_type, action.action)
            if key in seen:
                continue
            seen.add(key)
            output.append(action)
        return output[:80]
