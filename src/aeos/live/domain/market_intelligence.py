"""Evidence-backed commercial research contracts for LIVE market pilots."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from enum import StrEnum
import re
from urllib.parse import urlsplit

from aeos.live.domain.errors import InvalidLiveContract
from aeos.live.domain.evidence import EvidenceKind
from aeos.live.domain.vertical import (
    Vertical,
    canonical_service_for_vertical,
    normalize_taxonomy_label,
    vertical_profile_for,
    verticals_match,
)


class ResearchStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    NO_RESULTS_FOUND = "NO_RESULTS_FOUND"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_NOT_CONFIGURED = "PROVIDER_NOT_CONFIGURED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NOT_REQUESTED = "NOT_REQUESTED"


class OrganizationRole(StrEnum):
    COMPETITOR = "COMPETITOR"
    POTENTIAL_BUYER = "POTENTIAL_BUYER"
    REFERRAL_PARTNER = "REFERRAL_PARTNER"
    SUPPLIER = "SUPPLIER"
    DIRECTORY_CANDIDATE = "DIRECTORY_CANDIDATE"


class CompetitorClassification(StrEnum):
    DIRECT_COMPETITOR = "DIRECT_COMPETITOR"
    INDIRECT_COMPETITOR = "INDIRECT_COMPETITOR"
    UNVERIFIED_CLEANING_BUSINESS = (
        "UNVERIFIED_CLEANING_BUSINESS"  # Legacy cleaning classification.
    )
    UNVERIFIED_BUSINESS = "UNVERIFIED_BUSINESS"


class DemandStatus(StrEnum):
    BUYING_INTENT = "BUYING_INTENT"
    HISTORICAL_BUYING_INTENT = "HISTORICAL_BUYING_INTENT"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class OpportunityPriority(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


def _text(value: object, field: str, *, optional: bool = False) -> None:
    if optional and value is None:
        return
    if not isinstance(value, str) or not value.strip():
        raise InvalidLiveContract(f"{field} must be a non-blank string")


def _text_tuple(values: tuple[str, ...], field: str) -> None:
    if not isinstance(values, tuple) or any(
        not isinstance(value, str) or not value.strip() for value in values
    ):
        raise InvalidLiveContract(f"{field} must be a tuple of non-blank strings")


@dataclass(frozen=True, slots=True)
class MarketEvidence:
    """A source-backed claim; each item belongs to exactly one entity or signal."""

    evidence_id: str
    entity_id: str
    field: str
    value: str
    source_name: str
    source_url: str
    retrieved_at: datetime
    published_at: date | None
    classification: EvidenceKind
    confidence: float
    supporting_information: str
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field in (
            "evidence_id",
            "entity_id",
            "field",
            "value",
            "source_name",
            "source_url",
            "supporting_information",
        ):
            _text(getattr(self, field), field)
        parsed = urlsplit(self.source_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise InvalidLiveContract("source_url must be an absolute HTTP(S) URL")
        if (
            not isinstance(self.retrieved_at, datetime)
            or self.retrieved_at.tzinfo is None
        ):
            raise InvalidLiveContract("retrieved_at must be a timezone-aware datetime")
        object.__setattr__(
            self, "retrieved_at", self.retrieved_at.astimezone(timezone.utc)
        )
        if self.published_at is not None and not isinstance(self.published_at, date):
            raise InvalidLiveContract("published_at must be a date or None")
        if not isinstance(self.classification, EvidenceKind):
            raise InvalidLiveContract(
                "classification must use the LIVE evidence vocabulary"
            )
        if (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, (float, int))
            or not 0 <= self.confidence <= 1
        ):
            raise InvalidLiveContract("confidence must be between 0 and 1")
        _text_tuple(self.limitations, "limitations")


@dataclass(frozen=True, slots=True)
class MarketOrganization:
    """A company candidate in one independently researched city."""

    entity_id: str
    name: str
    city: str
    role: OrganizationRole
    website_url: str | None
    public_address: str | None
    service_areas: tuple[str, ...]
    services: tuple[str, ...]
    customer_segments: tuple[str, ...]
    vacation_rental_specialization: bool
    recurring_options: tuple[str, ...]
    pricing_model: str | None
    public_listing_url: str | None
    rating_claim: float | None
    review_count_claim: int | None
    booking_methods: tuple[str, ...]
    conversion_channels: tuple[str, ...]
    public_contacts: tuple[str, ...]
    buyer_fit_reason: str | None
    referral_reason: str | None
    recommended_action: str
    validation_question: str
    evidence_ids: tuple[str, ...]
    limitations: tuple[str, ...] = ()
    buying_intent_evidence_ids: tuple[str, ...] = ()
    vertical: str = Vertical.CLEANING_SERVICES.value
    synthetic_record: bool = False

    def __post_init__(self) -> None:
        for field in (
            "entity_id",
            "name",
            "city",
            "recommended_action",
            "validation_question",
            "vertical",
        ):
            _text(getattr(self, field), field)
        for field in (
            "website_url",
            "public_address",
            "pricing_model",
            "public_listing_url",
            "buyer_fit_reason",
            "referral_reason",
        ):
            _text(getattr(self, field), field, optional=True)
        if not isinstance(self.synthetic_record, bool):
            raise InvalidLiveContract("synthetic_record must be boolean")
        if not isinstance(self.role, OrganizationRole):
            raise InvalidLiveContract("role must be an OrganizationRole")
        if not isinstance(self.vacation_rental_specialization, bool):
            raise InvalidLiveContract("vacation_rental_specialization must be boolean")
        if self.rating_claim is not None and (
            isinstance(self.rating_claim, bool)
            or not isinstance(self.rating_claim, (float, int))
            or not 0 <= self.rating_claim <= 5
        ):
            raise InvalidLiveContract("rating_claim must be between 0 and 5")
        if self.review_count_claim is not None and (
            isinstance(self.review_count_claim, bool)
            or not isinstance(self.review_count_claim, int)
            or self.review_count_claim < 0
        ):
            raise InvalidLiveContract(
                "review_count_claim must be a non-negative integer"
            )
        for field in (
            "service_areas",
            "services",
            "customer_segments",
            "recurring_options",
            "booking_methods",
            "conversion_channels",
            "public_contacts",
            "evidence_ids",
            "limitations",
            "buying_intent_evidence_ids",
        ):
            _text_tuple(getattr(self, field), field)
        if not self.evidence_ids:
            raise InvalidLiveContract("every organization requires source evidence")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise InvalidLiveContract("organization evidence_ids must be unique")
        if len(set(self.buying_intent_evidence_ids)) != len(
            self.buying_intent_evidence_ids
        ):
            raise InvalidLiveContract("buying-intent evidence IDs must be unique")
        if not set(self.buying_intent_evidence_ids).issubset(self.evidence_ids):
            raise InvalidLiveContract(
                "buying-intent evidence must also be linked as organization evidence"
            )

    @property
    def competitor_classification(self) -> CompetitorClassification | None:
        if self.role is not OrganizationRole.COMPETITOR:
            return None
        profile = vertical_profile_for(self.vertical)
        if not self.services or not self.service_areas or profile is None:
            return (
                CompetitorClassification.UNVERIFIED_CLEANING_BUSINESS
                if self.vertical == Vertical.CLEANING_SERVICES.value
                else CompetitorClassification.UNVERIFIED_BUSINESS
            )
        normalized_services = normalize_taxonomy_label(" ".join(self.services))
        aliases = dict(profile.service_aliases)

        def mentions(category: str) -> bool:
            phrases = (
                category,
                *(
                    alias
                    for alias, canonical in aliases.items()
                    if canonical == category
                ),
            )
            return any(
                normalize_taxonomy_label(phrase) in normalized_services
                for phrase in phrases
            )

        direct = profile.direct_competitor_services or profile.service_categories
        if any(mentions(category) for category in direct):
            return CompetitorClassification.DIRECT_COMPETITOR
        if any(mentions(category) for category in profile.adjacent_competitor_services):
            return CompetitorClassification.INDIRECT_COMPETITOR
        return (
            CompetitorClassification.UNVERIFIED_CLEANING_BUSINESS
            if self.vertical == Vertical.CLEANING_SERVICES.value
            else CompetitorClassification.UNVERIFIED_BUSINESS
        )


@dataclass(frozen=True, slots=True)
class PublicDemandSignal:
    """A manually reviewed public request, never private-platform content."""

    signal_id: str
    city: str
    platform: str
    source_url: str
    publication_date: date | None
    retrieved_at: datetime
    service_requested: str
    supporting_excerpt: str
    evidence_id: str
    supporting_excerpt_es: str | None = None
    limitations: tuple[str, ...] = ()
    vertical: str = Vertical.CLEANING_SERVICES.value
    synthetic_record: bool = False

    def __post_init__(self) -> None:
        for field in (
            "signal_id",
            "city",
            "platform",
            "source_url",
            "service_requested",
            "supporting_excerpt",
            "evidence_id",
            "vertical",
        ):
            _text(getattr(self, field), field)
        _text(self.supporting_excerpt_es, "supporting_excerpt_es", optional=True)
        if not isinstance(self.synthetic_record, bool):
            raise InvalidLiveContract("synthetic_record must be boolean")
        if not self.is_explicit_request(
            self.supporting_excerpt, self.service_requested, self.vertical
        ):
            raise InvalidLiveContract(
                "a public demand signal must explicitly request the configured service"
            )
        parsed = urlsplit(self.source_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise InvalidLiveContract("source_url must be an absolute HTTP(S) URL")
        if (
            not isinstance(self.retrieved_at, datetime)
            or self.retrieved_at.tzinfo is None
        ):
            raise InvalidLiveContract("retrieved_at must be a timezone-aware datetime")
        object.__setattr__(
            self, "retrieved_at", self.retrieved_at.astimezone(timezone.utc)
        )
        if self.publication_date is not None and not isinstance(
            self.publication_date, date
        ):
            raise InvalidLiveContract("publication_date must be a date or None")
        _text_tuple(self.limitations, "limitations")

    @staticmethod
    def is_explicit_request(
        text: str,
        service_requested: str | None = None,
        vertical: str = Vertical.CLEANING_SERVICES.value,
    ) -> bool:
        request_terms = (
            "looking for",
            "need a",
            "need someone",
            "seeking",
            "request for",
            "request a",
            "quote for",
            "estimate for",
            "bid invitation",
        )
        normalized = normalize_taxonomy_label(text)
        if not any(
            normalize_taxonomy_label(term) in normalized for term in request_terms
        ):
            return False
        if service_requested is None:
            return False
        requested = normalize_taxonomy_label(service_requested)
        profile = vertical_profile_for(vertical)
        canonical = canonical_service_for_vertical(vertical, service_requested)
        phrases = {requested, canonical}
        if profile is not None:
            phrases.update(
                normalize_taxonomy_label(alias)
                for alias, target in profile.service_aliases
                if normalize_taxonomy_label(target) == canonical
            )
        normalized_words = set(normalized.split())

        def word_key(word: str) -> str:
            if word.startswith("clean"):
                return "clean"
            return word[:-3] if word.endswith("ing") and len(word) > 5 else word

        return any(
            phrase
            and (
                phrase in normalized
                or all(
                    word_key(word) in {word_key(item) for item in normalized_words}
                    for word in phrase.split()
                )
            )
            for phrase in phrases
        )

    def status_at(self, as_of: date, *, stale_after_days: int = 30) -> DemandStatus:
        if self.synthetic_record:
            return DemandStatus.INSUFFICIENT_EVIDENCE
        if self.publication_date is None:
            return DemandStatus.INSUFFICIENT_EVIDENCE
        age_days = (as_of - self.publication_date).days
        if age_days < 0:
            return DemandStatus.INSUFFICIENT_EVIDENCE
        if age_days > stale_after_days:
            return DemandStatus.HISTORICAL_BUYING_INTENT
        return DemandStatus.BUYING_INTENT

    def is_actionable(self, as_of: date, *, stale_after_days: int = 30) -> bool:
        return (
            self.status_at(as_of, stale_after_days=stale_after_days)
            is DemandStatus.BUYING_INTENT
        )


@dataclass(frozen=True, slots=True)
class SourceCoverage:
    source_name: str
    status: ResearchStatus
    retrieved_at: datetime
    result_count: int | None
    note: str
    request_count: int = 0

    def __post_init__(self) -> None:
        _text(self.source_name, "source_name")
        _text(self.note, "note")
        if not isinstance(self.status, ResearchStatus):
            raise InvalidLiveContract("status must be a ResearchStatus")
        if (
            not isinstance(self.retrieved_at, datetime)
            or self.retrieved_at.tzinfo is None
        ):
            raise InvalidLiveContract("retrieved_at must be a timezone-aware datetime")
        object.__setattr__(
            self, "retrieved_at", self.retrieved_at.astimezone(timezone.utc)
        )
        if self.result_count is not None and (
            isinstance(self.result_count, bool)
            or not isinstance(self.result_count, int)
            or self.result_count < 0
        ):
            raise InvalidLiveContract(
                "result_count must be a non-negative integer or None"
            )
        if not isinstance(self.request_count, int) or self.request_count < 0:
            raise InvalidLiveContract("request_count must be a non-negative integer")
        if (
            self.status
            in {
                ResearchStatus.PROVIDER_UNAVAILABLE,
                ResearchStatus.PROVIDER_NOT_CONFIGURED,
            }
            and self.result_count is not None
        ):
            raise InvalidLiveContract(
                "failed or unconfigured sources must not imply a result count"
            )


@dataclass(frozen=True, slots=True)
class CityMarketResearch:
    city: str
    state: str
    organizations: tuple[MarketOrganization, ...]
    demand_signals: tuple[PublicDemandSignal, ...]
    evidence: tuple[MarketEvidence, ...]
    source_coverage: tuple[SourceCoverage, ...]
    limitations: tuple[str, ...]
    vertical: str = Vertical.CLEANING_SERVICES.value

    def __post_init__(self) -> None:
        _text(self.city, "city")
        _text(self.state, "state")
        _text(self.vertical, "vertical")
        for field, expected in (
            ("organizations", MarketOrganization),
            ("demand_signals", PublicDemandSignal),
            ("evidence", MarketEvidence),
            ("source_coverage", SourceCoverage),
        ):
            values = getattr(self, field)
            if not isinstance(values, tuple) or any(
                not isinstance(item, expected) for item in values
            ):
                raise InvalidLiveContract(
                    f"{field} must contain {expected.__name__} values"
                )
        _text_tuple(self.limitations, "limitations")
        organization_ids = [item.entity_id for item in self.organizations]
        if len(set(organization_ids)) != len(organization_ids):
            raise InvalidLiveContract("organization IDs must be unique within a city")
        evidence_by_id = {item.evidence_id: item for item in self.evidence}
        if len(evidence_by_id) != len(self.evidence):
            raise InvalidLiveContract("evidence IDs must be unique within a city")
        signal_ids = {item.signal_id for item in self.demand_signals}
        if len(signal_ids) != len(self.demand_signals):
            raise InvalidLiveContract("demand signal IDs must be unique within a city")
        for organization in self.organizations:
            if not verticals_match(organization.vertical, self.vertical):
                raise InvalidLiveContract(
                    "organization vertical must match the market vertical"
                )
            if organization.city.casefold() != self.city.casefold():
                raise InvalidLiveContract(
                    "organization city must match the market scope"
                )
            self._check_ownership(
                organization.entity_id, organization.evidence_ids, evidence_by_id
            )
            for evidence_id in organization.buying_intent_evidence_ids:
                evidence_item = evidence_by_id[evidence_id]
                if (
                    organization.role is not OrganizationRole.POTENTIAL_BUYER
                    or evidence_item.field != "buying_intent"
                    or (
                        evidence_item.classification is not EvidenceKind.OBSERVED
                        and not (
                            organization.synthetic_record
                            and evidence_item.classification is EvidenceKind.REPORTED
                        )
                    )
                ):
                    raise InvalidLiveContract(
                        "buying-intent evidence must be observed or an explicitly synthetic report owned by a potential buyer"
                    )
        for signal in self.demand_signals:
            if not verticals_match(signal.vertical, self.vertical):
                raise InvalidLiveContract(
                    "demand signal vertical must match the market vertical"
                )
            if signal.city.casefold() != self.city.casefold():
                raise InvalidLiveContract(
                    "demand signal city must match the market scope"
                )
            self._check_ownership(
                signal.signal_id, (signal.evidence_id,), evidence_by_id
            )

    @staticmethod
    def _check_ownership(
        owner_id: str,
        evidence_ids: tuple[str, ...],
        evidence_by_id: dict[str, MarketEvidence],
    ) -> None:
        for evidence_id in evidence_ids:
            evidence = evidence_by_id.get(evidence_id)
            if evidence is None:
                raise InvalidLiveContract(f"unknown evidence reference {evidence_id!r}")
            if evidence.entity_id != owner_id:
                raise InvalidLiveContract(
                    f"evidence {evidence_id!r} has the wrong owner"
                )


@dataclass(frozen=True, slots=True)
class CommercialOpportunity:
    opportunity_id: str
    city: str
    priority: OpportunityPriority
    opportunity_type: str
    target_id: str
    target_name: str
    why_it_matters: str
    recommended_next_action: str
    validation_question: str
    public_contact_channel: str | None
    confidence: float
    evidence_ids: tuple[str, ...]
    limitations: tuple[str, ...]


def resolve_organization_duplicates(
    organizations: tuple[MarketOrganization, ...],
    evidence: tuple[MarketEvidence, ...],
) -> tuple[tuple[MarketOrganization, ...], tuple[MarketEvidence, ...]]:
    """Merge same-city identities by normalized website or name, retaining evidence."""

    resolved: list[MarketOrganization] = []
    key_to_index: dict[tuple[str, str, str], int] = {}
    aliases: dict[str, str] = {}
    for organization_item in organizations:
        keys = tuple(
            (organization_item.city.casefold(), kind, value)
            for kind, value in _identity_keys(organization_item)
        )
        matches = {key_to_index[key] for key in keys if key in key_to_index}
        if len(matches) > 1:
            raise InvalidLiveContract(
                "website and name point to different existing identities for "
                f"{organization_item.name!r}"
            )
        index = next(iter(matches), None)
        if index is None:
            for key in keys:
                key_to_index[key] = len(resolved)
            resolved.append(organization_item)
            aliases[organization_item.entity_id] = organization_item.entity_id
            continue
        existing = resolved[index]
        if existing.role is not organization_item.role:
            raise InvalidLiveContract(
                f"duplicate identity {organization_item.name!r} has conflicting organization roles"
            )
        canonical_id = existing.entity_id
        for key in keys:
            key_to_index[key] = index
        aliases[organization_item.entity_id] = canonical_id
        resolved[index] = replace(
            existing,
            service_areas=tuple(
                dict.fromkeys(
                    (*existing.service_areas, *organization_item.service_areas)
                )
            ),
            services=tuple(
                dict.fromkeys((*existing.services, *organization_item.services))
            ),
            customer_segments=tuple(
                dict.fromkeys(
                    (*existing.customer_segments, *organization_item.customer_segments)
                )
            ),
            recurring_options=tuple(
                dict.fromkeys(
                    (*existing.recurring_options, *organization_item.recurring_options)
                )
            ),
            booking_methods=tuple(
                dict.fromkeys(
                    (*existing.booking_methods, *organization_item.booking_methods)
                )
            ),
            conversion_channels=tuple(
                dict.fromkeys(
                    (
                        *existing.conversion_channels,
                        *organization_item.conversion_channels,
                    )
                )
            ),
            public_contacts=tuple(
                dict.fromkeys(
                    (*existing.public_contacts, *organization_item.public_contacts)
                )
            ),
            evidence_ids=tuple(
                dict.fromkeys((*existing.evidence_ids, *organization_item.evidence_ids))
            ),
            buying_intent_evidence_ids=tuple(
                dict.fromkeys(
                    (
                        *existing.buying_intent_evidence_ids,
                        *organization_item.buying_intent_evidence_ids,
                    )
                )
            ),
            limitations=tuple(
                dict.fromkeys((*existing.limitations, *organization_item.limitations))
            ),
        )
    evidence_by_id: dict[str, MarketEvidence] = {}
    for evidence_item in evidence:
        owner = aliases.get(evidence_item.entity_id, evidence_item.entity_id)
        remapped = replace(evidence_item, entity_id=owner)
        existing_evidence = evidence_by_id.get(remapped.evidence_id)
        if existing_evidence is not None and existing_evidence != remapped:
            raise InvalidLiveContract(
                f"conflicting evidence ID {remapped.evidence_id!r}"
            )
        evidence_by_id[remapped.evidence_id] = remapped
    return tuple(resolved), tuple(evidence_by_id.values())


def _identity_keys(organization: MarketOrganization) -> tuple[tuple[str, str], ...]:
    keys: list[tuple[str, str]] = []
    normalized_name = re.sub(r"[^a-z0-9]+", " ", organization.name.casefold()).strip()
    keys.append(("name", normalized_name))
    if organization.website_url:
        host = (urlsplit(organization.website_url).hostname or "").casefold()
        if host.startswith("www."):
            host = host[4:]
        if host:
            keys.append(("website", host))
    return tuple(keys)
