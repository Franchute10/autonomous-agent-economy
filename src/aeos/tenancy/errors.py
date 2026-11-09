"""Tenant-boundary failures."""

from aeos.core.errors import DomainError


class TenantAccessDenied(DomainError):
    def __init__(self) -> None:
        super().__init__("tenant_access_denied", "tenant access is not authorized")


class BusinessProfileAlreadyExists(DomainError):
    def __init__(self) -> None:
        super().__init__("business_profile_exists", "business profile already exists")


class BusinessProfileNotFound(DomainError):
    def __init__(self) -> None:
        super().__init__("business_profile_not_found", "business profile was not found")


class OrganizationAlreadyExists(DomainError):
    def __init__(self) -> None:
        super().__init__("organization_exists", "organization ID already exists")


class TenantRecordAlreadyExists(DomainError):
    def __init__(self) -> None:
        super().__init__("tenant_record_exists", "tenant record already exists")


class TenantRecordNotFound(DomainError):
    def __init__(self) -> None:
        super().__init__("tenant_record_not_found", "tenant record was not found")
