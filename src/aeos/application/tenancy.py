"""Authorized application use cases for registering and accessing tenants."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from aeos.core.actors import ActorRef
from aeos.core.ids import OrganizationId, RoleAssignmentId, RoleId
from aeos.core.time import UtcTimestamp
from aeos.live.domain.profile import BusinessProfile
from aeos.organization.domain.organization import Organization, OrganizationStatus
from aeos.organization.domain.role import Role
from aeos.organization.domain.role_assignment import RoleAssignment
from aeos.tenancy.domain import (
    TenantContext,
    TenantPrincipal,
    TenantRole,
    _resolve_tenant_context,
)
from aeos.tenancy.errors import (
    BusinessProfileAlreadyExists,
    BusinessProfileNotFound,
    OrganizationAlreadyExists,
    TenantAccessDenied,
)
from aeos.tenancy.ports import (
    TenantBusinessProfileRepository,
    TenantOrganizationRepository,
)


def _utc_now() -> UtcTimestamp:
    return datetime.now(timezone.utc)


def _role_for_actor(
    organization: Organization, principal: TenantPrincipal, at: datetime
) -> tuple[TenantRole, RoleAssignmentId] | None:
    matches: list[tuple[TenantRole, RoleAssignmentId]] = []
    for assignment in organization.assignments.values():
        if assignment.actor != principal.actor or not assignment.is_effective_at(at):
            continue
        role = organization.roles.get(assignment.role_id)
        if role is None:
            continue
        try:
            tenant_role = TenantRole(role.name.strip().casefold())
        except ValueError:
            continue
        matches.append((tenant_role, assignment.role_assignment_id))
    priority = {TenantRole.MEMBER: 0, TenantRole.ADMIN: 1, TenantRole.OWNER: 2}
    return max(matches, key=lambda item: priority[item[0]]) if matches else None


class TenantContextResolver:
    """Resolve an organization selector only after checking its stored membership."""

    def __init__(self, organizations: TenantOrganizationRepository) -> None:
        self._organizations = organizations

    def resolve(
        self,
        principal: TenantPrincipal,
        organization_id: OrganizationId,
        *,
        at: datetime | None = None,
    ) -> TenantContext:
        if not isinstance(principal, TenantPrincipal) or not isinstance(
            organization_id, OrganizationId
        ):
            raise TenantAccessDenied()
        organization = self._organizations.get(organization_id)
        point = at or _utc_now()
        if (
            organization is None
            or organization.status is not OrganizationStatus.ACTIVE
            or not isinstance(point, datetime)
            or point.tzinfo is None
        ):
            raise TenantAccessDenied()
        membership = _role_for_actor(organization, principal, point)
        if membership is None:
            raise TenantAccessDenied()
        role, assignment_id = membership
        return _resolve_tenant_context(
            organization,
            principal.actor,
            role,
            assignment_id,
            lambda: self._membership_is_current(
                organization.organization_id,
                principal.actor,
                role,
                assignment_id,
            ),
        )

    def _membership_is_current(
        self,
        organization_id: OrganizationId,
        actor: ActorRef,
        expected_role: TenantRole,
        assignment_id: RoleAssignmentId,
    ) -> bool:
        organization = self._organizations.get(organization_id)
        if organization is None or organization.status is not OrganizationStatus.ACTIVE:
            return False
        assignment = organization.assignments.get(assignment_id)
        if (
            assignment is None
            or assignment.actor != actor
            or assignment.organization_id != organization_id
            or not assignment.is_effective_at(_utc_now())
        ):
            return False
        role = organization.roles.get(assignment.role_id)
        return role is not None and role.name.strip().casefold() == expected_role.value


class RegisterOrganization:
    """Create an organization and assign its authenticated creator as owner."""

    def __init__(self, organizations: TenantOrganizationRepository) -> None:
        self._organizations = organizations

    def execute(
        self,
        principal: TenantPrincipal,
        name: str,
        *,
        at: datetime | None = None,
        organization_id: OrganizationId | None = None,
    ) -> Organization:
        if not isinstance(principal, TenantPrincipal):
            raise TenantAccessDenied()
        configured_id = organization_id or OrganizationId.new()
        if not isinstance(configured_id, OrganizationId):
            raise TenantAccessDenied()
        if self._organizations.get(configured_id) is not None:
            raise OrganizationAlreadyExists()
        created_at = at or _utc_now()
        organization = Organization(configured_id, name, OrganizationStatus.ACTIVE)
        owner_role = Role(
            RoleId.new(),
            organization.organization_id,
            TenantRole.OWNER.value,
            "Organization owner with profile administration authority.",
        )
        organization.add_role(owner_role)
        organization.add_assignment(
            RoleAssignment(
                RoleAssignmentId.new(),
                organization.organization_id,
                owner_role.role_id,
                principal.actor,
                created_at,
            )
        )
        self._organizations.add(organization)
        return organization


class RegisterBusinessProfile:
    def __init__(
        self,
        resolver: TenantContextResolver,
        profiles: TenantBusinessProfileRepository,
    ) -> None:
        self._resolver = resolver
        self._profiles = profiles

    def execute(
        self,
        principal: TenantPrincipal,
        organization_id: OrganizationId,
        profile: BusinessProfile,
        *,
        at: datetime | None = None,
    ) -> BusinessProfile:
        context = self._resolver.resolve(principal, organization_id, at=at)
        _require_profile_admin(context)
        if profile.organization_id not in (None, context.organization_id):
            raise TenantAccessDenied()
        scoped = replace(profile, organization_id=context.organization_id)
        if self._profiles.get(context) is not None:
            raise BusinessProfileAlreadyExists()
        self._profiles.add(context, scoped)
        return scoped


class GetOrganization:
    def __init__(self, resolver: TenantContextResolver) -> None:
        self._resolver = resolver

    def execute(
        self,
        principal: TenantPrincipal,
        organization_id: OrganizationId,
        *,
        at: datetime | None = None,
    ) -> Organization:
        return self._resolver.resolve(principal, organization_id, at=at).organization


class ListOrganizationsForActor:
    def __init__(self, organizations: TenantOrganizationRepository) -> None:
        self._organizations = organizations

    def execute(
        self, principal: TenantPrincipal, *, at: datetime | None = None
    ) -> tuple[Organization, ...]:
        if not isinstance(principal, TenantPrincipal):
            raise TenantAccessDenied()
        point = at or _utc_now()
        result = []
        for organization in self._organizations.list_for_actor(principal.actor):
            if (
                organization.status is OrganizationStatus.ACTIVE
                and _role_for_actor(organization, principal, point) is not None
            ):
                result.append(organization)
        return tuple(result)


class GetBusinessProfile:
    def __init__(
        self,
        resolver: TenantContextResolver,
        profiles: TenantBusinessProfileRepository,
    ) -> None:
        self._resolver = resolver
        self._profiles = profiles

    def execute(
        self,
        principal: TenantPrincipal,
        organization_id: OrganizationId,
        *,
        at: datetime | None = None,
    ) -> BusinessProfile:
        context = self._resolver.resolve(principal, organization_id, at=at)
        profile = self._profiles.get(context)
        if profile is None:
            raise BusinessProfileNotFound()
        if profile.organization_id != context.organization_id:
            raise TenantAccessDenied()
        return profile


class GetBusinessProfileForTenant(GetBusinessProfile):
    """Named read path for callers that already selected the current tenant."""


class UpdateBusinessProfile:
    def __init__(
        self,
        resolver: TenantContextResolver,
        profiles: TenantBusinessProfileRepository,
    ) -> None:
        self._resolver = resolver
        self._profiles = profiles

    def execute(
        self,
        principal: TenantPrincipal,
        organization_id: OrganizationId,
        profile: BusinessProfile,
        *,
        at: datetime | None = None,
    ) -> BusinessProfile:
        context = self._resolver.resolve(principal, organization_id, at=at)
        _require_profile_admin(context)
        if profile.organization_id not in (None, context.organization_id):
            raise TenantAccessDenied()
        if self._profiles.get(context) is None:
            raise BusinessProfileNotFound()
        scoped = replace(profile, organization_id=context.organization_id)
        self._profiles.update(context, scoped)
        return scoped


def _require_profile_admin(context: TenantContext) -> None:
    if not context.role.can_manage_profiles:
        raise TenantAccessDenied()


__all__ = [
    "GetBusinessProfile",
    "GetBusinessProfileForTenant",
    "GetOrganization",
    "ListOrganizationsForActor",
    "RegisterBusinessProfile",
    "RegisterOrganization",
    "TenantContextResolver",
    "UpdateBusinessProfile",
]
