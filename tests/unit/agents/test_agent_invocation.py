from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from typing import Any, cast

import pytest

from aeos.agents import (
    AgentInvocation,
    InvalidAgentInvocation,
    InvalidInvocationTimestamp,
)
from aeos.core import (
    ActorKind,
    ActorRef,
    AgentDefinitionId,
    AgentInvocationId,
    CorrelationId,
    IdempotencyKey,
    OrganizationId,
    TraceContext,
    VersionRef,
)


def trace() -> TraceContext:
    organization_id = OrganizationId("org-1")
    return TraceContext(
        actor=ActorRef(organization_id, ActorKind.SYSTEM),
        correlation_id=CorrelationId("request-1"),
        idempotency_key=IdempotencyKey("operation-1"),
    )


def make_invocation(**overrides: Any) -> AgentInvocation:
    values: dict[str, Any] = {
        "agent_invocation_id": AgentInvocationId("invocation-1"),
        "agent_definition_id": AgentDefinitionId("agent-1"),
        "agent_definition_version": VersionRef("agent:agent-1", "3"),
        "invoked_at": datetime(2026, 1, 1, 12, tzinfo=timezone.utc),
        "trace_context": trace(),
    }
    values.update(overrides)
    return AgentInvocation(**values)


def test_invocation_preserves_exact_reference_and_trace_context() -> None:
    version = VersionRef("agent:agent-1", "3")
    context = trace()
    invocation = make_invocation(
        agent_definition_version=version,
        trace_context=context,
    )

    assert invocation.agent_invocation_id == AgentInvocationId("invocation-1")
    assert invocation.agent_definition_id == AgentDefinitionId("agent-1")
    assert invocation.agent_definition_version is version
    assert invocation.invoked_at == datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    assert invocation.trace_context is context
    assert "organization_id" not in invocation.__dataclass_fields__


def test_invocation_normalizes_aware_non_utc_timestamp() -> None:
    invocation = make_invocation(
        invoked_at=datetime(2026, 1, 1, 15, tzinfo=timezone(timedelta(hours=3)))
    )

    assert invocation.invoked_at == datetime(2026, 1, 1, 12, tzinfo=timezone.utc)


def test_invocation_rejects_naive_or_non_datetime_timestamp() -> None:
    with pytest.raises(InvalidInvocationTimestamp):
        make_invocation(invoked_at=datetime(2026, 1, 1))
    with pytest.raises(InvalidInvocationTimestamp):
        make_invocation(invoked_at=cast(datetime, object()))


def test_invocation_requires_typed_values_and_trace_context() -> None:
    with pytest.raises(InvalidAgentInvocation):
        make_invocation(agent_invocation_id=cast(AgentInvocationId, object()))
    with pytest.raises(InvalidAgentInvocation):
        make_invocation(agent_definition_id=cast(AgentDefinitionId, object()))
    with pytest.raises(InvalidAgentInvocation):
        make_invocation(trace_context=cast(TraceContext, object()))


def test_invocation_is_immutable_and_has_no_lifecycle() -> None:
    invocation = make_invocation()

    with pytest.raises(FrozenInstanceError):
        invocation.invoked_at = datetime.now(timezone.utc)  # type: ignore[misc]
    assert not hasattr(invocation, "status")
    assert not hasattr(invocation, "model_invocation")
    assert not hasattr(invocation, "tool_invocation")
