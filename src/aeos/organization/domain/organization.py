"""Organization aggregate root for structural organization state."""

from enum import StrEnum
from types import MappingProxyType
from typing import Mapping

from aeos.core.ids import OrganizationId, RoleAssignmentId, RoleId
from aeos.core.versioning import VersionRef
from aeos.organization.domain.errors import (
    DuplicateRole,
    DuplicateRoleAssignment,
    InvalidOrganizationName,
    RoleOrganizationMismatch,
)
from aeos.organization.domain.role import Role
from aeos.organization.domain.role_assignment import RoleAssignment


class OrganizationStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class Organization:
    """Aggregate root owning roles and role assignments."""

    __slots__ = (
        "_organization_id",
        "_name",
        "_status",
        "_current_constitution",
        "_roles",
        "_assignments",
    )

    def __init__(
        self,
        organization_id: OrganizationId,
        name: str,
        status: OrganizationStatus,
        current_constitution: VersionRef | None = None,
    ) -> None:
        if not isinstance(organization_id, OrganizationId):
            raise ValueError("organization_id must be an OrganizationId")
        if not isinstance(name, str) or not name.strip():
            raise InvalidOrganizationName()
        if not isinstance(status, OrganizationStatus):
            raise ValueError("status must be an OrganizationStatus")
        if current_constitution is not None and not isinstance(
            current_constitution, VersionRef
        ):
            raise ValueError("current_constitution must be a VersionRef or None")
        self._organization_id = organization_id
        self._name = name
        self._status = status
        self._current_constitution = current_constitution
        self._roles: dict[RoleId, Role] = {}
        self._assignments: dict[RoleAssignmentId, RoleAssignment] = {}

    @property
    def organization_id(self) -> OrganizationId:
        return self._organization_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def status(self) -> OrganizationStatus:
        return self._status

    @property
    def current_constitution(self) -> VersionRef | None:
        return self._current_constitution

    @property
    def roles(self) -> Mapping[RoleId, Role]:
        return MappingProxyType(self._roles)

    @property
    def assignments(self) -> Mapping[RoleAssignmentId, RoleAssignment]:
        return MappingProxyType(self._assignments)

    def change_status(self, status: OrganizationStatus) -> None:
        if not isinstance(status, OrganizationStatus):
            raise ValueError("status must be an OrganizationStatus")
        self._status = status

    def add_role(self, role: Role) -> None:
        if not isinstance(role, Role):
            raise ValueError("role must be a Role")
        if role.organization_id != self.organization_id:
            raise RoleOrganizationMismatch()
        if role.role_id in self._roles:
            raise DuplicateRole()
        self._roles[role.role_id] = role

    def add_assignment(self, assignment: RoleAssignment) -> None:
        if not isinstance(assignment, RoleAssignment):
            raise ValueError("assignment must be a RoleAssignment")
        if assignment.organization_id != self.organization_id:
            raise RoleOrganizationMismatch()
        role = self._roles.get(assignment.role_id)
        if role is None or role.organization_id != assignment.organization_id:
            raise RoleOrganizationMismatch()
        if assignment.role_assignment_id in self._assignments:
            raise DuplicateRoleAssignment()
        self._assignments[assignment.role_assignment_id] = assignment
