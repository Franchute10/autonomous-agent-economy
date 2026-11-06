"""Optional structured website inspection contract."""

from dataclasses import dataclass
from typing import Protocol

from aeos.live.domain.evidence import SourceEvidence


@dataclass(frozen=True, slots=True)
class WebsiteSignal:
    field: str
    value: str | int | float | bool | None
    evidence_id: str


@dataclass(frozen=True, slots=True)
class WebsiteInspectionResult:
    signals: tuple[WebsiteSignal, ...]
    evidence: tuple[SourceEvidence, ...]


class WebsiteInspectionPort(Protocol):
    def inspect(self, website_url: str) -> WebsiteInspectionResult: ...
