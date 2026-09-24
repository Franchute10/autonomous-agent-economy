from datetime import datetime, timedelta, timezone
from typing import Any, cast

import pytest

from aeos.core import (
    ActorKind,
    ActorRef,
    BudgetId,
    CausationId,
    CorrelationId,
    IdempotencyKey,
    OrganizationId,
    ReservationId,
    ResourceId,
    ResourceQuantity,
    TraceContext,
    ResourceUnit,
)
from aeos.economics import (
    Budget,
    BudgetLimit,
    BudgetLimitMismatch,
    DuplicateBudgetLimit,
    InvalidBudgetLimit,
    InvalidBudgetPeriod,
    InvalidReservationPeriod,
    InvalidReservationState,
    InvalidReservationQuantity,
    ReservationBudgetMismatch,
    Reservation,
    ReservationState,
)


ORG = OrganizationId("org-1")
WHEN = datetime(2026, 1, 1, tzinfo=timezone.utc)
UNTIL = datetime(2026, 1, 31, tzinfo=timezone.utc)
TRACE = TraceContext(
    ActorRef(ORG, ActorKind.SYSTEM),
    CorrelationId("corr-1"),
    IdempotencyKey("idem-1"),
    CausationId("cause-1"),
)


def budget() -> Budget:
    return Budget(
        BudgetId("budget-1"),
        ORG,
        "experiment",
        (
            BudgetLimit(
                ResourceId("compute"),
                ResourceQuantity("10", ResourceUnit("unit")),
                WHEN,
                UNTIL,
            ),
        ),
        WHEN,
        UNTIL,
        TRACE,
    )


def reservation(quantity: str = "3") -> Reservation:
    return Reservation(
        ReservationId("reservation-1"),
        BudgetId("budget-1"),
        ORG,
        ResourceId("compute"),
        ResourceQuantity(quantity, "unit"),
        WHEN,
        UNTIL,
        TRACE,
    )


def test_reservation_must_be_positive_and_covered_by_budget() -> None:
    with pytest.raises(InvalidReservationQuantity):
        reservation("0")
    reservation().validate_against(budget())
    with pytest.raises(BudgetLimitMismatch):
        reservation("11").validate_against(budget())


def test_budget_limit_is_positive_and_reservation_lifecycle_is_immutable() -> None:
    with pytest.raises(InvalidBudgetLimit):
        BudgetLimit(ResourceId("compute"), ResourceQuantity("0", "unit"), WHEN)
    original = reservation()
    released = original.released(WHEN)
    assert original.state is ReservationState.ACTIVE
    assert released.state is ReservationState.RELEASED
    assert original is not released


def test_limit_predicate_is_safe_and_budget_limits_do_not_overlap() -> None:
    limit = budget().limits[0]
    assert limit.covers(ResourceQuantity("10", "unit"), WHEN)
    assert limit.covers(ResourceQuantity("1", "unit"), WHEN)
    assert not limit.covers(ResourceQuantity("11", "unit"), WHEN)
    assert not limit.covers(ResourceQuantity("0", "unit"), WHEN)
    assert not limit.covers(ResourceQuantity("-1", "unit"), WHEN)
    assert not limit.covers(ResourceQuantity("1", "other"), WHEN)
    overlapping = BudgetLimit(
        ResourceId("compute"),
        ResourceQuantity("5", "unit"),
        WHEN + timedelta(days=1),
        UNTIL,
    )
    with pytest.raises(DuplicateBudgetLimit):
        Budget(
            BudgetId("budget-1"),
            ORG,
            "experiment",
            (limit, overlapping),
            WHEN,
            UNTIL,
            TRACE,
        )


def test_non_overlapping_limits_and_different_resources_are_allowed() -> None:
    first = BudgetLimit(
        ResourceId("compute"), ResourceQuantity("5", "unit"), WHEN, WHEN
    )
    second = BudgetLimit(
        ResourceId("compute"),
        ResourceQuantity("5", "unit"),
        WHEN + timedelta(days=1),
        UNTIL,
    )
    other = BudgetLimit(
        ResourceId("tokens"), ResourceQuantity("5", "unit"), WHEN, UNTIL
    )
    value = Budget(
        BudgetId("budget-1"),
        ORG,
        "experiment",
        (first, second, other),
        WHEN,
        UNTIL,
        TRACE,
    )
    assert value.limits == (first, second, other)


def test_reservation_state_and_terminal_timestamps_are_domain_controlled() -> None:
    original = reservation()
    with pytest.raises(TypeError):
        Reservation(  # type: ignore[call-arg]
            ReservationId("r2"),
            BudgetId("budget-1"),
            ORG,
            ResourceId("compute"),
            ResourceQuantity("1", "unit"),
            WHEN,
            UNTIL,
            TRACE,
            ReservationState.RELEASED,
        )
    with pytest.raises(InvalidReservationPeriod):
        original.released(WHEN - timedelta(seconds=1))
    released = original.released(
        datetime(2026, 1, 1, 1, tzinfo=timezone(timedelta(hours=1)))
    )
    assert released.state is ReservationState.RELEASED
    assert released.resolved_at == WHEN
    with pytest.raises(InvalidReservationState):
        released.committed(WHEN)


def test_expiration_and_expiry_boundaries_are_inclusive() -> None:
    original = reservation()
    assert original.is_active_at(WHEN)
    assert original.is_active_at(UNTIL)
    assert not original.is_active_at(UNTIL + timedelta(seconds=1))
    expired = original.expired(UNTIL)
    assert expired.state is ReservationState.EXPIRED
    assert expired.resolved_at == UNTIL
    with pytest.raises(InvalidReservationPeriod):
        original.expired(UNTIL - timedelta(seconds=1))
    with pytest.raises(InvalidReservationPeriod):
        original.committed(UNTIL + timedelta(seconds=1))
    with pytest.raises(InvalidReservationState):
        expired.released(UNTIL)


def test_expiration_requires_an_expiry_timestamp() -> None:
    open_ended = Reservation(
        ReservationId("reservation-open"),
        BudgetId("budget-1"),
        ORG,
        ResourceId("compute"),
        ResourceQuantity("1", "unit"),
        WHEN,
        None,
        TRACE,
    )
    with pytest.raises(InvalidReservationPeriod):
        open_ended.expired(WHEN)


@pytest.mark.parametrize(
    ("field", "value"),
    [("resource_id", object()), ("quantity", object()), ("period_start", object())],
)
def test_budget_limit_type_boundaries(field: str, value: object) -> None:
    values: dict[str, object] = {
        "resource_id": ResourceId("compute"),
        "quantity": ResourceQuantity("1", "unit"),
        "period_start": WHEN,
    }
    values[field] = value
    with pytest.raises(ValueError):
        BudgetLimit(**values)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        BudgetLimit(
            ResourceId("compute"),
            ResourceQuantity("1", "unit"),
            WHEN,
            cast(Any, object()),
        )


def test_budget_limit_period_boundaries_and_normalization() -> None:
    shifted = datetime(2026, 1, 1, 3, tzinfo=timezone(timedelta(hours=3)))
    value = BudgetLimit(
        ResourceId("compute"), ResourceQuantity("1", "unit"), shifted, shifted
    )
    assert value.period_start == WHEN
    assert value.period_end == WHEN
    assert (
        BudgetLimit(
            ResourceId("compute"), ResourceQuantity("1", "unit"), WHEN
        ).period_end
        is None
    )
    with pytest.raises(ValueError):
        BudgetLimit(
            ResourceId("compute"), ResourceQuantity("1", "unit"), datetime(2026, 1, 1)
        )
    with pytest.raises(ValueError):
        BudgetLimit(
            ResourceId("compute"),
            ResourceQuantity("1", "unit"),
            WHEN,
            datetime(2026, 1, 1),
        )
    with pytest.raises(InvalidBudgetLimit):
        BudgetLimit(ResourceId("compute"), ResourceQuantity("-1", "unit"), WHEN)
    with pytest.raises(InvalidBudgetPeriod):
        BudgetLimit(ResourceId("compute"), ResourceQuantity("1", "unit"), UNTIL, WHEN)


def test_reservation_interval_must_be_fully_covered_by_one_limit() -> None:
    limit_start = WHEN + timedelta(days=5)
    limit_end = UNTIL - timedelta(days=5)
    limited_budget = Budget(
        BudgetId("budget-limited"),
        ORG,
        "experiment",
        (
            BudgetLimit(
                ResourceId("compute"),
                ResourceQuantity("10", "unit"),
                limit_start,
                limit_end,
            ),
        ),
        WHEN,
        UNTIL,
        TRACE,
    )
    valid = Reservation(
        ReservationId("valid"),
        BudgetId("budget-limited"),
        ORG,
        ResourceId("compute"),
        ResourceQuantity("10", "unit"),
        limit_start,
        limit_end,
        TRACE,
    )
    valid.validate_against(limited_budget)
    for start, end in ((WHEN, limit_end), (limit_start, UNTIL)):
        invalid = Reservation(
            ReservationId("invalid"),
            BudgetId("budget-limited"),
            ORG,
            ResourceId("compute"),
            ResourceQuantity("1", "unit"),
            start,
            end,
            TRACE,
        )
        with pytest.raises(BudgetLimitMismatch):
            invalid.validate_against(limited_budget)
    open_limit_budget = Budget(
        BudgetId("budget-open"),
        ORG,
        "experiment",
        (BudgetLimit(ResourceId("compute"), ResourceQuantity("10", "unit"), WHEN),),
        WHEN,
        None,
        TRACE,
    )
    open_reservation = Reservation(
        ReservationId("open"),
        BudgetId("budget-open"),
        ORG,
        ResourceId("compute"),
        ResourceQuantity("1", "unit"),
        WHEN,
        None,
        TRACE,
    )
    open_reservation.validate_against(open_limit_budget)

    bounded_open_reservation = Reservation(
        ReservationId("open-bounded"),
        BudgetId("budget-limited"),
        ORG,
        ResourceId("compute"),
        ResourceQuantity("1", "unit"),
        limit_start,
        None,
        TRACE,
    )
    with pytest.raises(BudgetLimitMismatch):
        bounded_open_reservation.validate_against(limited_budget)


def test_reservation_budget_reference_has_precise_error() -> None:
    wrong_budget = Reservation(
        ReservationId("wrong-budget"),
        BudgetId("other"),
        ORG,
        ResourceId("compute"),
        ResourceQuantity("1", "unit"),
        WHEN,
        UNTIL,
        TRACE,
    )
    with pytest.raises(ReservationBudgetMismatch):
        wrong_budget.validate_against(budget())


@pytest.mark.parametrize(
    "state",
    [
        ReservationState.RELEASED,
        ReservationState.COMMITTED,
        ReservationState.EXPIRED,
    ],
)
def test_all_terminal_reservation_transitions_are_blocked(
    state: ReservationState,
) -> None:
    original = reservation()
    terminal = {
        ReservationState.RELEASED: original.released(WHEN),
        ReservationState.COMMITTED: original.committed(WHEN),
        ReservationState.EXPIRED: original.expired(UNTIL),
    }[state]
    for transition in (terminal.released, terminal.committed, terminal.expired):
        with pytest.raises(InvalidReservationState):
            transition(WHEN)
