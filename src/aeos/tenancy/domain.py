"""Tenant context and role names over existing organization membership."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Callable

from aeos.core.actors import ActorRef
from aeos.core.ids import OrganizationId, RoleAssignmentId
from aeos.organization.domain.organization import Organization
from aeos.tenancy.errors import TenantAccessDenied


_TENANT_CONTEXT_TOKEN = object()


class TenantRole(StrEnum):
    OWNER = "tenant_owner"
    ADMIN = "tenant_admin"
    MEMBER = "tenant_member"

    @property
    def can_manage_profiles(self) -> bool:
        return self in {TenantRole.OWNER, TenantRole.ADMIN}


@dataclass(frozen=True, slots=True)
class TenantPrincipal:
    """Actor identity supplied by an authenticated application boundary."""

    actor: ActorRef

    def __post_init__(self) -> None:
        if not isinstance(self.actor, ActorRef):
            raise ValueError("actor must be an ActorRef")


@dataclass(frozen=True, slots=True)
class TenantContext:
    """Per-request tenant scope produced after membership validation."""

    organization: Organization
    actor: ActorRef
    role: TenantRole
    assignment_id: RoleAssignmentId
    _resolution_token: object = field(repr=False, compare=False)
    _membership_validator: Callable[[], bool] = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.organization, Organization):
            raise ValueError("organization must be an Organization")
        if not isinstance(self.actor, ActorRef):
            raise ValueError("actor must be an ActorRef")
        if not isinstance(self.role, TenantRole):
            raise ValueError("role must be a TenantRole")
        if not isinstance(self.assignment_id, RoleAssignmentId):
            raise ValueError("assignment_id must be a RoleAssignmentId")
        if self._resolution_token is not _TENANT_CONTEXT_TOKEN:
            raise TenantAccessDenied()
        if not callable(self._membership_validator):
            raise TenantAccessDenied()
        assignment = self.organization.assignments.get(self.assignment_id)
        role = (
            None
            if assignment is None
            else self.organization.roles.get(assignment.role_id)
        )
        if (
            assignment is None
            or assignment.actor != self.actor
            or assignment.organization_id != self.organization.organization_id
            or role is None
            or role.name.strip().casefold() != self.role.value
        ):
            raise TenantAccessDenied()

    @property
    def organization_id(self) -> OrganizationId:
        return self.organization.organization_id

    def require_manager_actor(self) -> str:
        """Return the authenticated tenant manager identity or fail closed."""

        if not self.role.can_manage_profiles or not self.is_active():
            raise TenantAccessDenied()
        return str(self.actor.actor_id)

    def require_owner_actor(self) -> str:
        """Return the active tenant owner identity or fail closed."""

        if self.role is not TenantRole.OWNER or not self.is_active():
            raise TenantAccessDenied()
        return str(self.actor.actor_id)

    def is_active(self, at: datetime | None = None) -> bool:
        point = at or datetime.now(timezone.utc)
        try:
            return self._membership_validator() and self._snapshot_is_active(point)
        except (LookupError, RuntimeError, ValueError):
            return False

    def _snapshot_is_active(self, at: datetime) -> bool:
        assignment = self.organization.assignments.get(self.assignment_id)
        return (
            self.organization.status.value == "active"
            and assignment is not None
            and assignment.actor == self.actor
            and assignment.is_effective_at(at)
        )


def _resolve_tenant_context(
    organization: Organization,
    actor: ActorRef,
    role: TenantRole,
    assignment_id: RoleAssignmentId,
    membership_validator: Callable[[], bool],
) -> TenantContext:
    return TenantContext(
        organization,
        actor,
        role,
        assignment_id,
        _TENANT_CONTEXT_TOKEN,
        membership_validator,
    )
