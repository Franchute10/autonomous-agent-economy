"""Narrow structural errors raised by the Economics domain."""

from aeos.core.errors import DomainError


class InvalidResourceName(DomainError):
    def __init__(self) -> None:
        super().__init__("invalid_resource_name", "resource name must not be blank")


class AccountOrganizationMismatch(DomainError):
    def __init__(self) -> None:
        super().__init__(
            "account_organization_mismatch",
            "resource account and resource must belong to the same organization",
        )


class AccountResourceMismatch(DomainError):
    def __init__(self) -> None:
        super().__init__(
            "account_resource_mismatch",
            "resource account references a different resource",
        )


class InvalidAccountType(DomainError):
    def __init__(self) -> None:
        super().__init__(
            "invalid_account_type", "resource account type is not approved"
        )


class ZeroPosting(DomainError):
    def __init__(self) -> None:
        super().__init__("zero_posting", "ledger posting quantity must not be zero")


class EmptyTransaction(DomainError):
    def __init__(self) -> None:
        super().__init__("empty_transaction", "economic transaction needs postings")


class UnbalancedEconomicTransaction(DomainError):
    def __init__(self, resource_id: object) -> None:
        super().__init__(
            "unbalanced_economic_transaction",
            f"postings for resource {resource_id} must sum to zero",
        )


class PostingResourceMismatch(DomainError):
    def __init__(self) -> None:
        super().__init__(
            "posting_resource_mismatch",
            "posting and resource account refer to different resources",
        )


class PostingUnitMismatch(DomainError):
    def __init__(self) -> None:
        super().__init__(
            "posting_unit_mismatch", "posting quantity unit does not match resource"
        )


class TransactionOrganizationMismatch(DomainError):
    def __init__(self) -> None:
        super().__init__(
            "transaction_organization_mismatch",
            "economic references must belong to the transaction organization",
        )


class MissingResourceDefinition(DomainError):
    def __init__(self, resource_id: object) -> None:
        super().__init__(
            "missing_resource_definition",
            f"resource definition is missing for {resource_id}",
        )


class MissingResourceAccountDefinition(DomainError):
    def __init__(self, resource_account_id: object) -> None:
        super().__init__(
            "missing_resource_account_definition",
            f"resource account definition is missing for {resource_account_id}",
        )


class InvalidBudgetPurpose(DomainError):
    def __init__(self) -> None:
        super().__init__("invalid_budget_purpose", "budget purpose must not be blank")


class InvalidBudgetLimit(DomainError):
    def __init__(self) -> None:
        super().__init__(
            "invalid_budget_limit", "budget limit must be positive and valid"
        )


class InvalidBudgetPeriod(DomainError):
    def __init__(self) -> None:
        super().__init__("invalid_budget_period", "budget period is invalid")


class DuplicateBudgetLimit(DomainError):
    def __init__(self) -> None:
        super().__init__(
            "duplicate_budget_limit",
            "budget limits with the same logical key must not overlap",
        )


class BudgetLimitMismatch(DomainError):
    def __init__(self) -> None:
        super().__init__(
            "budget_limit_mismatch",
            "reservation is not covered by a matching budget limit",
        )


class InvalidReservationQuantity(DomainError):
    def __init__(self) -> None:
        super().__init__(
            "invalid_reservation_quantity", "reservation quantity must be positive"
        )


class InvalidReservationPeriod(DomainError):
    def __init__(self) -> None:
        super().__init__("invalid_reservation_period", "reservation period is invalid")


class BudgetOrganizationMismatch(DomainError):
    def __init__(self) -> None:
        super().__init__(
            "budget_organization_mismatch",
            "reservation and budget organizations differ",
        )


class ReservationBudgetMismatch(DomainError):
    def __init__(self) -> None:
        super().__init__(
            "reservation_budget_mismatch",
            "reservation references a different budget",
        )


class InvalidReservationState(DomainError):
    def __init__(self) -> None:
        super().__init__(
            "invalid_reservation_state", "reservation lifecycle transition is invalid"
        )
