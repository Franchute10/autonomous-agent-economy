from datetime import datetime, timezone

import pytest

from aeos.core import (
    ActorKind,
    ActorRef,
    CausationId,
    CorrelationId,
    EconomicTransactionId,
    IdempotencyKey,
    OrganizationId,
    ResourceAccountId,
    ResourceId,
    ResourceQuantity,
    ResourceUnit,
    TraceContext,
)
from aeos.economics.domain import (
    EconomicTransaction,
    EconomicTransactionType,
    LedgerPosting,
    PostingResourceMismatch,
    PostingUnitMismatch,
    Resource,
    ResourceAccount,
    ResourceAccountType,
    UnbalancedEconomicTransaction,
    EmptyTransaction,
    MissingResourceAccountDefinition,
    MissingResourceDefinition,
    TransactionOrganizationMismatch,
    ZeroPosting,
)


ORG = OrganizationId("org-1")
ACTOR = ActorRef(ORG, ActorKind.SYSTEM)
WHEN = datetime(2026, 1, 1, tzinfo=timezone.utc)
TRACE = TraceContext(
    ACTOR,
    CorrelationId("correlation-1"),
    IdempotencyKey("idempotency-1"),
    CausationId("cause-1"),
)


def posting(account: str, amount: str, resource: str = "usd") -> LedgerPosting:
    return LedgerPosting(
        ResourceId(resource),
        ResourceAccountId(account),
        ResourceQuantity(amount, ResourceUnit("unit")),
    )


def transaction(*postings: LedgerPosting) -> EconomicTransaction:
    return EconomicTransaction(
        EconomicTransactionId("tx-1"),
        ORG,
        EconomicTransactionType.ALLOCATE,
        WHEN,
        WHEN,
        TRACE,
        postings,
    )


def test_transaction_types_are_exactly_approved() -> None:
    assert {member.name for member in EconomicTransactionType} == {
        "OPENING",
        "ALLOCATE",
        "RESERVE",
        "RELEASE",
        "COMMIT",
        "CONSUME",
        "CREDIT",
        "REFUND",
        "ADJUST",
    }


def test_balances_three_legs_and_multi_resource_independently() -> None:
    result = transaction(
        posting("a", "-10"),
        posting("b", "4"),
        posting("c", "6"),
        posting("d", "-100", "tokens"),
        posting("e", "100", "tokens"),
    )
    assert len(result.postings) == 5


def test_unbalanced_resource_fails() -> None:
    with pytest.raises(UnbalancedEconomicTransaction):
        transaction(posting("a", "-5"), posting("b", "4"))


def test_two_leg_balance_succeeds() -> None:
    assert transaction(posting("a", "-5"), posting("b", "5")).postings


def test_same_resource_mixed_units_fail() -> None:
    with pytest.raises(PostingUnitMismatch):
        transaction(
            posting("a", "-1"),
            LedgerPosting(
                ResourceId("usd"),
                ResourceAccountId("b"),
                ResourceQuantity("1", "other-unit"),
            ),
        )


def test_empty_and_single_transactions_raise_empty_transaction() -> None:
    with pytest.raises(EmptyTransaction):
        transaction()
    with pytest.raises(EmptyTransaction):
        transaction(posting("a", "1"))


def test_zero_posting_raises_zero_posting() -> None:
    with pytest.raises(ZeroPosting):
        posting("a", "0")


def test_exact_decimal_balancing_and_immutability() -> None:
    value = transaction(posting("a", "-0.3"), posting("b", "0.1"), posting("c", "0.2"))
    assert value.postings[0].quantity == ResourceQuantity("-0.3", "unit")
    with pytest.raises(AttributeError):
        value.organization_id = OrganizationId("other")  # type: ignore[misc]
    with pytest.raises(AttributeError):
        value.postings += (posting("d", "1"),)  # type: ignore[misc]


def test_utc_timestamps_are_normalized_and_naive_rejected() -> None:
    with pytest.raises(ValueError):
        EconomicTransaction(
            EconomicTransactionId("tx-1"),
            ORG,
            EconomicTransactionType.OPENING,
            datetime(2026, 1, 1),
            WHEN,
            TRACE,
            (posting("a", "-1"), posting("b", "1")),
        )
    with pytest.raises(ValueError):
        EconomicTransaction(
            EconomicTransactionId("tx-1"),
            ORG,
            EconomicTransactionType.OPENING,
            WHEN,
            datetime(2026, 1, 1),
            TRACE,
            (posting("a", "-1"), posting("b", "1")),
        )


def test_direct_constructor_requires_and_preserves_postings_tuple() -> None:
    values = (posting("a", "-1"), posting("b", "1"))
    value = EconomicTransaction(
        EconomicTransactionId("tx-1"),
        ORG,
        EconomicTransactionType.OPENING,
        WHEN,
        WHEN,
        TRACE,
        values,
    )
    assert value.postings is values
    with pytest.raises(ValueError):
        EconomicTransaction(
            EconomicTransactionId("tx-1"),
            ORG,
            EconomicTransactionType.OPENING,
            WHEN,
            WHEN,
            TRACE,
            list(values),  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError):
        EconomicTransaction(
            EconomicTransactionId("tx-1"),
            ORG,
            EconomicTransactionType.OPENING,
            WHEN,
            WHEN,
            TRACE,
            {values[0], values[1]},  # type: ignore[arg-type]
        )


def test_aware_non_utc_timestamps_are_normalized() -> None:
    from datetime import timedelta, timezone as dt_timezone

    value = EconomicTransaction(
        EconomicTransactionId("tx-1"),
        ORG,
        EconomicTransactionType.OPENING,
        datetime(2026, 1, 1, 3, tzinfo=dt_timezone(timedelta(hours=3))),
        datetime(2026, 1, 1, 3, tzinfo=dt_timezone(timedelta(hours=3))),
        TRACE,
        (posting("a", "-1"), posting("b", "1")),
    )
    assert value.occurred_at == WHEN
    assert value.effective_at == WHEN


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("economic_transaction_id", object()),
        ("organization_id", object()),
        ("transaction_type", object()),
        ("trace", object()),
        ("occurred_at", object()),
        ("effective_at", object()),
    ],
)
def test_transaction_invalid_boundaries_are_controlled_value_errors(
    field: str, value: object
) -> None:
    values: dict[str, object] = {
        "economic_transaction_id": EconomicTransactionId("tx-1"),
        "organization_id": ORG,
        "transaction_type": EconomicTransactionType.OPENING,
        "occurred_at": WHEN,
        "effective_at": WHEN,
        "trace": TRACE,
        "postings": (posting("a", "-1"), posting("b", "1")),
    }
    values[field] = value
    with pytest.raises(ValueError):
        EconomicTransaction(**values)  # type: ignore[arg-type]


def test_every_posting_must_be_a_ledger_posting() -> None:
    with pytest.raises(ValueError):
        EconomicTransaction(
            EconomicTransactionId("tx-1"),
            ORG,
            EconomicTransactionType.OPENING,
            WHEN,
            WHEN,
            TRACE,
            (object(), object()),  # type: ignore[arg-type]
        )


def test_from_definitions_validates_postings_before_definition_lookup() -> None:
    with pytest.raises(ValueError):
        EconomicTransaction.from_definitions(
            economic_transaction_id=EconomicTransactionId("tx-1"),
            organization_id=ORG,
            transaction_type=EconomicTransactionType.OPENING,
            occurred_at=WHEN,
            effective_at=WHEN,
            trace=TRACE,
            postings=[object(), posting("b", "1")],  # type: ignore[list-item]
            resources={},
        )


def test_definition_context_enforces_organization_resource_account_and_unit() -> None:
    resource = Resource(ResourceId("usd"), ORG, "USD", ResourceUnit("unit"))
    account = ResourceAccount.for_resource(
        ResourceAccountId("a"), resource, ResourceAccountType.AVAILABLE
    )
    good = LedgerPosting(
        ResourceId("usd"), ResourceAccountId("a"), ResourceQuantity("-1", "unit")
    )
    other = ResourceAccount.for_resource(
        ResourceAccountId("b"), resource, ResourceAccountType.RESERVED
    )
    EconomicTransaction.from_definitions(
        economic_transaction_id=EconomicTransactionId("tx-1"),
        organization_id=ORG,
        transaction_type=EconomicTransactionType.OPENING,
        occurred_at=WHEN,
        effective_at=WHEN,
        trace=TRACE,
        postings=(
            good,
            LedgerPosting(
                ResourceId("usd"), ResourceAccountId("b"), ResourceQuantity("1", "unit")
            ),
        ),
        resources={resource.resource_id: resource},
        resource_accounts={
            account.resource_account_id: account,
            other.resource_account_id: other,
        },
    )


def test_definition_context_rejects_account_for_another_resource() -> None:
    resource = Resource(ResourceId("usd"), ORG, "USD", ResourceUnit("unit"))
    tokens = Resource(ResourceId("tokens"), ORG, "Tokens", ResourceUnit("unit"))
    account = ResourceAccount.for_resource(
        ResourceAccountId("a"), resource, ResourceAccountType.AVAILABLE
    )
    with pytest.raises(PostingResourceMismatch):
        EconomicTransaction.from_definitions(
            economic_transaction_id=EconomicTransactionId("tx-1"),
            organization_id=ORG,
            transaction_type=EconomicTransactionType.OPENING,
            occurred_at=WHEN,
            effective_at=WHEN,
            trace=TRACE,
            postings=(
                LedgerPosting(
                    ResourceId("tokens"),
                    ResourceAccountId("a"),
                    ResourceQuantity("-1", "unit"),
                ),
                LedgerPosting(
                    ResourceId("tokens"),
                    ResourceAccountId("b"),
                    ResourceQuantity("1", "unit"),
                ),
            ),
            resources={resource.resource_id: resource, tokens.resource_id: tokens},
            resource_accounts={account.resource_account_id: account},
        )


def test_from_definitions_missing_entries_fail_only_when_mapping_supplied() -> None:
    postings = (posting("a", "-1"), posting("b", "1"))
    assert EconomicTransaction.from_definitions(
        economic_transaction_id=EconomicTransactionId("tx-1"),
        organization_id=ORG,
        transaction_type=EconomicTransactionType.OPENING,
        occurred_at=WHEN,
        effective_at=WHEN,
        trace=TRACE,
        postings=postings,
    )
    with pytest.raises(MissingResourceDefinition):
        EconomicTransaction.from_definitions(
            economic_transaction_id=EconomicTransactionId("tx-1"),
            organization_id=ORG,
            transaction_type=EconomicTransactionType.OPENING,
            occurred_at=WHEN,
            effective_at=WHEN,
            trace=TRACE,
            postings=postings,
            resources={},
        )
    with pytest.raises(MissingResourceAccountDefinition):
        EconomicTransaction.from_definitions(
            economic_transaction_id=EconomicTransactionId("tx-1"),
            organization_id=ORG,
            transaction_type=EconomicTransactionType.OPENING,
            occurred_at=WHEN,
            effective_at=WHEN,
            trace=TRACE,
            postings=postings,
            resource_accounts={},
        )


def test_cross_organization_definitions_fail() -> None:
    other = OrganizationId("org-2")
    resource = Resource(ResourceId("usd"), other, "USD", ResourceUnit("unit"))
    with pytest.raises(TransactionOrganizationMismatch):
        EconomicTransaction.from_definitions(
            economic_transaction_id=EconomicTransactionId("tx-1"),
            organization_id=ORG,
            transaction_type=EconomicTransactionType.OPENING,
            occurred_at=WHEN,
            effective_at=WHEN,
            trace=TRACE,
            postings=(
                LedgerPosting(
                    ResourceId("usd"),
                    ResourceAccountId("a"),
                    ResourceQuantity("-1", "unit"),
                ),
                LedgerPosting(
                    ResourceId("usd"),
                    ResourceAccountId("b"),
                    ResourceQuantity("1", "unit"),
                ),
            ),
            resources={resource.resource_id: resource},
        )
    account = ResourceAccount(
        ResourceAccountId("a"),
        other,
        resource.resource_id,
        ResourceAccountType.AVAILABLE,
    )
    with pytest.raises(TransactionOrganizationMismatch):
        EconomicTransaction.from_definitions(
            economic_transaction_id=EconomicTransactionId("tx-1"),
            organization_id=ORG,
            transaction_type=EconomicTransactionType.OPENING,
            occurred_at=WHEN,
            effective_at=WHEN,
            trace=TRACE,
            postings=(
                LedgerPosting(
                    ResourceId("usd"),
                    ResourceAccountId("a"),
                    ResourceQuantity("-1", "unit"),
                ),
                LedgerPosting(
                    ResourceId("usd"),
                    ResourceAccountId("b"),
                    ResourceQuantity("1", "unit"),
                ),
            ),
            resources={resource.resource_id: resource},
            resource_accounts={account.resource_account_id: account},
        )
