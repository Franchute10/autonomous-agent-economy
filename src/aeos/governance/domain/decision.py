"""Normalized governance results without evaluation or enforcement behavior."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from aeos.core import (
    ActorRef,
    GovernanceDecisionId,
    OrganizationId,
    TraceContext,
    VersionRef,
)
from aeos.core.time import UtcTimestamp, normalize_utc
from aeos.governance.domain.errors import InvalidGovernanceDecisionReason


class GovernanceDecisionResult(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


@dataclass(frozen=True, slots=True)
class GovernanceDecision:
    """An immutable normalized result produced by governance evaluation elsewhere."""

    governance_decision_id: GovernanceDecisionId
    organization_id: OrganizationId
    result: GovernanceDecisionResult
    reason: str
    constitution_version: VersionRef
    policy_versions: tuple[VersionRef, ...]
    trace: TraceContext
    decided_at: UtcTimestamp
    evaluated_actor: ActorRef | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.governance_decision_id, GovernanceDecisionId):
            raise ValueError("governance_decision_id must be a GovernanceDecisionId")
        if not isinstance(self.organization_id, OrganizationId):
            raise ValueError("organization_id must be an OrganizationId")
        if not isinstance(self.result, GovernanceDecisionResult):
            raise ValueError("result must be a GovernanceDecisionResult")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise InvalidGovernanceDecisionReason()
        if not isinstance(self.constitution_version, VersionRef):
            raise ValueError("constitution_version must be a VersionRef")
        if not isinstance(self.policy_versions, tuple) or not all(
            isinstance(reference, VersionRef) for reference in self.policy_versions
        ):
            raise ValueError("policy_versions must be a tuple of VersionRef")
        if not isinstance(self.trace, TraceContext):
            raise ValueError("trace must be a TraceContext")
        if self.evaluated_actor is not None and not isinstance(
            self.evaluated_actor, ActorRef
        ):
            raise ValueError("evaluated_actor must be an ActorRef or None")
        if not isinstance(self.decided_at, datetime):
            raise ValueError("decided_at must be a datetime")
        object.__setattr__(self, "decided_at", normalize_utc(self.decided_at))
