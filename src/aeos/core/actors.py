"""Actor identity metadata without authorization semantics."""

from dataclasses import dataclass
from enum import StrEnum

from aeos.core.ids import _AeosId


class ActorKind(StrEnum):
    HUMAN = "human"
    AGENT = "agent"
    SYSTEM = "system"


@dataclass(frozen=True, slots=True)
class ActorRef:
    """Identifies who acted; it does not express authority or permissions."""

    actor_id: _AeosId
    kind: ActorKind

    def __post_init__(self) -> None:
        if not isinstance(self.actor_id, _AeosId):
            raise ValueError("actor_id must be a non-blank AEOS ID")
        if not isinstance(self.kind, ActorKind):
            raise ValueError("kind must be an ActorKind")
