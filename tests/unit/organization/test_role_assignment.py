from datetime import datetime, timedelta, timezone
from dataclasses import FrozenInstanceError
from typing import cast

import pytest

from aeos.core import ActorKind, ActorRef, OrganizationId, RoleAssignmentId, RoleId
from aeos.organization import Organization, OrganizationStatus, Role, RoleAssignment
from aeos.organization.domain.errors import (
    DuplicateRoleAssignment,
    InvalidRoleAssignmentPeriod,
    RoleOrganizationMismatch,
)


def make_actor() -> ActorRef:
    return ActorRef(OrganizationId("actor-1"), ActorKind.HUMAN)


def test_assignment_normalizes_utc_and_evaluates_inclusive_period() -> None:
    start = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    end = start + timedelta(hours=1)
    assignment = RoleAssignment(
        RoleAssignmentId("assignment-1"),
        OrganizationId("org-1"),
        RoleId("role-1"),
        make_actor(),
        start,
        end,
    )
    assert assignment.starts_at == start
    assert assignment.is_effective_at(start)
    assert assignment.is_effective_at(end)
    assert not assignment.is_effective_at(start - timedelta(seconds=1))
    assert not assignment.is_effective_at(end + timedelta(seconds=1))


def test_open_ended_assignment_is_effective_after_start() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assignment = RoleAssignment(
        RoleAssignmentId("assignment-1"),
        OrganizationId("org-1"),
        RoleId("role-1"),
        make_actor(),
        start,
    )
    assert assignment.is_effective_at(start + timedelta(days=1))


def test_assignment_rejects_end_before_start() -> None:
    start = datetime(2026, 1, 2, tzinfo=timezone.utc)
    with pytest.raises(InvalidRoleAssignmentPeriod):
        RoleAssignment(
            RoleAssignmentId("assignment-1"),
            OrganizationId("org-1"),
            RoleId("role-1"),
            make_actor(),
            start,
            start - timedelta(seconds=1),
        )


def test_assignment_rejects_invalid_types() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    valid = (OrganizationId("org-1"), RoleId("role-1"), make_actor(), start)
    with pytest.raises(ValueError):
        RoleAssignment(cast(RoleAssignmentId, object()), *valid)
    with pytest.raises(ValueError):
        RoleAssignment(
            RoleAssignmentId("assignment-1"), cast(OrganizationId, object()), *valid[1:]
        )
    with pytest.raises(ValueError):
        RoleAssignment(
            RoleAssignmentId("assignment-1"),
            valid[0],
            cast(RoleId, object()),
            *valid[2:],
        )
    with pytest.raises(ValueError):
        RoleAssignment(
            RoleAssignmentId("assignment-1"),
            valid[0],
            valid[1],
            cast(ActorRef, object()),
            start,
        )
    with pytest.raises(ValueError):
        RoleAssignment(
            RoleAssignmentId("assignment-1"),
            valid[0],
            valid[1],
            valid[2],
            cast(datetime, object()),
        )
    with pytest.raises(ValueError):
        RoleAssignment(
            RoleAssignmentId("assignment-1"),
            valid[0],
            valid[1],
            valid[2],
            start,
            cast(datetime, object()),
        )


def test_assignment_rejects_naive_datetimes() -> None:
    naive = datetime(2026, 1, 1)
    with pytest.raises(ValueError):
        RoleAssignment(
            RoleAssignmentId("assignment-1"),
            OrganizationId("org-1"),
            RoleId("role-1"),
            make_actor(),
            naive,
        )
    with pytest.raises(ValueError):
        RoleAssignment(
            RoleAssignmentId("assignment-1"),
            OrganizationId("org-1"),
            RoleId("role-1"),
            make_actor(),
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            naive,
        )


def test_assignment_normalizes_aware_non_utc_bounds_and_allows_equal_bounds() -> None:
    offset = timezone(timedelta(hours=2))
    start = datetime(2026, 1, 1, 12, tzinfo=offset)
    end = datetime(2026, 1, 1, 12, tzinfo=offset)
    assignment = RoleAssignment(
        RoleAssignmentId("assignment-1"),
        OrganizationId("org-1"),
        RoleId("role-1"),
        make_actor(),
        start,
        end,
    )
    assert assignment.starts_at == datetime(2026, 1, 1, 10, tzinfo=timezone.utc)
    assert assignment.ends_at == datetime(2026, 1, 1, 10, tzinfo=timezone.utc)
    assert assignment.is_effective_at(assignment.starts_at)


def test_is_effective_at_rejects_non_datetime() -> None:
    assignment = RoleAssignment(
        RoleAssignmentId("assignment-1"),
        OrganizationId("org-1"),
        RoleId("role-1"),
        make_actor(),
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    with pytest.raises(ValueError):
        assignment.is_effective_at(cast(datetime, object()))


def test_assignment_is_immutable() -> None:
    assignment = RoleAssignment(
        RoleAssignmentId("assignment-1"),
        OrganizationId("org-1"),
        RoleId("role-1"),
        make_actor(),
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    with pytest.raises(FrozenInstanceError):
        assignment.role_id = RoleId("role-2")  # type: ignore[misc]


def test_organization_rejects_cross_organization_assignment_and_duplicates() -> None:
    organization = Organization(
        OrganizationId("org-1"), "AEOS", OrganizationStatus.ACTIVE
    )
    role = Role(RoleId("role-1"), organization.organization_id, "Analyst")
    organization.add_role(role)
    assignment = RoleAssignment(
        RoleAssignmentId("assignment-1"),
        OrganizationId("org-2"),
        role.role_id,
        make_actor(),
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    with pytest.raises(RoleOrganizationMismatch):
        organization.add_assignment(assignment)
    valid = RoleAssignment(
        RoleAssignmentId("assignment-1"),
        organization.organization_id,
        role.role_id,
        make_actor(),
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    organization.add_assignment(valid)
    with pytest.raises(DuplicateRoleAssignment):
        organization.add_assignment(valid)
