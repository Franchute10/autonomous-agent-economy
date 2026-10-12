"""Immutable declarative agent definitions."""

from dataclasses import dataclass

from aeos.agents.domain.capability import AgentCapability
from aeos.agents.domain.errors import (
    DuplicateAgentCapability,
    EmptyAgentCapabilities,
    InvalidAgentDefinition,
    InvalidAgentName,
    InvalidAgentPurpose,
)
from aeos.core import AgentDefinitionId, OrganizationId, VersionRef


@dataclass(frozen=True, slots=True)
class AgentDefinition:
    """One exact immutable version of an organization's agent definition."""

    agent_definition_id: AgentDefinitionId
    organization_id: OrganizationId
    version_ref: VersionRef
    name: str
    purpose: str
    capabilities: tuple[AgentCapability, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.agent_definition_id, AgentDefinitionId):
            raise InvalidAgentDefinition(
                "agent_definition_id must be an AgentDefinitionId"
            )
        if not isinstance(self.organization_id, OrganizationId):
            raise InvalidAgentDefinition("organization_id must be an OrganizationId")
        if not isinstance(self.version_ref, VersionRef):
            raise InvalidAgentDefinition("version_ref must be a VersionRef")
        if not isinstance(self.name, str) or not self.name.strip():
            raise InvalidAgentName()
        if not isinstance(self.purpose, str) or not self.purpose.strip():
            raise InvalidAgentPurpose()
        if not isinstance(self.capabilities, tuple):
            raise InvalidAgentDefinition("capabilities must be a tuple")
        if not self.capabilities:
            raise EmptyAgentCapabilities()
        if any(not isinstance(value, AgentCapability) for value in self.capabilities):
            raise InvalidAgentDefinition(
                "capabilities must contain only AgentCapability values"
            )
        if len(set(self.capabilities)) != len(self.capabilities):
            raise DuplicateAgentCapability()
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "purpose", self.purpose.strip())
