from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from aeos.core import (
    ActorKind,
    ActorRef,
    ApprovalDecisionId,
    ApprovalRequestId,
    CorrelationId,
    CausationId,
    GovernanceDecisionId,
    IdempotencyKey,
    OrganizationId,
    PermissionGrantId,
    RoleAssignmentId,
    RoleId,
    TraceContext,
    VersionRef,
)
from aeos.governance import (
    ApprovalDecision,
    ApprovalDecisionResult,
    ApprovalRequest,
    ApprovalRequestState,
    PermissionCapability,
    PermissionGrant,
    PermissionScope,
    PermissionScopeKind,
    GovernanceDecisionResult,
)
from aeos.governance.domain.errors import (
    ApprovalOrganizationMismatch,
    ApprovalRequestMismatch,
    InvalidApprovalTransition,
    InvalidApprovalDecisionReason,
    InvalidApprovalRequestPeriod,
    InvalidApprovalRequestReason,
    InvalidPermissionCapability,
    InvalidPermissionPeriod,
)


ORG = OrganizationId("org-1")
TRACE = TraceContext(
    actor=ActorRef(OrganizationId("system-1"), ActorKind.SYSTEM),
    correlation_id=CorrelationId("correlation-1"),
    idempotency_key=IdempotencyKey("idempotency-1"),
    causation_id=CausationId("cause-1"),
)
START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def actor() -> ActorRef:
    return ActorRef(OrganizationId("actor-1"), ActorKind.HUMAN)


def request(**overrides: object) -> ApprovalRequest:
    values: dict[str, object] = {
        "approval_request_id": ApprovalRequestId("request-1"),
        "organization_id": ORG,
        "requester": actor(),
        "capability": PermissionCapability("resource.read"),
        "reason": "requires human approval",
        "requested_at": START,
        "expires_at": START + timedelta(hours=1),
        "constitution_version": VersionRef("constitution", "3"),
        "policy_versions": (VersionRef("policy", "7"),),
        "governance_decision_id": None,
        "required_role_id": RoleId("approver"),
        "trace": TRACE,
    }
    values.update(overrides)
    return ApprovalRequest(**values)  # type: ignore[arg-type]


def decision(**overrides: object) -> ApprovalDecision:
    values: dict[str, object] = {
        "approval_decision_id": ApprovalDecisionId("decision-1"),
        "approval_request_id": ApprovalRequestId("request-1"),
        "organization_id": ORG,
        "decision": ApprovalDecisionResult.APPROVE,
        "decided_by": actor(),
        "reason": "reviewed",
        "decided_at": START + timedelta(minutes=1),
        "constitution_version": VersionRef("constitution", "3"),
        "policy_versions": (VersionRef("policy", "7"),),
        "trace": TRACE,
    }
    values.update(overrides)
    return ApprovalDecision(**values)  # type: ignore[arg-type]


def grant(**overrides: object) -> PermissionGrant:
    values: dict[str, object] = {
        "permission_grant_id": PermissionGrantId("grant-1"),
        "organization_id": ORG,
        "grantee": actor(),
        "capability": PermissionCapability("resource.read"),
        "scope": PermissionScope(),
        "policy_version": VersionRef("policy", "7"),
        "constitution_version": VersionRef("constitution", "3"),
        "valid_from": START,
        "valid_until": START + timedelta(hours=1),
        "created_at": START,
        "trace": TRACE,
    }
    values.update(overrides)
    return PermissionGrant(**values)  # type: ignore[arg-type]


def test_permission_grant_is_immutable_and_time_bounded() -> None:
    permission_grant = grant()
    assert permission_grant.organization_id is ORG
    assert permission_grant.is_effective_at(START)
    assert permission_grant.is_effective_at(START + timedelta(minutes=30))
    assert not permission_grant.is_effective_at(START - timedelta(seconds=1))
    assert not permission_grant.is_effective_at(START + timedelta(hours=2))
    with pytest.raises(FrozenInstanceError):
        permission_grant.capability = PermissionCapability("other")  # type: ignore[misc]


def test_permission_grant_rejects_reversed_period() -> None:
    with pytest.raises(InvalidPermissionPeriod):
        grant(valid_until=START - timedelta(seconds=1))


@pytest.mark.parametrize("value", ["", "   ", "*", "resource.*", "*.delete"])
def test_permission_capability_rejects_blank_and_wildcard_values(value: str) -> None:
    with pytest.raises(InvalidPermissionCapability):
        PermissionCapability(value)


def test_permission_capability_normalizes_and_is_immutable() -> None:
    capability = PermissionCapability(" resource.read ")
    assert capability.value == "resource.read"
    assert capability == PermissionCapability("resource.read")
    assert hash(capability) == hash(PermissionCapability("resource.read"))
    with pytest.raises(FrozenInstanceError):
        capability.value = "other"  # type: ignore[misc]


def test_permission_scope_has_only_organization_kind_and_is_immutable() -> None:
    scope = PermissionScope()
    assert scope.kind is PermissionScopeKind.ORGANIZATION
    assert list(PermissionScopeKind) == [PermissionScopeKind.ORGANIZATION]
    with pytest.raises(ValueError):
        PermissionScope("organization")  # type: ignore[arg-type]
    with pytest.raises(FrozenInstanceError):
        scope.kind = PermissionScopeKind.ORGANIZATION  # type: ignore[misc]


@pytest.mark.parametrize(
    "grantee", [actor(), RoleId("role-1"), RoleAssignmentId("assignment-1")]
)
def test_permission_grant_accepts_supported_grantee_types(grantee: object) -> None:
    assert grant(grantee=grantee).grantee == grantee


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("permission_grant_id", object()),
        ("organization_id", object()),
        ("grantee", object()),
        ("capability", "resource.read"),
        ("scope", object()),
        ("policy_version", object()),
        ("constitution_version", object()),
        ("trace", object()),
        ("valid_from", object()),
        ("valid_until", object()),
        ("created_at", object()),
    ],
)
def test_permission_grant_rejects_invalid_boundary_types(
    field: str, value: object
) -> None:
    with pytest.raises(ValueError):
        grant(**{field: value})


def test_permission_grant_normalizes_aware_times_and_supports_open_or_empty_periods() -> (
    None
):
    offset = timezone(timedelta(hours=3))
    normalized = grant(
        valid_from=datetime(2026, 1, 1, 3, tzinfo=offset),
        valid_until=datetime(2026, 1, 1, 3, tzinfo=offset),
        created_at=datetime(2026, 1, 1, 3, tzinfo=offset),
    )
    assert normalized.valid_from == START
    assert normalized.valid_until == START
    assert normalized.created_at == START
    assert normalized.is_effective_at(START)
    open_ended = grant(valid_until=None)
    assert open_ended.is_effective_at(START + timedelta(days=100))


def test_permission_grant_rejects_naive_and_non_datetime_effective_times() -> None:
    with pytest.raises(ValueError):
        grant(valid_from=datetime(2026, 1, 1))
    with pytest.raises(ValueError):
        grant(valid_until=datetime(2026, 1, 1))
    with pytest.raises(ValueError):
        grant(created_at=datetime(2026, 1, 1))
    permission_grant = grant()
    with pytest.raises(ValueError):
        permission_grant.is_effective_at(object())  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        permission_grant.is_effective_at(datetime(2026, 1, 1))


def test_approval_request_starts_pending_and_approve_decides_it() -> None:
    approval_request = request()
    initial_state = approval_request.state
    assert initial_state is ApprovalRequestState.PENDING
    approval_request.record_decision(decision())
    assert approval_request.state is ApprovalRequestState.DECIDED
    assert GovernanceDecisionResult.REQUIRE_APPROVAL.value == "require_approval"


def test_approval_request_expiry_and_terminal_decision_rules() -> None:
    approval_request = request()
    approval_request.expire(START + timedelta(hours=1))
    assert approval_request.state is ApprovalRequestState.EXPIRED
    with pytest.raises(InvalidApprovalTransition):
        approval_request.record_decision(decision())

    cancelled = request(approval_request_id=ApprovalRequestId("request-2"))
    cancelled.cancel()
    assert cancelled.state is ApprovalRequestState.CANCELLED
    with pytest.raises(InvalidApprovalTransition):
        cancelled.record_decision(
            decision(approval_request_id=ApprovalRequestId("request-2"))
        )


def test_approval_lifecycle_rejects_all_repeated_terminal_operations() -> None:
    decided = request()
    decided.record_decision(decision())
    with pytest.raises(InvalidApprovalTransition):
        decided.record_decision(decision())
    with pytest.raises(InvalidApprovalTransition):
        decided.expire(START + timedelta(hours=1))
    with pytest.raises(InvalidApprovalTransition):
        decided.cancel()

    expired = request()
    expired.expire(START + timedelta(hours=1))
    with pytest.raises(InvalidApprovalTransition):
        expired.expire(START + timedelta(hours=1))
    with pytest.raises(InvalidApprovalTransition):
        expired.cancel()

    cancelled = request(approval_request_id=ApprovalRequestId("request-2"))
    cancelled.cancel()
    with pytest.raises(InvalidApprovalTransition):
        cancelled.expire(START + timedelta(hours=1))
    with pytest.raises(InvalidApprovalTransition):
        cancelled.cancel()


def test_approval_lifecycle_checks_expiry_and_decision_time_boundaries() -> None:
    with pytest.raises(InvalidApprovalTransition):
        request().expire(START + timedelta(minutes=30))
    with pytest.raises(InvalidApprovalTransition):
        request(expires_at=None).expire(START)
    with pytest.raises(InvalidApprovalRequestPeriod):
        request().record_decision(decision(decided_at=START - timedelta(seconds=1)))
    at_expiry = request()
    at_expiry.record_decision(decision(decided_at=START + timedelta(hours=1)))
    assert at_expiry.state is ApprovalRequestState.DECIDED
    with pytest.raises(InvalidApprovalTransition):
        request().record_decision(
            decision(decided_at=START + timedelta(hours=1, seconds=1))
        )


def test_decision_request_and_organization_must_match() -> None:
    approval_request = request()
    with pytest.raises(ApprovalRequestMismatch):
        approval_request.record_decision(
            decision(approval_request_id=ApprovalRequestId("other"))
        )
    with pytest.raises(ApprovalOrganizationMismatch):
        approval_request.record_decision(
            decision(organization_id=OrganizationId("other-org"))
        )


def test_approval_request_rejects_invalid_boundary_types_and_preserves_trace() -> None:
    assert request().trace is TRACE
    invalid: list[tuple[str, object]] = [
        ("approval_request_id", object()),
        ("organization_id", object()),
        ("requester", object()),
        ("capability", "resource.read"),
        ("requested_at", object()),
        ("expires_at", object()),
        ("constitution_version", object()),
        ("policy_versions", [VersionRef("policy", "7")]),
        ("governance_decision_id", object()),
        ("required_role_id", object()),
        ("trace", object()),
    ]
    for field, value in invalid:
        with pytest.raises(ValueError):
            request(**{field: value})
    with pytest.raises(ValueError):
        request(capability="resource.read")
    with pytest.raises(InvalidApprovalRequestReason):
        request(reason=" ")
    with pytest.raises(ValueError):
        request(requested_at=datetime(2026, 1, 1))
    with pytest.raises(ValueError):
        request(expires_at=datetime(2026, 1, 1))
    with pytest.raises(InvalidApprovalRequestPeriod):
        request(expires_at=START - timedelta(seconds=1))


def test_approval_request_supports_optional_values_and_normalizes_times() -> None:
    offset = timezone(timedelta(hours=3))
    approval_request = request(
        requested_at=datetime(2026, 1, 1, 3, tzinfo=offset),
        expires_at=datetime(2026, 1, 1, 3, tzinfo=offset),
        constitution_version=None,
        policy_versions=(),
        governance_decision_id=GovernanceDecisionId("gov-1"),
        required_role_id=None,
    )
    assert approval_request.requested_at == START
    assert approval_request.expires_at == START
    assert approval_request.state is ApprovalRequestState.PENDING


@pytest.mark.parametrize(
    "result", [ApprovalDecisionResult.APPROVE, ApprovalDecisionResult.DENY]
)
def test_approval_decision_accepts_exactly_approve_and_deny(
    result: ApprovalDecisionResult,
) -> None:
    assert decision(decision=result).decision is result


def test_approval_decision_rejects_invalid_boundary_types_and_preserves_metadata() -> (
    None
):
    approved = decision()
    assert approved.trace is TRACE
    assert approved.constitution_version == VersionRef("constitution", "3")
    assert approved.policy_versions == (VersionRef("policy", "7"),)
    invalid: list[tuple[str, object]] = [
        ("approval_decision_id", object()),
        ("approval_request_id", object()),
        ("organization_id", object()),
        ("decision", "approve"),
        ("decided_by", object()),
        ("decided_at", object()),
        ("constitution_version", object()),
        ("policy_versions", [VersionRef("policy", "7")]),
        ("trace", object()),
    ]
    for field, value in invalid:
        with pytest.raises(ValueError):
            decision(**{field: value})
    with pytest.raises(InvalidApprovalDecisionReason):
        decision(reason=" ")
    with pytest.raises(ValueError):
        decision(decided_at=datetime(2026, 1, 1))
    normalized = decision(
        decided_at=datetime(2026, 1, 1, 3, tzinfo=timezone(timedelta(hours=3)))
    )
    assert normalized.decided_at == START


def test_approval_decision_is_immutable_and_deny_is_supported() -> None:
    deny = decision(decision=ApprovalDecisionResult.DENY)
    assert deny.decided_by is not None
    with pytest.raises(FrozenInstanceError):
        deny.reason = "changed"  # type: ignore[misc]
