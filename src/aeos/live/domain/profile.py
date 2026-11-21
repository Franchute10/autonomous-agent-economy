"""Owner-supplied business profiles for contextual LIVE discovery."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field, fields
from datetime import date, datetime, time, timezone
from enum import StrEnum
from math import isfinite
from types import MappingProxyType
from typing import Mapping

from aeos.core.ids import OrganizationId
from aeos.live.domain.business import BusinessInput
from aeos.live.domain.errors import InvalidLiveContract
from aeos.live.domain.evidence import EvidenceKind, SourceEvidence


class BusinessModel(StrEnum):
    B2C = "B2C"
    B2B = "B2B"
    B2B2C = "B2B2C"
    MIXED = "MIXED"  # Legacy value; supports both B2B and B2C.
    UNKNOWN = "UNKNOWN"


class ProfileFieldStatus(StrEnum):
    """Evidence-aware status for a profile field whose value may be absent."""

    REPORTED = "REPORTED"
    OBSERVED = "OBSERVED"
    UNKNOWN = "UNKNOWN"
    NOT_PROVIDED = "NOT_PROVIDED"
    NEEDS_CONFIRMATION = "NEEDS_CONFIRMATION"
    INFERRED = "INFERRED"


class RadiusUnit(StrEnum):
    MILES = "miles"
    KILOMETERS = "kilometers"


def _text(value: object, field: str, *, optional: bool = False) -> None:
    if optional and value is None:
        return
    if not isinstance(value, str) or not value.strip():
        raise InvalidLiveContract(f"{field} must be a non-blank string")


def _text_tuple(
    value: object, field: str, *, optional: bool = False, require_value: bool = False
) -> None:
    if optional and value is None:
        return
    if not isinstance(value, tuple) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise InvalidLiveContract(f"{field} must be a tuple of non-blank strings")
    if require_value and not value:
        raise InvalidLiveContract(f"{field} must contain at least one value")


@dataclass(frozen=True, slots=True)
class BusinessProfile:
    """Business context declared by an owner; it is never treated as verified."""

    business_name: str
    industry: str
    vertical: str
    description: str
    business_model: BusinessModel
    country: str
    state_region: str
    city: str
    service_radius: float | None
    service_radius_unit: RadiusUnit | None
    primary_services: tuple[str, ...]
    target_customer_segments: tuple[str, ...]
    owner_confirmed_service_areas: tuple[str, ...] | None = None
    owner_confirmation_source: str | None = None
    owner_confirmation_date: str | None = None
    owner_confirmed_fields: tuple[str, ...] | None = None
    legal_name: str | None = None
    registration_id: str | None = None
    legal_entity_status: str | None = None
    registered_address: str | None = None
    registered_agent: str | None = None
    reinstatement_filed_date: str | None = None
    reported_prior_names: tuple[str, ...] | None = None
    postal_code: str | None = None
    address: str | None = None
    additional_service_areas: tuple[str, ...] | None = None
    secondary_services: tuple[str, ...] | None = None
    products: tuple[str, ...] | None = None
    value_proposition: str | None = None
    differentiators: tuple[str, ...] | None = None
    website_url: str | None = None
    website_presence: bool | None = None
    google_business_profile_url: str | None = None
    google_business_profile_present: bool | None = None
    social_media_urls: tuple[str, ...] | None = None
    instagram_presence: bool | None = None
    instagram_url: str | None = None
    phone: str | None = None
    business_email: str | None = None
    years_in_operation: int | None = None
    approximate_employees: int | None = None
    existing_customer_sources: tuple[str, ...] | None = None
    commercial_challenges: tuple[str, ...] | None = None
    commercial_goals: tuple[str, ...] | None = None
    operational_capacity: str | None = None
    base_capacity_jobs_per_day: int | None = None
    expanded_capacity_jobs_per_day: int | None = None
    capacity_expansion_dependency: str | None = None
    weekend_available: bool | None = None
    urgent_service_available: bool | None = None
    legal_business_established: bool | None = None
    documentation_and_insurance_in_order: bool | None = None
    is_fictional_example: bool = False
    organization_id: OrganizationId | None = None
    licenses: tuple[str, ...] | None = None
    insurance: tuple[str, ...] | None = None
    technical_certifications: tuple[str, ...] | None = None
    subcontractor_count: int | None = None
    field_statuses: Mapping[str, ProfileFieldStatus] = dataclass_field(
        default_factory=dict
    )
    field_evidence: tuple[SourceEvidence, ...] = ()

    def __post_init__(self) -> None:
        if self.organization_id is not None and not isinstance(
            self.organization_id, OrganizationId
        ):
            raise InvalidLiveContract("organization_id must be an OrganizationId")
        if not isinstance(self.field_statuses, Mapping):
            raise InvalidLiveContract("field_statuses must be an object")
        profile_fields = {item.name for item in fields(type(self))} - {
            "organization_id",
            "field_statuses",
            "field_evidence",
            "owner_confirmed_fields",
            "owner_confirmation_source",
            "owner_confirmation_date",
            "is_fictional_example",
        }
        normalized_statuses: dict[str, ProfileFieldStatus] = {}
        for key, raw_status in self.field_statuses.items():
            if key not in profile_fields:
                raise InvalidLiveContract(f"unknown profile status field: {key}")
            try:
                normalized_statuses[key] = (
                    raw_status
                    if isinstance(raw_status, ProfileFieldStatus)
                    else ProfileFieldStatus(raw_status)
                )
            except (TypeError, ValueError) as error:
                raise InvalidLiveContract(
                    f"invalid status for profile field {key}"
                ) from error
        object.__setattr__(
            self, "field_statuses", MappingProxyType(normalized_statuses)
        )
        if not isinstance(self.field_evidence, tuple) or any(
            not isinstance(item, SourceEvidence) for item in self.field_evidence
        ):
            raise InvalidLiveContract(
                "field_evidence must be a tuple of SourceEvidence"
            )
        evidence_fields = {item.field for item in self.field_evidence}
        for key, status in normalized_statuses.items():
            value = getattr(self, key)
            has_value = value is not None and value != () and value != ""
            if key == "business_model" and value is BusinessModel.UNKNOWN:
                has_value = False
            if status in {
                ProfileFieldStatus.UNKNOWN,
                ProfileFieldStatus.NOT_PROVIDED,
                ProfileFieldStatus.NEEDS_CONFIRMATION,
            }:
                if has_value:
                    raise InvalidLiveContract(
                        f"{key} must be empty when its status is {status.value}"
                    )
            elif not has_value:
                raise InvalidLiveContract(
                    f"{key} must have a value when its status is {status.value}"
                )
            if status is ProfileFieldStatus.OBSERVED and not any(
                item.field == key and item.kind is EvidenceKind.OBSERVED
                for item in self.field_evidence
            ):
                raise InvalidLiveContract(
                    f"{key} requires matching OBSERVED field evidence"
                )
            if status is ProfileFieldStatus.INFERRED and not any(
                item.field == key and item.kind is EvidenceKind.INFERRED
                for item in self.field_evidence
            ):
                raise InvalidLiveContract(
                    f"{key} requires matching INFERRED field evidence"
                )
        if evidence_fields - set(normalized_statuses):
            raise InvalidLiveContract("field evidence requires a matching field status")
        for evidence in self.field_evidence:
            status = normalized_statuses[evidence.field]
            if evidence.kind.value != status.value:
                raise InvalidLiveContract(
                    f"{evidence.field} evidence kind must match its field status"
                )
            if status is ProfileFieldStatus.OBSERVED and (
                evidence.source_url is None or evidence.retrieved_at is None
            ):
                raise InvalidLiveContract(
                    f"{evidence.field} observed evidence requires a source URL and retrieval time"
                )
            field_value = getattr(self, evidence.field)
            permitted_values = (
                tuple(field_value) if isinstance(field_value, tuple) else (field_value,)
            )
            if evidence.value not in permitted_values:
                raise InvalidLiveContract(
                    f"{evidence.field} evidence value does not match the profile"
                )
        required_text_fields = ("business_name", "industry", "vertical", "description")
        location_fields = ("country", "state_region", "city")
        for field in required_text_fields:
            _text(getattr(self, field), field)
            object.__setattr__(self, field, getattr(self, field).strip())
        for field in location_fields:
            value = getattr(self, field)
            location_status = self.field_statuses.get(field)
            if location_status in {
                ProfileFieldStatus.UNKNOWN,
                ProfileFieldStatus.NOT_PROVIDED,
            }:
                if value not in (None, ""):
                    raise InvalidLiveContract(
                        f"{field} must be empty when its status is {location_status.value}"
                    )
                object.__setattr__(self, field, "")
            else:
                _text(value, field)
                object.__setattr__(self, field, value.strip())
        if not isinstance(self.business_model, BusinessModel):
            raise InvalidLiveContract(
                "business_model must be B2C, B2B, B2B2C, MIXED, or UNKNOWN"
            )
        if self.service_radius is not None:
            if not isinstance(self.service_radius, (int, float)) or isinstance(
                self.service_radius, bool
            ):
                raise InvalidLiveContract(
                    "service_radius must be a positive finite number or None"
                )
            if not isfinite(self.service_radius) or self.service_radius <= 0:
                raise InvalidLiveContract(
                    "service_radius must be a positive finite number or None"
                )
        if self.service_radius_unit is not None and not isinstance(
            self.service_radius_unit, RadiusUnit
        ):
            raise InvalidLiveContract(
                "service_radius_unit must be miles, kilometers, or None"
            )
        if (self.service_radius is None) != (self.service_radius_unit is None):
            raise InvalidLiveContract(
                "service_radius and service_radius_unit must be supplied together"
            )
        for field in (
            "primary_services",
            "target_customer_segments",
            "additional_service_areas",
            "owner_confirmed_service_areas",
            "secondary_services",
            "products",
            "differentiators",
            "social_media_urls",
            "reported_prior_names",
            "existing_customer_sources",
            "commercial_challenges",
            "commercial_goals",
            "licenses",
            "insurance",
            "technical_certifications",
        ):
            unknown_status = self.field_statuses.get(field) in {
                ProfileFieldStatus.UNKNOWN,
                ProfileFieldStatus.NOT_PROVIDED,
                ProfileFieldStatus.NEEDS_CONFIRMATION,
            }
            _text_tuple(
                getattr(self, field),
                field,
                optional=field not in {"primary_services", "target_customer_segments"}
                or unknown_status,
                require_value=(
                    field == "target_customer_segments"
                    or (field == "primary_services" and not self.products)
                )
                and not unknown_status,
            )
            values = getattr(self, field)
            if isinstance(values, tuple):
                object.__setattr__(self, field, tuple(item.strip() for item in values))
        if (
            self.additional_service_areas is not None
            and len(self.additional_service_areas) > 10
        ):
            raise InvalidLiveContract(
                "additional_service_areas may contain at most 10 entries"
            )
        if self.owner_confirmed_fields is not None:
            _text_tuple(self.owner_confirmed_fields, "owner_confirmed_fields")
            profile_fields = {item.name for item in fields(type(self))}
            metadata_fields = {
                "owner_confirmed_fields",
                "owner_confirmation_source",
                "owner_confirmation_date",
            }
            unknown_confirmed = set(self.owner_confirmed_fields) - (
                profile_fields - metadata_fields
            )
            if unknown_confirmed:
                raise InvalidLiveContract(
                    "owner_confirmed_fields contains unknown profile field(s): "
                    + ", ".join(sorted(unknown_confirmed))
                )
            if not self.owner_confirmation_source or not self.owner_confirmation_date:
                raise InvalidLiveContract(
                    "owner confirmation source and date are required when fields are confirmed"
                )
            _text(self.owner_confirmation_source, "owner_confirmation_source")
            if not isinstance(self.owner_confirmation_date, str):
                raise InvalidLiveContract(
                    "owner_confirmation_date must be an ISO calendar date"
                )
            try:
                parsed_date = date.fromisoformat(self.owner_confirmation_date)
            except ValueError as error:
                raise InvalidLiveContract(
                    "owner_confirmation_date must be an ISO calendar date"
                ) from error
            object.__setattr__(self, "owner_confirmation_date", parsed_date.isoformat())
            object.__setattr__(
                self,
                "owner_confirmed_fields",
                tuple(
                    dict.fromkeys(item.strip() for item in self.owner_confirmed_fields)
                ),
            )
        elif (
            self.owner_confirmation_source is not None
            or self.owner_confirmation_date is not None
        ):
            raise InvalidLiveContract(
                "owner confirmation source/date require owner_confirmed_fields"
            )
        _text(
            self.owner_confirmation_source, "owner_confirmation_source", optional=True
        )
        for field in (
            "legal_name",
            "registration_id",
            "legal_entity_status",
            "registered_address",
            "registered_agent",
            "reinstatement_filed_date",
            "postal_code",
            "address",
            "value_proposition",
            "website_url",
            "google_business_profile_url",
            "instagram_url",
            "phone",
            "business_email",
            "operational_capacity",
            "capacity_expansion_dependency",
        ):
            value = getattr(self, field)
            _text(value, field, optional=True)
            if isinstance(value, str):
                object.__setattr__(self, field, value.strip())
        if self.legal_entity_status is not None:
            object.__setattr__(
                self, "legal_entity_status", self.legal_entity_status.upper()
            )
        if self.reinstatement_filed_date is not None:
            try:
                parsed_date = date.fromisoformat(self.reinstatement_filed_date)
            except ValueError as error:
                raise InvalidLiveContract(
                    "reinstatement_filed_date must be an ISO calendar date"
                ) from error
            object.__setattr__(
                self, "reinstatement_filed_date", parsed_date.isoformat()
            )
        for field in (
            "years_in_operation",
            "approximate_employees",
            "base_capacity_jobs_per_day",
            "expanded_capacity_jobs_per_day",
            "subcontractor_count",
        ):
            value = getattr(self, field)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise InvalidLiveContract(
                    f"{field} must be a non-negative integer or None"
                )
        if (
            self.base_capacity_jobs_per_day is not None
            and self.expanded_capacity_jobs_per_day is not None
            and self.expanded_capacity_jobs_per_day < self.base_capacity_jobs_per_day
        ):
            raise InvalidLiveContract(
                "expanded_capacity_jobs_per_day cannot be below base capacity"
            )
        for field in (
            "weekend_available",
            "urgent_service_available",
            "legal_business_established",
            "documentation_and_insurance_in_order",
            "website_presence",
            "google_business_profile_present",
            "instagram_presence",
        ):
            value = getattr(self, field)
            if value is not None and not isinstance(value, bool):
                raise InvalidLiveContract(f"{field} must be a boolean or None")
        if not isinstance(self.is_fictional_example, bool):
            raise InvalidLiveContract("is_fictional_example must be a boolean")

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> BusinessProfile:
        """Parse a JSON object without accepting misspelled or unknown fields."""

        if not isinstance(payload, Mapping):
            raise InvalidLiveContract("business profile must be a JSON object")
        allowed = {item.name for item in fields(cls)}
        unknown = set(payload) - allowed
        if unknown:
            raise InvalidLiveContract(
                "unknown business profile field(s): " + ", ".join(sorted(unknown))
            )
        values = dict(payload)
        for field in (
            "primary_services",
            "target_customer_segments",
            "additional_service_areas",
            "owner_confirmed_service_areas",
            "secondary_services",
            "products",
            "differentiators",
            "social_media_urls",
            "reported_prior_names",
            "existing_customer_sources",
            "commercial_challenges",
            "commercial_goals",
            "licenses",
            "insurance",
            "technical_certifications",
        ):
            if field in values and values[field] is not None:
                raw = values[field]
                if not isinstance(raw, list | tuple):
                    raise InvalidLiveContract(f"{field} must be a JSON array")
                values[field] = tuple(raw)
        if "business_model" in values and isinstance(values["business_model"], str):
            try:
                values["business_model"] = BusinessModel(
                    values["business_model"].upper()
                )
            except ValueError as error:
                raise InvalidLiveContract(
                    "business_model must be B2C, B2B, B2B2C, MIXED, or UNKNOWN"
                ) from error
        if "organization_id" in values and isinstance(values["organization_id"], str):
            values["organization_id"] = OrganizationId.from_string(
                values["organization_id"]
            )
        if "field_statuses" in values:
            raw_statuses = values["field_statuses"]
            if not isinstance(raw_statuses, Mapping):
                raise InvalidLiveContract("field_statuses must be an object")
            try:
                values["field_statuses"] = {
                    str(key): ProfileFieldStatus(value)
                    for key, value in raw_statuses.items()
                }
            except (TypeError, ValueError) as error:
                raise InvalidLiveContract("invalid profile field status") from error
        if "field_evidence" in values:
            raw_evidence = values["field_evidence"]
            if not isinstance(raw_evidence, list | tuple):
                raise InvalidLiveContract("field_evidence must be an array")
            values["field_evidence"] = tuple(
                _source_evidence_from_dict(item) for item in raw_evidence
            )
        if (
            "owner_confirmed_fields" in values
            and values["owner_confirmed_fields"] is not None
        ):
            raw_confirmed = values["owner_confirmed_fields"]
            if not isinstance(raw_confirmed, list | tuple):
                raise InvalidLiveContract("owner_confirmed_fields must be a JSON array")
            values["owner_confirmed_fields"] = tuple(raw_confirmed)
        if "service_radius_unit" in values and isinstance(
            values["service_radius_unit"], str
        ):
            try:
                values["service_radius_unit"] = RadiusUnit(
                    values["service_radius_unit"].lower()
                )
            except ValueError as error:
                raise InvalidLiveContract(
                    "service_radius_unit must be miles or kilometers"
                ) from error
        try:
            return cls(**values)  # type: ignore[arg-type]
        except TypeError as error:
            raise InvalidLiveContract(f"invalid business profile: {error}") from error

    def to_business_input(self) -> BusinessInput:
        """Adapt the profile to the existing LIVE assessment contract."""

        radius_miles = self.service_radius
        if (
            self.service_radius is not None
            and self.service_radius_unit is RadiusUnit.KILOMETERS
        ):
            radius_miles = self.service_radius * 0.621371
        return BusinessInput(
            business_name=self.business_name,
            industry=self.vertical,
            city=self.city,
            state=self.state_region,
            country=self.country,
            service_radius_miles=radius_miles,
            website_url=self.website_url,
            google_business_url=self.google_business_profile_url,
            main_customer_sources=self.existing_customer_sources,
        )

    def reported_evidence(self) -> tuple[SourceEvidence, ...]:
        """Represent supplied profile values as REPORTED evidence records."""

        records: list[SourceEvidence] = []
        metadata_fields = {
            "owner_confirmation_source",
            "owner_confirmation_date",
            "owner_confirmed_fields",
        }
        explicitly_confirmed = (
            set(self.owner_confirmed_fields)
            if self.owner_confirmed_fields is not None
            else None
        )
        confirmation_instant = (
            datetime.combine(
                date.fromisoformat(self.owner_confirmation_date),
                time.min,
                tzinfo=timezone.utc,
            )
            if self.owner_confirmation_date is not None
            else None
        )
        explicit_evidence: dict[str, list[SourceEvidence]] = {}
        for item in self.field_evidence:
            explicit_evidence.setdefault(item.field, []).append(item)
        for field, raw_value in self.to_dict().items():
            status = self.field_statuses.get(field)
            if (
                raw_value is None
                or field == "is_fictional_example"
                or field
                in {
                    "organization_id",
                    "field_statuses",
                    "field_evidence",
                }
                or field in metadata_fields
                or status
                in {
                    ProfileFieldStatus.UNKNOWN,
                    ProfileFieldStatus.NOT_PROVIDED,
                    ProfileFieldStatus.NEEDS_CONFIRMATION,
                }
                or (
                    explicitly_confirmed is not None
                    and field not in explicitly_confirmed
                )
            ):
                continue
            supplied_evidence = explicit_evidence.get(field, [])
            if supplied_evidence:
                records.extend(supplied_evidence)
                continue
            values = (
                tuple(raw_value)
                if isinstance(raw_value, list | tuple)
                else (raw_value,)
            )
            if isinstance(raw_value, list | tuple) and not values:
                values = ("[]",)
            for index, value in enumerate(values):
                if type(value) not in (str, int, float, bool):
                    continue
                records.append(
                    SourceEvidence(
                        evidence_id=f"profile:{field}:{index}",
                        kind=EvidenceKind.REPORTED,
                        subject=self.business_name,
                        field=field,
                        value=value,
                        source_name=(
                            self.owner_confirmation_source
                            if explicitly_confirmed is not None
                            else "Business profile supplied by owner"
                        )
                        or "Business profile supplied by owner",
                        retrieved_at=confirmation_instant,
                        excerpt=(
                            f"Owner-confirmed profile value for {field} on "
                            f"{self.owner_confirmation_date}."
                            if explicitly_confirmed is not None
                            else f"Owner-declared profile value for {field}."
                        ),
                    )
                )
        return tuple(records)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible copy of the full profile."""

        result: dict[str, object] = {}
        for item in fields(self):
            value = getattr(self, item.name)
            if isinstance(value, StrEnum):
                result[item.name] = value.value
            elif isinstance(value, OrganizationId):
                result[item.name] = value.value
            elif isinstance(value, tuple):
                result[item.name] = [
                    _source_evidence_to_dict(item)
                    if isinstance(item, SourceEvidence)
                    else item
                    for item in value
                ]
            elif item.name == "field_statuses":
                result[item.name] = {key: status.value for key, status in value.items()}
            else:
                result[item.name] = value
        return result


def _source_evidence_to_dict(evidence: SourceEvidence) -> dict[str, object]:
    return {
        "evidence_id": evidence.evidence_id,
        "kind": evidence.kind.value,
        "subject": evidence.subject,
        "field": evidence.field,
        "value": evidence.value,
        "source_name": evidence.source_name,
        "source_url": evidence.source_url,
        "retrieved_at": (
            None if evidence.retrieved_at is None else evidence.retrieved_at.isoformat()
        ),
        "excerpt": evidence.excerpt,
        "confidence": evidence.confidence,
        "assumptions": list(evidence.assumptions),
        "owner_entity_id": evidence.owner_entity_id,
    }


@dataclass(frozen=True, slots=True)
class BusinessProfileFixture:
    """Explicit envelope for synthetic profile examples and fixtures."""

    synthetic_fixture: bool
    synthetic_record: bool
    business_profile: BusinessProfile

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> BusinessProfileFixture:
        if set(payload) != {"fixture_metadata", "business_profile"}:
            raise InvalidLiveContract(
                "business profile fixture must contain only fixture_metadata and business_profile"
            )
        metadata = payload.get("fixture_metadata")
        profile_payload = payload.get("business_profile")
        if not isinstance(metadata, Mapping) or set(metadata) != {
            "synthetic_fixture",
            "synthetic_record",
        }:
            raise InvalidLiveContract(
                "fixture_metadata must explicitly identify a synthetic fixture record"
            )
        if (
            metadata.get("synthetic_fixture") is not True
            or metadata.get("synthetic_record") is not True
        ):
            raise InvalidLiveContract(
                "business profile fixture metadata must be explicitly synthetic"
            )
        if not isinstance(profile_payload, Mapping):
            raise InvalidLiveContract("business_profile must be a JSON object")
        profile = BusinessProfile.from_dict(profile_payload)
        if not profile.is_fictional_example:
            raise InvalidLiveContract(
                "synthetic business profile fixtures must be marked fictional"
            )
        return cls(True, True, profile)


def parse_business_profile_document(
    payload: Mapping[str, object],
) -> BusinessProfile:
    """Parse either a strict profile contract or its explicit synthetic fixture envelope."""

    if not isinstance(payload, Mapping):
        raise InvalidLiveContract("business profile document must be a JSON object")
    if "fixture_metadata" in payload or "business_profile" in payload:
        return BusinessProfileFixture.from_dict(payload).business_profile
    return BusinessProfile.from_dict(payload)


def _source_evidence_from_dict(value: object) -> SourceEvidence:
    if not isinstance(value, Mapping):
        raise InvalidLiveContract("field evidence entries must be objects")
    retrieved_at = value.get("retrieved_at")
    if retrieved_at is not None:
        if not isinstance(retrieved_at, str):
            raise InvalidLiveContract("field evidence timestamp must be an ISO string")
        try:
            parsed_at = datetime.fromisoformat(retrieved_at.replace("Z", "+00:00"))
        except ValueError as error:
            raise InvalidLiveContract(
                "field evidence timestamp must be ISO-8601"
            ) from error
    else:
        parsed_at = None
    assumptions = value.get("assumptions", [])
    if not isinstance(assumptions, list | tuple):
        raise InvalidLiveContract("field evidence assumptions must be an array")
    try:
        return SourceEvidence(
            evidence_id=str(value["evidence_id"]),
            kind=EvidenceKind(str(value["kind"])),
            subject=str(value["subject"]),
            field=str(value["field"]),
            value=value.get("value"),
            source_name=str(value["source_name"]),
            source_url=(
                None if value.get("source_url") is None else str(value["source_url"])
            ),
            retrieved_at=parsed_at,
            excerpt=None if value.get("excerpt") is None else str(value["excerpt"]),
            confidence=(
                None if value.get("confidence") is None else float(value["confidence"])
            ),
            assumptions=tuple(str(item) for item in assumptions),
            owner_entity_id=(
                None
                if value.get("owner_entity_id") is None
                else str(value["owner_entity_id"])
            ),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise InvalidLiveContract(f"invalid field evidence record: {error}") from error
