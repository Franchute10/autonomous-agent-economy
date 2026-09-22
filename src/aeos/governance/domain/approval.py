"""Approval request and immutable decision state models."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from aeos.core import (
    ActorRef,
    ApprovalDecisionId,
    ApprovalRequestId,
    GovernanceDecisionId,
    OrganizationId,
    RoleId,
    TraceContext,
    UtcTimestamp,
    VersionRef,
    normalize_utc,
)
from aeos.governance.domain.errors import (
    ApprovalOrganizationMismatch,
    ApprovalRequestMismatch,
    InvalidApprovalDecisionReason,
    InvalidApprovalRequestPeriod,
    InvalidApprovalRequestReason,
    InvalidApprovalTransition,
)
from aeos.governance.domain.permission import PermissionCapability


class ApprovalRequestState(StrEnum):
    PENDING = "pending"
    DECIDED = "decided"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ApprovalDecisionResult(StrEnum):
    APPROVE = "approve"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class ApprovalDecision:
    """One immutable decision fact; recording an actor does not prove authority."""

    approval_decision_id: ApprovalDecisionId
    approval_request_id: ApprovalRequestId
    organization_id: OrganizationId
    decision: ApprovalDecisionResult
    decided_by: ActorRef
    reason: str
    decided_at: UtcTimestamp
    constitution_version: VersionRef | None
    policy_versions: tuple[VersionRef, ...]
    trace: TraceContext

    def __post_init__(self) -> None:
        if not isinstance(self.approval_decision_id, ApprovalDecisionId):
            raise ValueError("approval_decision_id must be an ApprovalDecisionId")
        if not isinstance(self.approval_request_id, ApprovalRequestId):
            raise ValueError("approval_request_id must be an ApprovalRequestId")
        if not isinstance(self.organization_id, OrganizationId):
            raise ValueError("organization_id must be an OrganizationId")
        if not isinstance(self.decision, ApprovalDecisionResult):
            raise ValueError("decision must be an ApprovalDecisionResult")
        if not isinstance(self.decided_by, ActorRef):
            raise ValueError("decided_by must be an ActorRef")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise InvalidApprovalDecisionReason()
        if not isinstance(self.decided_at, datetime):
            raise ValueError("decided_at must be a datetime")
        if self.constitution_version is not None and not isinstance(
            self.constitution_version, VersionRef
        ):
            raise ValueError("constitution_version must be a VersionRef or None")
        if not isinstance(self.policy_versions, tuple) or not all(
            isinstance(version, VersionRef) for version in self.policy_versions
        ):
            raise ValueError("policy_versions must be a tuple of VersionRef")
        if not isinstance(self.trace, TraceContext):
            raise ValueError("trace must be a TraceContext")
        object.__setattr__(self, "decided_at", normalize_utc(self.decided_at))


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    """A concrete approval request with controlled, explicit lifecycle state."""

    approval_request_id: ApprovalRequestId
    organization_id: OrganizationId
    requester: ActorRef
    capability: PermissionCapability
    reason: str
    requested_at: UtcTimestamp
    expires_at: UtcTimestamp | None
    constitution_version: VersionRef | None
    policy_versions: tuple[VersionRef, ...]
    governance_decision_id: GovernanceDecisionId | None
    required_role_id: RoleId | None
    trace: TraceContext
    _state: ApprovalRequestState = field(
        default=ApprovalRequestState.PENDING, init=False, repr=False
    )

    def __post_init__(self) -> None:
        if not isinstance(self.approval_request_id, ApprovalRequestId):
            raise ValueError("approval_request_id must be an ApprovalRequestId")
        if not isinstance(self.organization_id, OrganizationId):
            raise ValueError("organization_id must be an OrganizationId")
        if not isinstance(self.requester, ActorRef):
            raise ValueError("requester must be an ActorRef")
        if not isinstance(self.capability, PermissionCapability):
            raise ValueError("capability must be a PermissionCapability")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise InvalidApprovalRequestReason()
        if not isinstance(self.requested_at, datetime):
            raise ValueError("requested_at must be a datetime")
        if self.expires_at is not None and not isinstance(self.expires_at, datetime):
            raise ValueError("expires_at must be a datetime or None")
        if self.constitution_version is not None and not isinstance(
            self.constitution_version, VersionRef
        ):
            raise ValueError("constitution_version must be a VersionRef or None")
        if not isinstance(self.policy_versions, tuple) or not all(
            isinstance(version, VersionRef) for version in self.policy_versions
        ):
            raise ValueError("policy_versions must be a tuple of VersionRef")
        if self.governance_decision_id is not None and not isinstance(
            self.governance_decision_id, GovernanceDecisionId
        ):
            raise ValueError("governance_decision_id must be a GovernanceDecisionId")
        if self.required_role_id is not None and not isinstance(
            self.required_role_id, RoleId
        ):
            raise ValueError("required_role_id must be a RoleId")
        if not isinstance(self.trace, TraceContext):
            raise ValueError("trace must be a TraceContext")
        requested = normalize_utc(self.requested_at)
        expires = None if self.expires_at is None else normalize_utc(self.expires_at)
        if expires is not None and expires < requested:
            raise InvalidApprovalRequestPeriod()
        object.__setattr__(self, "requested_at", requested)
        object.__setattr__(self, "expires_at", expires)

    @property
    def state(self) -> ApprovalRequestState:
        return self._state

    def record_decision(self, decision: ApprovalDecision) -> None:
        if not isinstance(decision, ApprovalDecision):
            raise ValueError("decision must be an ApprovalDecision")
        if self.state is not ApprovalRequestState.PENDING:
            raise InvalidApprovalTransition(self.state.value)
        if decision.approval_request_id != self.approval_request_id:
            raise ApprovalRequestMismatch()
        if decision.organization_id != self.organization_id:
            raise ApprovalOrganizationMismatch()
        if decision.decided_at < self.requested_at:
            raise InvalidApprovalRequestPeriod()
        if self.expires_at is not None and decision.decided_at > self.expires_at:
            raise InvalidApprovalTransition("expired")
        object.__setattr__(self, "_state", ApprovalRequestState.DECIDED)

    def expire(self, at: datetime) -> None:
        if not isinstance(at, datetime):
            raise ValueError("at must be a datetime")
        point = normalize_utc(at)
        if self.state is not ApprovalRequestState.PENDING:
            raise InvalidApprovalTransition(self.state.value)
        if self.expires_at is None or point < self.expires_at:
            raise InvalidApprovalTransition(self.state.value)
        object.__setattr__(self, "_state", ApprovalRequestState.EXPIRED)

    def cancel(self) -> None:
        if self.state is not ApprovalRequestState.PENDING:
            raise InvalidApprovalTransition(self.state.value)
        object.__setattr__(self, "_state", ApprovalRequestState.CANCELLED)
