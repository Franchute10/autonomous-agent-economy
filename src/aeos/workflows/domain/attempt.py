"""Immutable concrete node execution attempt state."""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from aeos.core import NodeAttemptId, NodeRunId, TraceContext, UtcTimestamp
from aeos.workflows.domain._lifecycle import (
    required_timestamp,
    timestamp,
    validate_order,
)
from aeos.workflows.domain.errors import (
    InvalidAttemptNumber,
    InvalidNodeAttemptState,
    InvalidNodeAttemptTransition,
)


class NodeAttemptStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class NodeAttempt:
    node_attempt_id: NodeAttemptId
    node_run_id: NodeRunId
    attempt_number: int
    status: NodeAttemptStatus
    created_at: UtcTimestamp
    started_at: UtcTimestamp | None = None
    finished_at: UtcTimestamp | None = None
    trace_context: TraceContext | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.node_attempt_id, NodeAttemptId):
            raise InvalidNodeAttemptState("node_attempt_id must be a NodeAttemptId")
        if not isinstance(self.node_run_id, NodeRunId):
            raise InvalidNodeAttemptState("node_run_id must be a NodeRunId")
        if isinstance(self.attempt_number, bool) or not isinstance(
            self.attempt_number, int
        ):
            raise InvalidAttemptNumber()
        if self.attempt_number < 1:
            raise InvalidAttemptNumber()
        if not isinstance(self.status, NodeAttemptStatus):
            raise InvalidNodeAttemptState("status must be a NodeAttemptStatus")
        if self.trace_context is not None and not isinstance(
            self.trace_context, TraceContext
        ):
            raise InvalidNodeAttemptState(
                "trace_context must be a TraceContext or None"
            )
        created = required_timestamp(self.created_at, "created_at")
        started = timestamp(self.started_at, "started_at")
        finished = timestamp(self.finished_at, "finished_at")
        validate_order(created, started, finished)
        if self.status is NodeAttemptStatus.PENDING and started is not None:
            raise InvalidNodeAttemptState("started_at must be absent while PENDING")
        if self.status is NodeAttemptStatus.RUNNING and started is None:
            raise InvalidNodeAttemptState("RUNNING requires started_at")
        if (
            self.status in {NodeAttemptStatus.SUCCEEDED, NodeAttemptStatus.FAILED}
            and started is None
        ):
            raise InvalidNodeAttemptState(
                "successful and failed terminal states require started_at"
            )
        if (
            self.status
            not in {
                NodeAttemptStatus.SUCCEEDED,
                NodeAttemptStatus.FAILED,
                NodeAttemptStatus.CANCELLED,
            }
            and finished is not None
        ):
            raise InvalidNodeAttemptState(
                "finished_at must be absent before a terminal state"
            )
        if (
            self.status
            in {
                NodeAttemptStatus.SUCCEEDED,
                NodeAttemptStatus.FAILED,
                NodeAttemptStatus.CANCELLED,
            }
            and finished is None
        ):
            raise InvalidNodeAttemptState("terminal states require finished_at")
        object.__setattr__(self, "created_at", created)
        object.__setattr__(self, "started_at", started)
        object.__setattr__(self, "finished_at", finished)

    def _transition(self, status: NodeAttemptStatus, at: datetime) -> "NodeAttempt":
        allowed = {
            NodeAttemptStatus.PENDING: {
                NodeAttemptStatus.RUNNING,
                NodeAttemptStatus.CANCELLED,
            },
            NodeAttemptStatus.RUNNING: {
                NodeAttemptStatus.SUCCEEDED,
                NodeAttemptStatus.FAILED,
                NodeAttemptStatus.CANCELLED,
            },
        }
        if status not in allowed.get(self.status, set()):
            raise InvalidNodeAttemptTransition(
                f"{self.status} cannot transition to {status}"
            )
        event_time = required_timestamp(at, "transition timestamp")
        started = event_time if status is NodeAttemptStatus.RUNNING else self.started_at
        finished = (
            event_time
            if status
            in {
                NodeAttemptStatus.SUCCEEDED,
                NodeAttemptStatus.FAILED,
                NodeAttemptStatus.CANCELLED,
            }
            else self.finished_at
        )
        return replace(self, status=status, started_at=started, finished_at=finished)

    def start(self, at: datetime) -> "NodeAttempt":
        return self._transition(NodeAttemptStatus.RUNNING, at)

    def succeed(self, at: datetime) -> "NodeAttempt":
        return self._transition(NodeAttemptStatus.SUCCEEDED, at)

    def fail(self, at: datetime) -> "NodeAttempt":
        return self._transition(NodeAttemptStatus.FAILED, at)

    def cancel(self, at: datetime) -> "NodeAttempt":
        return self._transition(NodeAttemptStatus.CANCELLED, at)
