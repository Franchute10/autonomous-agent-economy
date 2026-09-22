"""Narrow structural errors raised by the organization domain."""

from aeos.core.errors import DomainError


class InvalidOrganizationName(DomainError):
    def __init__(self) -> None:
        super().__init__(
            "invalid_organization_name", "organization name must not be blank"
        )


class InvalidRoleName(DomainError):
    def __init__(self) -> None:
        super().__init__("invalid_role_name", "role name must not be blank")


class RoleOrganizationMismatch(DomainError):
    def __init__(self) -> None:
        super().__init__(
            "role_organization_mismatch",
            "role and assignment must belong to the same organization",
        )


class InvalidRoleAssignmentPeriod(DomainError):
    def __init__(self) -> None:
        super().__init__(
            "invalid_role_assignment_period",
            "role assignment end must not be earlier than its start",
        )


class DuplicateRole(DomainError):
    def __init__(self) -> None:
        super().__init__(
            "duplicate_role", "role identity already belongs to the organization"
        )


class DuplicateRoleAssignment(DomainError):
    def __init__(self) -> None:
        super().__init__(
            "duplicate_role_assignment",
            "role assignment identity already belongs to the organization",
        )
