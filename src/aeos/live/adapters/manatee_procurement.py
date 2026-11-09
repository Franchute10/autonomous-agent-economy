"""Read-only import adapter for Manatee County procurement source material.

This adapter deliberately performs no network requests. The County's public
procurement page documents a list export, but the linked portal is not available
to this runtime. Operators can import official URLs or an authorized export.
Every imported claim remains reported until the original record is verified.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, time, timezone
from enum import StrEnum
import hashlib
import json
from pathlib import Path
import re
from typing import Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from aeos.live.domain.evidence import EvidenceKind, SourceEvidence
from aeos.live.domain.opportunity_inbox import (
    DemandType,
    Opportunity,
    PermissionBasis,
    ProcurementStatus,
    SourceProvenance,
    duplicate_key,
)


MANATEE_BIDS_URL = (
    "https://www.mymanatee.org/services-and-amenities/service-listing/"
    "service-details/bids-proposals"
)
OFFICIAL_HOSTS = frozenset({"mymanatee.org", "demandstar.com"})


class AcquisitionState(StrEnum):
    SUCCESS = "SUCCESS"
    EMPTY = "EMPTY"
    BLOCKED = "BLOCKED"
    MALFORMED = "MALFORMED"


class SourceResponseState(StrEnum):
    AVAILABLE = "AVAILABLE"
    BLOCKED = "BLOCKED"


class RecordOrigin(StrEnum):
    MANUAL_OFFICIAL_IMPORT = "MANUAL_OFFICIAL_IMPORT"
    SECONDARY_DISCOVERY = "SECONDARY_DISCOVERY"


class ReferenceKind(StrEnum):
    OFFICIAL_PRIMARY = "OFFICIAL_PRIMARY"
    SECONDARY = "SECONDARY"


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    reference_id: str
    kind: ReferenceKind
    url: str
    label: str
    fields: tuple[str, ...] = ()
    excerpt: str | None = None


@dataclass(frozen=True, slots=True)
class SolicitationImport:
    origin: RecordOrigin
    issuing_agency: str | None
    solicitation_id: str | None
    title: str | None
    description: str | None
    official_source_url: str | None
    publication_date: date | None
    closing_date: date | None
    closing_time_local: str | None
    closing_timezone: str | None
    location: str | None
    city: str | None
    state: str | None
    publication_status: str | None
    service_categories: tuple[str, ...] | None
    eligibility_requirements: tuple[str, ...] | None
    operational_restrictions: tuple[str, ...] | None
    buying_solicitation: bool | None
    evidence_references: tuple[EvidenceReference, ...]
    retrieved_at: datetime
    duplicate_count: int = 0
    conflicting_fields: tuple[str, ...] = ()

    @property
    def has_primary_reference(self) -> bool:
        return any(
            ref.kind is ReferenceKind.OFFICIAL_PRIMARY
            for ref in self.evidence_references
        )


@dataclass(frozen=True, slots=True)
class DeduplicationSummary:
    records: tuple[SolicitationImport, ...]
    exact_duplicates_removed: int
    possible_url_matches: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class ManateeProcurementBatch:
    state: AcquisitionState
    response_state: SourceResponseState | None
    access_mode: str
    source_url: str
    retrieved_at: datetime
    block_reason: str | None
    solicitations: tuple[SolicitationImport, ...]
    secondary_candidates: tuple[SolicitationImport, ...]
    exact_duplicates_removed: int = 0
    possible_url_matches: tuple[tuple[str, str], ...] = ()
    malformed_reason: str | None = None


def parse_manual_import(
    payload: object, *, retrieved_at: datetime | None = None
) -> ManateeProcurementBatch:
    """Parse operator-supplied JSON without treating it as primary verification."""

    imported_at = retrieved_at or datetime.now(timezone.utc)
    try:
        if imported_at.tzinfo is None:
            raise ValueError("retrieved_at must include a timezone")
        document = _mapping(payload, "import")
        _only_keys(
            document,
            {"schema_version", "source", "solicitations", "secondary_candidates"},
            "import",
        )
        if document.get("schema_version") != 1:
            raise ValueError("schema_version must be 1")
        source = _mapping(document.get("source"), "source")
        _only_keys(
            source,
            {"name", "starting_url", "access_mode", "response_state", "block_reason"},
            "source",
        )
        if source.get("name") != "Manatee County Bids and Proposals":
            raise ValueError("source name must identify Manatee County procurement")
        starting_url = _required_text(source.get("starting_url"), "source.starting_url")
        if _canonical_url(starting_url) != _canonical_url(MANATEE_BIDS_URL):
            raise ValueError(
                "source.starting_url must be the official Manatee bids page"
            )
        access_mode = _required_text(source.get("access_mode"), "source.access_mode")
        if access_mode != "MANUAL_IMPORT":
            raise ValueError("access_mode must be MANUAL_IMPORT")
        try:
            response_state = SourceResponseState(
                _required_text(
                    source.get("response_state"), "source.response_state"
                ).upper()
            )
        except ValueError as error:
            raise ValueError("response_state must be AVAILABLE or BLOCKED") from error
        block_reason = _optional_text(source.get("block_reason"))
        if response_state is SourceResponseState.BLOCKED and block_reason is None:
            raise ValueError("blocked sources require a block_reason")

        raw_solicitations = _list(document.get("solicitations", []), "solicitations")
        raw_candidates = _list(
            document.get("secondary_candidates", []), "secondary_candidates"
        )
        solicitations = tuple(
            _parse_record(
                item, origin=RecordOrigin.MANUAL_OFFICIAL_IMPORT, at=imported_at
            )
            for item in raw_solicitations
        )
        candidates = tuple(
            _parse_record(item, origin=RecordOrigin.SECONDARY_DISCOVERY, at=imported_at)
            for item in raw_candidates
        )
        deduplicated = deduplicate_solicitations(solicitations)
        if response_state is SourceResponseState.BLOCKED:
            state = AcquisitionState.BLOCKED
        elif not deduplicated.records:
            state = AcquisitionState.EMPTY
        else:
            state = AcquisitionState.SUCCESS
        return ManateeProcurementBatch(
            state=state,
            response_state=response_state,
            access_mode=access_mode,
            source_url=starting_url,
            retrieved_at=imported_at,
            block_reason=block_reason,
            solicitations=deduplicated.records,
            secondary_candidates=candidates,
            exact_duplicates_removed=deduplicated.exact_duplicates_removed,
            possible_url_matches=deduplicated.possible_url_matches,
        )
    except (TypeError, ValueError, KeyError) as error:
        return ManateeProcurementBatch(
            state=AcquisitionState.MALFORMED,
            response_state=None,
            access_mode="MANUAL_IMPORT",
            source_url=MANATEE_BIDS_URL,
            retrieved_at=imported_at,
            block_reason=None,
            solicitations=(),
            secondary_candidates=(),
            malformed_reason=str(error),
        )


def load_manual_import(
    path: Path, *, retrieved_at: datetime | None = None
) -> ManateeProcurementBatch:
    """Read a local manual import file; this function has no network behavior."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        imported_at = retrieved_at or datetime.now(timezone.utc)
        return ManateeProcurementBatch(
            state=AcquisitionState.MALFORMED,
            response_state=None,
            access_mode="MANUAL_IMPORT",
            source_url=MANATEE_BIDS_URL,
            retrieved_at=imported_at,
            block_reason=None,
            solicitations=(),
            secondary_candidates=(),
            malformed_reason=f"cannot read import file: {error}",
        )
    return parse_manual_import(payload, retrieved_at=retrieved_at)


def deduplicate_solicitations(
    records: tuple[SolicitationImport, ...],
) -> DeduplicationSummary:
    """Deduplicate by agency plus solicitation ID; URLs only flag review matches."""

    canonical: list[SolicitationImport] = []
    identity_index: dict[str, int] = {}
    url_index: dict[tuple[str, str], list[int]] = {}
    possible: list[tuple[str, str]] = []
    removed = 0
    for record in records:
        agency = _identity_text(record.issuing_agency)
        solicitation_id = _identity_text(record.solicitation_id)
        identity = _dedup_identity_key(record) if agency and solicitation_id else None
        if identity is not None and identity in identity_index:
            index = identity_index[identity]
            canonical[index] = _merge_duplicate(canonical[index], record)
            removed += 1
            continue
        normalized_url = (
            _canonical_url(record.official_source_url)
            if record.official_source_url
            else None
        )
        if agency and normalized_url:
            for existing_index in url_index.get((agency, normalized_url), []):
                existing = canonical[existing_index]
                existing_id = _identity_text(existing.solicitation_id)
                if solicitation_id != existing_id:
                    possible.append(
                        (
                            _record_label(existing),
                            _record_label(record),
                        )
                    )
            url_index.setdefault((agency, normalized_url), []).append(len(canonical))
        if identity is not None:
            identity_index[identity] = len(canonical)
        canonical.append(record)
    return DeduplicationSummary(
        records=tuple(canonical),
        exact_duplicates_removed=removed,
        possible_url_matches=tuple(possible),
    )


def opportunity_for_import(record: SolicitationImport) -> Opportunity | None:
    """Adapt an official-source import to LIVE-003B's existing opportunity model."""

    source_url = record.official_source_url
    if source_url is None:
        primary = next(
            (
                item.url
                for item in record.evidence_references
                if item.kind is ReferenceKind.OFFICIAL_PRIMARY
            ),
            None,
        )
        source_url = primary
    if source_url is None:
        return None

    opportunity_id = _opportunity_id(record)
    status = _procurement_status(record.publication_status)
    evidence = _opportunity_evidence(record, opportunity_id, source_url)
    categories = record.service_categories or ()
    return Opportunity(
        opportunity_id=opportunity_id,
        title=record.title or "UNKNOWN",
        source_platform="Manatee County Procurement",
        demand_type=DemandType.PUBLIC_PROCUREMENT,
        publication_date=record.publication_date,
        discovered_at=record.retrieved_at,
        service_requested=categories[0] if categories else "UNKNOWN",
        summary=record.description or "UNKNOWN",
        source_url=source_url,
        source_event_ref=None,
        city=record.city,
        state=record.state,
        # The legacy contract uses a non-optional bool. The report retains UNKNOWN;
        # false here is a conservative adapter value, and provenance stays UNKNOWN.
        explicit_intent=record.buying_solicitation is True,
        is_open=_open_flag(record.publication_status),
        response_method=None,
        publicly_accessible=True,
        business_authorized=False,
        account_holder_authorized=False,
        permission_basis=PermissionBasis.NOT_APPROVED,
        source_terms_note=(
            "Manual import only; automated access and commercial-use permissions "
            "have not been independently verified."
        ),
        procurement_status=status,
        official_deadline=record.closing_date,
        eligibility_requirements=record.eligibility_requirements or (),
        expected_jobs_per_day=None,
        ongoing_need=False,
        limitations=record.operational_restrictions or (),
        evidence=evidence,
        stable_request_id=_stable_source_identity(record),
        procurement_scope=record.description,
        eligibility_reviewed=False,
        source_provenance=SourceProvenance.UNKNOWN,
    )


def deadline_disposition(
    closing_date: date | None,
    *,
    primary_source_verified: bool,
    as_of: date,
) -> str:
    """Never infer a valid or expired deadline from unverified imported claims."""

    if not primary_source_verified:
        return "UNVERIFIED" if closing_date is not None else "UNKNOWN"
    if closing_date is None:
        return "UNKNOWN"
    return "EXPIRED" if closing_date < as_of else "NOT_EXPIRED"


def _parse_record(
    payload: object, *, origin: RecordOrigin, at: datetime
) -> SolicitationImport:
    record = _mapping(payload, "solicitation")
    allowed = {
        "issuing_agency",
        "solicitation_id",
        "title",
        "description",
        "official_source_url",
        "publication_date",
        "closing_date",
        "closing_time_local",
        "closing_timezone",
        "location",
        "city",
        "state",
        "publication_status",
        "service_categories",
        "eligibility_requirements",
        "operational_restrictions",
        "buying_solicitation",
        "evidence_references",
    }
    _only_keys(record, allowed, "solicitation")
    agency = _optional_text(record.get("issuing_agency"))
    solicitation_id = _optional_text(record.get("solicitation_id"))
    title = _optional_text(record.get("title"))
    official_url = _optional_url(record.get("official_source_url"))
    if official_url and not _is_official_url(official_url):
        raise ValueError("official_source_url must use Manatee County or DemandStar")
    if not agency and not solicitation_id and not title and not official_url:
        raise ValueError("a solicitation requires an agency, identifier, title, or URL")
    references = tuple(
        _parse_reference(item)
        for item in _list(record.get("evidence_references", []), "evidence_references")
    )
    if official_url and not any(
        item.kind is ReferenceKind.OFFICIAL_PRIMARY
        and _canonical_url(item.url) == _canonical_url(official_url)
        for item in references
    ):
        references = (
            EvidenceReference(
                reference_id="official-record",
                kind=ReferenceKind.OFFICIAL_PRIMARY,
                url=official_url,
                label="Official solicitation record URL supplied for manual review",
                fields=(),
                excerpt=None,
            ),
            *references,
        )
    if origin is RecordOrigin.SECONDARY_DISCOVERY and not any(
        item.kind is ReferenceKind.SECONDARY for item in references
    ):
        raise ValueError(
            "secondary candidates require at least one secondary reference"
        )
    if origin is RecordOrigin.MANUAL_OFFICIAL_IMPORT and official_url is None:
        raise ValueError("official imports require official_source_url")
    if origin is RecordOrigin.MANUAL_OFFICIAL_IMPORT and not any(
        item.kind is ReferenceKind.OFFICIAL_PRIMARY for item in references
    ):
        raise ValueError("official imports require a primary source reference")

    categories = _optional_text_tuple(
        record.get("service_categories"), "service_categories"
    )
    eligibility = _optional_text_tuple(
        record.get("eligibility_requirements"), "eligibility_requirements"
    )
    restrictions = _optional_text_tuple(
        record.get("operational_restrictions"), "operational_restrictions"
    )
    buying = record.get("buying_solicitation")
    if buying is not None and type(buying) is not bool:
        raise ValueError("buying_solicitation must be true, false, or null")
    return SolicitationImport(
        origin=origin,
        issuing_agency=agency,
        solicitation_id=solicitation_id,
        title=title,
        description=_optional_text(record.get("description")),
        official_source_url=official_url,
        publication_date=_optional_date(
            record.get("publication_date"), "publication_date"
        ),
        closing_date=_optional_date(record.get("closing_date"), "closing_date"),
        closing_time_local=_optional_time(record.get("closing_time_local")),
        closing_timezone=_optional_text(record.get("closing_timezone")),
        location=_optional_text(record.get("location")),
        city=_optional_text(record.get("city")),
        state=_optional_text(record.get("state")),
        publication_status=_optional_text(record.get("publication_status")),
        service_categories=categories,
        eligibility_requirements=eligibility,
        operational_restrictions=restrictions,
        buying_solicitation=buying,
        evidence_references=references,
        retrieved_at=at.astimezone(timezone.utc),
    )


def _parse_reference(payload: object) -> EvidenceReference:
    reference = _mapping(payload, "evidence reference")
    _only_keys(
        reference,
        {"reference_id", "kind", "url", "label", "fields", "excerpt"},
        "evidence reference",
    )
    try:
        kind = ReferenceKind(
            _required_text(reference.get("kind"), "evidence reference.kind").upper()
        )
    except ValueError as error:
        raise ValueError(
            "evidence reference kind must be OFFICIAL_PRIMARY or SECONDARY"
        ) from error
    url = _required_text(reference.get("url"), "evidence reference.url")
    _validate_url(url)
    if kind is ReferenceKind.OFFICIAL_PRIMARY and not _is_official_url(url):
        raise ValueError(
            "official primary references must use Manatee County or DemandStar"
        )
    return EvidenceReference(
        reference_id=_required_text(reference.get("reference_id"), "reference_id"),
        kind=kind,
        url=url,
        label=_required_text(reference.get("label"), "evidence reference.label"),
        fields=_optional_text_tuple(reference.get("fields", []), "reference.fields")
        or (),
        excerpt=_optional_text(reference.get("excerpt")),
    )


def _opportunity_evidence(
    record: SolicitationImport, opportunity_id: str, source_url: str
) -> tuple[SourceEvidence, ...]:
    values: dict[str, str | bool | None] = {
        "source_url": source_url,
        "issuing_agency": record.issuing_agency,
        "solicitation_id": record.solicitation_id,
        "title": record.title,
        "description": record.description,
        "city": record.city,
        "state": record.state,
        "service_requested": (
            record.service_categories[0] if record.service_categories else None
        ),
        "explicit_intent": record.buying_solicitation,
        "publication_date": (
            record.publication_date.isoformat() if record.publication_date else None
        ),
        "open_status": _open_flag(record.publication_status),
        "procurement_status": (_procurement_status(record.publication_status).value),
    }
    result: list[SourceEvidence] = []
    for field_name, value in values.items():
        if value is None:
            continue
        matching_reference = next(
            (
                reference
                for reference in record.evidence_references
                if reference.kind is ReferenceKind.OFFICIAL_PRIMARY
                and (not reference.fields or field_name in reference.fields)
            ),
            None,
        )
        result.append(
            SourceEvidence(
                evidence_id=f"{opportunity_id}:{field_name}",
                kind=EvidenceKind.REPORTED,
                subject=opportunity_id,
                field=field_name,
                value=value,
                source_name="Manatee County Procurement",
                source_url=source_url,
                retrieved_at=None,
                excerpt=matching_reference.excerpt if matching_reference else None,
                confidence=None,
                owner_entity_id=opportunity_id,
            )
        )
    if not result:
        raise ValueError(
            "an imported opportunity must retain at least one evidence item"
        )
    return tuple(result)


def _procurement_status(value: str | None) -> ProcurementStatus:
    normalized = (value or "").strip().casefold()
    if normalized in {"open", "active", "open solicitation", "active solicitation"}:
        return ProcurementStatus.OPEN_SOLICITATION
    if normalized in {"closed", "closed solicitation"}:
        return ProcurementStatus.CLOSED_SOLICITATION
    if normalized in {"awarded", "award", "award notice"}:
        return ProcurementStatus.AWARD_NOTICE
    return ProcurementStatus.UNKNOWN_STATUS


def _open_flag(value: str | None) -> bool | None:
    status = _procurement_status(value)
    if status is ProcurementStatus.OPEN_SOLICITATION:
        return True
    if status in {
        ProcurementStatus.CLOSED_SOLICITATION,
        ProcurementStatus.AWARD_NOTICE,
    }:
        return False
    return None


def _opportunity_id(record: SolicitationImport) -> str:
    identity = _stable_source_identity(record)
    return "procurement:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


def _stable_source_identity(record: SolicitationImport) -> str:
    agency = _identity_text(record.issuing_agency) or "unknown-agency"
    solicitation_id = _identity_text(record.solicitation_id)
    if solicitation_id:
        return f"{agency}|{solicitation_id}"
    if record.official_source_url:
        return f"{agency}|url:{_canonical_url(record.official_source_url)}"
    return f"{agency}|title:{_identity_text(record.title) or 'unknown-title'}"


def _dedup_identity_key(record: SolicitationImport) -> str:
    """Prefer LIVE-003B's stable source identity; keep the same rule for URL-less rows."""

    opportunity = opportunity_for_import(record)
    if opportunity is not None:
        return duplicate_key(opportunity)
    identity = "stable:" + _stable_source_identity(record).casefold().strip()
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _merge_duplicate(
    canonical: SolicitationImport, duplicate: SolicitationImport
) -> SolicitationImport:
    conflicts = set(canonical.conflicting_fields) | set(duplicate.conflicting_fields)
    for name in (
        "title",
        "description",
        "official_source_url",
        "publication_date",
        "closing_date",
        "closing_time_local",
        "closing_timezone",
        "location",
        "city",
        "state",
        "publication_status",
        "service_categories",
        "eligibility_requirements",
        "operational_restrictions",
        "buying_solicitation",
    ):
        left = getattr(canonical, name)
        right = getattr(duplicate, name)
        if left is not None and right is not None and left != right:
            conflicts.add(name)
    references = list(canonical.evidence_references)
    seen = {_reference_identity(item) for item in references}
    for reference in duplicate.evidence_references:
        identity = _reference_identity(reference)
        if identity not in seen:
            references.append(reference)
            seen.add(identity)
    return replace(
        canonical,
        evidence_references=tuple(references),
        duplicate_count=canonical.duplicate_count + duplicate.duplicate_count + 1,
        conflicting_fields=tuple(sorted(conflicts)),
    )


def _reference_identity(reference: EvidenceReference) -> tuple[str, str, str]:
    return (
        reference.kind.value,
        _canonical_url(reference.url),
        reference.reference_id,
    )


def _record_label(record: SolicitationImport) -> str:
    return record.solicitation_id or record.title or "UNKNOWN"


def _identity_text(value: str | None) -> str:
    return " ".join(value.casefold().split()) if value else ""


def _canonical_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    hostname = (parsed.hostname or "").casefold().rstrip(".")
    if not parsed.scheme or not hostname:
        return value.strip()
    port = parsed.port
    netloc = (
        hostname
        if port is None or port == (443 if parsed.scheme == "https" else 80)
        else f"{hostname}:{port}"
    )
    query = urlencode(
        sorted(
            (key, item)
            for key, item in parse_qsl(parsed.query, keep_blank_values=True)
            if key.casefold() not in {"fbclid", "gclid"}
            and not key.casefold().startswith("utm_")
        )
    )
    path = re.sub(r"/{2,}", "/", parsed.path).rstrip("/") or "/"
    return urlunsplit((parsed.scheme.casefold(), netloc, path, query, ""))


def _is_official_url(value: str) -> bool:
    _validate_url(value)
    host = (urlsplit(value).hostname or "").casefold().rstrip(".")
    return any(host == root or host.endswith("." + root) for root in OFFICIAL_HOSTS)


def _validate_url(value: str) -> None:
    try:
        parsed = urlsplit(value)
        valid = (
            parsed.scheme in {"http", "https"}
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
        )
        _ = parsed.port
    except ValueError as error:
        raise ValueError("URL must be a valid absolute HTTP(S) URL") from error
    if not valid:
        raise ValueError("URL must be a valid absolute HTTP(S) URL without credentials")


def _optional_url(value: object) -> str | None:
    text = _optional_text(value)
    if text is None:
        return None
    _validate_url(text)
    return text


def _optional_date(value: object, field: str) -> date | None:
    text = _optional_text(value)
    if text is None:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError as error:
        raise ValueError(f"{field} must use YYYY-MM-DD or UNKNOWN") from error


def _optional_time(value: object) -> str | None:
    text = _optional_text(value)
    if text is None:
        return None
    try:
        parsed = time.fromisoformat(text)
    except ValueError as error:
        raise ValueError("closing_time_local must use HH:MM[:SS] or UNKNOWN") from error
    if parsed.tzinfo is not None:
        raise ValueError("closing_time_local must not include a timezone offset")
    return parsed.isoformat()


def _optional_text_tuple(value: object, field: str) -> tuple[str, ...] | None:
    if value is None or value == "UNKNOWN":
        return None
    if not isinstance(value, list | tuple):
        raise ValueError(f"{field} must be an array or UNKNOWN")
    result = tuple(_required_text(item, field) for item in value)
    return result or None


def _optional_text(value: object) -> str | None:
    if value is None or (isinstance(value, str) and value.strip().upper() == "UNKNOWN"):
        return None
    if not isinstance(value, str):
        raise ValueError("value must be text, null, or UNKNOWN")
    normalized = " ".join(value.split())
    return normalized or None


def _required_text(value: object, field: str) -> str:
    result = _optional_text(value)
    if result is None:
        raise ValueError(f"{field} is required")
    return result


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"{field} must be a JSON object")
    return value


def _list(value: object, field: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a JSON array")
    return value


def _only_keys(value: Mapping[str, object], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"{field} has unknown field(s): {', '.join(sorted(unknown))}")


__all__ = [
    "AcquisitionState",
    "DeduplicationSummary",
    "EvidenceReference",
    "MANATEE_BIDS_URL",
    "ManateeProcurementBatch",
    "RecordOrigin",
    "ReferenceKind",
    "SolicitationImport",
    "SourceResponseState",
    "deadline_disposition",
    "deduplicate_solicitations",
    "load_manual_import",
    "opportunity_for_import",
    "parse_manual_import",
]
