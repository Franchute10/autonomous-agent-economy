"""UTC timestamp validation and normalization."""

from datetime import datetime, timezone

UtcTimestamp = datetime


def normalize_utc(value: datetime) -> UtcTimestamp:
    """Return an aware UTC datetime, rejecting naive datetimes."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("UTC timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)
