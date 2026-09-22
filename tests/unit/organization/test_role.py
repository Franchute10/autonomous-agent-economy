import pytest
from dataclasses import FrozenInstanceError
from typing import cast

from aeos.core import OrganizationId, RoleId
from aeos.organization.domain.errors import InvalidRoleName
from aeos.organization.domain.role import Role


def test_role_preserves_identity_ownership_and_responsibilities() -> None:
    organization_id = OrganizationId("org-1")
    role = Role(RoleId("role-1"), organization_id, "Analyst", "Studies results")
    assert role.role_id == RoleId("role-1")
    assert role.organization_id == organization_id
    assert role.responsibilities == "Studies results"


@pytest.mark.parametrize("name", ["", "   "])
def test_role_rejects_blank_name(name: str) -> None:
    with pytest.raises(InvalidRoleName):
        Role(RoleId("role-1"), OrganizationId("org-1"), name)


def test_role_rejects_invalid_types() -> None:
    with pytest.raises(ValueError):
        Role(cast(RoleId, object()), OrganizationId("org-1"), "Analyst")
    with pytest.raises(ValueError):
        Role(RoleId("role-1"), cast(OrganizationId, object()), "Analyst")
    with pytest.raises(ValueError):
        Role(RoleId("role-1"), OrganizationId("org-1"), "Analyst", 42)  # type: ignore[arg-type]


def test_role_is_immutable() -> None:
    role = Role(RoleId("role-1"), OrganizationId("org-1"), "Analyst")
    with pytest.raises(FrozenInstanceError):
        role.name = "Other"  # type: ignore[misc]
