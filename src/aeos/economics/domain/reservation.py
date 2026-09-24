"""Immutable holds against a budget before economic consumption."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from aeos.core import (
    BudgetId,
    OrganizationId,
    ReservationId,
    ResourceId,
    ResourceQuantity,
    TraceContext,
    UtcTimestamp,
    normalize_utc,
)
from aeos.economics.domain.budget import Budget
from aeos.economics.domain.errors import (
    BudgetOrganizationMismatch,
    ReservationBudgetMismatch,
    InvalidReservationPeriod,
    InvalidReservationQuantity,
    InvalidReservationState,
)


class ReservationState(StrEnum):
    ACTIVE = "active"
    RELEASED = "released"
    COMMITTED = "committed"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class Reservation:
    """One immutable authorization hold; lifecycle changes are new facts."""

    reservation_id: ReservationId
    budget_id: BudgetId
    organization_id: OrganizationId
    resource_id: ResourceId
    quantity: ResourceQuantity
    reserved_at: UtcTimestamp
    expires_at: UtcTimestamp | None
    trace: TraceContext
    state: ReservationState = field(default=ReservationState.ACTIVE, init=False)
    resolved_at: UtcTimestamp | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.reservation_id, ReservationId):
            raise ValueError("reservation_id must be a ReservationId")
        if not isinstance(self.budget_id, BudgetId):
            raise ValueError("budget_id must be a BudgetId")
        if not isinstance(self.organization_id, OrganizationId):
            raise ValueError("organization_id must be an OrganizationId")
        if not isinstance(self.resource_id, ResourceId):
            raise ValueError("resource_id must be a ResourceId")
        if not isinstance(self.quantity, ResourceQuantity):
            raise ValueError("quantity must be a ResourceQuantity")
        if self.quantity.quantity <= 0:
            raise InvalidReservationQuantity()
        if not isinstance(self.reserved_at, datetime):
            raise ValueError("reserved_at must be a datetime")
        if self.expires_at is not None and not isinstance(self.expires_at, datetime):
            raise ValueError("expires_at must be a datetime or None")
        if not isinstance(self.trace, TraceContext):
            raise ValueError("trace must be a TraceContext")
        start = normalize_utc(self.reserved_at)
        end = None if self.expires_at is None else normalize_utc(self.expires_at)
        if end is not None and end < start:
            raise InvalidReservationPeriod()
        object.__setattr__(self, "reserved_at", start)
        object.__setattr__(self, "expires_at", end)

    def _resolve(self, state: ReservationState, at: datetime) -> "Reservation":
        if self.state is not ReservationState.ACTIVE:
            raise InvalidReservationState()
        if not isinstance(at, datetime):
            raise ValueError("at must be a datetime")
        resolved = normalize_utc(at)
        if resolved < self.reserved_at:
            raise InvalidReservationPeriod()
        if state is ReservationState.EXPIRED:
            if self.expires_at is None or resolved < self.expires_at:
                raise InvalidReservationPeriod()
        elif self.expires_at is not None and resolved > self.expires_at:
            raise InvalidReservationPeriod()
        result = self.__class__(
            self.reservation_id,
            self.budget_id,
            self.organization_id,
            self.resource_id,
            self.quantity,
            self.reserved_at,
            self.expires_at,
            self.trace,
        )
        object.__setattr__(result, "state", state)
        object.__setattr__(result, "resolved_at", resolved)
        return result

    def validate_against(self, budget: Budget) -> None:
        """Validate organization, budget period, resource and limit coverage."""
        if not isinstance(budget, Budget):
            raise ValueError("budget must be a Budget")
        if self.budget_id != budget.budget_id:
            raise ReservationBudgetMismatch()
        if self.organization_id != budget.organization_id:
            raise BudgetOrganizationMismatch()
        if self.reserved_at < budget.valid_from or (
            budget.valid_until is not None and self.reserved_at > budget.valid_until
        ):
            raise InvalidReservationPeriod()
        if self.expires_at is not None and budget.valid_until is not None:
            if self.expires_at > budget.valid_until:
                raise InvalidReservationPeriod()
        budget.limit_for(
            self.resource_id, self.quantity, self.reserved_at, self.expires_at
        )

    def is_active_at(self, timestamp: datetime) -> bool:
        if not isinstance(timestamp, datetime):
            raise ValueError("timestamp must be a datetime")
        point = normalize_utc(timestamp)
        return (
            self.state is ReservationState.ACTIVE
            and point >= self.reserved_at
            and (self.expires_at is None or point <= self.expires_at)
        )

    def released(self, at: datetime) -> "Reservation":
        return self._resolve(ReservationState.RELEASED, at)

    def committed(self, at: datetime) -> "Reservation":
        return self._resolve(ReservationState.COMMITTED, at)

    def expired(self, at: datetime) -> "Reservation":
        return self._resolve(ReservationState.EXPIRED, at)
