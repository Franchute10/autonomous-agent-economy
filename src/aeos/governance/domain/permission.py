"""Immutable permission grant state; authorization is intentionally out of scope."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from aeos.core import (
    ActorRef,
    OrganizationId,
    PermissionGrantId,
    RoleAssignmentId,
    RoleId,
    TraceContext,
    UtcTimestamp,
    VersionRef,
    normalize_utc,
)
from aeos.governance.domain.errors import (
    InvalidPermissionCapability,
    InvalidPermissionPeriod,
)


@dataclass(frozen=True, slots=True)
class PermissionCapability:
    """One exact capability/action identifier, never a policy expression."""

    value: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.value, str)
            or not self.value.strip()
            or "*" in self.value
        ):
            raise InvalidPermissionCapability()
        object.__setattr__(self, "value", self.value.strip())


class PermissionScopeKind(StrEnum):
    ORGANIZATION = "organization"


@dataclass(frozen=True, slots=True)
class PermissionScope:
    """The minimal bounded scope currently supported by AEOS."""

    kind: PermissionScopeKind = PermissionScopeKind.ORGANIZATION

    def __post_init__(self) -> None:
        if not isinstance(self.kind, PermissionScopeKind):
            raise ValueError("kind must be a PermissionScopeKind")


PermissionGrantee = ActorRef | RoleId | RoleAssignmentId


@dataclass(frozen=True, slots=True)
class PermissionGrant:
    """An immutable grant fact, not an authorization or permission evaluator."""

    permission_grant_id: PermissionGrantId
    organization_id: OrganizationId
    grantee: PermissionGrantee
    capability: PermissionCapability
    scope: PermissionScope
    policy_version: VersionRef
    constitution_version: VersionRef | None
    valid_from: UtcTimestamp
    valid_until: UtcTimestamp | None
    created_at: UtcTimestamp
    trace: TraceContext

    def __post_init__(self) -> None:
        if not isinstance(self.permission_grant_id, PermissionGrantId):
            raise ValueError("permission_grant_id must be a PermissionGrantId")
        if not isinstance(self.organization_id, OrganizationId):
            raise ValueError("organization_id must be an OrganizationId")
        if not isinstance(self.grantee, (ActorRef, RoleId, RoleAssignmentId)):
            raise ValueError("grantee must be an ActorRef, RoleId, or RoleAssignmentId")
        if not isinstance(self.capability, PermissionCapability):
            raise ValueError("capability must be a PermissionCapability")
        if not isinstance(self.scope, PermissionScope):
            raise ValueError("scope must be a PermissionScope")
        if not isinstance(self.policy_version, VersionRef):
            raise ValueError("policy_version must be a VersionRef")
        if self.constitution_version is not None and not isinstance(
            self.constitution_version, VersionRef
        ):
            raise ValueError("constitution_version must be a VersionRef or None")
        for name, value in (
            ("valid_from", self.valid_from),
            ("created_at", self.created_at),
        ):
            if not isinstance(value, datetime):
                raise ValueError(f"{name} must be a datetime")
        if self.valid_until is not None and not isinstance(self.valid_until, datetime):
            raise ValueError("valid_until must be a datetime or None")
        if not isinstance(self.trace, TraceContext):
            raise ValueError("trace must be a TraceContext")
        start = normalize_utc(self.valid_from)
        end = None if self.valid_until is None else normalize_utc(self.valid_until)
        if end is not None and end < start:
            raise InvalidPermissionPeriod()
        object.__setattr__(self, "valid_from", start)
        object.__setattr__(self, "valid_until", end)
        object.__setattr__(self, "created_at", normalize_utc(self.created_at))

    def is_effective_at(self, timestamp: datetime) -> bool:
        """Evaluate only this grant's temporal bounds."""
        if not isinstance(timestamp, datetime):
            raise ValueError("timestamp must be a datetime")
        point = normalize_utc(timestamp)
        return point >= self.valid_from and (
            self.valid_until is None or point <= self.valid_until
        )
