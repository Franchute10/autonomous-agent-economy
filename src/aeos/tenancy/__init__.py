"""Tenant boundary contracts built on the existing organization domain."""

from aeos.tenancy.domain import TenantContext, TenantPrincipal, TenantRole
from aeos.tenancy.errors import (
    BusinessProfileAlreadyExists,
    BusinessProfileNotFound,
    OrganizationAlreadyExists,
    TenantAccessDenied,
)

__all__ = [
    "BusinessProfileAlreadyExists",
    "BusinessProfileNotFound",
    "OrganizationAlreadyExists",
    "TenantAccessDenied",
    "TenantContext",
    "TenantPrincipal",
    "TenantRole",
]
