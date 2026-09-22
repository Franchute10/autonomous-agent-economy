from datetime import datetime, timedelta, timezone

import pytest

from aeos.core import (
    ActorKind,
    ActorRef,
    CausationId,
    CorrelationId,
    DomainEvent,
    DomainEventId,
    IdempotencyKey,
    OrganizationId,
)


def _event(**overrides: object) -> DomainEvent:
    values: dict[str, object] = {
        "event_id": DomainEventId("event-1"),
        "event_type": "workflow.node_succeeded",
        "occurred_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "actor": ActorRef(OrganizationId("org-1"), ActorKind.SYSTEM),
        "correlation_id": CorrelationId("correlation-1"),
        "causation_id": CausationId("cause-1"),
        "idempotency_key": IdempotencyKey("idempotency-1"),
    }
    values.update(overrides)
    return DomainEvent(**values)  # type: ignore[arg-type]


def test_domain_event_preserves_trace_metadata_and_normalizes_utc() -> None:
    occurred_at = datetime(2026, 1, 1, 1, tzinfo=timezone.utc)
    event = _event(occurred_at=occurred_at)
    assert event.event_id == DomainEventId("event-1")
    assert event.event_type == "workflow.node_succeeded"
    assert event.occurred_at == occurred_at
    assert event.actor.actor_id == OrganizationId("org-1")
    assert event.correlation_id == CorrelationId("correlation-1")
    assert event.causation_id == CausationId("cause-1")
    assert event.idempotency_key == IdempotencyKey("idempotency-1")


def test_domain_event_normalizes_aware_non_utc_timestamp() -> None:
    non_utc = _event(
        occurred_at=datetime(2026, 1, 1, 3, tzinfo=timezone(timedelta(hours=2)))
    )
    assert non_utc.occurred_at == datetime(2026, 1, 1, 1, tzinfo=timezone.utc)


def test_root_event_can_omit_causation() -> None:
    assert _event(causation_id=None).causation_id is None
    assert _event(idempotency_key=None).idempotency_key is None


@pytest.mark.parametrize("event_type", ["", " "])
def test_domain_event_rejects_blank_type(event_type: str) -> None:
    with pytest.raises(ValueError):
        _event(event_type=event_type)


def test_domain_event_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError):
        _event(occurred_at=datetime(2026, 1, 1))


def test_domain_event_rejects_non_datetime_timestamp() -> None:
    with pytest.raises(ValueError):
        _event(occurred_at="2026-01-01T00:00:00Z")


@pytest.mark.parametrize(
    "field, value",
    [
        ("actor", "not-an-actor"),
        ("correlation_id", "not-a-correlation-id"),
        ("causation_id", "not-a-causation-id"),
        ("idempotency_key", "not-an-idempotency-key"),
    ],
)
def test_domain_event_rejects_invalid_trace_types(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        _event(**{field: value})


def test_domain_event_is_immutable() -> None:
    event = _event()
    with pytest.raises(AttributeError):
        event.event_type = "changed"  # type: ignore[misc]
