"""Minimal immutable domain-event metadata contract."""

from dataclasses import dataclass
from datetime import datetime

from aeos.core.actors import ActorRef
from aeos.core.ids import CausationId, CorrelationId, DomainEventId, IdempotencyKey
from aeos.core.time import normalize_utc


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Metadata-only fact contract; publication and persistence are out of scope."""

    event_id: DomainEventId
    event_type: str
    occurred_at: datetime
    actor: ActorRef
    correlation_id: CorrelationId
    causation_id: CausationId | None = None
    idempotency_key: IdempotencyKey | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.event_id, DomainEventId):
            raise ValueError("event_id must be a DomainEventId")
        if not isinstance(self.event_type, str) or not self.event_type.strip():
            raise ValueError("event_type must be a non-blank string")
        if not isinstance(self.occurred_at, datetime):
            raise ValueError("occurred_at must be a datetime")
        if not isinstance(self.actor, ActorRef):
            raise ValueError("actor must be an ActorRef")
        if not isinstance(self.correlation_id, CorrelationId):
            raise ValueError("correlation_id must be a CorrelationId")
        if self.causation_id is not None and not isinstance(
            self.causation_id, CausationId
        ):
            raise ValueError("causation_id must be a CausationId or None")
        if self.idempotency_key is not None and not isinstance(
            self.idempotency_key, IdempotencyKey
        ):
            raise ValueError("idempotency_key must be an IdempotencyKey or None")
        object.__setattr__(self, "event_type", self.event_type.strip())
        object.__setattr__(self, "occurred_at", normalize_utc(self.occurred_at))
