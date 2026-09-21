from dataclasses import FrozenInstanceError

import pytest

from aeos.core.actors import ActorKind, ActorRef
from aeos.core.ids import OrganizationId


@pytest.mark.parametrize("kind", list(ActorKind))
def test_actor_ref_supports_generic_actor_kinds(kind: ActorKind) -> None:
    actor = ActorRef(OrganizationId("actor-1"), kind)
    assert actor.actor_id == OrganizationId("actor-1")
    assert actor.kind is kind


def test_actor_ref_rejects_invalid_fields() -> None:
    with pytest.raises(ValueError):
        ActorRef("actor-1", ActorKind.SYSTEM)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        ActorRef(OrganizationId("actor-1"), "admin")  # type: ignore[arg-type]


def test_actor_ref_is_immutable() -> None:
    actor = ActorRef(OrganizationId("actor-1"), ActorKind.HUMAN)
    with pytest.raises(FrozenInstanceError):
        actor.kind = ActorKind.AGENT  # type: ignore[misc]
