"""Small immutable common trace metadata."""

from dataclasses import dataclass

from aeos.core.actors import ActorRef
from aeos.core.ids import CausationId, CorrelationId, IdempotencyKey


@dataclass(frozen=True, slots=True)
class TraceContext:
    """Common operation metadata; authorization and execution are out of scope."""

    actor: ActorRef
    correlation_id: CorrelationId
    idempotency_key: IdempotencyKey
    causation_id: CausationId | None = None
