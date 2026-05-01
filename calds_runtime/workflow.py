from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json

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
    RunTrace,
    TaskStatus,
    TraceEvent,
    WorkflowStatus,
    read_json,
    stable_id,
    to_jsonable,
    utc_now,
    write_json,
)
from .review import ReviewArtifactService
from .scoring import LeadScoringService
from .search import KeywordSearchIndex
from .sentinel import SentinelPolicy
from .truth import JsonCorpusTruthStore


@dataclass(frozen=True)
class WorkflowRunResult:
    case_id: str
    status: WorkflowStatus
    run_dir: Path
    review_packet_path: Path
    state_path: Path
    trace_path: Path


class FileWorkflowStore:
    """Local durable workflow-plane adapter with JSON artifacts and trace events."""

    def __init__(self, runs_dir: Path, case_id: str, runtime_logic_version: str = "") -> None:
        self.run_dir = runs_dir / case_id
        self.artifact_dir = self.run_dir / "artifacts"
        self.trace_jsonl_path = self.run_dir / "trace.jsonl"
        self.trace_json_path = self.run_dir / "run_trace.json"
        self.state_path = self.run_dir / "workflow_state.json"
        self.runtime_logic_version = runtime_logic_version
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self._events: list[TraceEvent] = []

    def artifact_path(self, name: str) -> Path:
        return self.artifact_dir / name

    def write_artifact(self, name: str, value: Any) -> Path:
        return write_json(self.artifact_path(name), value)

    def write_state(
        self,
        request: CaseRequest,
        status: WorkflowStatus,
        completed_steps: list[str],
        artifacts: dict[str, str],
    ) -> Path:
        return write_json(
            self.state_path,
            {
                "case_id": request.case_id,
                "status": status,
                "runtime_logic_version": self.runtime_logic_version,
                "completed_steps": completed_steps,
                "artifacts": artifacts,
                "updated_at": utc_now(),
            },
        )

    def read_state(self) -> dict[str, Any] | None:
        if not self.state_path.exists():
            return None
        return read_json(self.state_path)

    def trace(
        self,
        case_id: str,
        plane: Plane,
        actor: str,
        action: str,
        summary: str,
        inputs: dict[str, Any] | None = None,
        outputs: dict[str, Any] | None = None,
        artifacts: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TraceEvent:
        event = TraceEvent(
            event_id=stable_id("event", case_id, action, utc_now(), str(len(self._events))),
            timestamp=utc_now(),
            plane=plane,
            actor=actor,
            action=action,
            summary=summary,
            inputs=inputs or {},
            outputs=outputs or {},
            artifacts=artifacts or [],
            metadata=metadata or {},
        )
        self._events.append(event)
        with self.trace_jsonl_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(to_jsonable(event), sort_keys=True) + "\n")
        return event

    def write_run_trace(self, case_id: str, status: WorkflowStatus) -> Path:
        started_at = self._events[0].timestamp if self._events else utc_now()
        trace = RunTrace(
            trace_id=stable_id("trace", case_id, started_at),
            case_id=case_id,
            started_at=started_at,
            status=status,
            events=self._events,
        )
        return write_json(self.trace_json_path, trace)
