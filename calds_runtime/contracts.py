from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def stable_id(prefix: str, *parts: str) -> str:
    digest = sha256_text("|".join(parts))[:16]
    return f"{prefix}_{digest}"


class Plane(str, Enum):
    TRUTH = "truth"
    SEARCH = "search"
    WORKFLOW = "workflow"
    AGENT = "agent"
    PROVIDER = "provider"


class AgentRole(str, Enum):
    CASE_DIRECTOR = "Case Director"
    RETRIEVAL_STRATEGIST = "Retrieval Strategist"
    CONTEXT_STEWARD = "Context Steward"
    TRIAGE_SCREENER = "Triage Screener"
    ENFORCEMENT_DOCKET_ANALYST = "Enforcement and Docket Analyst"
    TAX_AUDIT_ANALYST = "Tax and Audit Analyst"
    WEB_SOCIAL_STATEMENTS_ANALYST = "Web and Social Statements Analyst"
    FORENSIC_SYNTHESIS_ANALYST = "Forensic Synthesis Analyst"
    ENTITY_NETWORK_ANALYST = "Entity and Network Analyst"
    EVIDENCE_ANALYST = "Evidence Analyst"
    LEAD_SCORER = "Lead Scorer"
    SENTINEL = "Sentinel"
    REVIEW_PACKAGER = "Review Packager"
    CASE_COMPILER = "Case Compiler"
    COMPLETION_GUARD = "Completion Guard"
    CITATION_VERIFIER = "Citation Verifier"


class WorkflowStatus(str, Enum):
    OPENED = "OPENED"
    TRIAGED = "TRIAGED"
    FORENSIC_INVESTIGATED = "FORENSIC_INVESTIGATED"
    RETRIEVED = "RETRIEVED"
    EVIDENCE_BUNDLED = "EVIDENCE_BUNDLED"
    LEAD_CANDIDATE_READY = "LEAD_CANDIDATE_READY"
    SENTINEL_REVIEWED = "SENTINEL_REVIEWED"
    AWAITING_HUMAN_REVIEW = "AWAITING_HUMAN_REVIEW"
    REVIEWED = "REVIEWED"


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"


class SentinelDecision(str, Enum):
    ALLOW_FOR_REVIEW = "ALLOW_FOR_REVIEW"
    DOWNGRADE_FOR_REVIEW = "DOWNGRADE_FOR_REVIEW"
    BLOCK_REPAIR_REQUIRED = "BLOCK_REPAIR_REQUIRED"


class HumanDecision(str, Enum):
    PENDING = "PENDING"
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    DOWNGRADE = "DOWNGRADE"
    REPAIR = "REPAIR"


@dataclass(frozen=True)
class CaseRequest:
    case_id: str
    title: str
    objective: str
    jurisdiction: str = "California"
    allowed_sources: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    requested_by: str = "local-operator"
    created_at: str = field(default_factory=utc_now)
    max_results: int = 5
    evaluation_case_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "CaseRequest":
        return cls(
            case_id=value["case_id"],
            title=value["title"],
            objective=value["objective"],
            jurisdiction=value.get("jurisdiction", "California"),
            allowed_sources=list(value.get("allowed_sources", [])),
            entities=list(value.get("entities", [])),
            requested_by=value.get("requested_by", "local-operator"),
            created_at=value.get("created_at", utc_now()),
            max_results=int(value.get("max_results", 5)),
            evaluation_case_id=value.get("evaluation_case_id"),
            metadata=dict(value.get("metadata", {})),
        )


@dataclass(frozen=True)
class AgentTask:
    task_id: str
    case_id: str
    role: AgentRole
    objective: str
    inputs: dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    created_at: str = field(default_factory=utc_now)
    completed_at: str | None = None
    output_refs: list[str] = field(default_factory=list)

    def complete(self, output_refs: list[str]) -> "AgentTask":
        return AgentTask(
            task_id=self.task_id,
            case_id=self.case_id,
            role=self.role,
            objective=self.objective,
            inputs=self.inputs,
            status=TaskStatus.COMPLETED,
            created_at=self.created_at,
            completed_at=utc_now(),
            output_refs=output_refs,
        )


@dataclass(frozen=True)
class Provenance:
    record_id: str
    source_uri: str
    source_type: str
    collected_at: str
    checksum: str
    corpus_name: str
    chunk_id: str


@dataclass(frozen=True)
class CanonicalRecord:
    record_id: str
    title: str
    body: str
    source_uri: str
    source_type: str
    published_at: str
    entities: list[str]
    attributes: dict[str, Any]
    provenance: Provenance


@dataclass(frozen=True)
class SearchHit:
    record_id: str
    relevance_score: float
    matched_terms: list[str]


@dataclass(frozen=True)
class EvidenceItem:
    item_id: str
    record_id: str
    title: str
    source_uri: str
    source_type: str
    published_at: str
    excerpt: str
    relevance_score: float
    matched_terms: list[str]
    provenance: Provenance
    signals: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EntityLink:
    entity: str
    record_ids: list[str]
    link_type: str
    strength: float
    rationale: str


@dataclass(frozen=True)
class EvidenceBundle:
    bundle_id: str
    case_id: str
    query_terms: list[str]
    items: list[EvidenceItem]
    entity_links: list[EntityLink]
    created_at: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class ScoreInputs:
    support_count: int
    average_relevance: float
    source_diversity: int
    hard_link_count: int
    contradiction_count: int
    missing_data_count: int
    final_score: float


@dataclass(frozen=True)
class LeadCandidate:
    lead_id: str
    case_id: str
    statement: str
    support_summary: str
    uncertainty: list[str]
    required_review_questions: list[str]
    evidence_ids: list[str]
    score: float
    score_inputs: ScoreInputs
    status: str = "READY_FOR_SENTINEL"
    created_at: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class OversightRiskIndicator:
    indicator_id: str
    case_id: str
    risk_area: str
    entity: str
    test_name: str
    observed_fact: str
    risk_level: str
    data_status: str
    reviewer_action: str
    evidence_ids: list[str] = field(default_factory=list)
    record_ids: list[str] = field(default_factory=list)
    source_uris: list[str] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class OversightRiskMatrix:
    matrix_id: str
    case_id: str
    methodology: str
    score_scale: str
    indicators: list[OversightRiskIndicator]
    created_at: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class TriageFinding:
    finding_id: str
    case_id: str
    entity: str
    source_family: str
    finding_type: str
    observed_fact: str
    risk_level: str
    data_status: str
    trigger_reason: str
    source_uris: list[str] = field(default_factory=list)
    record_ids: list[str] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EntityTriageResult:
    result_id: str
    case_id: str
    entity: str
    triage_priority: str
    deep_dive_recommended: bool
    rationale: str
    findings: list[TriageFinding]
    missing_source_families: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class ForensicInvestigationPlan:
    plan_id: str
    case_id: str
    selected_entities: list[str]
    selection_rule: str
    source_families: list[str]
    entity_rationales: dict[str, str]
    created_at: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class ForensicFinding:
    finding_id: str
    case_id: str
    entity: str
    hypothesis: str
    basis: str
    confidence: str
    evidence_record_ids: list[str]
    source_uris: list[str]
    caveats: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ContextHandoffLedger:
    ledger_id: str
    case_id: str
    from_step: str
    to_step: str
    required_fields: list[str]
    present_fields: list[str]
    missing_fields: list[str]
    artifact_refs: list[str]
    status: str
    created_at: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class AcquisitionSearchRun:
    search_id: str
    case_id: str
    entity: str
    source_family: str
    query: str
    attempted_sources: list[str]
    matched_record_ids: list[str]
    source_uris: list[str]
    status: str
    confidence: str
    blocker_reason: str = ""
    created_at: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class CompletionGuardResult:
    guard_id: str
    case_id: str
    status: str
    required_source_families: list[str]
    selected_entities: list[str]
    total_searches: int
    hit_count: int
    miss_count: int
    blocker_count: int
    missing_required: list[str]
    notes: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class CitationCheck:
    check_id: str
    case_id: str
    check_type: str
    status: str
    message: str
    evidence_refs: list[str] = field(default_factory=list)
    record_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CitationVerificationResult:
    verification_id: str
    case_id: str
    status: str
    checked_claim_count: int
    error_count: int
    warning_count: int
    checks: list[CitationCheck]
    created_at: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class SourceLinkCheck:
    check_id: str
    url: str
    status: str
    http_status: int | None
    final_url: str
    content_type: str
    error: str = ""


@dataclass(frozen=True)
class LinkIntegrityReport:
    report_id: str
    status: str
    checked_url_count: int
    error_count: int
    warning_count: int
    checks: list[SourceLinkCheck]
    created_at: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class SentinelResult:
    decision_id: str
    case_id: str
    decision: SentinelDecision
    flags: list[str]
    rationale: str
    repair_instructions: list[str]
    checked_at: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class ReviewDecision:
    decision_id: str
    case_id: str
    decision: HumanDecision = HumanDecision.PENDING
    reviewer: str = "unassigned"
    rationale: str = "Pending explicit human review."
    created_at: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class ReviewPacket:
    packet_id: str
    case_id: str
    markdown_path: str
    artifact_refs: list[str]
    created_at: str = field(default_factory=utc_now)



@dataclass(frozen=True)
class CompiledCaseDossier:
    dossier_id: str
    case_id: str
    markdown_path: str
    source_artifact_refs: list[str]
    sentinel_decision: SentinelDecision
    compiler_role: AgentRole = AgentRole.CASE_COMPILER
    created_at: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class TraceEvent:
    event_id: str
    timestamp: str
    plane: Plane
    actor: str
    action: str
    summary: str
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RunTrace:
    trace_id: str
    case_id: str
    started_at: str
    status: WorkflowStatus
    events: list[TraceEvent]


def to_jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: to_jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    return value


def write_json(path: Path, value: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(to_jsonable(value), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))



