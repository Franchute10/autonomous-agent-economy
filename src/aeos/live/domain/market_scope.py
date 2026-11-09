"""An owner-selected, provenance-preserving market research scope."""

from dataclasses import dataclass
from datetime import datetime
from math import isfinite

from aeos.live.domain.errors import InvalidLiveContract


@dataclass(frozen=True, slots=True)
class MarketResearchScope:
    city: str
    state: str
    postal_code: str | None
    research_radius: float | None
    radius_unit: str | None
    selected_services: tuple[str, ...]
    selected_at: datetime
    owner_confirmed: bool
    source_evidence_id: str | None = None

    def __post_init__(self) -> None:
        for field in ("city", "state"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise InvalidLiveContract(f"{field} must be non-blank")
            object.__setattr__(self, field, value.strip())
        if self.postal_code is not None and not self.postal_code.strip():
            raise InvalidLiveContract("postal_code must be non-blank or None")
        if self.research_radius is not None and (
            isinstance(self.research_radius, bool)
            or not isinstance(self.research_radius, (int, float))
            or not isfinite(self.research_radius)
            or self.research_radius <= 0
        ):
            raise InvalidLiveContract("research_radius must be positive and finite")
        if self.radius_unit is not None and self.radius_unit not in {
            "miles",
            "kilometers",
        }:
            raise InvalidLiveContract("radius_unit must be miles, kilometers, or None")
        if (self.research_radius is None) != (self.radius_unit is None):
            raise InvalidLiveContract(
                "research_radius and radius_unit must be supplied together"
            )
        if not isinstance(self.selected_services, tuple) or any(
            not isinstance(item, str) or not item.strip()
            for item in self.selected_services
        ):
            raise InvalidLiveContract(
                "selected_services must be a tuple of non-blank strings"
            )
        if not isinstance(self.selected_at, datetime):
            raise InvalidLiveContract("selected_at must be a datetime")
        if not isinstance(self.owner_confirmed, bool):
            raise InvalidLiveContract("owner_confirmed must be a boolean")
        if self.source_evidence_id is not None and not self.source_evidence_id.strip():
            raise InvalidLiveContract("source_evidence_id must be non-blank or None")
