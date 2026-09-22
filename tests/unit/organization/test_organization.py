import pytest
from typing import cast

from aeos.core import OrganizationId, VersionRef
from aeos.organization import Organization, OrganizationStatus
from aeos.organization.domain.errors import (
    DuplicateRole,
    InvalidOrganizationName,
    RoleOrganizationMismatch,
)
from aeos.organization.domain.role import Role
from aeos.core import RoleId


def test_organization_preserves_typed_identity_and_reference() -> None:
    identifier = OrganizationId("org-1")
    constitution = VersionRef("constitution", "3")
    organization = Organization(
        identifier, " AEOS ", OrganizationStatus.ACTIVE, constitution
    )
    assert organization.organization_id is identifier
    assert organization.name == " AEOS "
    assert organization.status is OrganizationStatus.ACTIVE
    assert organization.current_constitution == constitution


@pytest.mark.parametrize("name", ["", "   "])
def test_organization_rejects_blank_name(name: str) -> None:
    with pytest.raises(InvalidOrganizationName):
        Organization(OrganizationId("org-1"), name, OrganizationStatus.ACTIVE)


def test_organization_rejects_invalid_types() -> None:
    with pytest.raises(ValueError):
        Organization(cast(OrganizationId, object()), "AEOS", OrganizationStatus.ACTIVE)
    with pytest.raises(ValueError):
        Organization(
            OrganizationId("org-1"), "AEOS", cast(OrganizationStatus, object())
        )
    with pytest.raises(ValueError):
        Organization(
            OrganizationId("org-1"),
            "AEOS",
            OrganizationStatus.ACTIVE,
            cast(VersionRef, object()),
        )


def test_organization_controls_status_and_role_collection() -> None:
    organization = Organization(
        OrganizationId("org-1"), "AEOS", OrganizationStatus.ACTIVE
    )
    role = Role(RoleId("role-1"), organization.organization_id, "Analyst")
    organization.add_role(role)
    organization.change_status(OrganizationStatus.INACTIVE)
    assert organization.status is OrganizationStatus.INACTIVE
    with pytest.raises(TypeError):
        organization.roles[role.role_id] = role  # type: ignore[index]
    with pytest.raises(DuplicateRole):
        organization.add_role(role)


def test_organization_rejects_role_from_another_organization() -> None:
    organization = Organization(
        OrganizationId("org-1"), "AEOS", OrganizationStatus.ACTIVE
    )
    role = Role(RoleId("role-1"), OrganizationId("org-2"), "Analyst")
    with pytest.raises(RoleOrganizationMismatch):
        organization.add_role(role)


def test_organization_rejects_assignment_for_unregistered_role() -> None:
    from datetime import datetime, timezone

    from aeos.core import ActorKind, ActorRef, RoleAssignmentId
    from aeos.organization import RoleAssignment

    organization = Organization(
        OrganizationId("org-1"), "AEOS", OrganizationStatus.ACTIVE
    )
    assignment = RoleAssignment(
        RoleAssignmentId("assignment-1"),
        organization.organization_id,
        RoleId("role-1"),
        ActorRef(OrganizationId("actor-1"), ActorKind.HUMAN),
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    with pytest.raises(RoleOrganizationMismatch):
        organization.add_assignment(assignment)


def test_assignments_collection_is_externally_read_only() -> None:
    from datetime import datetime, timezone

    from aeos.core import ActorKind, ActorRef, RoleAssignmentId
    from aeos.organization import RoleAssignment

    organization = Organization(
        OrganizationId("org-1"), "AEOS", OrganizationStatus.ACTIVE
    )
    role = Role(RoleId("role-1"), organization.organization_id, "Analyst")
    organization.add_role(role)
    assignment = RoleAssignment(
        RoleAssignmentId("assignment-1"),
        organization.organization_id,
        role.role_id,
        ActorRef(OrganizationId("actor-1"), ActorKind.HUMAN),
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    organization.add_assignment(assignment)
    with pytest.raises(TypeError):
        organization.assignments[assignment.role_assignment_id] = assignment  # type: ignore[index]


def test_change_status_rejects_invalid_type() -> None:
    organization = Organization(
        OrganizationId("org-1"), "AEOS", OrganizationStatus.ACTIVE
    )
    with pytest.raises(ValueError):
        organization.change_status(cast(OrganizationStatus, object()))


def test_organization_does_not_expose_uncontrolled_field_mutation() -> None:
    organization = Organization(
        OrganizationId("org-1"), "AEOS", OrganizationStatus.ACTIVE
    )
    with pytest.raises(AttributeError):
        organization.name = "other"  # type: ignore[misc]
