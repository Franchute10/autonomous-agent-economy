"""Shared validation for immutable workflow lifecycle snapshots."""

from datetime import datetime

from aeos.core import UtcTimestamp, normalize_utc
from aeos.workflows.domain.errors import InvalidLifecycleTimestamp


def timestamp(value: datetime | None, field: str) -> UtcTimestamp | None:
    if value is None:
        return None
    try:
        return normalize_utc(value)
    except (AttributeError, TypeError, ValueError) as exc:
        raise InvalidLifecycleTimestamp(
            f"{field} must be a timezone-aware datetime"
        ) from exc


def required_timestamp(value: datetime | None, field: str) -> UtcTimestamp:
    normalized = timestamp(value, field)
    if normalized is None:
        raise InvalidLifecycleTimestamp(f"{field} is required")
    return normalized


def validate_order(
    created_at: UtcTimestamp,
    started_at: UtcTimestamp | None,
    finished_at: UtcTimestamp | None,
) -> None:
    if started_at is not None and started_at < created_at:
        raise InvalidLifecycleTimestamp("started_at cannot precede created_at")
    if finished_at is not None and finished_at < created_at:
        raise InvalidLifecycleTimestamp("finished_at cannot precede created_at")
    if started_at is not None and finished_at is not None and finished_at < started_at:
        raise InvalidLifecycleTimestamp("finished_at cannot precede started_at")
