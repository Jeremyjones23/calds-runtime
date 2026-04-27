from __future__ import annotations

from pathlib import Path

from .case_compiler import CaseDossierService

from .agents import (
    CaseDirector,
    EntityNetworkAnalyst,
    EvidenceAnalyst,
    LeadScorerAgent,
    LocalProviderAdapter,
    RetrievalStrategist,
)
from .contracts import (
    AgentRole,
    AgentTask,
    CaseRequest,
    HumanDecision,
    Plane,
    ReviewDecision,
    SearchHit,
    TaskStatus,
    WorkflowStatus,
    stable_id,
    utc_now,
)
from .review import ReviewArtifactService
from .risk_matrix import OversightRiskMatrixService
from .scoring import LeadScoringService
from .search import KeywordSearchIndex
from .sentinel import SentinelPolicy
from .truth import JsonCorpusTruthStore, tokenize
from .workflow import FileWorkflowStore, WorkflowRunResult


class CaseWorkflow:
    """Workflow-first case runner with local adapters for missing production stack."""

    def __init__(self, corpus_dir: Path, runs_dir: Path) -> None:
        self.truth_store = JsonCorpusTruthStore(corpus_dir)
        self.search_index = KeywordSearchIndex(self.truth_store.records)
        self.scoring_service = LeadScoringService()
        self.review_artifacts = ReviewArtifactService()
        self.case_dossiers = CaseDossierService()
        self.risk_matrix_service = OversightRiskMatrixService()
        self.sentinel_policy = SentinelPolicy()
        self.provider = LocalProviderAdapter()
        self.runs_dir = runs_dir

    def run_case(self, request: CaseRequest) -> WorkflowRunResult:
        store = FileWorkflowStore(self.runs_dir, request.case_id)
        prior_state = store.read_state()
        prior_packet = store.artifact_path("review_packet.md")
        prior_dossier = store.artifact_path("case_dossier.md")
        if (
            prior_state
            and prior_state.get("status") == WorkflowStatus.AWAITING_HUMAN_REVIEW.value
            and prior_packet.exists()
            and prior_dossier.exists()
        ):
            return WorkflowRunResult(
                case_id=request.case_id,
                status=WorkflowStatus.AWAITING_HUMAN_REVIEW,
                run_dir=store.run_dir,
                review_packet_path=prior_packet,
                state_path=store.state_path,
                trace_path=store.trace_json_path,
            )

        completed_steps: list[str] = []
        artifacts: dict[str, str] = {}
        self._open_case(store, request, completed_steps, artifacts)

        case_director = CaseDirector()
        bounded_case = case_director.bound(request)
        scope_path = store.write_artifact("case_scope.json", bounded_case)
        self._write_task(store, request, AgentRole.CASE_DIRECTOR, "Bound the case scope.", [str(scope_path)])
        artifacts["case_scope"] = str(scope_path)
        store.trace(
            request.case_id,
            Plane.AGENT,
            AgentRole.CASE_DIRECTOR.value,
            "case_scope_bounded",
            "Case Director narrowed the request to an internal triage scope.",
            outputs={"scope_note": bounded_case.scope_note},
            artifacts=[str(scope_path)],
            metadata=self.provider.describe_role_call(AgentRole.CASE_DIRECTOR.value),
        )

        retrieval_strategist = RetrievalStrategist()
        search_plan = retrieval_strategist.plan(request, bounded_case)
        plan_path = store.write_artifact("retrieval_plan.json", search_plan)
        self._write_task(store, request, AgentRole.RETRIEVAL_STRATEGIST, "Plan bounded retrieval.", [str(plan_path)])
        artifacts["retrieval_plan"] = str(plan_path)
        store.trace(
            request.case_id,
            Plane.AGENT,
            AgentRole.RETRIEVAL_STRATEGIST.value,
            "retrieval_terms_planned",
            "Retrieval Strategist produced search terms without changing truth records.",
            outputs={"term_count": len(search_plan.terms)},
            artifacts=[str(plan_path)],
            metadata=self.provider.describe_role_call(AgentRole.RETRIEVAL_STRATEGIST.value),
        )

        hits = self._ensure_entity_context_hits(request, self.search_index.search(search_plan))
        hits_path = store.write_artifact("search_hits.json", {"hits": hits})
        artifacts["search_hits"] = str(hits_path)
        completed_steps.append("retrieved")
        store.trace(
            request.case_id,
            Plane.SEARCH,
            "KeywordSearchIndex",
            "records_retrieved",
            "Search plane returned deterministic ranked record IDs.",
            inputs={"terms": search_plan.terms, "allowed_sources": search_plan.allowed_sources},
            outputs={"hit_count": len(hits)},
            artifacts=[str(hits_path)],
        )
        store.write_state(request, WorkflowStatus.RETRIEVED, completed_steps, artifacts)

        bundle = self.truth_store.build_evidence_bundle(request, search_plan.terms, hits)
        bundle_path = store.write_artifact("evidence_bundle.json", bundle)
        artifacts["evidence_bundle"] = str(bundle_path)
        evidence_summary = EvidenceAnalyst().summarize_bundle(bundle)
        evidence_summary_path = store.write_artifact("evidence_analysis.json", evidence_summary)
        self._write_task(
            store,
            request,
            AgentRole.EVIDENCE_ANALYST,
            "Assemble cited evidence bundle.",
            [str(bundle_path), str(evidence_summary_path)],
        )
        completed_steps.append("evidence_bundled")
        store.trace(
            request.case_id,
            Plane.TRUTH,
            "JsonCorpusTruthStore",
            "evidence_bundle_created",
            "Truth plane assembled evidence items with provenance and entity links.",
            outputs={"evidence_count": len(bundle.items), "entity_link_count": len(bundle.entity_links)},
            artifacts=[str(bundle_path), str(evidence_summary_path)],
        )
        store.write_state(request, WorkflowStatus.EVIDENCE_BUNDLED, completed_steps, artifacts)

        risk_matrix = self.risk_matrix_service.build(request, self.truth_store.records, bundle)
        risk_matrix_path = store.write_artifact("oversight_risk_matrix.json", risk_matrix)
        artifacts["oversight_risk_matrix"] = str(risk_matrix_path)
        store.trace(
            request.case_id,
            Plane.TRUTH,
            "OversightRiskMatrixService",
            "oversight_risk_matrix_created",
            "Truth plane computed deterministic WFA screening indicators from parsed source facts.",
            outputs={
                "indicator_count": len(risk_matrix.indicators),
                "high_count": sum(1 for item in risk_matrix.indicators if item.risk_level == "High"),
                "data_gap_count": sum(1 for item in risk_matrix.indicators if item.risk_level == "Data gap"),
            },
            artifacts=[str(risk_matrix_path)],
        )

        network_summary = EntityNetworkAnalyst().summarize_links(bundle)
        network_path = store.write_artifact("entity_network_analysis.json", network_summary)
        self._write_task(
            store,
            request,
            AgentRole.ENTITY_NETWORK_ANALYST,
            "Summarize deterministic entity links.",
            [str(network_path)],
        )
        artifacts["entity_network_analysis"] = str(network_path)
        store.trace(
            request.case_id,
            Plane.AGENT,
            AgentRole.ENTITY_NETWORK_ANALYST.value,
            "entity_links_summarized",
            "Entity analyst interpreted truth-plane joins without creating canonical state.",
            outputs={"hard_link_count": network_summary["hard_link_count"]},
            artifacts=[str(network_path)],
            metadata=self.provider.describe_role_call(AgentRole.ENTITY_NETWORK_ANALYST.value),
        )

        lead = LeadScorerAgent(self.scoring_service).create_candidate(request, bundle)
        lead_path = store.write_artifact("lead_candidate.json", lead)
        self._write_task(store, request, AgentRole.LEAD_SCORER, "Create reviewer-safe lead candidate.", [str(lead_path)])
        artifacts["lead_candidate"] = str(lead_path)
        completed_steps.append("lead_candidate_ready")
        store.trace(
            request.case_id,
            Plane.AGENT,
            AgentRole.LEAD_SCORER.value,
            "lead_candidate_created",
            "Lead Scorer used deterministic score inputs to draft an internal lead candidate.",
            outputs={"score": lead.score, "evidence_ids": lead.evidence_ids},
            artifacts=[str(lead_path)],
            metadata=self.provider.describe_role_call(AgentRole.LEAD_SCORER.value),
        )
        store.write_state(request, WorkflowStatus.LEAD_CANDIDATE_READY, completed_steps, artifacts)

        sentinel = self.sentinel_policy.review(request, lead)
        sentinel_path = store.write_artifact("sentinel_decision.json", sentinel)
        self._write_task(store, request, AgentRole.SENTINEL, "Gate lead language and review posture.", [str(sentinel_path)])
        artifacts["sentinel_decision"] = str(sentinel_path)
        completed_steps.append("sentinel_reviewed")
        store.trace(
            request.case_id,
            Plane.AGENT,
            AgentRole.SENTINEL.value,
            "sentinel_gate_completed",
            "Sentinel checked the lead before human review pause.",
            outputs={"decision": sentinel.decision.value, "flags": sentinel.flags},
            artifacts=[str(sentinel_path)],
            metadata=self.provider.describe_role_call(AgentRole.SENTINEL.value),
        )
        store.write_state(request, WorkflowStatus.SENTINEL_REVIEWED, completed_steps, artifacts)

        review_packet_path = store.artifact_path("review_packet.md")
        packet = self.review_artifacts.write_packet(
            review_packet_path,
            request,
            bundle,
            lead,
            sentinel,
            risk_matrix,
            artifact_refs=list(artifacts.values()),
        )
        packet_path = store.write_artifact("review_packet.json", packet)
        self._write_task(
            store,
            request,
            AgentRole.REVIEW_PACKAGER,
            "Package artifacts for human review.",
            [str(review_packet_path), str(packet_path)],
        )
        artifacts["review_packet"] = str(packet_path)
        artifacts["review_packet_markdown"] = str(review_packet_path)
        store.trace(
            request.case_id,
            Plane.TRUTH,
            "ReviewArtifactService",
            "review_packet_created",
            "Reviewer artifact created with raw evidence references.",
            artifacts=[str(review_packet_path), str(packet_path)],
        )

        review_decision = ReviewDecision(
            decision_id=stable_id("review", request.case_id, "pending"),
            case_id=request.case_id,
            decision=HumanDecision.PENDING,
        )

        dossier_path = store.artifact_path("case_dossier.md")
        dossier = self.case_dossiers.write_dossier(
            dossier_path,
            request,
            bundle,
            lead,
            sentinel,
            risk_matrix,
            packet,
            review_decision,
            source_artifact_refs=list(artifacts.values()) + [str(packet_path), str(review_packet_path)],
        )
        dossier_json_path = store.write_artifact("case_dossier.json", dossier)
        self._write_task(
            store,
            request,
            AgentRole.CASE_COMPILER,
            "Compile final case dossier for human review.",
            [str(dossier_path), str(dossier_json_path)],
        )
        artifacts["case_dossier"] = str(dossier_json_path)
        artifacts["case_dossier_markdown"] = str(dossier_path)
        completed_steps.append("case_compiled")
        store.trace(
            request.case_id,
            Plane.TRUTH,
            "CaseDossierService",
            "case_dossier_created",
            "Deterministic service compiled the final human-review dossier from existing workflow artifacts.",
            outputs={"sentinel_decision": sentinel.decision.value, "priority_rows": len([item for item in risk_matrix.indicators if item.risk_level in {"High", "Medium", "Data gap"}])},
            artifacts=[str(dossier_path), str(dossier_json_path)],
            metadata=self.provider.describe_role_call(AgentRole.CASE_COMPILER.value),
        )

        review_decision_path = store.write_artifact("review_decision.json", review_decision)
        artifacts["review_decision"] = str(review_decision_path)
        completed_steps.append("awaiting_human_review")
        store.trace(
            request.case_id,
            Plane.WORKFLOW,
            "LocalDurableWorkflowAdapter",
            "human_review_pause",
            "Workflow paused pending explicit human review decision.",
            outputs={"status": WorkflowStatus.AWAITING_HUMAN_REVIEW.value},
            artifacts=[str(review_decision_path)],
        )
        store.write_state(request, WorkflowStatus.AWAITING_HUMAN_REVIEW, completed_steps, artifacts)
        store.write_run_trace(request.case_id, WorkflowStatus.AWAITING_HUMAN_REVIEW)

        return WorkflowRunResult(
            case_id=request.case_id,
            status=WorkflowStatus.AWAITING_HUMAN_REVIEW,
            run_dir=store.run_dir,
            review_packet_path=review_packet_path,
            state_path=store.state_path,
            trace_path=store.trace_json_path,
        )

    def _ensure_entity_context_hits(self, request: CaseRequest, hits: list[SearchHit]) -> list[SearchHit]:
        if "org_service_page" not in request.allowed_sources:
            return hits
        selected_ids = {hit.record_id for hit in hits}
        context_hits: list[SearchHit] = []
        requested_entities = {self._normalize_entity(entity): entity for entity in request.entities}
        for record in sorted(self.truth_store.records, key=lambda item: item.record_id):
            if record.source_type != "org_service_page" or record.record_id in selected_ids:
                continue
            record_entities = {self._normalize_entity(entity) for entity in record.entities}
            matched_entity = next((entity for entity in requested_entities if entity in record_entities), "")
            if not matched_entity:
                continue
            terms = [term for term in tokenize(requested_entities[matched_entity]) if term not in {"inc", "of", "california", "the"}]
            context_hits.append(SearchHit(record_id=record.record_id, relevance_score=1.0, matched_terms=terms or ["service"]))
            selected_ids.add(record.record_id)
        return [*hits, *context_hits]

    def _normalize_entity(self, value: str) -> str:
        tokens = [token for token in tokenize(value) if token not in {"inc", "of", "the"}]
        return " ".join(tokens)
    def record_review(
        self,
        case_id: str,
        reviewer: str,
        decision: HumanDecision,
        rationale: str,
    ) -> Path:
        store = FileWorkflowStore(self.runs_dir, case_id)
        review_decision = ReviewDecision(
            decision_id=stable_id("review", case_id, reviewer, decision.value, utc_now()),
            case_id=case_id,
            decision=decision,
            reviewer=reviewer,
            rationale=rationale,
        )
        path = store.write_artifact("review_decision.json", review_decision)
        prior_state = store.read_state() or {"completed_steps": [], "artifacts": {}}
        completed_steps = list(prior_state.get("completed_steps", []))
        if "reviewed" not in completed_steps:
            completed_steps.append("reviewed")
        artifacts = dict(prior_state.get("artifacts", {}))
        artifacts["review_decision"] = str(path)
        continuation = CaseRequest(
            case_id=case_id,
            title=case_id,
            objective="review continuation",
        )
        store.write_state(continuation, WorkflowStatus.REVIEWED, completed_steps, artifacts)
        return path

    def _open_case(
        self,
        store: FileWorkflowStore,
        request: CaseRequest,
        completed_steps: list[str],
        artifacts: dict[str, str],
    ) -> None:
        case_request_path = store.write_artifact("case_request.json", request)
        artifacts["case_request"] = str(case_request_path)
        store.trace(
            request.case_id,
            Plane.WORKFLOW,
            "LocalDurableWorkflowAdapter",
            "case_opened",
            "Case request persisted before agent work.",
            inputs={"case_id": request.case_id},
            artifacts=[str(case_request_path)],
        )
        completed_steps.append("case_opened")
        store.write_state(request, WorkflowStatus.OPENED, completed_steps, artifacts)

    def _write_task(
        self,
        store: FileWorkflowStore,
        request: CaseRequest,
        role: AgentRole,
        objective: str,
        output_refs: list[str],
    ) -> Path:
        task = AgentTask(
            task_id=stable_id("task", request.case_id, role.value, objective),
            case_id=request.case_id,
            role=role,
            objective=objective,
            inputs={"case_id": request.case_id},
            status=TaskStatus.PENDING,
        ).complete(output_refs)
        name = "task_" + role.value.lower().replace(" ", "_").replace("and", "").replace("__", "_") + ".json"
        return store.write_artifact(name, task)





