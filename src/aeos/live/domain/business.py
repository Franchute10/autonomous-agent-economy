"""Initial, owner-provided business facts."""

from dataclasses import dataclass
from math import isfinite

from aeos.live.domain.errors import InvalidLiveContract


def _non_blank(value: object, field: str, *, optional: bool = False) -> None:
    if optional and value is None:
        return
    if not isinstance(value, str) or not value.strip():
        raise InvalidLiveContract(f"{field} must be a non-blank string")


def _non_negative_number(value: object, field: str, *, optional: bool = True) -> None:
    if optional and value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidLiveContract(f"{field} must be a non-negative number or None")
    if not isfinite(value) or value < 0:
        raise InvalidLiveContract(f"{field} must be a non-negative finite number")


@dataclass(frozen=True, slots=True)
class BusinessInput:
    """Business details supplied by an owner; unknown values stay as ``None``."""

    business_name: str
    industry: str
    city: str
    state: str
    country: str = "US"
    service_radius_miles: float | None = None
    website_url: str | None = None
    google_business_url: str | None = None
    main_customer_sources: tuple[str, ...] | None = None
    monthly_inquiries: int | None = None
    monthly_quotes: int | None = None
    monthly_jobs: int | None = None
    average_job_value: float | None = None
    repeat_customer_share: float | None = None
    has_structured_follow_up: bool | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        for field in ("business_name", "industry", "city", "state", "country"):
            _non_blank(getattr(self, field), field)
            object.__setattr__(self, field, getattr(self, field).strip())
        for field in ("website_url", "google_business_url", "notes"):
            value = getattr(self, field)
            _non_blank(value, field, optional=True)
            if isinstance(value, str):
                object.__setattr__(self, field, value.strip())
        _non_negative_number(self.service_radius_miles, "service_radius_miles")
        _non_negative_number(self.average_job_value, "average_job_value")
        for field in ("monthly_inquiries", "monthly_quotes", "monthly_jobs"):
            value = getattr(self, field)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise InvalidLiveContract(
                    f"{field} must be a non-negative integer or None"
                )
        share = self.repeat_customer_share
        if share is not None:
            _non_negative_number(share, "repeat_customer_share", optional=False)
            if share > 1:
                raise InvalidLiveContract(
                    "repeat_customer_share must be between 0 and 1"
                )
        if self.has_structured_follow_up is not None and not isinstance(
            self.has_structured_follow_up, bool
        ):
            raise InvalidLiveContract(
                "has_structured_follow_up must be a boolean or None"
            )
        sources = self.main_customer_sources
        if sources is not None:
            if not isinstance(sources, tuple) or any(
                not isinstance(source, str) or not source.strip() for source in sources
            ):
                raise InvalidLiveContract(
                    "main_customer_sources must be a tuple of non-blank strings or None"
                )
            object.__setattr__(
                self,
                "main_customer_sources",
                tuple(source.strip() for source in sources),
            )
