"""Immutable budget authorization and limit definitions."""

from dataclasses import dataclass
from datetime import datetime

from aeos.core import (
    BudgetId,
    OrganizationId,
    ResourceId,
    ResourceQuantity,
    TraceContext,
    UtcTimestamp,
    normalize_utc,
)
from aeos.economics.domain.errors import (
    BudgetLimitMismatch,
    DuplicateBudgetLimit,
    InvalidBudgetLimit,
    InvalidBudgetPeriod,
    InvalidBudgetPurpose,
)


@dataclass(frozen=True, slots=True)
class BudgetLimit:
    """A positive ceiling for one resource and one bounded period."""

    resource_id: ResourceId
    quantity: ResourceQuantity
    period_start: UtcTimestamp
    period_end: UtcTimestamp | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.resource_id, ResourceId):
            raise ValueError("resource_id must be a ResourceId")
        if not isinstance(self.quantity, ResourceQuantity):
            raise ValueError("quantity must be a ResourceQuantity")
        if self.quantity.quantity <= 0:
            raise InvalidBudgetLimit()
        if not isinstance(self.period_start, datetime):
            raise ValueError("period_start must be a datetime")
        if self.period_end is not None and not isinstance(self.period_end, datetime):
            raise ValueError("period_end must be a datetime or None")
        start = normalize_utc(self.period_start)
        end = None if self.period_end is None else normalize_utc(self.period_end)
        if end is not None and end < start:
            raise InvalidBudgetPeriod()
        object.__setattr__(self, "period_start", start)
        object.__setattr__(self, "period_end", end)

    def covers(self, quantity: ResourceQuantity, at: datetime) -> bool:
        """Return whether this limit can authorize the requested quantity."""
        if not isinstance(quantity, ResourceQuantity):
            raise ValueError("quantity must be a ResourceQuantity")
        if not isinstance(at, datetime):
            raise ValueError("at must be a datetime")
        point = normalize_utc(at)
        return quantity.quantity > 0 and (
            quantity.unit == self.quantity.unit
            and quantity.quantity <= self.quantity.quantity
            and point >= self.period_start
            and (self.period_end is None or point <= self.period_end)
        )

    def covers_interval(
        self,
        quantity: ResourceQuantity,
        start: datetime,
        end: datetime | None,
    ) -> bool:
        """Return whether this limit covers a complete inclusive interval."""
        if not isinstance(start, datetime):
            raise ValueError("start must be a datetime")
        if end is not None and not isinstance(end, datetime):
            raise ValueError("end must be a datetime or None")
        start_utc = normalize_utc(start)
        end_utc = None if end is None else normalize_utc(end)
        if end_utc is not None and end_utc < start_utc:
            return False
        return self.covers(quantity, start_utc) and (
            end_utc is None
            and self.period_end is None
            or end_utc is not None
            and (self.period_end is None or end_utc <= self.period_end)
        )


@dataclass(frozen=True, slots=True)
class Budget:
    """A purpose-bound, immutable authorization over one or more limits."""

    budget_id: BudgetId
    organization_id: OrganizationId
    purpose: str
    limits: tuple[BudgetLimit, ...]
    valid_from: UtcTimestamp
    valid_until: UtcTimestamp | None
    trace: TraceContext

    def __post_init__(self) -> None:
        if not isinstance(self.budget_id, BudgetId):
            raise ValueError("budget_id must be a BudgetId")
        if not isinstance(self.organization_id, OrganizationId):
            raise ValueError("organization_id must be an OrganizationId")
        if not isinstance(self.purpose, str) or not self.purpose.strip():
            raise InvalidBudgetPurpose()
        if not isinstance(self.limits, tuple) or not self.limits:
            raise InvalidBudgetLimit()
        if any(not isinstance(limit, BudgetLimit) for limit in self.limits):
            raise ValueError("limits must contain BudgetLimit values")
        if not isinstance(self.valid_from, datetime):
            raise ValueError("valid_from must be a datetime")
        if self.valid_until is not None and not isinstance(self.valid_until, datetime):
            raise ValueError("valid_until must be a datetime or None")
        if not isinstance(self.trace, TraceContext):
            raise ValueError("trace must be a TraceContext")
        start = normalize_utc(self.valid_from)
        end = None if self.valid_until is None else normalize_utc(self.valid_until)
        if end is not None and end < start:
            raise InvalidBudgetPeriod()
        for index, left in enumerate(self.limits):
            for right in self.limits[index + 1 :]:
                if left.resource_id == right.resource_id and _periods_overlap(
                    left, right
                ):
                    raise DuplicateBudgetLimit()
        if any(
            limit.period_start < start
            or (
                end is not None and (limit.period_end is None or limit.period_end > end)
            )
            for limit in self.limits
        ):
            raise InvalidBudgetPeriod()
        object.__setattr__(self, "purpose", self.purpose.strip())
        object.__setattr__(self, "valid_from", start)
        object.__setattr__(self, "valid_until", end)

    def limit_for(
        self,
        resource_id: ResourceId,
        quantity: ResourceQuantity,
        start: datetime,
        end: datetime | None = None,
    ) -> BudgetLimit:
        """Return the matching limit for a complete reservation interval."""
        if not isinstance(resource_id, ResourceId):
            raise ValueError("resource_id must be a ResourceId")
        for limit in self.limits:
            if limit.resource_id == resource_id and limit.covers_interval(
                quantity, start, end
            ):
                return limit
        raise BudgetLimitMismatch()


def _periods_overlap(left: BudgetLimit, right: BudgetLimit) -> bool:
    """Check overlap for inclusive, optionally open-ended periods."""
    return not (
        left.period_end is not None and left.period_end < right.period_start
    ) and not (right.period_end is not None and right.period_end < left.period_start)
