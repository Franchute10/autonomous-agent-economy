from datetime import datetime, timezone
from decimal import Decimal

import pytest

from aeos.core import (
    ActorKind,
    ActorRef,
    AgentDefinitionId,
    CorrelationId,
    IdempotencyKey,
    OrganizationId,
    ResourceQuantity,
    TraceContext,
    VersionRef,
)
from aeos.infrastructure.persistence.types import (
    actor_from_values,
    actor_values,
    quantity_from_values,
    quantity_values,
    trace_from_values,
    trace_values,
)


def test_typed_id_version_quantity_and_trace_conversions_are_lossless() -> None:
    organization = OrganizationId("org-1")
    actor = ActorRef(AgentDefinitionId("agent-1"), ActorKind.AGENT)
    trace = TraceContext(actor, CorrelationId("corr-1"), IdempotencyKey("idem-1"))
    quantity = ResourceQuantity(Decimal("12.340000000000000001"), "tokens")

    actor_row = actor_values(actor)
    assert actor_from_values(*actor_row) == actor
    assert VersionRef("workflow", "2026.10").canonical == "workflow:2026.10"
    assert quantity_from_values(*quantity_values(quantity)) == quantity
    assert trace_from_values(trace_values(trace)) == trace
    assert datetime.now(timezone.utc).tzinfo is not None
    assert organization.value == "org-1"


def test_unknown_persisted_actor_id_type_is_rejected() -> None:
    with pytest.raises(ValueError, match="invalid persisted ActorRef"):
        actor_from_values("actor-1", "UnknownId", ActorKind.AGENT.value)
