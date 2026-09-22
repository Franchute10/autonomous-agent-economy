"""Structural economic resource definition."""

from dataclasses import dataclass

from aeos.core import OrganizationId, ResourceId, ResourceUnit
from aeos.economics.domain.errors import InvalidResourceName


@dataclass(frozen=True, slots=True)
class Resource:
    """One organization-owned resource definition, without quantity semantics."""

    resource_id: ResourceId
    organization_id: OrganizationId
    name: str
    unit: ResourceUnit
    description: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.resource_id, ResourceId):
            raise ValueError("resource_id must be a ResourceId")
        if not isinstance(self.organization_id, OrganizationId):
            raise ValueError("organization_id must be an OrganizationId")
        if not isinstance(self.name, str) or not self.name.strip():
            raise InvalidResourceName()
        if not isinstance(self.unit, ResourceUnit):
            raise ValueError("unit must be a ResourceUnit")
        if self.description is not None and not isinstance(self.description, str):
            raise ValueError("description must be a string or None")
