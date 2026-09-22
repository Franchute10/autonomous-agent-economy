from typing import Any, cast

import pytest

from aeos.core import ResourceAccountId, ResourceId, ResourceQuantity
from aeos.economics.domain import (
    LedgerPosting,
    PostingResourceMismatch,
    PostingUnitMismatch,
    Resource,
    ResourceAccount,
    ResourceAccountType,
    TransactionOrganizationMismatch,
    ZeroPosting,
)


def test_signed_posting_preserves_typed_references_and_quantity() -> None:
    posting = LedgerPosting(
        ResourceId("cash"),
        ResourceAccountId("available"),
        ResourceQuantity("-5", "USD"),
    )
    assert posting.resource_id == ResourceId("cash")
    assert posting.resource_account_id == ResourceAccountId("available")
    assert posting.quantity == ResourceQuantity("-5", "USD")


def test_zero_posting_is_rejected() -> None:
    with pytest.raises(ZeroPosting):
        LedgerPosting(
            ResourceId("cash"),
            ResourceAccountId("available"),
            ResourceQuantity("0", "USD"),
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("resource_id", object()),
        ("resource_account_id", object()),
        ("quantity", object()),
    ],
)
def test_invalid_typed_fields_are_rejected(field: str, value: object) -> None:
    values: dict[str, object] = {
        "resource_id": ResourceId("cash"),
        "resource_account_id": ResourceAccountId("available"),
        "quantity": ResourceQuantity("1", "USD"),
    }
    values[field] = value
    with pytest.raises(ValueError):
        LedgerPosting(**values)  # type: ignore[arg-type]


def test_posting_resource_unit_mismatch_is_rejected() -> None:
    from aeos.core import OrganizationId, ResourceUnit

    resource = Resource(
        ResourceId("cash"), OrganizationId("org"), "Cash", ResourceUnit("USD")
    )
    with pytest.raises(PostingUnitMismatch):
        LedgerPosting(
            ResourceId("cash"),
            ResourceAccountId("available"),
            ResourceQuantity("1", "EUR"),
            resource=resource,
        )


def test_posting_is_immutable() -> None:
    posting = LedgerPosting(
        ResourceId("cash"), ResourceAccountId("available"), ResourceQuantity("1", "USD")
    )
    with pytest.raises(AttributeError):
        posting.quantity = ResourceQuantity("2", "USD")  # type: ignore[misc]


def test_embedded_definitions_and_controlled_invalid_types() -> None:
    from aeos.core import OrganizationId, ResourceUnit

    resource = Resource(
        ResourceId("cash"), OrganizationId("org"), "Cash", ResourceUnit("USD")
    )
    account = ResourceAccount.for_resource(
        ResourceAccountId("available"), resource, ResourceAccountType.AVAILABLE
    )
    posting = LedgerPosting(
        ResourceId("cash"),
        ResourceAccountId("available"),
        ResourceQuantity("1", "USD"),
        resource,
        account,
    )
    assert posting.resource is resource
    assert posting.resource_account is account
    with pytest.raises(ValueError):
        LedgerPosting(
            ResourceId("cash"),
            ResourceAccountId("available"),
            ResourceQuantity("1", "USD"),
            cast(Any, object()),
        )
    with pytest.raises(ValueError):
        LedgerPosting(
            ResourceId("cash"),
            ResourceAccountId("available"),
            ResourceQuantity("1", "USD"),
            resource,
            cast(Any, object()),
        )


def test_posting_definition_mismatches_are_rejected() -> None:
    from aeos.core import OrganizationId, ResourceUnit

    resource = Resource(
        ResourceId("cash"), OrganizationId("org"), "Cash", ResourceUnit("USD")
    )
    with pytest.raises(PostingResourceMismatch):
        LedgerPosting(
            ResourceId("other"),
            ResourceAccountId("available"),
            ResourceQuantity("1", "USD"),
            resource,
        )
    account = ResourceAccount.for_resource(
        ResourceAccountId("available"), resource, ResourceAccountType.AVAILABLE
    )
    with pytest.raises(PostingResourceMismatch):
        LedgerPosting(
            ResourceId("cash"),
            ResourceAccountId("other"),
            ResourceQuantity("1", "USD"),
            resource,
            account,
        )
    other_resource = Resource(
        ResourceId("other"), OrganizationId("org"), "Other", ResourceUnit("USD")
    )
    other_account = ResourceAccount.for_resource(
        ResourceAccountId("available"), other_resource, ResourceAccountType.AVAILABLE
    )
    with pytest.raises(PostingResourceMismatch):
        LedgerPosting(
            ResourceId("cash"),
            ResourceAccountId("available"),
            ResourceQuantity("1", "USD"),
            resource,
            other_account,
        )


def test_validate_against_rejects_organization_and_needs_no_repository() -> None:
    from aeos.core import OrganizationId, ResourceUnit

    resource = Resource(
        ResourceId("cash"), OrganizationId("org"), "Cash", ResourceUnit("USD")
    )
    posting = LedgerPosting(
        ResourceId("cash"), ResourceAccountId("available"), ResourceQuantity("1", "USD")
    )
    with pytest.raises(TransactionOrganizationMismatch):
        posting.validate_against(OrganizationId("other"), resource)
    posting.validate_against(OrganizationId("org"), resource)
