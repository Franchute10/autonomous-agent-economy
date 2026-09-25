"""Immutable logical node execution state."""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from aeos.core import NodeDefinitionId, NodeRunId, UtcTimestamp, WorkflowRunId
from aeos.workflows.domain._lifecycle import (
    required_timestamp,
    timestamp,
    validate_order,
)
from aeos.workflows.domain.errors import InvalidNodeRunState, InvalidNodeRunTransition


class NodeRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class NodeRun:
    node_run_id: NodeRunId
    workflow_run_id: WorkflowRunId
    node_definition_id: NodeDefinitionId
    status: NodeRunStatus
    created_at: UtcTimestamp
    started_at: UtcTimestamp | None = None
    finished_at: UtcTimestamp | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.node_run_id, NodeRunId):
            raise InvalidNodeRunState("node_run_id must be a NodeRunId")
        if not isinstance(self.workflow_run_id, WorkflowRunId):
            raise InvalidNodeRunState("workflow_run_id must be a WorkflowRunId")
        if not isinstance(self.node_definition_id, NodeDefinitionId):
            raise InvalidNodeRunState("node_definition_id must be a NodeDefinitionId")
        if not isinstance(self.status, NodeRunStatus):
            raise InvalidNodeRunState("status must be a NodeRunStatus")
        created = required_timestamp(self.created_at, "created_at")
        started = timestamp(self.started_at, "started_at")
        finished = timestamp(self.finished_at, "finished_at")
        validate_order(created, started, finished)
        if self.status is NodeRunStatus.PENDING and started is not None:
            raise InvalidNodeRunState("started_at must be absent before RUNNING")
        if self.status is NodeRunStatus.RUNNING and started is None:
            raise InvalidNodeRunState("RUNNING requires started_at")
        if (
            self.status in {NodeRunStatus.SUCCEEDED, NodeRunStatus.FAILED}
            and started is None
        ):
            raise InvalidNodeRunState(
                "successful and failed terminal states require started_at"
            )
        if (
            self.status
            not in {
                NodeRunStatus.SUCCEEDED,
                NodeRunStatus.FAILED,
                NodeRunStatus.CANCELLED,
            }
            and finished is not None
        ):
            raise InvalidNodeRunState(
                "finished_at must be absent before a terminal state"
            )
        if (
            self.status
            in {
                NodeRunStatus.SUCCEEDED,
                NodeRunStatus.FAILED,
                NodeRunStatus.CANCELLED,
            }
            and finished is None
        ):
            raise InvalidNodeRunState("terminal states require finished_at")
        object.__setattr__(self, "created_at", created)
        object.__setattr__(self, "started_at", started)
        object.__setattr__(self, "finished_at", finished)

    def _transition(
        self, status: NodeRunStatus, at: datetime | None = None
    ) -> "NodeRun":
        allowed = {
            NodeRunStatus.PENDING: {NodeRunStatus.RUNNING, NodeRunStatus.CANCELLED},
            NodeRunStatus.RUNNING: {
                NodeRunStatus.SUCCEEDED,
                NodeRunStatus.FAILED,
                NodeRunStatus.CANCELLED,
            },
        }
        if status not in allowed.get(self.status, set()):
            raise InvalidNodeRunTransition(
                f"{self.status} cannot transition to {status}"
            )
        if at is None:
            raise InvalidNodeRunTransition(
                "a transition requires an explicit timestamp"
            )
        event_time = required_timestamp(at, "transition timestamp")
        started = event_time if status is NodeRunStatus.RUNNING else self.started_at
        finished = (
            event_time
            if status
            in {
                NodeRunStatus.SUCCEEDED,
                NodeRunStatus.FAILED,
                NodeRunStatus.CANCELLED,
            }
            else self.finished_at
        )
        return replace(self, status=status, started_at=started, finished_at=finished)

    def start(self, at: datetime) -> "NodeRun":
        return self._transition(NodeRunStatus.RUNNING, at)

    def succeed(self, at: datetime) -> "NodeRun":
        return self._transition(NodeRunStatus.SUCCEEDED, at)

    def fail(self, at: datetime) -> "NodeRun":
        return self._transition(NodeRunStatus.FAILED, at)

    def cancel(self, at: datetime) -> "NodeRun":
        return self._transition(NodeRunStatus.CANCELLED, at)
