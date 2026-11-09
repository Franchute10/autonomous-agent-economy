"""Optional structured website inspection contract."""

from dataclasses import dataclass
from typing import Protocol

from aeos.live.domain.evidence import SourceEvidence
from aeos.live.domain.location_candidate import LocationCandidate, ServiceCandidate
from aeos.live.domain.website_inspection import (
    WebsiteInspectionDetails,
    WebsitePage,
)


@dataclass(frozen=True, slots=True)
class WebsiteSignal:
    field: str
    value: str | int | float | bool | None
    evidence_id: str


@dataclass(frozen=True, slots=True)
class WebsiteInspectionResult:
    signals: tuple[WebsiteSignal, ...]
    evidence: tuple[SourceEvidence, ...]
    details: WebsiteInspectionDetails | None = None
    pages: tuple[WebsitePage, ...] = ()
    locations: tuple[LocationCandidate, ...] = ()
    services: tuple[ServiceCandidate, ...] = ()


class WebsiteInspectionPort(Protocol):
    def inspect(self, website_url: str) -> WebsiteInspectionResult: ...
