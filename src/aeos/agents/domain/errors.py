"""Narrow semantic errors for the Agents bounded context."""

from aeos.core.errors import DomainError


class InvalidAgentDefinition(DomainError):
    def __init__(self, message: str = "invalid agent definition") -> None:
        super().__init__("invalid_agent_definition", message)


class InvalidAgentName(DomainError):
    def __init__(self) -> None:
        super().__init__("invalid_agent_name", "agent name must be a non-blank string")


class InvalidAgentPurpose(DomainError):
    def __init__(self) -> None:
        super().__init__(
            "invalid_agent_purpose", "agent purpose must be a non-blank string"
        )


class InvalidAgentCapability(DomainError):
    def __init__(self, message: str = "invalid agent capability") -> None:
        super().__init__("invalid_agent_capability", message)


class EmptyAgentCapabilities(DomainError):
    def __init__(self) -> None:
        super().__init__(
            "empty_agent_capabilities",
            "agent definition must declare at least one capability",
        )


class DuplicateAgentCapability(DomainError):
    def __init__(self) -> None:
        super().__init__(
            "duplicate_agent_capability",
            "agent definition must not declare duplicate capabilities",
        )


class InvalidAgentInvocation(DomainError):
    def __init__(self, message: str = "invalid agent invocation") -> None:
        super().__init__("invalid_agent_invocation", message)


class InvalidInvocationTimestamp(DomainError):
    def __init__(self, message: str = "invalid agent invocation timestamp") -> None:
        super().__init__("invalid_invocation_timestamp", message)
