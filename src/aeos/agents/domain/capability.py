"""Minimal declarative capability value object for agent definitions."""

from dataclasses import dataclass

from aeos.agents.domain.errors import InvalidAgentCapability


@dataclass(frozen=True, slots=True)
class AgentCapability:
    """One conceptual capability declared by an agent definition.

    This declaration is not a permission grant, authorization decision, or
    promise that a runtime tool or provider is available.
    """

    identifier: str

    def __post_init__(self) -> None:
        if not isinstance(self.identifier, str):
            raise InvalidAgentCapability("capability identifier must be a string")
        identifier = self.identifier.strip()
        if not identifier:
            raise InvalidAgentCapability(
                "capability identifier must be a non-blank string"
            )
        object.__setattr__(self, "identifier", identifier)
