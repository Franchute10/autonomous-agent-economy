from dataclasses import FrozenInstanceError
from typing import Any, cast

import pytest

from aeos.agents import (
    AgentCapability,
    AgentDefinition,
    DuplicateAgentCapability,
    EmptyAgentCapabilities,
    InvalidAgentDefinition,
    InvalidAgentName,
    InvalidAgentPurpose,
)
from aeos.core import AgentDefinitionId, OrganizationId, VersionRef


def make_definition(**overrides: Any) -> AgentDefinition:
    values: dict[str, Any] = {
        "agent_definition_id": AgentDefinitionId("agent-1"),
        "organization_id": OrganizationId("org-1"),
        "version_ref": VersionRef("agent:agent-1", "3"),
        "name": "  Research Analyst  ",
        "purpose": "  Produce structured research analysis  ",
        "capabilities": (AgentCapability("research.synthesis"),),
    }
    values.update(overrides)
    return AgentDefinition(**values)


def test_definition_preserves_exact_identity_version_and_order() -> None:
    first = AgentCapability("research.synthesis")
    second = AgentCapability("evidence.assessment")
    version = VersionRef("agent:agent-1", "3")

    definition = make_definition(
        version_ref=version,
        capabilities=(first, second),
    )

    assert definition.agent_definition_id == AgentDefinitionId("agent-1")
    assert definition.organization_id == OrganizationId("org-1")
    assert definition.version_ref is version
    assert definition.name == "Research Analyst"
    assert definition.purpose == "Produce structured research analysis"
    assert definition.capabilities == (first, second)


@pytest.mark.parametrize("field", ["name", "purpose"])
@pytest.mark.parametrize("value", ["", "   ", cast(str, 123)])
def test_definition_rejects_invalid_text(field: str, value: str) -> None:
    with pytest.raises((InvalidAgentName, InvalidAgentPurpose)):
        make_definition(**{field: value})


def test_definition_requires_typed_shared_kernel_values() -> None:
    with pytest.raises(InvalidAgentDefinition):
        make_definition(agent_definition_id=cast(AgentDefinitionId, object()))
    with pytest.raises(InvalidAgentDefinition):
        make_definition(organization_id=cast(OrganizationId, object()))
    with pytest.raises(InvalidAgentDefinition):
        make_definition(version_ref=cast(VersionRef, object()))


def test_definition_requires_strict_nonempty_tuple_without_duplicates() -> None:
    capability = AgentCapability("research.synthesis")

    with pytest.raises(InvalidAgentDefinition):
        make_definition(capabilities=cast(tuple[AgentCapability, ...], [capability]))
    with pytest.raises(EmptyAgentCapabilities):
        make_definition(capabilities=())
    with pytest.raises(DuplicateAgentCapability):
        make_definition(capabilities=(capability, capability))


def test_definition_is_immutable_and_does_not_embed_runtime_contracts() -> None:
    definition = make_definition()

    with pytest.raises(FrozenInstanceError):
        definition.name = "other"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        definition.capabilities += (AgentCapability("other"),)  # type: ignore[misc]
    assert not hasattr(definition, "is_authorized")
    assert not hasattr(definition, "provider")
    assert not hasattr(definition, "model_client")
