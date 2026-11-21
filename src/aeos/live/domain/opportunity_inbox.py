"""Evidence-grounded demand opportunities for the bounded LIVE inbox."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from enum import StrEnum
import hashlib
from ipaddress import ip_address
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from aeos.live.domain.errors import InvalidLiveContract
from aeos.live.domain.evidence import EvidenceKind, SourceEvidence
from aeos.live.domain.profile import BusinessModel, BusinessProfile
from aeos.live.domain.vertical import (
    canonical_service_for_vertical,
    normalize_taxonomy_label,
)
from aeos.live.domain.url_policy import has_sensitive_query_parameter


class DemandType(StrEnum):
    DIRECT_CUSTOMER_DEMAND = "DIRECT_CUSTOMER_DEMAND"
    MARKETPLACE_LEAD = "MARKETPLACE_LEAD"
    POTENTIAL_B2B_BUYER = "POTENTIAL_B2B_BUYER"
    PUBLIC_PROCUREMENT = "PUBLIC_PROCUREMENT"
    REFERRAL_PARTNER = "REFERRAL_PARTNER"
    RECOMMENDATION_SIGNAL = "RECOMMENDATION_SIGNAL"
    BUSINESS_DIRECTORY = "BUSINESS_DIRECTORY"


class LeadClassification(StrEnum):
    HOT = "HOT"
    WARM = "WARM"
    COLD = "COLD"
    EXPIRED = "EXPIRED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class ProcurementStatus(StrEnum):
    OPEN_SOLICITATION = "OPEN_SOLICITATION"
    CLOSED_SOLICITATION = "CLOSED_SOLICITATION"
    AWARD_NOTICE = "AWARD_NOTICE"
    UNKNOWN_STATUS = "UNKNOWN_STATUS"


class PermissionBasis(StrEnum):
    PUBLIC_NOTICE = "PUBLIC_NOTICE"
    AUTHORIZED_ACCOUNT = "AUTHORIZED_ACCOUNT"
    OWNER_PROVIDED = "OWNER_PROVIDED"
    MANUAL_ONLY = "MANUAL_ONLY"
    NOT_APPROVED = "NOT_APPROVED"


class SourceProvenance(StrEnum):
    REAL = "REAL"
    SYNTHETIC = "SYNTHETIC"
    UNKNOWN = "UNKNOWN"


class OpportunityStatus(StrEnum):
    DISCOVERED = "DISCOVERED"
    VERIFIED = "VERIFIED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    APPROVED_FOR_CONTACT = "APPROVED_FOR_CONTACT"
    CONTACTED = "CONTACTED"
    REPLIED = "REPLIED"
    QUOTE_REQUESTED = "QUOTE_REQUESTED"
    QUOTE_SENT = "QUOTE_SENT"
    WON = "WON"
    LOST = "LOST"
    EXPIRED = "EXPIRED"
    DISQUALIFIED = "DISQUALIFIED"
    DUPLICATE = "DUPLICATE"


class DuplicateMatchType(StrEnum):
    EXACT = "EXACT"
    STRONG = "STRONG"
    HUMAN_CONFIRMED = "HUMAN_CONFIRMED"


class OpportunityEventAction(StrEnum):
    IMPORTED = "IMPORTED"
    STATUS_UPDATED = "STATUS_UPDATED"
    CONTACT_APPROVED = "CONTACT_APPROVED"
    QUOTE_APPROVED = "QUOTE_APPROVED"
    MANUAL_CONTACT_RECORDED = "MANUAL_CONTACT_RECORDED"
    QUOTE_RECORDED = "QUOTE_RECORDED"
    RESPONSE_RECORDED = "RESPONSE_RECORDED"
    OPEN_STATUS_VERIFIED = "OPEN_STATUS_VERIFIED"
    POSSIBLE_DUPLICATE_FLAGGED = "POSSIBLE_DUPLICATE_FLAGGED"
    POSSIBLE_DUPLICATE_RESOLVED = "POSSIBLE_DUPLICATE_RESOLVED"
    DUPLICATE_SOURCE_LINKED = "DUPLICATE_SOURCE_LINKED"
    DUPLICATE_MARKED = "DUPLICATE_MARKED"


class SourceState(StrEnum):
    READY = "READY"
    PROVIDER_NOT_CONFIGURED = "PROVIDER_NOT_CONFIGURED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    FIXTURE_ONLY = "FIXTURE_ONLY"


@dataclass(frozen=True, slots=True)
class Opportunity:
    """A minimally retained, traceable demand signal."""

    opportunity_id: str
    title: str
    source_platform: str
    demand_type: DemandType
    publication_date: date | None
    discovered_at: datetime
    service_requested: str
    summary: str
    source_url: str | None
    source_event_ref: str | None
    city: str | None
    state: str | None
    explicit_intent: bool
    is_open: bool | None
    response_method: str | None
    publicly_accessible: bool
    business_authorized: bool
    account_holder_authorized: bool
    permission_basis: PermissionBasis
    source_terms_note: str
    procurement_status: ProcurementStatus | None
    official_deadline: date | None
    eligibility_requirements: tuple[str, ...]
    expected_jobs_per_day: int | None
    ongoing_need: bool
    limitations: tuple[str, ...]
    evidence: tuple[SourceEvidence, ...]
    stable_request_id: str | None = None
    procurement_scope: str | None = None
    eligibility_reviewed: bool = False
    source_provenance: SourceProvenance = SourceProvenance.UNKNOWN
    customer_segment: str | None = None

    def __post_init__(self) -> None:
        for field in (
            "opportunity_id",
            "title",
            "source_platform",
            "service_requested",
            "summary",
            "source_terms_note",
        ):
            _text(getattr(self, field), field)
        for field in (
            "city",
            "state",
            "source_url",
            "source_event_ref",
            "response_method",
            "stable_request_id",
            "procurement_scope",
            "customer_segment",
        ):
            _text(getattr(self, field), field, optional=True)
        if not isinstance(self.demand_type, DemandType):
            raise InvalidLiveContract("demand_type must use DemandType")
        if not isinstance(self.permission_basis, PermissionBasis):
            raise InvalidLiveContract("permission_basis must use PermissionBasis")
        if not isinstance(self.source_provenance, SourceProvenance):
            raise InvalidLiveContract("source_provenance must use SourceProvenance")
        if self.procurement_status is not None and not isinstance(
            self.procurement_status, ProcurementStatus
        ):
            raise InvalidLiveContract("procurement_status must use ProcurementStatus")
        if (self.source_url is None) == (self.source_event_ref is None):
            raise InvalidLiveContract(
                "provide exactly one public source URL or authorized account event reference"
            )
        if self.source_url is not None:
            parsed = urlsplit(self.source_url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise InvalidLiveContract("source_url must be an absolute HTTP(S) URL")
            if parsed.username or parsed.password:
                raise InvalidLiveContract("source_url must not contain credentials")
            if has_sensitive_query_parameter(self.source_url):
                raise InvalidLiveContract(
                    "source_url contains a sensitive query parameter"
                )
            if is_reserved_example_source_url(self.source_url):
                raise InvalidLiveContract(
                    "reserved example and test domains cannot identify a real source"
                )
        if self.source_event_ref is not None and self.publicly_accessible:
            raise InvalidLiveContract("account event references must remain private")
        if self.source_event_ref is not None and not self.account_holder_authorized:
            raise InvalidLiveContract(
                "private marketplace events require account-holder authorization"
            )
        if not self.publicly_accessible and self.source_url is not None:
            raise InvalidLiveContract(
                "private platform records must use an account event reference"
            )
        if self.demand_type is DemandType.PUBLIC_PROCUREMENT:
            if self.procurement_status is None:
                raise InvalidLiveContract(
                    "public procurement requires an explicit or unknown status"
                )
        elif (
            self.procurement_status is not None
            or self.official_deadline is not None
            or self.procurement_scope is not None
            or self.eligibility_reviewed
        ):
            raise InvalidLiveContract(
                "procurement fields are only valid for procurement"
            )
        if self.official_deadline is not None and not isinstance(
            self.official_deadline, date
        ):
            raise InvalidLiveContract("official_deadline must be a date or None")
        if self.publication_date is not None and not isinstance(
            self.publication_date, date
        ):
            raise InvalidLiveContract("publication_date must be a date or None")
        if (
            not isinstance(self.discovered_at, datetime)
            or self.discovered_at.tzinfo is None
        ):
            raise InvalidLiveContract("discovered_at must be timezone-aware")
        object.__setattr__(
            self, "discovered_at", self.discovered_at.astimezone(timezone.utc)
        )
        for field in (
            "explicit_intent",
            "is_open",
            "publicly_accessible",
            "business_authorized",
            "account_holder_authorized",
            "ongoing_need",
            "eligibility_reviewed",
        ):
            value = getattr(self, field)
            if value is not None and not isinstance(value, bool):
                raise InvalidLiveContract(f"{field} must be boolean")
        if self.expected_jobs_per_day is not None and (
            isinstance(self.expected_jobs_per_day, bool)
            or not isinstance(self.expected_jobs_per_day, int)
            or self.expected_jobs_per_day < 0
        ):
            raise InvalidLiveContract(
                "expected_jobs_per_day must be non-negative or None"
            )
        if not isinstance(self.eligibility_requirements, tuple) or any(
            not isinstance(item, str) or not item.strip()
            for item in self.eligibility_requirements
        ):
            raise InvalidLiveContract(
                "eligibility_requirements must be non-blank strings"
            )
        if not isinstance(self.limitations, tuple) or any(
            not isinstance(item, str) or not item.strip() for item in self.limitations
        ):
            raise InvalidLiveContract("limitations must contain non-blank strings")
        if not self.evidence or any(
            not isinstance(item, SourceEvidence) for item in self.evidence
        ):
            raise InvalidLiveContract("every opportunity requires SourceEvidence")
        evidence_ids = tuple(item.evidence_id for item in self.evidence)
        if len(set(evidence_ids)) != len(evidence_ids):
            raise InvalidLiveContract("opportunity evidence IDs must be unique")
        for item in self.evidence:
            if item.owner_entity_id not in (None, self.opportunity_id):
                raise InvalidLiveContract("evidence belongs to a different opportunity")
            expected_values: dict[str, object] = {
                "city": self.city,
                "state": self.state,
                "service_requested": self.service_requested,
                "explicit_intent": self.explicit_intent,
                "open_status": self.is_open,
                "response_method": self.response_method,
                "publication_date": (
                    self.publication_date.isoformat() if self.publication_date else None
                ),
                "procurement_status": (
                    self.procurement_status.value if self.procurement_status else None
                ),
                "procurement_scope": self.procurement_scope,
                "eligibility_reviewed": self.eligibility_reviewed,
                "expected_jobs_per_day": self.expected_jobs_per_day,
            }
            expected = expected_values.get(item.field)
            if item.field in expected_values:
                if item.field == "service_requested":
                    matches = isinstance(item.value, str) and normalize_service(
                        item.value
                    ) == normalize_service(str(expected))
                elif item.field in {"city", "state", "response_method"}:
                    matches = (
                        isinstance(item.value, str)
                        and isinstance(expected, str)
                        and item.value.casefold() == expected.casefold()
                    )
                elif item.field in {
                    "explicit_intent",
                    "open_status",
                    "eligibility_reviewed",
                }:
                    matches = type(item.value) is bool and item.value is expected
                elif item.field == "expected_jobs_per_day":
                    matches = (type(item.value) is int and item.value == expected) or (
                        item.value is None and expected is None
                    )
                elif item.field in {"publication_date", "procurement_status"}:
                    matches = isinstance(item.value, str) and item.value == expected
                else:
                    matches = item.value == expected
                if not matches:
                    raise InvalidLiveContract(
                        f"evidence field {item.field!r} does not match the opportunity"
                    )
        if (
            not self.business_authorized
            and self.permission_basis is not PermissionBasis.NOT_APPROVED
        ):
            raise InvalidLiveContract(
                "unauthorized records must use permission basis NOT_APPROVED"
            )
        if (
            self.business_authorized
            and self.permission_basis is PermissionBasis.NOT_APPROVED
        ):
            raise InvalidLiveContract("approved records cannot use NOT_APPROVED")
        if (
            self.source_event_ref is not None
            and self.permission_basis is not PermissionBasis.AUTHORIZED_ACCOUNT
        ):
            raise InvalidLiveContract(
                "private events require AUTHORIZED_ACCOUNT permission basis"
            )


_RESERVED_SOURCE_HOSTS = frozenset(
    {
        "example.com",
        "example.net",
        "example.org",
        "example",
        "test",
        "invalid",
        "localhost",
        "localhost.localdomain",
    }
)
_RESERVED_SOURCE_SUFFIXES = (
    ".example",
    ".test",
    ".invalid",
    ".localhost",
    ".example.com",
    ".example.net",
    ".example.org",
)


def is_reserved_example_source_url(source_url: str) -> bool:
    """Return whether a URL uses a reserved example/test hostname."""

    try:
        hostname = urlsplit(source_url).hostname
    except ValueError:
        return True
    if not hostname:
        return True
    try:
        normalized = hostname.encode("idna").decode("ascii").casefold().rstrip(".")
    except UnicodeError:
        return True
    try:
        address = ip_address(normalized)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        return True
    return (
        normalized in _RESERVED_SOURCE_HOSTS
        or "%" in normalized
        or any(normalized.endswith(suffix) for suffix in _RESERVED_SOURCE_SUFFIXES)
    )


def _identified_source_evidence(opportunity: Opportunity) -> tuple[SourceEvidence, ...]:
    return tuple(
        item
        for item in opportunity.evidence
        if item.source_name.casefold() == opportunity.source_platform.casefold()
        and (
            item.source_url == opportunity.source_url
            if opportunity.source_url is not None
            else item.source_url is None
        )
    )


def _verified_source_fields(opportunity: Opportunity) -> set[str]:
    return {
        item.field
        for item in _identified_source_evidence(opportunity)
        if item.kind is EvidenceKind.OBSERVED
        and item.confidence is not None
        and item.confidence >= 0.7
        and item.retrieved_at is not None
    }


def _verified_preview_fields(opportunity: Opportunity) -> set[str]:
    """Use confident fixture claims for preview scoring without authenticating them."""

    return {
        item.field
        for item in opportunity.evidence
        if item.confidence is not None and item.confidence >= 0.7
    }


def source_authenticity_issue(opportunity: Opportunity) -> str | None:
    """Check origin and source-linked evidence without conflating permission."""

    if opportunity.source_provenance is SourceProvenance.SYNTHETIC:
        return "Synthetic records are restricted to isolated tests and previews."
    if opportunity.source_provenance is not SourceProvenance.REAL:
        return "Source provenance is UNKNOWN; a real source was not established."
    if opportunity.source_url is not None:
        if is_reserved_example_source_url(opportunity.source_url):
            return (
                "A reserved example or test URL cannot establish source authenticity."
            )
        matching = _identified_source_evidence(opportunity)
    else:
        if (
            not opportunity.account_holder_authorized
            or not opportunity.source_event_ref
            or opportunity.permission_basis is not PermissionBasis.AUTHORIZED_ACCOUNT
        ):
            return "A private source requires an authorized account event reference."
        matching = _identified_source_evidence(opportunity)
        if not any(
            item.field == "source_event_ref"
            and item.value == opportunity.source_event_ref
            and item.kind is EvidenceKind.OBSERVED
            and item.confidence is not None
            and item.confidence >= 0.7
            and item.retrieved_at is not None
            for item in matching
        ):
            return (
                "Private source event reference must be observed, confident, and "
                "retrieved from the authorized account."
            )

    if not any(
        item.kind is EvidenceKind.OBSERVED
        and item.confidence is not None
        and item.confidence >= 0.7
        and item.retrieved_at is not None
        for item in matching
    ):
        return "No sufficiently confident observed evidence is linked to the source."
    return None


def source_evidence_quality_issue(opportunity: Opportunity) -> str | None:
    """Require dated source observations for the fields that define a lead."""

    authenticity_issue = source_authenticity_issue(opportunity)
    if authenticity_issue:
        return authenticity_issue
    required_fields = {
        "city",
        "state",
        "service_requested",
        "explicit_intent",
        "publication_date",
        "response_method",
    }
    if opportunity.demand_type is DemandType.PUBLIC_PROCUREMENT:
        required_fields.add("procurement_status")
    elif opportunity.is_open is not None:
        required_fields.add("open_status")
    missing = sorted(required_fields - _verified_source_fields(opportunity))
    if missing:
        return "Source evidence is insufficient for: " + ", ".join(missing)
    if (
        opportunity.publication_date is not None
        and opportunity.publication_date > opportunity.discovered_at.date()
    ):
        return "Publication date cannot be later than the source observation time."
    return None


def validate_persistent_import(opportunity: Opportunity) -> None:
    """Require real source origin, usable source evidence, and permission to persist."""

    issue = source_evidence_quality_issue(opportunity)
    if issue:
        raise InvalidLiveContract(issue)
    if not opportunity.business_authorized:
        raise InvalidLiveContract(
            "persistent commercial import requires business-use authorization"
        )
    if opportunity.permission_basis is PermissionBasis.NOT_APPROVED:
        raise InvalidLiveContract(
            "persistent commercial import requires an approved permission basis"
        )


@dataclass(frozen=True, slots=True)
class ScoreComponent:
    key: str
    label_es: str
    score: int
    maximum: int
    explanation_es: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OpportunityAssessment:
    opportunity: Opportunity
    classification: LeadClassification
    commercial_fit_score: int
    score_components: tuple[ScoreComponent, ...]
    capacity_note_es: str
    capacity_review_required: bool
    potentially_oversized: bool
    priority_reason_es: str
    recommended_action_es: str
    classification_reasons_es: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OpportunityPreviewAssessment:
    """Isolated scoring output; it can never qualify a persistent opportunity."""

    opportunity: Opportunity
    classification: LeadClassification
    commercial_fit_score: int
    score_components: tuple[ScoreComponent, ...]
    capacity_note_es: str
    capacity_review_required: bool
    potentially_oversized: bool
    priority_reason_es: str
    recommended_action_es: str
    classification_reasons_es: tuple[str, ...] = ()

    @property
    def actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class OpportunityEvent:
    event_id: str
    action: OpportunityEventAction
    actor: str
    note: str
    occurred_at: datetime
    scope_id: str | None = None
    related_event_id: str | None = None
    from_status: OpportunityStatus | None = None
    to_status: OpportunityStatus | None = None

    def __post_init__(self) -> None:
        for field in ("event_id", "actor", "note"):
            _text(getattr(self, field), field)
        for field in ("scope_id", "related_event_id"):
            _text(getattr(self, field), field, optional=True)
        if not isinstance(self.action, OpportunityEventAction):
            raise InvalidLiveContract("action must use OpportunityEventAction")
        for field in ("from_status", "to_status"):
            value = getattr(self, field)
            if value is not None and not isinstance(value, OpportunityStatus):
                raise InvalidLiveContract(f"{field} must use OpportunityStatus")
        if (self.from_status is None) != (self.to_status is None):
            raise InvalidLiveContract("status audit events require both from and to")
        if (
            not isinstance(self.occurred_at, datetime)
            or self.occurred_at.tzinfo is None
        ):
            raise InvalidLiveContract("occurred_at must be timezone-aware")
        object.__setattr__(
            self, "occurred_at", self.occurred_at.astimezone(timezone.utc)
        )


@dataclass(frozen=True, slots=True)
class OpportunityRecord:
    opportunity: Opportunity
    status: OpportunityStatus
    events: tuple[OpportunityEvent, ...]
    next_action: str | None = None
    follow_up_date: date | None = None
    duplicate_of: str | None = None
    duplicate_match: DuplicateMatchType | None = None
    duplicate_source_ids: tuple[str, ...] = ()
    possible_duplicate_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.opportunity, Opportunity):
            raise InvalidLiveContract("opportunity must be an Opportunity")
        if not isinstance(self.status, OpportunityStatus):
            raise InvalidLiveContract("status must use OpportunityStatus")
        if not isinstance(self.events, tuple) or any(
            not isinstance(item, OpportunityEvent) for item in self.events
        ):
            raise InvalidLiveContract("events must contain OpportunityEvent values")
        if len({item.event_id for item in self.events}) != len(self.events):
            raise InvalidLiveContract("event IDs must be unique")
        _text(self.duplicate_of, "duplicate_of", optional=True)
        if self.duplicate_match is not None and not isinstance(
            self.duplicate_match, DuplicateMatchType
        ):
            raise InvalidLiveContract("duplicate_match must use DuplicateMatchType")
        if (self.duplicate_of is None) != (self.duplicate_match is None):
            raise InvalidLiveContract("duplicate relationship metadata is incomplete")
        if (self.status is OpportunityStatus.DUPLICATE) != (
            self.duplicate_of is not None
        ):
            raise InvalidLiveContract(
                "DUPLICATE status requires a canonical relationship"
            )
        for values, field in (
            (self.duplicate_source_ids, "duplicate_source_ids"),
            (self.possible_duplicate_ids, "possible_duplicate_ids"),
        ):
            if not isinstance(values, tuple) or any(
                not isinstance(item, str) or not item.strip() for item in values
            ):
                raise InvalidLiveContract(f"{field} must contain non-blank IDs")
            if len(set(values)) != len(values):
                raise InvalidLiveContract(f"{field} IDs must be unique")
        if self.duplicate_of == self.opportunity.opportunity_id:
            raise InvalidLiveContract("an opportunity cannot duplicate itself")
        _text(self.next_action, "next_action", optional=True)
        if self.follow_up_date is not None and not isinstance(
            self.follow_up_date, date
        ):
            raise InvalidLiveContract("follow_up_date must be a date or None")


TRANSITION_MATRIX: dict[OpportunityStatus, frozenset[OpportunityStatus]] = {
    OpportunityStatus.DISCOVERED: frozenset(
        {
            OpportunityStatus.VERIFIED,
            OpportunityStatus.NEEDS_REVIEW,
            OpportunityStatus.EXPIRED,
            OpportunityStatus.DISQUALIFIED,
            OpportunityStatus.DUPLICATE,
        }
    ),
    OpportunityStatus.VERIFIED: frozenset(
        {
            OpportunityStatus.NEEDS_REVIEW,
            OpportunityStatus.EXPIRED,
            OpportunityStatus.DISQUALIFIED,
        }
    ),
    OpportunityStatus.NEEDS_REVIEW: frozenset(
        {
            OpportunityStatus.APPROVED_FOR_CONTACT,
            OpportunityStatus.EXPIRED,
            OpportunityStatus.DISQUALIFIED,
            OpportunityStatus.DUPLICATE,
        }
    ),
    OpportunityStatus.APPROVED_FOR_CONTACT: frozenset(
        {
            OpportunityStatus.CONTACTED,
            OpportunityStatus.EXPIRED,
            OpportunityStatus.DISQUALIFIED,
        }
    ),
    OpportunityStatus.CONTACTED: frozenset(
        {
            OpportunityStatus.REPLIED,
            OpportunityStatus.LOST,
            OpportunityStatus.EXPIRED,
            OpportunityStatus.DISQUALIFIED,
        }
    ),
    OpportunityStatus.REPLIED: frozenset(
        {
            OpportunityStatus.QUOTE_REQUESTED,
            OpportunityStatus.LOST,
            OpportunityStatus.EXPIRED,
            OpportunityStatus.DISQUALIFIED,
        }
    ),
    OpportunityStatus.QUOTE_REQUESTED: frozenset(
        {
            OpportunityStatus.QUOTE_SENT,
            OpportunityStatus.LOST,
            OpportunityStatus.EXPIRED,
            OpportunityStatus.DISQUALIFIED,
        }
    ),
    OpportunityStatus.QUOTE_SENT: frozenset(
        {
            OpportunityStatus.WON,
            OpportunityStatus.LOST,
            OpportunityStatus.EXPIRED,
            OpportunityStatus.DISQUALIFIED,
        }
    ),
    OpportunityStatus.WON: frozenset(),
    OpportunityStatus.LOST: frozenset(),
    OpportunityStatus.EXPIRED: frozenset(),
    OpportunityStatus.DISQUALIFIED: frozenset(),
    OpportunityStatus.DUPLICATE: frozenset(),
}


def validate_status_transition(
    record: OpportunityRecord,
    target: OpportunityStatus,
    action: OpportunityEventAction,
    *,
    note: str,
    related_event_id: str | None = None,
) -> None:
    """Apply the authoritative lifecycle policy for every mutation path."""

    current = record.status
    action_targets = {
        OpportunityEventAction.STATUS_UPDATED: {
            OpportunityStatus.NEEDS_REVIEW,
            OpportunityStatus.EXPIRED,
            OpportunityStatus.DISQUALIFIED,
        },
        OpportunityEventAction.OPEN_STATUS_VERIFIED: {
            OpportunityStatus.VERIFIED,
            current,
        },
        OpportunityEventAction.CONTACT_APPROVED: {
            OpportunityStatus.APPROVED_FOR_CONTACT,
        },
        OpportunityEventAction.MANUAL_CONTACT_RECORDED: {
            OpportunityStatus.CONTACTED,
        },
        OpportunityEventAction.RESPONSE_RECORDED: {
            OpportunityStatus.REPLIED,
            OpportunityStatus.QUOTE_REQUESTED,
            OpportunityStatus.WON,
            OpportunityStatus.LOST,
        },
        OpportunityEventAction.QUOTE_RECORDED: {OpportunityStatus.QUOTE_SENT},
        OpportunityEventAction.DUPLICATE_MARKED: {OpportunityStatus.DUPLICATE},
        OpportunityEventAction.QUOTE_APPROVED: {OpportunityStatus.QUOTE_REQUESTED},
        OpportunityEventAction.POSSIBLE_DUPLICATE_FLAGGED: {
            current,
            OpportunityStatus.NEEDS_REVIEW,
        },
        OpportunityEventAction.POSSIBLE_DUPLICATE_RESOLVED: {current},
        OpportunityEventAction.DUPLICATE_SOURCE_LINKED: {current},
    }
    same_state_action = action in {
        OpportunityEventAction.QUOTE_APPROVED,
        OpportunityEventAction.POSSIBLE_DUPLICATE_FLAGGED,
        OpportunityEventAction.POSSIBLE_DUPLICATE_RESOLVED,
        OpportunityEventAction.DUPLICATE_SOURCE_LINKED,
        OpportunityEventAction.OPEN_STATUS_VERIFIED,
    }
    if target is current and same_state_action:
        pass
    elif target not in TRANSITION_MATRIX[current]:
        raise InvalidLiveContract(
            f"invalid opportunity transition: {current.value} -> {target.value}"
        )
    if target not in action_targets.get(action, set()):
        raise InvalidLiveContract(f"{action.value} cannot transition to {target.value}")
    if (
        action is OpportunityEventAction.STATUS_UPDATED
        and target is OpportunityStatus.NEEDS_REVIEW
        and current is not OpportunityStatus.VERIFIED
    ):
        raise InvalidLiveContract("NEEDS_REVIEW requires prior source verification")
    if target is not current and target in {
        OpportunityStatus.WON,
        OpportunityStatus.LOST,
        OpportunityStatus.EXPIRED,
        OpportunityStatus.DISQUALIFIED,
        OpportunityStatus.DUPLICATE,
    }:
        _require_reason(note, target.value)
    if target is OpportunityStatus.APPROVED_FOR_CONTACT:
        if current is not OpportunityStatus.NEEDS_REVIEW:
            raise InvalidLiveContract("contact approval requires NEEDS_REVIEW")
        if record.possible_duplicate_ids:
            raise InvalidLiveContract(
                "possible duplicates must be resolved before contact approval"
            )
    if target is OpportunityStatus.CONTACTED:
        if record.possible_duplicate_ids:
            raise InvalidLiveContract(
                "possible duplicates must be resolved before contact"
            )
        approval = unused_approval_event(
            record,
            OpportunityEventAction.CONTACT_APPROVED,
            OpportunityEventAction.MANUAL_CONTACT_RECORDED,
        )
        if approval is None or related_event_id != approval.event_id:
            raise InvalidLiveContract(
                "contact requires its specific unused owner approval"
            )
        if approval.scope_id not in (None, record.opportunity.opportunity_id):
            raise InvalidLiveContract(
                "contact approval scope does not match opportunity"
            )
    if action is OpportunityEventAction.QUOTE_APPROVED:
        if current is not OpportunityStatus.QUOTE_REQUESTED:
            raise InvalidLiveContract("quote approval requires QUOTE_REQUESTED")
        if record.possible_duplicate_ids:
            raise InvalidLiveContract(
                "possible duplicates must be resolved before quote approval"
            )
    if action is OpportunityEventAction.POSSIBLE_DUPLICATE_FLAGGED:
        if not related_event_id:
            raise InvalidLiveContract("duplicate review flag requires a related ID")
    if target is OpportunityStatus.QUOTE_SENT:
        if record.possible_duplicate_ids:
            raise InvalidLiveContract(
                "possible duplicates must be resolved before sending a quote"
            )
        approval = unused_approval_event(
            record,
            OpportunityEventAction.QUOTE_APPROVED,
            OpportunityEventAction.QUOTE_RECORDED,
        )
        if approval is None or related_event_id != approval.event_id:
            raise InvalidLiveContract(
                "quote requires its specific unused owner approval"
            )
        if approval.scope_id not in (None, record.opportunity.opportunity_id):
            raise InvalidLiveContract("quote approval scope does not match opportunity")
    if target is OpportunityStatus.WON and not _has_action_history(
        record,
        {
            OpportunityEventAction.MANUAL_CONTACT_RECORDED,
            OpportunityEventAction.RESPONSE_RECORDED,
            OpportunityEventAction.QUOTE_RECORDED,
            OpportunityEventAction.QUOTE_APPROVED,
        },
    ):
        raise InvalidLiveContract(
            "WON requires recorded contact, reply, approved quote, and manually sent quote"
        )
    if target is OpportunityStatus.DUPLICATE and not related_event_id:
        raise InvalidLiveContract(
            "duplicate status requires a canonical opportunity ID"
        )


def history_issues(record: OpportunityRecord) -> tuple[str, ...]:
    """Report definitive lifecycle problems without rewriting legacy JSON."""

    actions = {event.action for event in record.events}
    issues: list[str] = []
    required_actions: dict[OpportunityStatus, set[OpportunityEventAction]] = {
        OpportunityStatus.APPROVED_FOR_CONTACT: {
            OpportunityEventAction.CONTACT_APPROVED
        },
        OpportunityStatus.CONTACTED: {OpportunityEventAction.MANUAL_CONTACT_RECORDED},
        OpportunityStatus.REPLIED: {OpportunityEventAction.RESPONSE_RECORDED},
        OpportunityStatus.QUOTE_REQUESTED: {OpportunityEventAction.RESPONSE_RECORDED},
        OpportunityStatus.QUOTE_SENT: {
            OpportunityEventAction.QUOTE_APPROVED,
            OpportunityEventAction.QUOTE_RECORDED,
        },
        OpportunityStatus.WON: {
            OpportunityEventAction.MANUAL_CONTACT_RECORDED,
            OpportunityEventAction.RESPONSE_RECORDED,
            OpportunityEventAction.QUOTE_APPROVED,
            OpportunityEventAction.QUOTE_RECORDED,
        },
        OpportunityStatus.LOST: {OpportunityEventAction.RESPONSE_RECORDED},
        OpportunityStatus.EXPIRED: {OpportunityEventAction.STATUS_UPDATED},
        OpportunityStatus.DISQUALIFIED: {OpportunityEventAction.STATUS_UPDATED},
        OpportunityStatus.DUPLICATE: {OpportunityEventAction.DUPLICATE_MARKED},
    }
    required = required_actions.get(record.status, set())
    if not required.issubset(actions):
        missing = ", ".join(sorted(item.value for item in required - actions))
        issues.append(
            f"{record.status.value} lacks required audit action(s): {missing}"
        )
    for event in record.events:
        if event.from_status is not None and event.to_status is not None:
            if event.scope_id not in (None, record.opportunity.opportunity_id):
                issues.append(
                    f"event {event.event_id} has a mismatched opportunity scope"
                )
            if (
                event.to_status is not event.from_status
                and event.to_status not in TRANSITION_MATRIX[event.from_status]
            ):
                issues.append(
                    f"event {event.event_id} records an impossible transition"
                )
            if event.to_status is not record.status and event is record.events[-1]:
                issues.append("latest audited transition does not match stored status")
    return tuple(issues)


def validate_record_mutation(
    previous: OpportunityRecord, updated: OpportunityRecord
) -> None:
    if previous.opportunity.opportunity_id != updated.opportunity.opportunity_id:
        raise InvalidLiveContract("a mutation cannot change the opportunity ID")
    issues = history_issues(previous)
    if issues:
        raise InvalidLiveContract(
            "historical record requires review: " + "; ".join(issues)
        )
    if updated.events[: len(previous.events)] != previous.events:
        raise InvalidLiveContract("mutation must preserve the complete audit history")
    appended = updated.events[len(previous.events) :]
    if len(appended) != 1:
        raise InvalidLiveContract("each mutation must append exactly one audit event")
    event = appended[0]
    if event.scope_id != previous.opportunity.opportunity_id:
        raise InvalidLiveContract("mutation event is not scoped to this opportunity")
    if (
        event.from_status is not previous.status
        or event.to_status is not updated.status
    ):
        raise InvalidLiveContract("mutation event status does not match the record")
    if event.action is OpportunityEventAction.OPEN_STATUS_VERIFIED:
        if len(updated.opportunity.evidence) != len(previous.opportunity.evidence) + 1:
            raise InvalidLiveContract(
                "source verification must append one evidence item"
            )
        new_evidence = updated.opportunity.evidence[-1]
        expected_opportunity = replace(
            previous.opportunity,
            is_open=True,
            evidence=(*previous.opportunity.evidence, new_evidence),
        )
        if updated.opportunity != expected_opportunity:
            raise InvalidLiveContract(
                "source verification changed unrelated opportunity data"
            )
        if (
            new_evidence.field != "open_status"
            or new_evidence.value is not True
            or new_evidence.kind is not EvidenceKind.OBSERVED
        ):
            raise InvalidLiveContract("source verification evidence is invalid")
    elif updated.opportunity != previous.opportunity:
        raise InvalidLiveContract("mutation cannot alter source opportunity evidence")
    if event.action not in {
        OpportunityEventAction.MANUAL_CONTACT_RECORDED,
        OpportunityEventAction.QUOTE_RECORDED,
        OpportunityEventAction.RESPONSE_RECORDED,
    } and (
        updated.next_action != previous.next_action
        or updated.follow_up_date != previous.follow_up_date
    ):
        raise InvalidLiveContract("mutation cannot alter unrelated follow-up data")
    validate_status_transition(
        previous,
        updated.status,
        event.action,
        note=event.note,
        related_event_id=event.related_event_id,
    )
    issues = history_issues(updated)
    if issues:
        raise InvalidLiveContract("invalid lifecycle history: " + "; ".join(issues))


def unused_approval_event(
    record: OpportunityRecord,
    approval_action: OpportunityEventAction,
    use_action: OpportunityEventAction,
) -> OpportunityEvent | None:
    approvals = [event for event in record.events if event.action is approval_action]
    if not approvals:
        return None
    approval = approvals[-1]
    approval_index = max(
        index
        for index, event in enumerate(record.events)
        if event.action is approval_action
    )
    use_index = max(
        (
            index
            for index, event in enumerate(record.events)
            if event.action is use_action
        ),
        default=-1,
    )
    return approval if approval_index > use_index else None


def _has_action_history(
    record: OpportunityRecord, required: set[OpportunityEventAction]
) -> bool:
    return required.issubset({event.action for event in record.events})


def _require_reason(note: str, outcome: str) -> None:
    normalized = " ".join(note.casefold().split())
    if len(normalized) < 8 or normalized in {
        "done",
        "complete",
        "closed",
        "test",
        "other",
        "n/a",
    }:
        raise InvalidLiveContract(f"{outcome} requires an explicit reason")


def classify_opportunity(
    opportunity: Opportunity,
    *,
    as_of: date,
    organization_profile: BusinessProfile | None = None,
) -> OpportunityAssessment:
    """Qualify only evidence-backed opportunities from established real sources."""

    return _classify_opportunity(
        opportunity,
        as_of=as_of,
        organization_profile=organization_profile,
        preview_only=False,
    )


def score_opportunity_preview(
    opportunity: Opportunity,
    *,
    as_of: date,
    organization_profile: BusinessProfile | None = None,
) -> OpportunityPreviewAssessment:
    """Score isolated synthetic fixtures without granting real-lead actionability."""

    if opportunity.source_provenance is not SourceProvenance.SYNTHETIC:
        raise InvalidLiveContract(
            "preview scoring requires explicitly synthetic provenance"
        )

    assessment = _classify_opportunity(
        opportunity,
        as_of=as_of,
        organization_profile=organization_profile,
        preview_only=True,
    )
    return OpportunityPreviewAssessment(
        opportunity=assessment.opportunity,
        classification=assessment.classification,
        commercial_fit_score=assessment.commercial_fit_score,
        score_components=assessment.score_components,
        capacity_note_es=assessment.capacity_note_es,
        capacity_review_required=assessment.capacity_review_required,
        potentially_oversized=assessment.potentially_oversized,
        priority_reason_es=assessment.priority_reason_es,
        recommended_action_es=assessment.recommended_action_es,
        classification_reasons_es=assessment.classification_reasons_es,
    )


def _classify_opportunity(
    opportunity: Opportunity,
    *,
    as_of: date,
    organization_profile: BusinessProfile | None,
    preview_only: bool,
) -> OpportunityAssessment:
    """Score demand and profile fit using only real evidence or isolated preview claims."""

    reasons: list[str] = []
    verified_fields = _verified_source_fields(opportunity)
    if preview_only:
        verified_fields.update(_verified_preview_fields(opportunity))
    date_known = opportunity.publication_date is not None
    age_days = (
        (as_of - opportunity.publication_date).days
        if opportunity.publication_date is not None
        else None
    )
    permission_ok = opportunity.business_authorized and (
        opportunity.publicly_accessible or opportunity.account_holder_authorized
    )
    procurement = opportunity.procurement_status
    authenticity_issue = (
        None if preview_only else source_authenticity_issue(opportunity)
    )
    service_fit, geography_fit, segment_fit, business_model_fit = _profile_match(
        opportunity, organization_profile
    )

    classification = LeadClassification.WARM
    if authenticity_issue:
        classification = LeadClassification.INSUFFICIENT_EVIDENCE
        reasons.append(authenticity_issue)
    elif (
        procurement
        in {
            ProcurementStatus.CLOSED_SOLICITATION,
            ProcurementStatus.AWARD_NOTICE,
        }
        or opportunity.is_open is False
    ):
        classification = LeadClassification.EXPIRED
        reasons.append("La solicitud está cerrada o ya fue adjudicada.")
    elif (
        procurement is ProcurementStatus.OPEN_SOLICITATION
        and opportunity.official_deadline is not None
        and opportunity.official_deadline < as_of
    ):
        classification = LeadClassification.EXPIRED
        reasons.append("El plazo oficial para presentar ofertas ya venció.")
    elif (
        not date_known
        or age_days is None
        or age_days < 0
        or "publication_date" not in verified_fields
    ):
        classification = LeadClassification.INSUFFICIENT_EVIDENCE
        reasons.append("Falta una fecha de publicación verificada en la fuente.")
    elif not permission_ok:
        classification = LeadClassification.INSUFFICIENT_EVIDENCE
        reasons.append("No se confirmó autorización para usar esta información.")
    elif not opportunity.city or "city" not in verified_fields:
        classification = LeadClassification.INSUFFICIENT_EVIDENCE
        reasons.append("La ciudad no está respaldada por evidencia observada.")
    elif not opportunity.state or "state" not in verified_fields:
        classification = LeadClassification.INSUFFICIENT_EVIDENCE
        reasons.append("El estado no está respaldado por evidencia observada.")
    elif (
        not opportunity.service_requested or "service_requested" not in verified_fields
    ):
        classification = LeadClassification.INSUFFICIENT_EVIDENCE
        reasons.append(
            "El servicio solicitado no está respaldado por evidencia observada."
        )
    elif organization_profile is None:
        classification = LeadClassification.INSUFFICIENT_EVIDENCE
        reasons.append(
            "Seleccione un perfil de organización para evaluar servicios y cobertura."
        )
    elif service_fit is None:
        classification = LeadClassification.INSUFFICIENT_EVIDENCE
        reasons.append("El perfil de organización no tiene servicios configurados.")
    elif service_fit is False:
        classification = LeadClassification.COLD
        reasons.append(
            "El servicio solicitado no coincide con los servicios del perfil seleccionado."
        )
    elif geography_fit is None:
        classification = LeadClassification.INSUFFICIENT_EVIDENCE
        reasons.append(
            "El perfil seleccionado no tiene áreas de servicio configuradas."
        )
    elif geography_fit is False:
        classification = LeadClassification.COLD
        reasons.append(
            "La ubicación está fuera de las áreas de servicio configuradas para la organización."
        )
    elif business_model_fit is False:
        classification = LeadClassification.COLD
        reasons.append(
            "El tipo de comprador no coincide con el modelo B2B/B2C configurado."
        )
    elif segment_fit is False:
        classification = LeadClassification.COLD
        reasons.append(
            "El segmento del cliente no coincide con los segmentos objetivo configurados."
        )
    elif opportunity.demand_type in {
        DemandType.BUSINESS_DIRECTORY,
        DemandType.REFERRAL_PARTNER,
        DemandType.POTENTIAL_B2B_BUYER,
        DemandType.RECOMMENDATION_SIGNAL,
    }:
        classification = LeadClassification.COLD
        reasons.append(
            "Es una señal indirecta, recomendación o directorio, no una compra confirmada."
        )
    else:
        is_procurement = opportunity.demand_type is DemandType.PUBLIC_PROCUREMENT
        max_age = 30 if is_procurement else 14
        expired_age = 30 if is_procurement or not opportunity.ongoing_need else 90
        if age_days > expired_age:
            classification = LeadClassification.EXPIRED
            reasons.append(
                "La solicitud superó su ventana de vigencia sin revalidación."
            )
        else:
            intent_observed = "explicit_intent" in verified_fields
            response_ready = (
                bool(opportunity.response_method)
                and "response_method" in verified_fields
            )
            if is_procurement:
                open_verified = (
                    procurement is ProcurementStatus.OPEN_SOLICITATION
                    and "procurement_status" in verified_fields
                )
            else:
                open_verified = (
                    opportunity.is_open is True and "open_status" in verified_fields
                )
            if not opportunity.explicit_intent or not intent_observed:
                reasons.append("La intención explícita requiere revisión en la fuente.")
            if not response_ready:
                reasons.append("El canal legítimo de respuesta aún no está verificado.")
            if not open_verified:
                reasons.append(
                    "El estado abierto de la solicitud requiere confirmación."
                )
            if age_days > max_age:
                reasons.append(
                    "La publicación ya no es reciente; requiere revalidación."
                )
            jobs = (
                opportunity.expected_jobs_per_day
                if "expected_jobs_per_day" in verified_fields
                else None
            )
            base_capacity = organization_profile.base_capacity_jobs_per_day
            capacity_block = (
                jobs is not None and base_capacity is not None and jobs > base_capacity
            )
            procurement_review_block = is_procurement and (
                not opportunity.procurement_scope
                or not opportunity.eligibility_reviewed
                or "procurement_scope" not in verified_fields
                or "eligibility_reviewed" not in verified_fields
                or (
                    base_capacity is not None
                    and (jobs is None or "expected_jobs_per_day" not in verified_fields)
                )
            )
            if procurement_review_block:
                reasons.append(
                    "El alcance, la elegibilidad y la capacidad del pliego requieren revisión."
                )
            if jobs is not None and base_capacity is not None and jobs > base_capacity:
                reasons.append(
                    "El volumen supera la capacidad diaria base configurada para la organización."
                )
            if (
                age_days <= max_age
                and opportunity.explicit_intent
                and intent_observed
                and response_ready
                and open_verified
                and service_fit is True
                and geography_fit is True
                and not capacity_block
                and not procurement_review_block
            ):
                classification = LeadClassification.HOT
                reasons.append(
                    "Demanda reciente, compatible con el perfil, y con respuesta autorizada."
                )
            else:
                classification = LeadClassification.WARM

    capacity_note, capacity_review, oversized = _capacity_note(
        opportunity, organization_profile, preview_only=preview_only
    )
    components = _score_components(
        opportunity,
        as_of,
        organization_profile,
        verified_fields,
        preview_only=preview_only,
    )
    fit_score = sum(item.score for item in components)
    if classification is LeadClassification.HOT:
        reason = "Alta prioridad: demanda vigente, servicios, cobertura y respuesta comprobados para el perfil seleccionado."
    elif classification is LeadClassification.WARM:
        reason = "Revisar pronto: la demanda tiene evidencia, pero faltan verificaciones de intención, respuesta o capacidad."
    elif classification is LeadClassification.EXPIRED:
        reason = "No priorizar: la solicitud está cerrada o fuera de vigencia."
    elif classification is LeadClassification.COLD:
        reason = "Baja prioridad: la señal no coincide con los servicios, el mercado o el modelo comercial configurado."
    else:
        reason = "No calificar todavía: falta evidencia o un perfil de organización seleccionado."
    if classification is LeadClassification.HOT and capacity_review:
        reason += " Requiere revisión de capacidad antes de aceptar el trabajo."
    action = _recommended_action(opportunity, classification, reasons, capacity_review)
    return OpportunityAssessment(
        opportunity=opportunity,
        classification=classification,
        commercial_fit_score=fit_score,
        score_components=components,
        capacity_note_es=capacity_note,
        capacity_review_required=capacity_review,
        potentially_oversized=oversized,
        priority_reason_es=reason,
        recommended_action_es=action,
        classification_reasons_es=tuple(reasons),
    )


def duplicate_key(opportunity: Opportunity) -> str:
    """Return a deterministic exact source identity, never a person identity."""

    if opportunity.stable_request_id:
        identity = "stable:" + opportunity.stable_request_id.casefold().strip()
    elif opportunity.source_event_ref:
        identity = (
            "event:"
            + opportunity.source_platform.casefold()
            + ":"
            + (opportunity.source_event_ref.casefold())
        )
    elif opportunity.source_url:
        identity = "url:" + _canonical_source_url(opportunity.source_url)
    else:
        identity = "source-record:" + opportunity.opportunity_id
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def duplicate_match_evidence(
    left: Opportunity, right: Opportunity
) -> tuple[DuplicateMatchType | None, str]:
    """Classify an exact, strong, or review-only cross-source match."""

    if duplicate_key(left) == duplicate_key(right):
        return DuplicateMatchType.EXACT, "Coincide la identidad exacta de la fuente."
    if not _same_market_and_service(left, right):
        return None, ""
    details = _request_detail_tokens(left) & _request_detail_tokens(right)
    dates_match = (
        left.publication_date is not None
        and right.publication_date is not None
        and left.publication_date == right.publication_date
    )
    if dates_match and len(details) >= 2:
        return (
            DuplicateMatchType.STRONG,
            "Coinciden ciudad, servicio, fecha de publicación y detalles específicos: "
            + ", ".join(sorted(details)),
        )
    dates_close = (
        left.publication_date is not None
        and right.publication_date is not None
        and abs((left.publication_date - right.publication_date).days) <= 1
    )
    dates_missing = left.publication_date is None or right.publication_date is None
    if (dates_match and len(details) < 2) or (
        (dates_close or dates_missing) and len(details) >= 2
    ):
        return (
            None,
            "POSSIBLE_DUPLICATE: coinciden ciudad y servicio, pero falta evidencia "
            "distintiva suficiente para confirmar identidad.",
        )
    return None, ""


def possible_duplicate_candidate(left: Opportunity, right: Opportunity) -> bool:
    match, evidence = duplicate_match_evidence(left, right)
    return match is None and evidence.startswith("POSSIBLE_DUPLICATE:")


def _same_market_and_service(left: Opportunity, right: Opportunity) -> bool:
    return (
        (left.city or "").strip().casefold() == (right.city or "").strip().casefold()
        and (left.state or "").strip().casefold()
        == (right.state or "").strip().casefold()
        and normalize_service(left.service_requested)
        == normalize_service(right.service_requested)
        and bool(left.city and left.state)
    )


_DETAIL_STOP_WORDS = frozenset(
    "a an and are as at be by for from has have in is it of on or the to with "
    "we they this that looking need needs wants want requesting request "
    "service vendor provider company business request proposal bid quote "
    "someone person professional company local reliable good please help "
    "quote estimate job jobs "
    "house home residential clean cleaning cleaner commercial "
    "standard apartment condo property "
    "today available required requested requestor customer buyer customers "
    "synthetic public source fixture details detail retained no account "
    "solicitation procurement bid facility services evidence summary real data "
    "provided observed described".split()
)


def _request_detail_tokens(opportunity: Opportunity) -> set[str]:
    text = f"{opportunity.title} {opportunity.summary}".casefold()
    tokens = set(re.findall(r"[a-z]{3,}", text))
    tokens -= set(normalize_taxonomy_label(opportunity.city or "").split())
    tokens -= set(normalize_taxonomy_label(opportunity.state or "").split())
    tokens -= _DETAIL_STOP_WORDS
    tokens -= set(
        re.findall(r"[a-z]{3,}", normalize_service(opportunity.service_requested))
    )
    return tokens


def _canonical_source_url(value: str) -> str:
    parsed = urlsplit(value)
    hostname = (parsed.hostname or "").casefold()
    if hostname.startswith("www."):
        hostname = hostname[4:]
    port = parsed.port
    netloc = hostname
    if port is not None and not (
        (parsed.scheme.casefold() == "http" and port == 80)
        or (parsed.scheme.casefold() == "https" and port == 443)
    ):
        netloc = f"{hostname}:{port}"
    query = urlencode(
        sorted(
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key.casefold() not in {"fbclid", "gclid"}
            and not key.casefold().startswith("utm_")
        )
    )
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme.casefold(), netloc, path, query, ""))


def make_initial_record(
    opportunity: Opportunity, *, occurred_at: datetime
) -> OpportunityRecord:
    event = OpportunityEvent(
        event_id=f"import:{opportunity.opportunity_id}",
        action=OpportunityEventAction.IMPORTED,
        actor="operator",
        note="Oportunidad importada manualmente; no se realizó contacto.",
        occurred_at=occurred_at,
        scope_id=opportunity.opportunity_id,
    )
    return OpportunityRecord(opportunity, OpportunityStatus.DISCOVERED, (event,))


def normalize_service(value: str, *, vertical: str | None = None) -> str:
    """Normalize with the selected vertical's taxonomy when one is provided."""

    return canonical_service_for_vertical(vertical or "OTHER", value)


def _profile_match(
    opportunity: Opportunity, profile: BusinessProfile | None
) -> tuple[bool | None, bool | None, bool | None, bool | None]:
    if profile is None:
        return None, None, None, None
    offerings = (
        tuple(profile.primary_services)
        + tuple(profile.secondary_services or ())
        + tuple(profile.products or ())
    )
    requested = canonical_service_for_vertical(
        profile.vertical, opportunity.service_requested
    )
    configured = {
        canonical_service_for_vertical(profile.vertical, item) for item in offerings
    }
    service_fit: bool | None = requested in configured if configured else None

    coverage = (
        profile.owner_confirmed_service_areas or profile.additional_service_areas or ()
    )
    geography_fit: bool | None = None
    if coverage:
        geography_fit = any(
            _service_area_matches(
                area,
                opportunity.city or "",
                opportunity.state or "",
                profile.state_region,
            )
            for area in coverage
        )

    segment_fit: bool | None = None
    if opportunity.customer_segment:
        segments = {
            normalize_taxonomy_label(item) for item in profile.target_customer_segments
        }
        segment_fit = (
            normalize_taxonomy_label(opportunity.customer_segment) in segments
            if segments
            else None
        )

    b2b_models = {BusinessModel.B2B, BusinessModel.B2B2C, BusinessModel.MIXED}
    b2c_models = {BusinessModel.B2C, BusinessModel.B2B2C, BusinessModel.MIXED}
    if opportunity.demand_type in {
        DemandType.POTENTIAL_B2B_BUYER,
        DemandType.PUBLIC_PROCUREMENT,
    }:
        business_model_fit = profile.business_model in b2b_models
    elif opportunity.demand_type in {
        DemandType.DIRECT_CUSTOMER_DEMAND,
        DemandType.MARKETPLACE_LEAD,
    }:
        business_model_fit = profile.business_model in b2c_models
    else:
        business_model_fit = None
    if profile.business_model is BusinessModel.UNKNOWN:
        business_model_fit = None
    return service_fit, geography_fit, segment_fit, business_model_fit


def _service_area_matches(area: str, city: str, state: str, profile_state: str) -> bool:
    """Match a city and optional region from owner-supplied coverage text."""

    parts = [
        normalize_taxonomy_label(item)
        for item in re.split(r"[,|]", area)
        if item.strip()
    ]
    target_city = normalize_taxonomy_label(city)
    target_state = normalize_taxonomy_label(state)
    if not target_city or not target_state or not parts:
        return False
    if len(parts) == 1:
        return (
            parts[0] == target_city
            and normalize_taxonomy_label(profile_state) == target_state
        )
    return parts[0] == target_city and parts[-1] == target_state


def _evidence_ids_for(
    opportunity: Opportunity, fields: set[str], *, preview_only: bool
) -> tuple[str, ...]:
    return tuple(
        item.evidence_id
        for item in opportunity.evidence
        if item.field in fields
        and item.confidence is not None
        and item.confidence >= 0.7
        and (
            preview_only
            or (item.kind is EvidenceKind.OBSERVED and item.retrieved_at is not None)
        )
    )


def _score_components(
    opportunity: Opportunity,
    as_of: date,
    profile: BusinessProfile | None,
    verified: set[str],
    *,
    preview_only: bool,
) -> tuple[ScoreComponent, ...]:
    service_fit, geography_fit, segment_fit, _ = _profile_match(opportunity, profile)
    age = (
        (as_of - opportunity.publication_date).days
        if opportunity.publication_date
        else None
    )
    jobs = (
        opportunity.expected_jobs_per_day
        if "expected_jobs_per_day" in verified
        else None
    )
    base_capacity = profile.base_capacity_jobs_per_day if profile else None
    expanded_capacity = profile.expanded_capacity_jobs_per_day if profile else None
    if opportunity.demand_type in {
        DemandType.DIRECT_CUSTOMER_DEMAND,
        DemandType.MARKETPLACE_LEAD,
        DemandType.PUBLIC_PROCUREMENT,
    }:
        intent_score = 15 if opportunity.explicit_intent else 6
    elif opportunity.demand_type is DemandType.RECOMMENDATION_SIGNAL:
        intent_score = 5
    else:
        intent_score = 2
    geo_score = (
        15 if geography_fit is True and {"city", "state"}.issubset(verified) else 0
    )
    service_score = 15 if service_fit is True and "service_requested" in verified else 0
    segment_score = 5 if segment_fit is True and "customer_segment" in verified else 0
    recency_score = (
        15
        if age is not None and 0 <= age <= 14
        else 10
        if age is not None and 15 <= age <= 30
        else 5
        if age is not None and 31 <= age <= 90
        else 0
    )
    if opportunity.demand_type is DemandType.PUBLIC_PROCUREMENT:
        if (
            opportunity.procurement_status is ProcurementStatus.OPEN_SOLICITATION
            and "procurement_status" in verified
        ):
            status_score = (
                15
                if opportunity.official_deadline is None
                or opportunity.official_deadline >= as_of
                else 0
            )
        elif (
            opportunity.procurement_status
            in {ProcurementStatus.CLOSED_SOLICITATION, ProcurementStatus.AWARD_NOTICE}
            or opportunity.is_open is False
        ):
            status_score = 0
        else:
            status_score = 5
    elif opportunity.is_open is False:
        status_score = 0
    elif opportunity.is_open is True and "open_status" in verified:
        status_score = 15
    else:
        status_score = 5
    response_score = (
        10
        if opportunity.business_authorized
        and opportunity.response_method
        and "response_method" in verified
        else 0
    )
    required = {
        "city",
        "state",
        "publication_date",
        "service_requested",
        "explicit_intent",
        "response_method",
    }
    evidence_score = 5 if required.issubset(verified) else 3 if verified else 0
    capacity_score = (
        5
        if base_capacity is not None
        and jobs is not None
        and jobs <= base_capacity
        and "expected_jobs_per_day" in verified
        else 2
        if expanded_capacity is not None
        and jobs is not None
        and jobs <= expanded_capacity
        and "expected_jobs_per_day" in verified
        else 0
    )

    evidence_fields = {
        "intent": {"explicit_intent"},
        "geography": {"city", "state"},
        "service": {"service_requested"},
        "customer_segment": {"customer_segment"},
        "recency": {"publication_date"},
        "open_status": {"open_status", "procurement_status"},
        "response": {"response_method"},
        "evidence": required,
        "capacity": {"expected_jobs_per_day"},
    }
    components = (
        (
            "intent",
            "Intención de compra",
            intent_score,
            15,
            "La puntuación de intención depende de la intención observada; el encaje comercial no implica intención de compra.",
        ),
        (
            "geography",
            "Cobertura geográfica",
            geo_score,
            15,
            "La cobertura se compara con las áreas configuradas para la organización seleccionada."
            if profile
            else "Sin perfil seleccionado no se puede evaluar la cobertura.",
        ),
        (
            "service",
            "Servicio compatible",
            service_score,
            15,
            "El servicio solicitado se normaliza con la taxonomía de la vertical seleccionada."
            if profile
            else "Sin perfil seleccionado no se puede confirmar compatibilidad de servicio.",
        ),
        (
            "customer_segment",
            "Segmento de cliente",
            segment_score,
            5,
            "Se puntúa solo cuando el segmento observado coincide con un segmento objetivo configurado.",
        ),
        (
            "recency",
            "Recencia",
            recency_score,
            15,
            "Se puntúa la fecha publicada y respaldada por la fuente.",
        ),
        (
            "open_status",
            "Estado abierto",
            status_score,
            15,
            "Una solicitud abierta confirmada puntúa; un cierre o adjudicación no puntúa.",
        ),
        (
            "response",
            "Ruta de respuesta autorizada",
            response_score,
            10,
            "Se requiere permiso de uso y un canal legítimo respaldados por evidencia.",
        ),
        (
            "evidence",
            "Calidad de evidencia",
            evidence_score,
            5,
            "La puntuación refleja campos observados y sus fuentes.",
        ),
        (
            "capacity",
            "Compatibilidad de capacidad",
            capacity_score,
            5,
            "La capacidad se compara solo con límites configurados para el perfil seleccionado.",
        ),
    )
    profile_evidence_fields = {
        "geography": {"owner_confirmed_service_areas", "additional_service_areas"},
        "service": {"primary_services", "secondary_services"},
        "customer_segment": {"target_customer_segments"},
        "capacity": {"base_capacity_jobs_per_day", "expanded_capacity_jobs_per_day"},
    }

    def component_evidence_ids(key: str) -> tuple[str, ...]:
        ids = list(
            _evidence_ids_for(
                opportunity,
                evidence_fields[key],
                preview_only=preview_only,
            )
        )
        if profile is not None:
            ids.extend(
                item.evidence_id
                for item in profile.field_evidence
                if item.field in profile_evidence_fields.get(key, set())
            )
        return tuple(dict.fromkeys(ids))

    return tuple(
        ScoreComponent(
            key, label, score, maximum, explanation, component_evidence_ids(key)
        )
        for key, label, score, maximum, explanation in components
    )


def _capacity_note(
    opportunity: Opportunity,
    profile: BusinessProfile | None,
    *,
    preview_only: bool = False,
) -> tuple[str, bool, bool]:
    verified_fields = _verified_source_fields(opportunity)
    if preview_only:
        verified_fields.update(_verified_preview_fields(opportunity))
    jobs = (
        opportunity.expected_jobs_per_day
        if "expected_jobs_per_day" in verified_fields
        else None
    )
    base = profile.base_capacity_jobs_per_day if profile else None
    expanded = profile.expanded_capacity_jobs_per_day if profile else None
    if base is None:
        return (
            "La capacidad operativa no tiene un límite diario comparable configurado; confirme disponibilidad antes de aceptar.",
            True,
            opportunity.demand_type is DemandType.PUBLIC_PROCUREMENT and jobs is None,
        )
    if jobs is None:
        return (
            "No se indicó volumen diario verificable; confirme el alcance y la capacidad antes de aceptar.",
            True,
            opportunity.demand_type is DemandType.PUBLIC_PROCUREMENT,
        )
    if jobs <= base:
        return (
            f"El volumen indicado está dentro de la capacidad diaria configurada ({base}).",
            False,
            False,
        )
    if expanded is not None and jobs <= expanded:
        dependency = (
            profile.capacity_expansion_dependency
            if profile and profile.capacity_expansion_dependency
            else "recursos adicionales configurados"
        )
        return (
            f"El volumen excede la capacidad base; confirme {dependency}.",
            True,
            False,
        )
    return (
        "El volumen supera la capacidad diaria configurada; revise el alcance antes de aceptar.",
        True,
        True,
    )


def _recommended_action(
    opportunity: Opportunity,
    classification: LeadClassification,
    reasons: list[str],
    capacity_review: bool,
) -> str:
    if classification is LeadClassification.EXPIRED:
        return "Marcar EXPIRED y conservar la evidencia de cierre; no enviar oferta."
    if classification is LeadClassification.INSUFFICIENT_EVIDENCE:
        return "Verificar fecha, autorización, ubicación, servicio e intención en la fuente original."
    if classification is LeadClassification.COLD:
        return "Mantener como señal de mercado; no tratarlo como solicitud activa."
    if (
        classification is LeadClassification.HOT
        and opportunity.demand_type is DemandType.PUBLIC_PROCUREMENT
    ):
        return "Revisar el pliego, la elegibilidad y el plazo; el dueño debe aprobar cualquier decisión de cotizar."
    if (
        classification is LeadClassification.WARM
        and opportunity.demand_type is DemandType.PUBLIC_PROCUREMENT
    ):
        return "Revisar el pliego, documentar alcance y elegibilidad, confirmar carga operativa y pedir aprobación humana antes de cualquier contacto o presentación."
    if capacity_review:
        return "Revisar el alcance y confirmar capacidad o subcontratistas; no cotizar hasta la aprobación del dueño."
    if classification is LeadClassification.WARM:
        return "Revalidar el estado y completar las verificaciones pendientes antes de solicitar aprobación de contacto."
    return "El dueño debe revisar la evidencia y aprobar cada contacto antes de responder por el canal autorizado."


def _text(value: object, field: str, *, optional: bool = False) -> None:
    if optional and value is None:
        return
    if not isinstance(value, str) or not value.strip():
        qualifier = " or None" if optional else ""
        raise InvalidLiveContract(f"{field} must be a non-blank string{qualifier}")
