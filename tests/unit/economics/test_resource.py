from dataclasses import FrozenInstanceError
from typing import cast

import pytest

from aeos.core import OrganizationId, ResourceId, ResourceUnit
from aeos.economics import InvalidResourceName, Resource


def test_resource_preserves_typed_identity_ownership_name_and_unit() -> None:
    resource_id = ResourceId("resource-1")
    organization_id = OrganizationId("org-1")
    unit = ResourceUnit("input_tokens")
    resource = Resource(resource_id, organization_id, " OpenAI input tokens ", unit)

    assert resource.resource_id is resource_id
    assert resource.organization_id is organization_id
    assert resource.name == " OpenAI input tokens "
    assert resource.unit is unit


@pytest.mark.parametrize("name", ["", "   "])
def test_resource_rejects_blank_name(name: str) -> None:
    with pytest.raises(InvalidResourceName):
        Resource(
            ResourceId("resource-1"), OrganizationId("org-1"), name, ResourceUnit("USD")
        )


def test_resource_rejects_invalid_types() -> None:
    with pytest.raises(ValueError):
        Resource(
            cast(ResourceId, object()),
            OrganizationId("org-1"),
            "USD",
            ResourceUnit("USD"),
        )
    with pytest.raises(ValueError):
        Resource(
            ResourceId("resource-1"),
            cast(OrganizationId, object()),
            "USD",
            ResourceUnit("USD"),
        )
    with pytest.raises(ValueError):
        Resource(
            ResourceId("resource-1"),
            OrganizationId("org-1"),
            "USD",
            cast(ResourceUnit, object()),
        )
    with pytest.raises(ValueError):
        Resource(
            ResourceId("resource-1"),
            OrganizationId("org-1"),
            "USD",
            ResourceUnit("USD"),
            cast(str, 123),
        )


def test_resource_description_is_optional_and_preserved() -> None:
    assert (
        Resource(
            ResourceId("resource-1"),
            OrganizationId("org-1"),
            "USD",
            ResourceUnit("USD"),
        ).description
        is None
    )
    resource = Resource(
        ResourceId("resource-1"),
        OrganizationId("org-1"),
        "USD",
        ResourceUnit("USD"),
        "US dollar resource",
    )
    assert resource.description == "US dollar resource"


def test_resource_is_immutable_and_has_no_quantity_or_balance() -> None:
    resource = Resource(
        ResourceId("resource-1"), OrganizationId("org-1"), "USD", ResourceUnit("USD")
    )
    with pytest.raises(FrozenInstanceError):
        resource.unit = ResourceUnit("EUR")  # type: ignore[misc]
    assert not hasattr(resource, "quantity")
    assert not hasattr(resource, "balance")
