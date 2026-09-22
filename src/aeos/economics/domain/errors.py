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
