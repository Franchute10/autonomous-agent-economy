"""Evidence-backed locations and services extracted from public websites."""

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from aeos.live.domain.errors import InvalidLiveContract
from aeos.live.domain.evidence import EvidenceKind


class LocationType(StrEnum):
    BUSINESS_ADDRESS = "BUSINESS_ADDRESS"
    PHYSICAL_OPERATING_LOCATION = "PHYSICAL_OPERATING_LOCATION"
    SERVICE_AREA = "SERVICE_AREA"
    EXPLICITLY_SERVED_CITY = "EXPLICITLY_SERVED_CITY"
    CITY_MENTION = "CITY_MENTION"
    UNVERIFIED_REFERENCE = "UNVERIFIED_REFERENCE"


class VerificationStatus(StrEnum):
    WEBSITE_REPORTED = "WEBSITE_REPORTED"
    WEBSITE_OBSERVED = "WEBSITE_OBSERVED"
    OWNER_CONFIRMED = "OWNER_CONFIRMED"
    UNVERIFIED = "UNVERIFIED"


def _non_blank(value: object, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise InvalidLiveContract(f"{field} must be a non-blank string")


@dataclass(frozen=True, slots=True)
class LocationCandidate:
    """A place mentioned by a website, with its claim type and provenance."""

    city: str
    state: str | None
    postal_code: str | None
    location_type: LocationType
    source_url: str
    supporting_text: str
    evidence_classification: EvidenceKind
    confidence: float
    verification_status: VerificationStatus
    evidence_id: str

    def __post_init__(self) -> None:
        for field in ("city", "source_url", "supporting_text", "evidence_id"):
            _non_blank(getattr(self, field), field)
        for field in ("state", "postal_code"):
            value = getattr(self, field)
            if value is not None:
                _non_blank(value, field)
                object.__setattr__(self, field, value.strip())
        if not isinstance(self.location_type, LocationType):
            raise InvalidLiveContract("location_type must be a LocationType")
        if not isinstance(self.evidence_classification, EvidenceKind):
            raise InvalidLiveContract("evidence_classification must be an EvidenceKind")
        if not isinstance(self.verification_status, VerificationStatus):
            raise InvalidLiveContract(
                "verification_status must be a VerificationStatus"
            )
        if (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, (float, int))
            or not isfinite(self.confidence)
            or not 0 <= self.confidence <= 1
        ):
            raise InvalidLiveContract("confidence must be between 0 and 1")
        for field in ("city", "source_url", "supporting_text", "evidence_id"):
            object.__setattr__(self, field, getattr(self, field).strip())


@dataclass(frozen=True, slots=True)
class ServiceCandidate:
    """A website service signal with provenance and its verification level."""

    service: str
    source_url: str
    supporting_text: str
    evidence_classification: EvidenceKind
    confidence: float
    verification_status: VerificationStatus
    evidence_id: str

    def __post_init__(self) -> None:
        for field in ("service", "source_url", "supporting_text", "evidence_id"):
            _non_blank(getattr(self, field), field)
            object.__setattr__(self, field, getattr(self, field).strip())
        if not isinstance(self.evidence_classification, EvidenceKind):
            raise InvalidLiveContract("evidence_classification must be an EvidenceKind")
        if not isinstance(self.verification_status, VerificationStatus):
            raise InvalidLiveContract(
                "verification_status must be a VerificationStatus"
            )
        if (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, (float, int))
            or not isfinite(self.confidence)
            or not 0 <= self.confidence <= 1
        ):
            raise InvalidLiveContract("confidence must be between 0 and 1")
