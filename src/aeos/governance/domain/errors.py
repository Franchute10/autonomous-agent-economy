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
