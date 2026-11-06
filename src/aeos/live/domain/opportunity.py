"""Candidate commercial moves, with explainable scoring dimensions."""

from dataclasses import dataclass
from enum import StrEnum

from aeos.live.domain.errors import InvalidLiveContract


class OpportunityType(StrEnum):
    CUSTOMER_ACQUISITION = "CUSTOMER_ACQUISITION"
    PARTNERSHIP = "PARTNERSHIP"
    SUPPLIER = "SUPPLIER"
    LOCAL_VISIBILITY = "LOCAL_VISIBILITY"
    WEBSITE_CONVERSION = "WEBSITE_CONVERSION"
    REPUTATION = "REPUTATION"
    OFFER = "OFFER"
    RETENTION = "RETENTION"
    FOLLOW_UP = "FOLLOW_UP"
    COMPETITIVE_GAP = "COMPETITIVE_GAP"


@dataclass(frozen=True, slots=True)
class Opportunity:
    opportunity_id: str
    opportunity_type: OpportunityType
    title: str
    description: str
    evidence_ids: tuple[str, ...]
    impact: int
    confidence: int
    evidence_strength: int
    executability: int
    effort: int
    time_to_value: str
    recommended_action: str
    ready_to_use_asset: str | None = None

    def __post_init__(self) -> None:
        for field in (
            "opportunity_id",
            "title",
            "description",
            "time_to_value",
            "recommended_action",
        ):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise InvalidLiveContract(f"{field} must be a non-blank string")
            object.__setattr__(self, field, value.strip())
        if not isinstance(self.opportunity_type, OpportunityType):
            raise InvalidLiveContract("opportunity_type must be an OpportunityType")
        for field in (
            "impact",
            "confidence",
            "evidence_strength",
            "executability",
            "effort",
        ):
            score = getattr(self, field)
            if (
                isinstance(score, bool)
                or not isinstance(score, int)
                or not 1 <= score <= 5
            ):
                raise InvalidLiveContract(f"{field} must be an integer from 1 to 5")
        if not isinstance(self.evidence_ids, tuple) or any(
            not isinstance(item, str) or not item.strip() for item in self.evidence_ids
        ):
            raise InvalidLiveContract(
                "evidence_ids must be a tuple of non-blank strings"
            )
        if self.ready_to_use_asset is not None and (
            not isinstance(self.ready_to_use_asset, str)
            or not self.ready_to_use_asset.strip()
        ):
            raise InvalidLiveContract("ready_to_use_asset must be non-blank or None")
