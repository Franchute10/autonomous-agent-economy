"""Market entities, comparative position, and market-structure observations."""

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from aeos.live.domain.errors import InvalidLiveContract


class MarketEntityType(StrEnum):
    COMPETITOR = "COMPETITOR"
    POTENTIAL_CUSTOMER = "POTENTIAL_CUSTOMER"
    PARTNER = "PARTNER"
    SUPPLIER = "SUPPLIER"


class MarketStructureDimension(StrEnum):
    COMPETITIVE_RIVALRY = "COMPETITIVE_RIVALRY"
    CUSTOMER_ALTERNATIVES = "CUSTOMER_ALTERNATIVES"
    SUPPLIER_ALTERNATIVES = "SUPPLIER_ALTERNATIVES"
    SUBSTITUTES = "SUBSTITUTES"
    POTENTIAL_ENTRY_SATURATION = "POTENTIAL_ENTRY_SATURATION"


def _optional_number(
    value: object, field: str, *, minimum: float | None = None
) -> None:
    if value is None:
        return
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(value)
    ):
        raise InvalidLiveContract(f"{field} must be a finite number or None")
    if minimum is not None and value < minimum:
        raise InvalidLiveContract(f"{field} must be at least {minimum}")


def _text(value: object, field: str, *, optional: bool = False) -> None:
    if optional and value is None:
        return
    if not isinstance(value, str) or not value.strip():
        raise InvalidLiveContract(f"{field} must be a non-blank string")


@dataclass(frozen=True, slots=True)
class MarketEntity:
    entity_id: str
    name: str
    entity_type: MarketEntityType
    category: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    distance_miles: float | None = None
    website: str | None = None
    phone: str | None = None
    rating: float | None = None
    review_count: int | None = None
    services: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(self.entity_id, "entity_id")
        _text(self.name, "name")
        object.__setattr__(self, "entity_id", self.entity_id.strip())
        object.__setattr__(self, "name", self.name.strip())
        if not isinstance(self.entity_type, MarketEntityType):
            raise InvalidLiveContract("entity_type must be a MarketEntityType")
        for field in ("category", "address", "city", "state", "website", "phone"):
            value = getattr(self, field)
            _text(value, field, optional=True)
            if isinstance(value, str):
                object.__setattr__(self, field, value.strip())
        _optional_number(self.latitude, "latitude", minimum=-90)
        _optional_number(self.longitude, "longitude", minimum=-180)
        if self.latitude is not None and self.latitude > 90:
            raise InvalidLiveContract("latitude must be between -90 and 90")
        if self.longitude is not None and self.longitude > 180:
            raise InvalidLiveContract("longitude must be between -180 and 180")
        _optional_number(self.distance_miles, "distance_miles", minimum=0)
        _optional_number(self.rating, "rating", minimum=0)
        if self.rating is not None and self.rating > 5:
            raise InvalidLiveContract("rating must be between 0 and 5")
        if self.review_count is not None and (
            isinstance(self.review_count, bool)
            or not isinstance(self.review_count, int)
            or self.review_count < 0
        ):
            raise InvalidLiveContract(
                "review_count must be a non-negative integer or None"
            )
        for field in ("services", "evidence_ids"):
            values = getattr(self, field)
            if not isinstance(values, tuple) or any(
                not isinstance(item, str) or not item.strip() for item in values
            ):
                raise InvalidLiveContract(
                    f"{field} must be a tuple of non-blank strings"
                )
            normalized = tuple(item.strip() for item in values)
            if field == "evidence_ids" and len(set(normalized)) != len(normalized):
                raise InvalidLiveContract(
                    "evidence identifiers must be unique per entity"
                )
            object.__setattr__(self, field, normalized)


@dataclass(frozen=True, slots=True)
class MarketFinding:
    label: str
    description: str
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(self.label, "finding label")
        _text(self.description, "finding description")
        if not isinstance(self.evidence_ids, tuple) or any(
            not isinstance(item, str) or not item.strip() for item in self.evidence_ids
        ):
            raise InvalidLiveContract("finding evidence_ids must be non-blank strings")


@dataclass(frozen=True, slots=True)
class DataCoverage:
    signal: str
    available: bool
    sample_size: int | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        _text(self.signal, "coverage signal")
        if not isinstance(self.available, bool):
            raise InvalidLiveContract("coverage available must be a boolean")
        if self.sample_size is not None and (
            isinstance(self.sample_size, bool)
            or not isinstance(self.sample_size, int)
            or self.sample_size < 0
        ):
            raise InvalidLiveContract(
                "coverage sample_size must be a non-negative integer"
            )
        _text(self.notes, "coverage notes", optional=True)


@dataclass(frozen=True, slots=True)
class MarketPosition:
    comparable_competitor_ids: tuple[str, ...] = ()
    comparison_sample_size: int = 0
    metrics_compared: tuple[str, ...] = ()
    relative_strengths: tuple[MarketFinding, ...] = ()
    relative_weaknesses: tuple[MarketFinding, ...] = ()
    market_gaps: tuple[MarketFinding, ...] = ()
    data_coverage: tuple[DataCoverage, ...] = ()
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (
            isinstance(self.comparison_sample_size, bool)
            or not isinstance(self.comparison_sample_size, int)
            or self.comparison_sample_size < 0
        ):
            raise InvalidLiveContract(
                "comparison_sample_size must be a non-negative integer"
            )
        for field in ("comparable_competitor_ids", "metrics_compared", "limitations"):
            values = getattr(self, field)
            if not isinstance(values, tuple) or any(
                not isinstance(item, str) or not item.strip() for item in values
            ):
                raise InvalidLiveContract(
                    f"{field} must be a tuple of non-blank strings"
                )
        if len(set(self.comparable_competitor_ids)) != len(
            self.comparable_competitor_ids
        ):
            raise InvalidLiveContract(
                "comparable competitor identifiers must be unique"
            )
        if self.comparison_sample_size != len(self.comparable_competitor_ids):
            raise InvalidLiveContract(
                "comparison_sample_size must match the comparable competitor count"
            )
        for field, expected in (
            ("relative_strengths", MarketFinding),
            ("relative_weaknesses", MarketFinding),
            ("market_gaps", MarketFinding),
            ("data_coverage", DataCoverage),
        ):
            values = getattr(self, field)
            if not isinstance(values, tuple) or any(
                not isinstance(item, expected) for item in values
            ):
                raise InvalidLiveContract(
                    f"{field} must contain {expected.__name__} values"
                )


@dataclass(frozen=True, slots=True)
class MarketStructureObservation:
    dimension: MarketStructureDimension
    description: str
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.dimension, MarketStructureDimension):
            raise InvalidLiveContract("dimension must be a MarketStructureDimension")
        _text(self.description, "market structure description")
        if not isinstance(self.evidence_ids, tuple) or any(
            not isinstance(item, str) or not item.strip() for item in self.evidence_ids
        ):
            raise InvalidLiveContract(
                "market structure evidence_ids must be non-blank strings"
            )
