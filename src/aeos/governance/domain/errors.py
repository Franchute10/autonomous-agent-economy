"""Narrow semantic errors for governance models."""

from aeos.core.errors import DomainError


class InvalidConstitutionTitle(DomainError):
    def __init__(self) -> None:
        super().__init__(
            "invalid_constitution_title", "constitution title must not be blank"
        )


class InvalidPolicyKey(DomainError):
    def __init__(self) -> None:
        super().__init__("invalid_policy_key", "policy key must not be blank")


class InvalidGovernanceDecisionReason(DomainError):
    def __init__(self) -> None:
        super().__init__(
            "invalid_governance_decision_reason", "decision reason must not be blank"
        )


class InvalidPermissionCapability(DomainError):
    def __init__(self) -> None:
        super().__init__(
            "invalid_permission_capability", "permission capability must not be blank"
        )


class InvalidPermissionPeriod(DomainError):
    def __init__(self) -> None:
        super().__init__(
            "invalid_permission_period",
            "permission valid_until must not be earlier than valid_from",
        )


class InvalidApprovalRequestPeriod(DomainError):
    def __init__(self) -> None:
        super().__init__(
            "invalid_approval_request_period",
            "approval expires_at must not be earlier than requested_at",
        )


class InvalidApprovalRequestReason(DomainError):
    def __init__(self) -> None:
        super().__init__(
            "invalid_approval_request_reason", "approval reason must not be blank"
        )


class InvalidApprovalDecisionReason(DomainError):
    def __init__(self) -> None:
        super().__init__(
            "invalid_approval_decision_reason",
            "approval decision reason must not be blank",
        )


class InvalidApprovalTransition(DomainError):
    def __init__(self, state: str) -> None:
        super().__init__(
            "invalid_approval_transition",
            f"approval request in {state} cannot receive this transition",
        )


class ApprovalRequestMismatch(DomainError):
    def __init__(self) -> None:
        super().__init__(
            "approval_request_mismatch",
            "approval decision must reference the same approval request",
        )


class ApprovalOrganizationMismatch(DomainError):
    def __init__(self) -> None:
        super().__init__(
            "approval_organization_mismatch",
            "approval request and decision must belong to the same organization",
        )
