"""Immutable facts recording concrete agent-definition invocations."""

from dataclasses import dataclass
from datetime import datetime

from aeos.agents.domain.errors import (
    InvalidAgentInvocation,
    InvalidInvocationTimestamp,
)
from aeos.core import (
    AgentDefinitionId,
    AgentInvocationId,
    TraceContext,
    UtcTimestamp,
    VersionRef,
    normalize_utc,
)


@dataclass(frozen=True, slots=True)
class AgentInvocation:
    """One immutable causal occurrence for one exact agent definition version."""

    agent_invocation_id: AgentInvocationId
    agent_definition_id: AgentDefinitionId
    agent_definition_version: VersionRef
    invoked_at: UtcTimestamp
    trace_context: TraceContext

    def __post_init__(self) -> None:
        if not isinstance(self.agent_invocation_id, AgentInvocationId):
            raise InvalidAgentInvocation(
                "agent_invocation_id must be an AgentInvocationId"
            )
        if not isinstance(self.agent_definition_id, AgentDefinitionId):
            raise InvalidAgentInvocation(
                "agent_definition_id must be an AgentDefinitionId"
            )
        if not isinstance(self.agent_definition_version, VersionRef):
            raise InvalidAgentInvocation(
                "agent_definition_version must be a VersionRef"
            )
        if not isinstance(self.invoked_at, datetime):
            raise InvalidInvocationTimestamp("invoked_at must be a datetime")
        try:
            timestamp = normalize_utc(self.invoked_at)
        except (AttributeError, TypeError, ValueError) as exc:
            raise InvalidInvocationTimestamp(
                "invoked_at must be a timezone-aware datetime"
            ) from exc
        if not isinstance(self.trace_context, TraceContext):
            raise InvalidAgentInvocation("trace_context must be a TraceContext")
        object.__setattr__(self, "invoked_at", timestamp)
