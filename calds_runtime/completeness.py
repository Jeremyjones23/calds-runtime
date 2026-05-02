from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .contracts import (
    AcquisitionSearchRun,
    AgentRole,
    CaseRequest,
    CitationVerificationResult,
    CompletenessCheck,
    CompletenessControllerReport,
    CompletenessRepairAction,
    CompletionGuardResult,
    ContextHandoffLedger,
    InvestigationProfile,
    SentinelResult,
    WorkflowStatus,
    stable_id,
)


class CompletenessControllerService:
    """Active completeness controller for anti-laziness and context-loss gates."""

    def build_report(
        self,
        request: CaseRequest,
        profile: InvestigationProfile,
        artifact_refs: dict[str, str],
        handoffs: Iterable[ContextHandoffLedger],
        acquisition_ledger: Iterable[AcquisitionSearchRun],
        completion_guard: CompletionGuardResult | None = None,
        citation_verification: CitationVerificationResult | None = None,
        sentinel: SentinelResult | None = None,
        dossier_text: str = "",
        workflow_status: WorkflowStatus | None = None,
        run_attempt: int = 1,
    ) -> CompletenessControllerReport:
        checks: list[CompletenessCheck] = []
        actions: list[CompletenessRepairAction] = []
        handoff_list = list(handoffs)
        acquisition_list = list(acquisition_ledger)

        checks.extend(self._handoff_checks(request, handoff_list, artifact_refs, actions))
        if completion_guard is not None:
            checks.extend(
                self._source_checks(
                    request,
                    profile,
                    acquisition_list,
                    completion_guard,
                    artifact_refs,
                    actions,
                    run_attempt,
                )
            )
        if citation_verification is not None:
            checks.append(self._citation_check(request, citation_verification, artifact_refs, actions))
        if sentinel is not None:
            checks.append(self._sentinel_check(request, sentinel, artifact_refs, actions))
        if dossier_text:
            checks.append(self._presentation_check(request, dossier_text, artifact_refs, actions))
            checks.append(self._hallucination_check(request, dossier_text, artifact_refs, actions))
        if workflow_status is not None:
            checks.append(self._human_review_check(request, workflow_status, artifact_refs, actions))

        critical = [check for check in checks if check.status == "REPAIR_REQUIRED"]
        retry_required = [action for action in actions if action.status == "retry_required"]
        blocked = [action for action in actions if action.status == "blocked_with_documented_reason"]
        if critical:
            status = "REPAIR_REQUIRED"
        elif blocked:
            status = "PASS_WITH_BLOCKERS"
        else:
            status = "PASS"
        notes = [
            "Completeness Controller is an audit and retry driver, not a source of canonical facts.",
            "Every repair_required action must be repaired and rerun before a step can be accepted as complete.",
            "Documented external blockers may remain only when the blocker reason and next rerun target are preserved.",
        ]
        return CompletenessControllerReport(
            report_id=stable_id("completeness", request.case_id, profile.profile_id, status, str(run_attempt), str(len(checks))),
            case_id=request.case_id,
            status=status,
            profile_id=profile.profile_id,
            run_attempt=run_attempt,
            checks=checks,
            repair_actions=actions,
            handoff_count=len(handoff_list),
            critical_anomaly_count=len(critical),
            retry_required_count=len(retry_required),
            blocked_count=len(blocked),
            notes=notes,
        )

    def _handoff_checks(
        self,
        request: CaseRequest,
        handoffs: list[ContextHandoffLedger],
        artifact_refs: dict[str, str],
        actions: list[CompletenessRepairAction],
    ) -> list[CompletenessCheck]:
        checks: list[CompletenessCheck] = []
        if not handoffs:
            action = self._action(
                request,
                "handoff",
                "No context handoff ledger was produced.",
                "Add a handoff ledger that includes case scope, entities, evidence IDs, source URIs, caveats, and next task.",
                "rerun affected agent handoff",
                "retry_required",
            )
            actions.append(action)
            return [
                self._check(
                    request,
                    "handoff",
                    "REPAIR_REQUIRED",
                    "No handoff ledger exists for the run.",
                    artifact_refs,
                    ["context_handoff_ledger"],
                    [action.action_id],
                )
            ]
        for handoff in handoffs:
            if handoff.status == "PASS":
                checks.append(
                    self._check(
                        request,
                        "handoff",
                        "PASS",
                        f"{handoff.from_step} to {handoff.to_step} preserved required context.",
                        artifact_refs,
                    )
                )
                continue
            action = self._action(
                request,
                "handoff",
                f"{handoff.from_step} to {handoff.to_step} is missing {', '.join(handoff.missing_fields)}.",
                "Repair the emitting role or handoff schema so the next role receives all required context.",
                f"rerun {handoff.from_step}",
                "retry_required",
            )
            actions.append(action)
            checks.append(
                self._check(
                    request,
                    "handoff",
                    "REPAIR_REQUIRED",
                    action.issue,
                    artifact_refs,
                    handoff.missing_fields,
                    [action.action_id],
                )
            )
        return checks

    def _source_checks(
        self,
        request: CaseRequest,
        profile: InvestigationProfile,
        ledger: list[AcquisitionSearchRun],
        guard: CompletionGuardResult,
        artifact_refs: dict[str, str],
        actions: list[CompletenessRepairAction],
        run_attempt: int,
    ) -> list[CompletenessCheck]:
        if not ledger or guard.status == "FAIL":
            action = self._action(
                request,
                "source_acquisition",
                "Source acquisition produced no usable ledger or no selected entities.",
                "Repair the source profile or entity-selection step and rerun acquisition.",
                "rerun source acquisition",
                "retry_required",
            )
            actions.append(action)
            return [
                self._check(
                    request,
                    "source",
                    "REPAIR_REQUIRED",
                    "No usable source-acquisition ledger exists.",
                    artifact_refs,
                    ["acquisition_ledger"],
                    [action.action_id],
                )
            ]
        missing_rows = [row for row in ledger if row.status not in {"hit", "searched_no_public_official_record"}]
        missing_required = list(guard.missing_required)
        if not missing_required and not missing_rows:
            return [self._check(request, "source", "PASS", "All required source-family checks have citation-ready hits or verified public no-record rows.", artifact_refs)]

        repair_ids: list[str] = []
        for missing in missing_required[:40]:
            status = "blocked_with_documented_reason"
            blocker = self._blocker_for_missing(missing, ledger)
            if not blocker:
                status = "retry_required"
                blocker = "No documented blocker reason was found for this missing source-family check."
            if run_attempt <= 0:
                status = "retry_required"
            action = self._action(
                request,
                "source_acquisition",
                f"Required source-family check remains unresolved: {missing}.",
                "Add or repair the source acquisition path, then rerun acquisition for this entity/source family.",
                "rerun source acquisition",
                status,
                blocker,
            )
            actions.append(action)
            repair_ids.append(action.action_id)
        check_status = "REPAIR_REQUIRED" if any(action.status == "retry_required" for action in actions if action.action_id in repair_ids) else "PASS_WITH_BLOCKERS"
        return [
            self._check(
                request,
                "source",
                check_status,
                (
                    f"{len(missing_required)} required source-family check(s) remain unresolved under profile "
                    f"{profile.profile_id}; each has a repair/rerun action or documented external blocker."
                ),
                artifact_refs,
                missing_required,
                repair_ids,
            )
        ]

    def _citation_check(
        self,
        request: CaseRequest,
        citation: CitationVerificationResult,
        artifact_refs: dict[str, str],
        actions: list[CompletenessRepairAction],
    ) -> CompletenessCheck:
        if citation.status == "PASS":
            return self._check(request, "citation", "PASS", "Citation verifier passed with no unsupported dossier claims.", artifact_refs)
        action = self._action(
            request,
            "citation",
            f"Citation verifier returned {citation.status} with {citation.error_count} errors and {citation.warning_count} warnings.",
            "Repair uncited or overstated claims and rerun dossier compilation plus citation verification.",
            "rerun case dossier",
            "retry_required",
        )
        actions.append(action)
        return self._check(request, "citation", "REPAIR_REQUIRED", action.issue, artifact_refs, ["citation_verification"], [action.action_id])

    def _sentinel_check(
        self,
        request: CaseRequest,
        sentinel: SentinelResult,
        artifact_refs: dict[str, str],
        actions: list[CompletenessRepairAction],
    ) -> CompletenessCheck:
        if sentinel.decision.value != "BLOCK_REPAIR_REQUIRED":
            return self._check(request, "sentinel", "PASS", f"Sentinel posture is {sentinel.decision.value}; human-review safe language is preserved.", artifact_refs)
        action = self._action(
            request,
            "sentinel",
            "Sentinel blocked the lead for repair.",
            "Apply sentinel repair instructions, then rerun lead, sentinel, and dossier steps.",
            "rerun sentinel step",
            "retry_required",
            "; ".join(sentinel.repair_instructions),
        )
        actions.append(action)
        return self._check(request, "sentinel", "REPAIR_REQUIRED", action.issue, artifact_refs, sentinel.flags, [action.action_id])

    def _presentation_check(
        self,
        request: CaseRequest,
        dossier_text: str,
        artifact_refs: dict[str, str],
        actions: list[CompletenessRepairAction],
    ) -> CompletenessCheck:
        required = [
            "Bottom line:",
            "What CalDS found first",
            "Why CalDS flagged it",
            "What this does not prove",
            "Next human step",
        ]
        missing = [phrase for phrase in required if phrase not in dossier_text]
        if not missing:
            return self._check(request, "presentation", "PASS", "Dossier contains the required cold-reader briefing structure.", artifact_refs)
        action = self._action(
            request,
            "presentation",
            f"Dossier is missing required briefing structure: {', '.join(missing)}.",
            "Repair the case compiler or prompt and rerun dossier compilation.",
            "rerun case dossier",
            "retry_required",
        )
        actions.append(action)
        return self._check(request, "presentation", "REPAIR_REQUIRED", action.issue, artifact_refs, missing, [action.action_id])

    def _hallucination_check(
        self,
        request: CaseRequest,
        dossier_text: str,
        artifact_refs: dict[str, str],
        actions: list[CompletenessRepairAction],
    ) -> CompletenessCheck:
        suspicious = []
        for phrase in ["obviously proves", "without evidence", "must be guilty", "definitively caused"]:
            if phrase in dossier_text.lower():
                suspicious.append(phrase)
        if not suspicious:
            return self._check(request, "hallucination", "PASS", "No configured hallucination or overclaim phrases were found in the dossier.", artifact_refs)
        action = self._action(
            request,
            "hallucination",
            f"Dossier contains overclaim language: {', '.join(suspicious)}.",
            "Remove unsupported overclaim language and rerun citation plus sentinel gates.",
            "rerun dossier and sentinel",
            "retry_required",
        )
        actions.append(action)
        return self._check(request, "hallucination", "REPAIR_REQUIRED", action.issue, artifact_refs, suspicious, [action.action_id])

    def _human_review_check(
        self,
        request: CaseRequest,
        status: WorkflowStatus,
        artifact_refs: dict[str, str],
        actions: list[CompletenessRepairAction],
    ) -> CompletenessCheck:
        if status == WorkflowStatus.AWAITING_HUMAN_REVIEW:
            return self._check(request, "human_review", "PASS", "Workflow ended in explicit human-review pause.", artifact_refs)
        action = self._action(
            request,
            "human_review",
            f"Workflow status is {status.value}; expected AWAITING_HUMAN_REVIEW.",
            "Repair workflow state transition and rerun to human-review pause.",
            "rerun workflow",
            "retry_required",
        )
        actions.append(action)
        return self._check(request, "human_review", "REPAIR_REQUIRED", action.issue, artifact_refs, [status.value], [action.action_id])

    def _blocker_for_missing(self, missing: str, ledger: list[AcquisitionSearchRun]) -> str:
        for row in ledger:
            key = f"{row.entity}: {row.source_family}"
            if key == missing:
                return row.blocker_reason
        return ""

    def _action(
        self,
        request: CaseRequest,
        step: str,
        issue: str,
        required_change: str,
        rerun_step: str,
        status: str,
        blocker_reason: str = "",
    ) -> CompletenessRepairAction:
        return CompletenessRepairAction(
            action_id=stable_id("repair", request.case_id, step, issue, status),
            case_id=request.case_id,
            step=step,
            issue=issue,
            required_change=required_change,
            rerun_step=rerun_step,
            status=status,
            blocker_reason=blocker_reason,
        )

    def _check(
        self,
        request: CaseRequest,
        gate: str,
        status: str,
        summary: str,
        artifact_refs: dict[str, str],
        missing_context: list[str] | None = None,
        repair_action_ids: list[str] | None = None,
    ) -> CompletenessCheck:
        return CompletenessCheck(
            check_id=stable_id("completeness_check", request.case_id, gate, status, summary),
            case_id=request.case_id,
            gate=gate,
            status=status,
            summary=summary,
            artifact_refs=[str(Path(value)) for value in artifact_refs.values() if value],
            missing_context=missing_context or [],
            repair_action_ids=repair_action_ids or [],
        )
