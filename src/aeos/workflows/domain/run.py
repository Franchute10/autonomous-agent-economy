"""Immutable logical workflow execution state."""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from aeos.core import (
    OrganizationId,
    TraceContext,
    UtcTimestamp,
    WorkflowDefinitionId,
    WorkflowRunId,
)
from aeos.workflows.domain._lifecycle import (
    required_timestamp,
    timestamp,
    validate_order,
)
from aeos.workflows.domain.errors import (
    InvalidWorkflowRunState,
    InvalidWorkflowRunTransition,
)


class WorkflowRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class WorkflowRun:
    workflow_run_id: WorkflowRunId
    organization_id: OrganizationId
    workflow_definition_id: WorkflowDefinitionId
    status: WorkflowRunStatus
    created_at: UtcTimestamp
    started_at: UtcTimestamp | None = None
    finished_at: UtcTimestamp | None = None
    trace_context: TraceContext | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.workflow_run_id, WorkflowRunId):
            raise InvalidWorkflowRunState("workflow_run_id must be a WorkflowRunId")
        if not isinstance(self.organization_id, OrganizationId):
            raise InvalidWorkflowRunState("organization_id must be an OrganizationId")
        if not isinstance(self.workflow_definition_id, WorkflowDefinitionId):
            raise InvalidWorkflowRunState(
                "workflow_definition_id must be a WorkflowDefinitionId"
            )
        if not isinstance(self.status, WorkflowRunStatus):
            raise InvalidWorkflowRunState("status must be a WorkflowRunStatus")
        if self.trace_context is not None and not isinstance(
            self.trace_context, TraceContext
        ):
            raise InvalidWorkflowRunState(
                "trace_context must be a TraceContext or None"
            )
        created = required_timestamp(self.created_at, "created_at")
        started = timestamp(self.started_at, "started_at")
        finished = timestamp(self.finished_at, "finished_at")
        validate_order(created, started, finished)
        if self.status is WorkflowRunStatus.PENDING and started is not None:
            raise InvalidWorkflowRunState("started_at must be absent while PENDING")
        if self.status is WorkflowRunStatus.RUNNING and started is None:
            raise InvalidWorkflowRunState("RUNNING requires started_at")
        if (
            self.status in {WorkflowRunStatus.SUCCEEDED, WorkflowRunStatus.FAILED}
            and started is None
        ):
            raise InvalidWorkflowRunState(
                "successful and failed terminal states require started_at"
            )
        if (
            self.status
            not in {
                WorkflowRunStatus.SUCCEEDED,
                WorkflowRunStatus.FAILED,
                WorkflowRunStatus.CANCELLED,
            }
            and finished is not None
        ):
            raise InvalidWorkflowRunState(
                "finished_at must be absent before a terminal state"
            )
        if (
            self.status
            in {
                WorkflowRunStatus.SUCCEEDED,
                WorkflowRunStatus.FAILED,
                WorkflowRunStatus.CANCELLED,
            }
            and finished is None
        ):
            raise InvalidWorkflowRunState("terminal states require finished_at")
        object.__setattr__(self, "created_at", created)
        object.__setattr__(self, "started_at", started)
        object.__setattr__(self, "finished_at", finished)

    def _transition(
        self, status: WorkflowRunStatus, at: datetime | None = None
    ) -> "WorkflowRun":
        allowed = {
            WorkflowRunStatus.PENDING: {
                WorkflowRunStatus.RUNNING,
                WorkflowRunStatus.CANCELLED,
            },
            WorkflowRunStatus.RUNNING: {
                WorkflowRunStatus.SUCCEEDED,
                WorkflowRunStatus.FAILED,
                WorkflowRunStatus.CANCELLED,
            },
        }
        if status not in allowed.get(self.status, set()):
            raise InvalidWorkflowRunTransition(
                f"{self.status} cannot transition to {status}"
            )
        if at is None:
            raise InvalidWorkflowRunTransition(
                "a transition requires an explicit timestamp"
            )
        event_time = required_timestamp(at, "transition timestamp")
        started = event_time if status is WorkflowRunStatus.RUNNING else self.started_at
        finished = (
            event_time
            if status
            in {
                WorkflowRunStatus.SUCCEEDED,
                WorkflowRunStatus.FAILED,
                WorkflowRunStatus.CANCELLED,
            }
            else self.finished_at
        )
        return replace(self, status=status, started_at=started, finished_at=finished)

    def start(self, at: datetime) -> "WorkflowRun":
        return self._transition(WorkflowRunStatus.RUNNING, at)

    def succeed(self, at: datetime) -> "WorkflowRun":
        return self._transition(WorkflowRunStatus.SUCCEEDED, at)

    def fail(self, at: datetime) -> "WorkflowRun":
        return self._transition(WorkflowRunStatus.FAILED, at)

    def cancel(self, at: datetime) -> "WorkflowRun":
        return self._transition(WorkflowRunStatus.CANCELLED, at)
