"""Immutable signed movements in the balanced economic journal."""

from dataclasses import dataclass

from aeos.core import ResourceAccountId, ResourceId, ResourceQuantity
from aeos.economics.domain.account import ResourceAccount
from aeos.economics.domain.errors import (
    PostingResourceMismatch,
    PostingUnitMismatch,
    TransactionOrganizationMismatch,
    ZeroPosting,
)
from aeos.economics.domain.resource import Resource


@dataclass(frozen=True, slots=True)
class LedgerPosting:
    """One immutable signed quantity applied to one resource account."""

    resource_id: ResourceId
    resource_account_id: ResourceAccountId
    quantity: ResourceQuantity
    resource: Resource | None = None
    resource_account: ResourceAccount | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.resource_id, ResourceId):
            raise ValueError("resource_id must be a ResourceId")
        if not isinstance(self.resource_account_id, ResourceAccountId):
            raise ValueError("resource_account_id must be a ResourceAccountId")
        if not isinstance(self.quantity, ResourceQuantity):
            raise ValueError("quantity must be a ResourceQuantity")
        if self.quantity.quantity == 0:
            raise ZeroPosting()
        if self.resource is not None:
            if not isinstance(self.resource, Resource):
                raise ValueError("resource must be a Resource or None")
            self._validate_resource(self.resource)
        if self.resource_account is not None:
            if not isinstance(self.resource_account, ResourceAccount):
                raise ValueError("resource_account must be a ResourceAccount or None")
            if self.resource_account.resource_account_id != self.resource_account_id:
                raise PostingResourceMismatch()
            if self.resource_account.resource_id != self.resource_id:
                raise PostingResourceMismatch()
            if self.resource is not None:
                self.resource_account.validate_against(self.resource)

    def _validate_resource(self, resource: Resource) -> None:
        if resource.resource_id != self.resource_id:
            raise PostingResourceMismatch()
        if resource.unit != self.quantity.unit:
            raise PostingUnitMismatch()

    def validate_against(
        self,
        organization_id: object,
        resource: Resource | None = None,
        resource_account: ResourceAccount | None = None,
    ) -> None:
        """Validate optional caller-supplied definitions without repository access."""
        resource = resource or self.resource
        resource_account = resource_account or self.resource_account
        if resource is not None:
            if not isinstance(resource, Resource):
                raise ValueError("resource must be a Resource or None")
            self._validate_resource(resource)
            if resource.organization_id != organization_id:
                raise TransactionOrganizationMismatch()
        if resource_account is not None:
            if not isinstance(resource_account, ResourceAccount):
                raise ValueError("resource_account must be a ResourceAccount or None")
            if resource_account.resource_account_id != self.resource_account_id:
                raise PostingResourceMismatch()
            if resource_account.resource_id != self.resource_id:
                raise PostingResourceMismatch()
            if resource_account.organization_id != organization_id:
                raise TransactionOrganizationMismatch()
            if resource is not None:
                resource_account.validate_against(resource)
