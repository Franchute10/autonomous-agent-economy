from dataclasses import FrozenInstanceError
from typing import cast

import pytest

from aeos.agents import AgentCapability, InvalidAgentCapability


def test_capability_trims_identifier_and_is_hashable() -> None:
    capability = AgentCapability("  research.synthesis  ")

    assert capability.identifier == "research.synthesis"
    assert capability == AgentCapability("research.synthesis")
    assert hash(capability) == hash(AgentCapability("research.synthesis"))


@pytest.mark.parametrize("value", ["", "   ", cast(str, 123)])
def test_capability_rejects_nonblank_string_only(value: str) -> None:
    with pytest.raises(InvalidAgentCapability):
        AgentCapability(value)


def test_capability_is_immutable() -> None:
    capability = AgentCapability("research.synthesis")

    with pytest.raises(FrozenInstanceError):
        capability.identifier = "other"  # type: ignore[misc]


def test_capability_has_no_authorization_behavior() -> None:
    capability = AgentCapability("research.synthesis")

    assert not hasattr(capability, "is_authorized")
    assert not hasattr(capability, "can_execute")
    assert not hasattr(capability, "has_permission")
