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
