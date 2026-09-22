from dataclasses import FrozenInstanceError
from typing import cast

import pytest

from aeos.core import OrganizationId, ResourceAccountId, ResourceId, ResourceUnit
from aeos.economics import (
    AccountOrganizationMismatch,
    AccountResourceMismatch,
    InvalidAccountType,
    Resource,
    ResourceAccount,
    ResourceAccountType,
)


def make_resource(organization_id: str = "org-1") -> Resource:
    return Resource(
        ResourceId("resource-1"),
        OrganizationId(organization_id),
        "USD",
        ResourceUnit("USD"),
    )


def test_resource_account_is_structural_and_resource_bound() -> None:
    resource = make_resource()
    account = ResourceAccount.for_resource(
        ResourceAccountId("account-1"), resource, ResourceAccountType.AVAILABLE
    )

    assert account.organization_id is resource.organization_id
    assert account.resource_id is resource.resource_id
    assert account.account_type is ResourceAccountType.AVAILABLE
    account.validate_against(resource)
    with pytest.raises(FrozenInstanceError):
        account.account_type = ResourceAccountType.RESERVED  # type: ignore[misc]
    assert not hasattr(account, "balance")
    assert not hasattr(account, "available_amount")
    assert not hasattr(account, "quantity")
    assert not hasattr(account, "reserved_amount")
    assert not hasattr(account, "committed_amount")
    assert not hasattr(account, "consumed_amount")


def test_account_type_set_is_exact() -> None:
    assert {member.name for member in ResourceAccountType} == {
        "AVAILABLE",
        "RESERVED",
        "COMMITTED",
        "CONSUMED",
        "EXTERNAL_SOURCE_OR_SINK",
    }


def test_account_rejects_invalid_type() -> None:
    with pytest.raises(InvalidAccountType):
        ResourceAccount(
            ResourceAccountId("account-1"),
            OrganizationId("org-1"),
            ResourceId("resource-1"),
            cast(ResourceAccountType, "available"),
        )


def test_account_rejects_invalid_types_and_supports_optional_name() -> None:
    with pytest.raises(ValueError):
        ResourceAccount(
            cast(ResourceAccountId, object()),
            OrganizationId("org-1"),
            ResourceId("resource-1"),
            ResourceAccountType.AVAILABLE,
        )
    with pytest.raises(ValueError):
        ResourceAccount(
            ResourceAccountId("account-1"),
            cast(OrganizationId, object()),
            ResourceId("resource-1"),
            ResourceAccountType.AVAILABLE,
        )
    with pytest.raises(ValueError):
        ResourceAccount(
            ResourceAccountId("account-1"),
            OrganizationId("org-1"),
            cast(ResourceId, object()),
            ResourceAccountType.AVAILABLE,
        )
    assert (
        ResourceAccount(
            ResourceAccountId("account-1"),
            OrganizationId("org-1"),
            ResourceId("resource-1"),
            ResourceAccountType.AVAILABLE,
        ).name
        is None
    )
    assert (
        ResourceAccount(
            ResourceAccountId("account-1"),
            OrganizationId("org-1"),
            ResourceId("resource-1"),
            ResourceAccountType.AVAILABLE,
            "Available USD",
        ).name
        == "Available USD"
    )
    for invalid_name in ["", "   ", cast(str, 123)]:
        with pytest.raises(ValueError):
            ResourceAccount(
                ResourceAccountId("account-1"),
                OrganizationId("org-1"),
                ResourceId("resource-1"),
                ResourceAccountType.AVAILABLE,
                invalid_name,
            )


def test_for_resource_derives_relationship_and_preserves_fields() -> None:
    resource = make_resource("org-1")
    account = ResourceAccount.for_resource(
        ResourceAccountId("account-1"),
        resource,
        ResourceAccountType.RESERVED,
        "Reserved USD",
    )
    assert account.organization_id is resource.organization_id
    assert account.resource_id is resource.resource_id
    assert account.account_type is ResourceAccountType.RESERVED
    assert account.name == "Reserved USD"
    with pytest.raises(ValueError):
        ResourceAccount.for_resource(
            ResourceAccountId("account-1"),
            cast(Resource, object()),
            ResourceAccountType.AVAILABLE,
        )
    with pytest.raises(ValueError):
        ResourceAccount.for_resource(
            cast(ResourceAccountId, object()), resource, ResourceAccountType.AVAILABLE
        )
    with pytest.raises(InvalidAccountType):
        ResourceAccount.for_resource(
            ResourceAccountId("account-1"),
            resource,
            cast(ResourceAccountType, "available"),
        )


def test_account_resource_organization_mismatch_is_rejected() -> None:
    resource = make_resource("org-1")
    account = ResourceAccount(
        ResourceAccountId("account-1"),
        OrganizationId("org-2"),
        resource.resource_id,
        ResourceAccountType.AVAILABLE,
    )
    with pytest.raises(AccountOrganizationMismatch):
        account.validate_against(resource)


def test_account_validation_rejects_different_resource() -> None:
    account = ResourceAccount(
        ResourceAccountId("account-1"),
        OrganizationId("org-1"),
        ResourceId("resource-1"),
        ResourceAccountType.AVAILABLE,
    )
    with pytest.raises(AccountResourceMismatch):
        account.validate_against(
            Resource(
                ResourceId("resource-2"),
                OrganizationId("org-1"),
                "USD",
                ResourceUnit("USD"),
            )
        )


def test_validate_against_requires_a_resource() -> None:
    account = ResourceAccount(
        ResourceAccountId("account-1"),
        OrganizationId("org-1"),
        ResourceId("resource-1"),
        ResourceAccountType.AVAILABLE,
    )
    with pytest.raises(ValueError):
        account.validate_against(object())  # type: ignore[arg-type]
