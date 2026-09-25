from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Any, cast

import pytest

from aeos.core import NodeAttemptId, NodeDefinitionId, NodeRunId, OrganizationId
from aeos.core import WorkflowDefinitionId, WorkflowRunId
from aeos.core import ActorKind, ActorRef, CorrelationId, IdempotencyKey, TraceContext
from aeos.workflows import (
    InvalidAttemptNumber,
    InvalidLifecycleTimestamp,
    InvalidNodeAttemptState,
    InvalidNodeAttemptTransition,
    InvalidNodeRunState,
    InvalidNodeRunTransition,
    InvalidWorkflowRunState,
    InvalidWorkflowRunTransition,
    NodeAttempt,
    NodeAttemptStatus,
    NodeRun,
    NodeRunStatus,
    WorkflowRun,
    WorkflowRunStatus,
)


def dt(hour: int) -> datetime:
    return datetime(2026, 1, 1, hour, tzinfo=timezone.utc)


def workflow_run(
    status: WorkflowRunStatus = WorkflowRunStatus.PENDING, **kwargs: object
) -> WorkflowRun:
    return WorkflowRun(
        WorkflowRunId("wr-1"),
        OrganizationId("org-1"),
        WorkflowDefinitionId("wd-1"),
        status,
        cast(datetime, kwargs.pop("created_at", dt(0))),
        **kwargs,  # type: ignore[arg-type]
    )


def node_run(
    status: NodeRunStatus = NodeRunStatus.PENDING, **kwargs: object
) -> NodeRun:
    return NodeRun(
        NodeRunId("nr-1"),
        WorkflowRunId("wr-1"),
        NodeDefinitionId("nd-1"),
        status,
        cast(datetime, kwargs.pop("created_at", dt(0))),
        **kwargs,  # type: ignore[arg-type]
    )


def attempt(
    status: NodeAttemptStatus = NodeAttemptStatus.PENDING, **kwargs: object
) -> NodeAttempt:
    return NodeAttempt(
        NodeAttemptId("na-1"),
        NodeRunId("nr-1"),
        cast(int, kwargs.pop("attempt_number", 1)),
        status,
        cast(datetime, kwargs.pop("created_at", dt(0))),
        **kwargs,  # type: ignore[arg-type]
    )


def test_status_enums_are_exactly_minimal() -> None:
    assert set(WorkflowRunStatus) == {
        WorkflowRunStatus.PENDING,
        WorkflowRunStatus.RUNNING,
        WorkflowRunStatus.SUCCEEDED,
        WorkflowRunStatus.FAILED,
        WorkflowRunStatus.CANCELLED,
    }
    assert set(NodeRunStatus) == {
        NodeRunStatus.PENDING,
        NodeRunStatus.RUNNING,
        NodeRunStatus.SUCCEEDED,
        NodeRunStatus.FAILED,
        NodeRunStatus.CANCELLED,
    }
    assert set(NodeAttemptStatus) == {
        NodeAttemptStatus.PENDING,
        NodeAttemptStatus.RUNNING,
        NodeAttemptStatus.SUCCEEDED,
        NodeAttemptStatus.FAILED,
        NodeAttemptStatus.CANCELLED,
    }


@pytest.mark.parametrize("factory", [workflow_run, node_run, attempt])
def test_pending_construction_and_immutability(factory: object) -> None:
    value = cast(Any, factory)()
    assert value.status.name == "PENDING"
    with pytest.raises(AttributeError):
        value.status = value.status


def test_workflow_run_lifecycle_and_terminal_protection() -> None:
    original = workflow_run()
    running = original.start(dt(1))
    succeeded = running.succeed(dt(2))
    assert original.status is WorkflowRunStatus.PENDING
    assert running.started_at == dt(1)
    assert succeeded.finished_at == dt(2)
    assert succeeded is not running
    with pytest.raises(InvalidWorkflowRunTransition):
        succeeded.cancel(dt(3))
    assert workflow_run().cancel(dt(1)).started_at is None


def test_node_run_lifecycle_and_terminal_protection() -> None:
    original = node_run()
    running = original.start(dt(1))
    failed = running.fail(dt(2))
    assert original.status is NodeRunStatus.PENDING
    assert failed.status is NodeRunStatus.FAILED
    with pytest.raises(InvalidNodeRunTransition):
        failed.start(dt(3))
    assert not hasattr(original, "attempts")


def test_attempt_lifecycle_and_no_retry_creation() -> None:
    original = attempt()
    failed = original.start(dt(1)).fail(dt(2))
    assert original.status is NodeAttemptStatus.PENDING
    assert failed.status is NodeAttemptStatus.FAILED
    with pytest.raises(InvalidNodeAttemptTransition):
        failed.start(dt(3))


@pytest.mark.parametrize("value", [0, -1, True, False, 1.0, "1", None])
def test_attempt_number_is_strict(value: object) -> None:
    with pytest.raises(InvalidAttemptNumber):
        attempt(attempt_number=value)


@pytest.mark.parametrize("factory", [workflow_run, node_run, attempt])
def test_naive_timestamps_are_rejected(factory: object) -> None:
    with pytest.raises(InvalidLifecycleTimestamp):
        cast(Any, factory)(created_at=datetime(2026, 1, 1))


def test_non_utc_timestamps_are_normalized() -> None:
    value = attempt(
        created_at=datetime(2026, 1, 1, 2, tzinfo=timezone(timedelta(hours=2)))
    )
    assert value.created_at == datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "factory, status, fields, error",
    [
        (
            workflow_run,
            WorkflowRunStatus.PENDING,
            {"started_at": dt(1)},
            InvalidWorkflowRunState,
        ),
        (
            workflow_run,
            WorkflowRunStatus.PENDING,
            {"finished_at": dt(1)},
            InvalidWorkflowRunState,
        ),
        (workflow_run, WorkflowRunStatus.RUNNING, {}, InvalidWorkflowRunState),
        (
            workflow_run,
            WorkflowRunStatus.RUNNING,
            {"started_at": dt(1), "finished_at": dt(2)},
            InvalidWorkflowRunState,
        ),
        (
            workflow_run,
            WorkflowRunStatus.SUCCEEDED,
            {"finished_at": dt(2)},
            InvalidWorkflowRunState,
        ),
        (
            workflow_run,
            WorkflowRunStatus.FAILED,
            {"finished_at": dt(2)},
            InvalidWorkflowRunState,
        ),
        (
            workflow_run,
            WorkflowRunStatus.SUCCEEDED,
            {"started_at": dt(1)},
            InvalidWorkflowRunState,
        ),
        (
            workflow_run,
            WorkflowRunStatus.FAILED,
            {"started_at": dt(1)},
            InvalidWorkflowRunState,
        ),
        (
            workflow_run,
            WorkflowRunStatus.CANCELLED,
            {},
            InvalidWorkflowRunState,
        ),
        (node_run, NodeRunStatus.PENDING, {"started_at": dt(1)}, InvalidNodeRunState),
        (node_run, NodeRunStatus.PENDING, {"finished_at": dt(1)}, InvalidNodeRunState),
        (node_run, NodeRunStatus.RUNNING, {}, InvalidNodeRunState),
        (
            node_run,
            NodeRunStatus.RUNNING,
            {"started_at": dt(1), "finished_at": dt(2)},
            InvalidNodeRunState,
        ),
        (
            node_run,
            NodeRunStatus.SUCCEEDED,
            {"finished_at": dt(2)},
            InvalidNodeRunState,
        ),
        (
            node_run,
            NodeRunStatus.FAILED,
            {"finished_at": dt(2)},
            InvalidNodeRunState,
        ),
        (
            node_run,
            NodeRunStatus.SUCCEEDED,
            {"started_at": dt(1)},
            InvalidNodeRunState,
        ),
        (
            node_run,
            NodeRunStatus.FAILED,
            {"started_at": dt(1)},
            InvalidNodeRunState,
        ),
        (node_run, NodeRunStatus.CANCELLED, {}, InvalidNodeRunState),
        (
            attempt,
            NodeAttemptStatus.PENDING,
            {"finished_at": dt(1)},
            InvalidNodeAttemptState,
        ),
        (attempt, NodeAttemptStatus.RUNNING, {}, InvalidNodeAttemptState),
        (
            attempt,
            NodeAttemptStatus.RUNNING,
            {"started_at": dt(1), "finished_at": dt(2)},
            InvalidNodeAttemptState,
        ),
        (
            attempt,
            NodeAttemptStatus.SUCCEEDED,
            {"finished_at": dt(2)},
            InvalidNodeAttemptState,
        ),
        (
            attempt,
            NodeAttemptStatus.FAILED,
            {"finished_at": dt(2)},
            InvalidNodeAttemptState,
        ),
        (
            attempt,
            NodeAttemptStatus.SUCCEEDED,
            {"started_at": dt(1)},
            InvalidNodeAttemptState,
        ),
        (
            attempt,
            NodeAttemptStatus.FAILED,
            {"started_at": dt(1)},
            InvalidNodeAttemptState,
        ),
        (attempt, NodeAttemptStatus.CANCELLED, {}, InvalidNodeAttemptState),
    ],
)
def test_direct_state_timestamp_invariants(
    factory: object, status: StrEnum, fields: dict[str, object], error: type[Exception]
) -> None:
    with pytest.raises(error):
        cast(Any, factory)(status=status, **fields)


@pytest.mark.parametrize("factory", [workflow_run, node_run, attempt])
def test_cancelled_without_start_is_valid(factory: object) -> None:
    statuses = cast(
        Any,
        {
            workflow_run: WorkflowRunStatus.CANCELLED,
            node_run: NodeRunStatus.CANCELLED,
            attempt: NodeAttemptStatus.CANCELLED,
        },
    )
    status = statuses[factory]
    value = cast(Any, factory)(status=status, finished_at=dt(1))
    assert value.started_at is None
    assert value.finished_at == dt(1)


@pytest.mark.parametrize("factory", [workflow_run, node_run, attempt])
def test_timestamp_ordering_is_non_decreasing(factory: object) -> None:
    statuses = cast(
        Any,
        {
            workflow_run: (
                WorkflowRunStatus.RUNNING,
                WorkflowRunStatus.CANCELLED,
                WorkflowRunStatus.SUCCEEDED,
            ),
            node_run: (
                NodeRunStatus.RUNNING,
                NodeRunStatus.CANCELLED,
                NodeRunStatus.SUCCEEDED,
            ),
            attempt: (
                NodeAttemptStatus.RUNNING,
                NodeAttemptStatus.CANCELLED,
                NodeAttemptStatus.SUCCEEDED,
            ),
        },
    )
    status = statuses[factory]
    with pytest.raises(InvalidLifecycleTimestamp):
        cast(Any, factory)(status=status[0], created_at=dt(2), started_at=dt(1))
    with pytest.raises(InvalidLifecycleTimestamp):
        cast(Any, factory)(status=status[1], created_at=dt(2), finished_at=dt(1))
    with pytest.raises(InvalidLifecycleTimestamp):
        cast(Any, factory)(
            status=status[2], created_at=dt(0), started_at=dt(2), finished_at=dt(1)
        )
    if factory is workflow_run:
        value = cast(
            Any,
            WorkflowRun(
                WorkflowRunId("wr"),
                OrganizationId("org"),
                WorkflowDefinitionId("wd"),
                WorkflowRunStatus.SUCCEEDED,
                dt(1),
                dt(1),
                dt(1),
            ),
        )
    elif factory is node_run:
        value = cast(
            Any,
            NodeRun(
                NodeRunId("nr"),
                WorkflowRunId("wr"),
                NodeDefinitionId("nd"),
                NodeRunStatus.SUCCEEDED,
                dt(1),
                dt(1),
                dt(1),
            ),
        )
    else:
        value = cast(
            Any,
            NodeAttempt(
                NodeAttemptId("na"),
                NodeRunId("nr"),
                1,
                NodeAttemptStatus.SUCCEEDED,
                dt(1),
                dt(1),
                dt(1),
            ),
        )
    assert value.started_at == value.created_at == value.finished_at


def test_transition_timestamps_reapply_invariants() -> None:
    for value in (workflow_run(), node_run(), attempt()):
        with pytest.raises(InvalidLifecycleTimestamp):
            value.start(datetime(2025, 12, 31, 23, tzinfo=timezone.utc))
        running = value.start(dt(1))
        with pytest.raises(InvalidLifecycleTimestamp):
            if isinstance(running, WorkflowRun):
                running.succeed(dt(0))
            elif isinstance(running, NodeRun):
                running.succeed(dt(0))
            else:
                running.succeed(dt(0))
        with pytest.raises(InvalidLifecycleTimestamp):
            value.start(datetime(2026, 1, 1))
        normalized = value.start(
            datetime(2026, 1, 1, 2, tzinfo=timezone(timedelta(hours=2)))
        )
        assert normalized.started_at == dt(0)


def test_trace_context_is_validated_where_present() -> None:
    trace = TraceContext(
        ActorRef(OrganizationId("actor"), ActorKind.SYSTEM),
        CorrelationId("correlation"),
        IdempotencyKey("idempotency"),
    )
    assert workflow_run(trace_context=trace).trace_context is trace
    assert attempt(trace_context=trace).trace_context is trace
    with pytest.raises(InvalidWorkflowRunState):
        workflow_run(trace_context=cast(Any, object()))
    with pytest.raises(InvalidNodeAttemptState):
        attempt(trace_context=cast(Any, object()))


def test_wrong_typed_ids_and_statuses_are_rejected() -> None:
    with pytest.raises(InvalidWorkflowRunState):
        WorkflowRun(
            cast(Any, NodeRunId("wrong")),
            OrganizationId("org-1"),
            WorkflowDefinitionId("wd-1"),
            WorkflowRunStatus.PENDING,
            dt(0),
        )
    with pytest.raises(InvalidNodeRunState):
        NodeRun(
            NodeRunId("nr-1"),
            WorkflowRunId("wr-1"),
            cast(Any, NodeRunId("wrong")),
            NodeRunStatus.PENDING,
            dt(0),
        )
    with pytest.raises(InvalidWorkflowRunState):
        WorkflowRun(
            WorkflowRunId("wr"),
            cast(Any, NodeRunId("wrong")),
            WorkflowDefinitionId("wd"),
            WorkflowRunStatus.PENDING,
            dt(0),
        )
    with pytest.raises(InvalidWorkflowRunState):
        WorkflowRun(
            WorkflowRunId("wr"),
            OrganizationId("org"),
            cast(Any, NodeRunId("wrong")),
            WorkflowRunStatus.PENDING,
            dt(0),
        )
    with pytest.raises(InvalidNodeRunState):
        NodeRun(
            NodeRunId("nr"),
            cast(Any, NodeRunId("wrong")),
            NodeDefinitionId("nd"),
            NodeRunStatus.PENDING,
            dt(0),
        )
    with pytest.raises(InvalidNodeRunState):
        NodeRun(
            NodeRunId("nr"),
            WorkflowRunId("wr"),
            cast(Any, NodeRunId("wrong")),
            NodeRunStatus.PENDING,
            dt(0),
        )
    with pytest.raises(InvalidNodeAttemptState):
        NodeAttempt(
            cast(Any, NodeRunId("wrong")),
            NodeRunId("nr"),
            1,
            NodeAttemptStatus.PENDING,
            dt(0),
        )
    with pytest.raises(InvalidNodeAttemptState):
        NodeAttempt(
            NodeAttemptId("na"),
            cast(Any, WorkflowRunId("wrong")),
            1,
            NodeAttemptStatus.PENDING,
            dt(0),
        )
    with pytest.raises(InvalidNodeAttemptState):
        attempt(status=cast(NodeAttemptStatus, "pending"))
