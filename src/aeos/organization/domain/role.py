"""Organizational positions and descriptive responsibilities."""

from dataclasses import dataclass

from aeos.core.ids import OrganizationId, RoleId
from aeos.organization.domain.errors import InvalidRoleName


@dataclass(frozen=True, slots=True)
class Role:
    """An organizational position; it carries no permission semantics."""

    role_id: RoleId
    organization_id: OrganizationId
    name: str
    responsibilities: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.role_id, RoleId):
            raise ValueError("role_id must be a RoleId")
        if not isinstance(self.organization_id, OrganizationId):
            raise ValueError("organization_id must be an OrganizationId")
        if not isinstance(self.name, str) or not self.name.strip():
            raise InvalidRoleName()
        if self.responsibilities is not None and not isinstance(
            self.responsibilities, str
        ):
            raise ValueError("responsibilities must be a string or None")
