"""Evidence-grounded commercial qualification and activation contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from urllib.parse import urlsplit

from aeos.live.domain.errors import InvalidLiveContract
from aeos.live.domain.evidence import EvidenceKind
from aeos.live.domain.market_intelligence import OrganizationRole


class ProspectClassification(StrEnum):
    POTENTIAL_BUYER = "POTENTIAL_BUYER"
    QUALIFIED_PROSPECT = "QUALIFIED_PROSPECT"
    ACTIVE_BUYING_INTENT = "ACTIVE_BUYING_INTENT"
    REFERRAL_PARTNER = "REFERRAL_PARTNER"
    OVERFLOW_PARTNER = "OVERFLOW_PARTNER"
    NOT_QUALIFIED = "NOT_QUALIFIED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class ActivationOpportunityType(StrEnum):
    OVERFLOW_CLEANING_PARTNER = "OVERFLOW_CLEANING_PARTNER"


class CapacityState(StrEnum):
    BASE_CAPACITY = "BASE_CAPACITY"
    EXPANDED_CAPACITY = "EXPANDED_CAPACITY"
    CAPACITY_NOT_SCOPED = "CAPACITY_NOT_SCOPED"
    OVER_CAPACITY = "OVER_CAPACITY"


class VendorOnboardingState(StrEnum):
    PUBLIC_VENDOR_ROUTE = "PUBLIC_VENDOR_ROUTE"
    NO_PUBLIC_ROUTE_FOUND = "NO_PUBLIC_ROUTE_FOUND"
    UNKNOWN = "UNKNOWN"


class PipelineStatus(StrEnum):
    DISCOVERED = "DISCOVERED"
    RESEARCH_PENDING = "RESEARCH_PENDING"
    RESEARCHED = "RESEARCHED"
    QUALIFIED = "QUALIFIED"
    READY_FOR_APPROVAL = "READY_FOR_APPROVAL"
    APPROVED_FOR_CONTACT = "APPROVED_FOR_CONTACT"
    CONTACTED = "CONTACTED"
    REPLIED = "REPLIED"
    MEETING_SCHEDULED = "MEETING_SCHEDULED"
    QUOTE_REQUESTED = "QUOTE_REQUESTED"
    QUOTE_SENT = "QUOTE_SENT"
    WON = "WON"
    LOST = "LOST"
    DISQUALIFIED = "DISQUALIFIED"


@dataclass(frozen=True, slots=True)
class ProspectEvidence:
    """A dated public or owner-reported source record tied to one prospect."""

    evidence_id: str
    entity_id: str
    field: str
    value: str
    source_name: str
    source_url: str
    observed_on: date
    classification: EvidenceKind
    confidence: float
    supporting_information: str
    limitations: tuple[str, ...] = ()
    published_on: date | None = None

    def __post_init__(self) -> None:
        for field in (
            "evidence_id",
            "entity_id",
            "field",
            "value",
            "source_name",
            "supporting_information",
        ):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise InvalidLiveContract(f"{field} must be a non-blank string")
            object.__setattr__(self, field, value.strip())
        parsed = urlsplit(self.source_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise InvalidLiveContract("source_url must be an absolute HTTP(S) URL")
        if not isinstance(self.observed_on, date):
            raise InvalidLiveContract("observed_on must be a date")
        if self.published_on is not None and not isinstance(self.published_on, date):
            raise InvalidLiveContract("published_on must be a date or None")
        if not isinstance(self.classification, EvidenceKind):
            raise InvalidLiveContract("classification must be an EvidenceKind")
        if (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, (int, float))
            or not 0 <= self.confidence <= 1
        ):
            raise InvalidLiveContract("confidence must be between 0 and 1")
        if not isinstance(self.limitations, tuple) or any(
            not isinstance(item, str) or not item.strip() for item in self.limitations
        ):
            raise InvalidLiveContract("limitations must be non-blank strings")


@dataclass(frozen=True, slots=True)
class ActivationProspect:
    """Normalized prospect view assembled from reviewed market evidence."""

    prospect_id: str
    organization: str
    market: str
    source_role: OrganizationRole
    website_url: str | None
    services: tuple[str, ...]
    service_areas: tuple[str, ...]
    customer_segments: tuple[str, ...]
    recurring_options: tuple[str, ...]
    public_contact_channels: tuple[str, ...]
    public_contact_details: tuple[str, ...]
    relevant_public_contact_role: str | None
    vendor_onboarding: VendorOnboardingState
    vendor_onboarding_evidence_ids: tuple[str, ...]
    external_cleaning_vendor_evidence_ids: tuple[str, ...]
    buying_intent_evidence_ids: tuple[str, ...]
    cleaning_delivery_model: str
    operational_scale: str
    buyer_fit_reason: str | None
    recommended_action: str
    validation_question: str
    evidence: tuple[ProspectEvidence, ...]
    limitations: tuple[str, ...] = ()
    contact_revalidation_required: bool = False
    contact_revalidation_note: str | None = None
    overflow_partner_evidence_ids: tuple[str, ...] = ()
    synthetic_fixture: bool = False

    def __post_init__(self) -> None:
        for field in (
            "prospect_id",
            "organization",
            "market",
            "cleaning_delivery_model",
            "operational_scale",
            "recommended_action",
            "validation_question",
        ):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise InvalidLiveContract(f"{field} must be a non-blank string")
        if not isinstance(self.source_role, OrganizationRole):
            raise InvalidLiveContract("source_role must be an OrganizationRole")
        if not isinstance(self.vendor_onboarding, VendorOnboardingState):
            raise InvalidLiveContract(
                "vendor_onboarding must use VendorOnboardingState"
            )
        for field in (
            "services",
            "service_areas",
            "customer_segments",
            "recurring_options",
            "public_contact_channels",
            "public_contact_details",
            "vendor_onboarding_evidence_ids",
            "external_cleaning_vendor_evidence_ids",
            "buying_intent_evidence_ids",
            "evidence",
            "limitations",
            "overflow_partner_evidence_ids",
        ):
            values = getattr(self, field)
            if not isinstance(values, tuple):
                raise InvalidLiveContract(f"{field} must be a tuple")
            if field == "evidence":
                if any(not isinstance(item, ProspectEvidence) for item in values):
                    raise InvalidLiveContract(
                        "evidence must contain ProspectEvidence values"
                    )
            elif any(not isinstance(item, str) or not item.strip() for item in values):
                raise InvalidLiveContract(f"{field} must contain non-blank strings")
        if not self.evidence:
            raise InvalidLiveContract("evidence must contain ProspectEvidence values")
        evidence_ids = tuple(item.evidence_id for item in self.evidence)
        if len(set(evidence_ids)) != len(evidence_ids):
            raise InvalidLiveContract("prospect evidence IDs must be unique")
        referenced_ids = {
            *self.vendor_onboarding_evidence_ids,
            *self.external_cleaning_vendor_evidence_ids,
            *self.buying_intent_evidence_ids,
            *self.overflow_partner_evidence_ids,
        }
        if not referenced_ids.issubset(evidence_ids):
            raise InvalidLiveContract(
                "prospect source references must resolve to evidence"
            )
        if (
            self.vendor_onboarding is VendorOnboardingState.PUBLIC_VENDOR_ROUTE
            and not self.vendor_onboarding_evidence_ids
        ):
            raise InvalidLiveContract("a public vendor route requires evidence")
        if not isinstance(self.contact_revalidation_required, bool):
            raise InvalidLiveContract("contact_revalidation_required must be boolean")
        if not isinstance(self.synthetic_fixture, bool):
            raise InvalidLiveContract("synthetic_fixture must be boolean")
        for field in (
            "buyer_fit_reason",
            "contact_revalidation_note",
            "relevant_public_contact_role",
        ):
            value = getattr(self, field)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise InvalidLiveContract(f"{field} must be a non-blank string or None")
        if self.website_url is not None:
            parsed = urlsplit(self.website_url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise InvalidLiveContract("website_url must be an absolute HTTP(S) URL")


@dataclass(frozen=True, slots=True)
class OperationalCapacity:
    """Owner-reported capacity limits and service availability."""

    base_capacity_jobs_per_day: int
    expanded_capacity_jobs_per_day: int
    expansion_dependency: str
    weekend_available: bool
    urgent_service_available: bool
    legal_business_established_reported: bool
    documents_and_insurance_in_order_reported: bool
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            isinstance(self.base_capacity_jobs_per_day, bool)
            or not isinstance(self.base_capacity_jobs_per_day, int)
            or self.base_capacity_jobs_per_day < 0
        ):
            raise InvalidLiveContract("base capacity must be a non-negative integer")
        if (
            isinstance(self.expanded_capacity_jobs_per_day, bool)
            or not isinstance(self.expanded_capacity_jobs_per_day, int)
            or self.expanded_capacity_jobs_per_day < self.base_capacity_jobs_per_day
            or self.expanded_capacity_jobs_per_day > 5
        ):
            raise InvalidLiveContract("expanded capacity must be between base and 5")
        if (
            not isinstance(self.expansion_dependency, str)
            or not self.expansion_dependency.strip()
        ):
            raise InvalidLiveContract("expansion_dependency must be non-blank")
        for field in (
            "weekend_available",
            "urgent_service_available",
            "legal_business_established_reported",
            "documents_and_insurance_in_order_reported",
        ):
            if not isinstance(getattr(self, field), bool):
                raise InvalidLiveContract(f"{field} must be boolean")
        if not self.evidence_ids or any(
            not isinstance(value, str) or not value.strip()
            for value in self.evidence_ids
        ):
            raise InvalidLiveContract("capacity facts require reported evidence IDs")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise InvalidLiveContract("capacity evidence IDs must be unique")


@dataclass(frozen=True, slots=True)
class CapacityAssessment:
    expected_jobs_per_day: int | None
    state: CapacityState
    base_capacity_jobs_per_day: int
    expanded_capacity_jobs_per_day: int
    expansion_dependency: str
    recommendation: str
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.state, CapacityState):
            raise InvalidLiveContract("state must be a CapacityState")
        if (
            self.base_capacity_jobs_per_day < 0
            or self.expanded_capacity_jobs_per_day < self.base_capacity_jobs_per_day
            or self.expanded_capacity_jobs_per_day > 5
        ):
            raise InvalidLiveContract(
                "capacity assessment must not exceed five jobs/day"
            )
        if self.expected_jobs_per_day is None:
            if self.state is not CapacityState.CAPACITY_NOT_SCOPED:
                raise InvalidLiveContract("unknown workload must remain unscoped")
        elif self.expected_jobs_per_day > self.expanded_capacity_jobs_per_day:
            if self.state is not CapacityState.OVER_CAPACITY:
                raise InvalidLiveContract("work above the maximum must be flagged")
        elif self.expected_jobs_per_day > self.base_capacity_jobs_per_day:
            if self.state is not CapacityState.EXPANDED_CAPACITY:
                raise InvalidLiveContract(
                    "expanded workload requires a dependency check"
                )
        elif self.state is not CapacityState.BASE_CAPACITY:
            raise InvalidLiveContract(
                "work within base capacity must use BASE_CAPACITY"
            )
        for field in ("expansion_dependency", "recommendation"):
            if (
                not isinstance(getattr(self, field), str)
                or not getattr(self, field).strip()
            ):
                raise InvalidLiveContract(f"{field} must be a non-blank string")
        if not self.evidence_ids:
            raise InvalidLiveContract("capacity assessment requires evidence IDs")


@dataclass(frozen=True, slots=True)
class ScoreComponent:
    key: str
    label: str
    score: int
    maximum: int
    evidence_ids: tuple[str, ...]
    explanation: str

    def __post_init__(self) -> None:
        if (
            not self.key.strip()
            or not self.label.strip()
            or not self.explanation.strip()
        ):
            raise InvalidLiveContract("score components need labels and an explanation")
        if self.maximum < 0 or not 0 <= self.score <= self.maximum:
            raise InvalidLiveContract("score must be between zero and its maximum")
        if any(not item.strip() for item in self.evidence_ids):
            raise InvalidLiveContract("score evidence IDs must be non-blank")


@dataclass(frozen=True, slots=True)
class ProspectAssessment:
    prospect: ActivationProspect
    fit_score: int
    fit_classification: ProspectClassification
    classifications: tuple[ProspectClassification, ...]
    score_components: tuple[ScoreComponent, ...]
    buying_intent_evidence_ids: tuple[str, ...]
    buying_intent_status: str
    opportunity_type: ActivationOpportunityType
    overflow_hypothesis: str
    overflow_hypothesis_only: bool
    capacity: CapacityAssessment
    stale_evidence_ids: tuple[str, ...]
    next_action: str

    def __post_init__(self) -> None:
        if not isinstance(self.prospect, ActivationProspect):
            raise InvalidLiveContract("prospect must be an ActivationProspect")
        if not isinstance(self.fit_classification, ProspectClassification):
            raise InvalidLiveContract(
                "fit_classification must be a ProspectClassification"
            )
        if self.fit_score != sum(item.score for item in self.score_components):
            raise InvalidLiveContract("fit_score must equal its component total")
        if (
            not 0
            <= self.fit_score
            <= sum(item.maximum for item in self.score_components)
        ):
            raise InvalidLiveContract("fit_score is outside its component range")
        if self.fit_classification not in self.classifications:
            raise InvalidLiveContract("classifications must include the fit result")
        if (
            self.opportunity_type
            is not ActivationOpportunityType.OVERFLOW_CLEANING_PARTNER
        ):
            raise InvalidLiveContract("unsupported activation opportunity type")
        if not self.overflow_hypothesis.strip() or not self.next_action.strip():
            raise InvalidLiveContract("assessment needs a hypothesis and next action")
        if set(self.buying_intent_evidence_ids) - set(
            self.prospect.buying_intent_evidence_ids
        ):
            raise InvalidLiveContract("buying intent must reference candidate evidence")


@dataclass(frozen=True, slots=True)
class PipelineEvent:
    event_id: str
    action: str
    occurred_at: str
    actor: str
    details: str
    source_evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field in ("event_id", "action", "occurred_at", "actor", "details"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise InvalidLiveContract(f"{field} must be a non-blank string")
        try:
            parsed = datetime.fromisoformat(self.occurred_at)
        except ValueError as error:
            raise InvalidLiveContract("occurred_at must be an ISO datetime") from error
        if parsed.tzinfo is None:
            raise InvalidLiveContract("occurred_at must include a timezone")
        if any(not item.strip() for item in self.source_evidence_ids):
            raise InvalidLiveContract("event evidence IDs must be non-blank")


@dataclass(frozen=True, slots=True)
class PipelineRecord:
    prospect_id: str
    organization: str
    market: str
    status: PipelineStatus
    source_evidence_ids: tuple[str, ...]
    contact_channel: str | None = None
    last_action_date: str | None = None
    next_action: str | None = None
    follow_up_date: str | None = None
    owner_notes: str | None = None
    outcome: str | None = None
    events: tuple[PipelineEvent, ...] = ()

    def __post_init__(self) -> None:
        for field in ("prospect_id", "organization", "market"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise InvalidLiveContract(f"{field} must be a non-blank string")
        if not isinstance(self.status, PipelineStatus):
            raise InvalidLiveContract("status must be a PipelineStatus")
        if not isinstance(self.source_evidence_ids, tuple) or any(
            not isinstance(item, str) or not item.strip()
            for item in self.source_evidence_ids
        ):
            raise InvalidLiveContract("source_evidence_ids must be non-blank strings")
        if len(set(self.source_evidence_ids)) != len(self.source_evidence_ids):
            raise InvalidLiveContract("source evidence IDs must be unique")
        for field in ("last_action_date", "follow_up_date"):
            value = getattr(self, field)
            if value is not None:
                try:
                    date.fromisoformat(value)
                except (TypeError, ValueError) as error:
                    raise InvalidLiveContract(f"{field} must be an ISO date") from error
        for field in ("contact_channel", "next_action", "owner_notes", "outcome"):
            value = getattr(self, field)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise InvalidLiveContract(f"{field} must be a non-blank string or None")
        if not isinstance(self.events, tuple) or any(
            not isinstance(item, PipelineEvent) for item in self.events
        ):
            raise InvalidLiveContract("events must contain PipelineEvent values")
        event_ids = tuple(item.event_id for item in self.events)
        if len(set(event_ids)) != len(event_ids):
            raise InvalidLiveContract("pipeline event IDs must be unique")
