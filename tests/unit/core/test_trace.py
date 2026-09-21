from dataclasses import FrozenInstanceError

import pytest

from aeos.core.actors import ActorKind, ActorRef
from aeos.core.ids import (
    CausationId,
    CorrelationId,
    IdempotencyKey,
    OrganizationId,
)
from aeos.core.trace import TraceContext


def test_trace_context_supports_root_and_caused_operations() -> None:
    actor = ActorRef(OrganizationId("actor-1"), ActorKind.SYSTEM)
    correlation = CorrelationId("request-1")
    idempotency = IdempotencyKey("operation-1")
    root = TraceContext(actor, correlation, idempotency)
    caused = TraceContext(actor, correlation, idempotency, CausationId("operation-1"))
    assert root.causation_id is None
    assert caused.causation_id == CausationId("operation-1")
    assert root.idempotency_key == idempotency


def test_trace_context_requires_idempotency_key() -> None:
    with pytest.raises(TypeError):
        TraceContext(  # type: ignore[call-arg]
            ActorRef(OrganizationId("actor-1"), ActorKind.SYSTEM),
            CorrelationId("request-1"),
        )


def test_trace_context_is_immutable() -> None:
    context = TraceContext(
        ActorRef(OrganizationId("actor-1"), ActorKind.AGENT),
        CorrelationId("request-1"),
        IdempotencyKey("operation-1"),
    )
    with pytest.raises(FrozenInstanceError):
        context.correlation_id = CorrelationId("request-2")  # type: ignore[misc]
