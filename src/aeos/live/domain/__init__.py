"""Immutable LIVE opportunity-intelligence domain contracts."""

from aeos.live.domain.assessment import (
    AssessmentStatus,
    BestNextMove,
    BusinessAssessment,
    assessment_to_dict,
    assessment_to_json,
)
from aeos.live.domain.business import BusinessInput
from aeos.live.domain.errors import InvalidLiveContract
from aeos.live.domain.evidence import EvidenceKind, JsonScalar, SourceEvidence
from aeos.live.domain.market import (
    DataCoverage,
    MarketEntity,
    MarketEntityType,
    MarketFinding,
    MarketPosition,
    MarketStructureDimension,
    MarketStructureObservation,
)
from aeos.live.domain.opportunity import Opportunity, OpportunityType
from aeos.live.domain.vertical import Vertical, VerticalProfile, vertical_profile_for

__all__ = [
    "AssessmentStatus",
    "BestNextMove",
    "BusinessAssessment",
    "BusinessInput",
    "DataCoverage",
    "EvidenceKind",
    "InvalidLiveContract",
    "JsonScalar",
    "MarketEntity",
    "MarketEntityType",
    "MarketFinding",
    "MarketPosition",
    "MarketStructureDimension",
    "MarketStructureObservation",
    "Opportunity",
    "OpportunityType",
    "SourceEvidence",
    "Vertical",
    "VerticalProfile",
    "assessment_to_dict",
    "assessment_to_json",
    "vertical_profile_for",
]
