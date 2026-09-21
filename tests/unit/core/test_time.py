from datetime import datetime, timedelta, timezone

import pytest

from aeos.core.time import normalize_utc


def test_utc_timestamp_is_accepted() -> None:
    value = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert normalize_utc(value) == value
    assert normalize_utc(value).utcoffset() == timedelta(0)


def test_non_utc_timestamp_is_normalized_without_changing_instant() -> None:
    value = datetime(2026, 1, 1, 3, tzinfo=timezone(timedelta(hours=3)))
    normalized = normalize_utc(value)
    assert normalized == datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_naive_timestamp_is_rejected() -> None:
    with pytest.raises(ValueError):
        normalize_utc(datetime(2026, 1, 1))
