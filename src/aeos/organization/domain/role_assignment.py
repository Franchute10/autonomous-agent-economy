"""Explicit actor-to-role assignments."""

from dataclasses import dataclass
from datetime import datetime

from aeos.core.actors import ActorRef
from aeos.core.ids import OrganizationId, RoleAssignmentId, RoleId
from aeos.core.time import UtcTimestamp, normalize_utc
from aeos.organization.domain.errors import InvalidRoleAssignmentPeriod


@dataclass(frozen=True, slots=True)
class RoleAssignment:
    """A time-bounded structural relationship, not an authorization grant."""

    role_assignment_id: RoleAssignmentId
    organization_id: OrganizationId
    role_id: RoleId
    actor: ActorRef
    starts_at: UtcTimestamp
    ends_at: UtcTimestamp | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.role_assignment_id, RoleAssignmentId):
            raise ValueError("role_assignment_id must be a RoleAssignmentId")
        if not isinstance(self.organization_id, OrganizationId):
            raise ValueError("organization_id must be an OrganizationId")
        if not isinstance(self.role_id, RoleId):
            raise ValueError("role_id must be a RoleId")
        if not isinstance(self.actor, ActorRef):
            raise ValueError("actor must be an ActorRef")
        if not isinstance(self.starts_at, datetime):
            raise ValueError("starts_at must be a datetime")
        if self.ends_at is not None and not isinstance(self.ends_at, datetime):
            raise ValueError("ends_at must be a datetime or None")
        start = normalize_utc(self.starts_at)
        end = None if self.ends_at is None else normalize_utc(self.ends_at)
        if end is not None and end < start:
            raise InvalidRoleAssignmentPeriod()
        object.__setattr__(self, "starts_at", start)
        object.__setattr__(self, "ends_at", end)

    def is_effective_at(self, timestamp: datetime) -> bool:
        """Return whether the timestamp is inside this assignment's period."""
        if not isinstance(timestamp, datetime):
            raise ValueError("timestamp must be a datetime")
        point = normalize_utc(timestamp)
        return point >= self.starts_at and (
            self.ends_at is None or point <= self.ends_at
        )
