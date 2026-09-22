"""Structural economic resource account definition."""

from dataclasses import dataclass
from enum import StrEnum

from aeos.core import OrganizationId, ResourceAccountId, ResourceId
from aeos.economics.domain.errors import (
    AccountOrganizationMismatch,
    AccountResourceMismatch,
    InvalidAccountType,
)
from aeos.economics.domain.resource import Resource


class ResourceAccountType(StrEnum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    COMMITTED = "committed"
    CONSUMED = "consumed"
    EXTERNAL_SOURCE_OR_SINK = "external_source_or_sink"


@dataclass(frozen=True, slots=True)
class ResourceAccount:
    """One immutable account category associated with one resource identity."""

    resource_account_id: ResourceAccountId
    organization_id: OrganizationId
    resource_id: ResourceId
    account_type: ResourceAccountType
    name: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.resource_account_id, ResourceAccountId):
            raise ValueError("resource_account_id must be a ResourceAccountId")
        if not isinstance(self.organization_id, OrganizationId):
            raise ValueError("organization_id must be an OrganizationId")
        if not isinstance(self.resource_id, ResourceId):
            raise ValueError("resource_id must be a ResourceId")
        if not isinstance(self.account_type, ResourceAccountType):
            raise InvalidAccountType()
        if self.name is not None and (
            not isinstance(self.name, str) or not self.name.strip()
        ):
            raise ValueError("name must be a non-blank string or None")

    @classmethod
    def for_resource(
        cls,
        resource_account_id: ResourceAccountId,
        resource: Resource,
        account_type: ResourceAccountType,
        name: str | None = None,
    ) -> "ResourceAccount":
        """Create an account while enforcing the resource ownership invariant."""
        if not isinstance(resource, Resource):
            raise ValueError("resource must be a Resource")
        return cls(
            resource_account_id,
            resource.organization_id,
            resource.resource_id,
            account_type,
            name,
        )

    def validate_against(self, resource: Resource) -> None:
        """Validate this account's organization and resource relationship."""
        if not isinstance(resource, Resource):
            raise ValueError("resource must be a Resource")
        if self.organization_id != resource.organization_id:
            raise AccountOrganizationMismatch()
        if self.resource_id != resource.resource_id:
            raise AccountResourceMismatch()
