"""Advisor contract for explanations and ready-to-use assets."""

from dataclasses import dataclass
from typing import Protocol

from aeos.live.domain.assessment import BusinessAssessment


@dataclass(frozen=True, slots=True)
class AdvisorResponse:
    explanation: str
    ready_to_use_asset: str | None = None


class AdvisorPort(Protocol):
    def advise(self, assessment: BusinessAssessment) -> AdvisorResponse: ...
