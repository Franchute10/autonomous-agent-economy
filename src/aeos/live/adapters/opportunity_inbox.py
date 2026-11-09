"""Offline local inbox storage; multi-tenant callers use tenant_storage wrappers."""

from __future__ import annotations

from dataclasses import fields, is_dataclass, replace
from datetime import date, datetime, timezone
from enum import StrEnum
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import cast

from aeos.application.live.opportunity_inbox import (
    flag_possible_duplicate,
    import_record,
    link_duplicate_source,
)
from aeos.live.domain.errors import InvalidLiveContract
from aeos.live.domain.evidence import EvidenceKind, SourceEvidence
from aeos.live.domain.opportunity_inbox import (
    DemandType,
    DuplicateMatchType,
    Opportunity,
    OpportunityEvent,
    OpportunityEventAction,
    OpportunityRecord,
    OpportunityStatus,
    PermissionBasis,
    ProcurementStatus,
    SourceProvenance,
    SourceState,
    duplicate_match_evidence,
    history_issues,
    possible_duplicate_candidate,
    validate_persistent_import,
    validate_record_mutation,
)
from aeos.core.ids import OrganizationId
from aeos.tenancy.domain import TenantContext


def _attest_persistent_import(
    record: OpportunityRecord,
    *,
    operator_context: TenantContext | None,
    attested_evidence_ids: tuple[str, ...],
    organization_id: OrganizationId | None,
) -> OpportunityRecord:
    """Bind declared source evidence to an active tenant-owner attestation."""

    if not isinstance(operator_context, TenantContext):
        raise InvalidLiveContract(
            "persistent imports require an authenticated tenant operator attestation"
        )
    actor = operator_context.require_owner_actor()
    if (
        organization_id is not None
        and operator_context.organization_id != organization_id
    ):
        raise InvalidLiveContract("source attestation belongs to another tenant")
    opportunity = record.opportunity
    if opportunity.source_provenance is SourceProvenance.SYNTHETIC:
        raise InvalidLiveContract(
            "Synthetic records are restricted to isolated previews and tests"
        )
    all_ids = {item.evidence_id for item in opportunity.evidence}
    observed_ids = {
        item.evidence_id
        for item in opportunity.evidence
        if item.kind is EvidenceKind.OBSERVED
    }
    requested = set(attested_evidence_ids)
    if not requested or not requested <= observed_ids or not requested <= all_ids:
        raise InvalidLiveContract(
            "operator attestation must identify source evidence marked OBSERVED"
        )
    attested_at = datetime.now(timezone.utc)
    evidence = tuple(
        replace(
            item,
            kind=EvidenceKind.OBSERVED
            if item.evidence_id in requested
            else EvidenceKind.REPORTED,
            retrieved_at=attested_at if item.evidence_id in requested else None,
        )
        if item.kind is EvidenceKind.OBSERVED
        else replace(item, retrieved_at=None)
        for item in opportunity.evidence
    )
    attested_opportunity = replace(
        opportunity,
        source_provenance=SourceProvenance.REAL,
        evidence=evidence,
    )
    attested_event = replace(
        record.events[0],
        actor=actor,
        note="Authenticated tenant owner attested source authenticity and selected observations.",
        occurred_at=attested_at,
    )
    return replace(
        record,
        opportunity=attested_opportunity,
        events=(attested_event, *record.events[1:]),
    )


class LocalOpportunityInbox:
    """Persist the current inbox and its append-only manual action history."""

    def __init__(
        self, path: str | Path, *, organization_id: OrganizationId | None = None
    ) -> None:
        self.path = Path(path)
        self.organization_id = organization_id

    def list_records(self) -> tuple[OpportunityRecord, ...]:
        return tuple(self._read().values())

    def get(self, opportunity_id: str) -> OpportunityRecord | None:
        return self._read().get(opportunity_id)

    def find_duplicate(self, record: OpportunityRecord) -> OpportunityRecord | None:
        key = _record_key(record)
        return next(
            (
                item
                for item in self._read().values()
                if item.status is not OpportunityStatus.DUPLICATE
                and _record_key(item) == key
            ),
            None,
        )

    def add(
        self,
        record: OpportunityRecord,
        *,
        operator_context: TenantContext | None = None,
        attested_evidence_ids: tuple[str, ...] = (),
    ) -> tuple[OpportunityRecord, bool]:
        if not isinstance(record, OpportunityRecord):
            raise TypeError("record must be an OpportunityRecord")
        if (
            record.status is not OpportunityStatus.DISCOVERED
            or len(record.events) != 1
            or record.events[0].action is not OpportunityEventAction.IMPORTED
            or record.events[0].scope_id != record.opportunity.opportunity_id
        ):
            raise InvalidLiveContract(
                "new opportunities must enter through the DISCOVERED import path"
            )
        record = _attest_persistent_import(
            record,
            operator_context=operator_context,
            attested_evidence_ids=attested_evidence_ids,
            organization_id=self.organization_id,
        )
        validate_persistent_import(record.opportunity)
        records = self._read()
        existing = records.get(record.opportunity.opportunity_id)
        if existing is not None:
            if existing == record:
                return existing, False
            if _same_source_observation(record, existing):
                canonical = (
                    records.get(existing.duplicate_of, existing)
                    if existing.status is OpportunityStatus.DUPLICATE
                    and existing.duplicate_of is not None
                    else existing
                )
                return canonical, False
            raise InvalidLiveContract(
                "opportunity ID already belongs to another source"
            )

        matches: dict[
            str, tuple[OpportunityRecord, OpportunityRecord, DuplicateMatchType, str]
        ] = {}
        possible: dict[str, OpportunityRecord] = {}
        for stored in records.values():
            canonical = (
                records.get(stored.duplicate_of, stored)
                if stored.status is OpportunityStatus.DUPLICATE
                and stored.duplicate_of is not None
                else stored
            )
            if canonical.status is OpportunityStatus.DUPLICATE:
                continue
            relation, evidence = duplicate_match_evidence(
                record.opportunity, stored.opportunity
            )
            canonical_id = canonical.opportunity.opportunity_id
            if relation is not None:
                matches[canonical_id] = (canonical, stored, relation, evidence)
            elif possible_duplicate_candidate(record.opportunity, stored.opportunity):
                possible[canonical_id] = canonical

        exact = [
            item for item in matches.values() if item[2] is DuplicateMatchType.EXACT
        ]
        strong = [
            item for item in matches.values() if item[2] is DuplicateMatchType.STRONG
        ]
        selected = exact if exact else strong
        can_auto_link = len(exact) == 1 or (
            not exact and len(strong) == 1 and not possible
        )
        if can_auto_link:
            canonical, matched, relation, evidence = selected[0]
            if _same_source_observation(record, matched):
                return canonical, False
            linked_canonical, linked_source = link_duplicate_source(
                canonical,
                record,
                match_type=relation,
                actor="AEOS duplicate matcher",
                note=evidence,
                occurred_at=record.opportunity.discovered_at,
            )
            records[canonical.opportunity.opportunity_id] = linked_canonical
            records[record.opportunity.opportunity_id] = linked_source
            self._write(records)
            return linked_canonical, False

        if selected or possible:
            related = dict(possible)
            related.update(
                {
                    item[0].opportunity.opportunity_id: item[0]
                    for item in (selected or matches.values())
                }
            )
            incoming = record
            for canonical in related.values():
                _, evidence = duplicate_match_evidence(
                    incoming.opportunity, canonical.opportunity
                )
                reason = evidence or (
                    "POSSIBLE_DUPLICATE: varias coincidencias requieren revisión humana."
                )
                incoming = flag_possible_duplicate(
                    incoming,
                    canonical.opportunity.opportunity_id,
                    actor="AEOS duplicate matcher",
                    note=reason,
                    occurred_at=record.opportunity.discovered_at,
                )
                updated = flag_possible_duplicate(
                    canonical,
                    incoming.opportunity.opportunity_id,
                    actor="AEOS duplicate matcher",
                    note=reason,
                    occurred_at=record.opportunity.discovered_at,
                )
                records[canonical.opportunity.opportunity_id] = updated
            records[record.opportunity.opportunity_id] = incoming
            self._write(records)
            return incoming, True

        records[record.opportunity.opportunity_id] = record
        self._write(records)
        return record, True

    def put(self, record: OpportunityRecord) -> None:
        if not isinstance(record, OpportunityRecord):
            raise TypeError("record must be an OpportunityRecord")
        self.put_many((record,))

    def put_many(self, updated_records: tuple[OpportunityRecord, ...]) -> None:
        if not updated_records or any(
            not isinstance(record, OpportunityRecord) for record in updated_records
        ):
            raise TypeError("put_many requires one or more OpportunityRecord values")
        if len(
            {record.opportunity.opportunity_id for record in updated_records}
        ) != len(updated_records):
            raise InvalidLiveContract("put_many cannot update an opportunity twice")
        records = self._read()
        for updated in updated_records:
            opportunity_id = updated.opportunity.opportunity_id
            previous = records.get(opportunity_id)
            if previous is None:
                raise InvalidLiveContract("opportunity ID was not found")
            if updated == previous:
                continue
            validate_record_mutation(previous, updated)
        for updated in updated_records:
            records[updated.opportunity.opportunity_id] = updated
        self._write(records)

    def audit_history(self) -> dict[str, tuple[str, ...]]:
        return {
            record.opportunity.opportunity_id: issues
            for record in self._read().values()
            if (issues := history_issues(record))
        }

    def _read(self) -> dict[str, OpportunityRecord]:
        self._validate_tenant_path()
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise InvalidLiveContract(
                f"could not read opportunity inbox: {error}"
            ) from error
        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            raise InvalidLiveContract("opportunity inbox schema_version must be 1")
        stored_organization = payload.get("organization_id")
        if self.organization_id is None:
            if stored_organization is not None:
                raise InvalidLiveContract(
                    "tenant-scoped inbox requires a tenant-aware adapter"
                )
        elif stored_organization != self.organization_id.value:
            raise InvalidLiveContract("opportunity inbox tenant ownership mismatch")
        raw_records = payload.get("records")
        if not isinstance(raw_records, list):
            raise InvalidLiveContract("opportunity inbox records must be an array")
        result: dict[str, OpportunityRecord] = {}
        for raw in raw_records:
            if not isinstance(raw, dict):
                raise InvalidLiveContract("opportunity record must be an object")
            record = _record_from_dict(cast(dict[str, object], raw))
            opportunity_id = record.opportunity.opportunity_id
            if opportunity_id in result:
                raise InvalidLiveContract("opportunity IDs must be unique")
            result[opportunity_id] = record
        return result

    def _write(self, records: dict[str, OpportunityRecord]) -> None:
        self._validate_tenant_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, object] = {
            "schema_version": 1,
            "records": [
                _jsonable(item)
                for item in sorted(
                    records.values(),
                    key=lambda value: value.opportunity.title.casefold(),
                )
            ],
        }
        if self.organization_id is not None:
            payload["organization_id"] = self.organization_id.value
        temporary_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                dir=self.path.parent,
                prefix=".opportunity-inbox-",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_path = temporary.name
                json.dump(payload, temporary, ensure_ascii=False, indent=2)
                temporary.write("\n")
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, self.path)
        finally:
            if temporary_path is not None and os.path.exists(temporary_path):
                os.unlink(temporary_path)

    def _validate_tenant_path(self) -> None:
        if self.organization_id is None:
            return
        try:
            if self.path.resolve(strict=False) != self.path:
                raise InvalidLiveContract(
                    "tenant inbox paths cannot follow symbolic links"
                )
        except (OSError, RuntimeError) as error:
            raise InvalidLiveContract("tenant inbox path is invalid") from error


def thumbtack_source_state(
    *, provider_configured: bool, provider_available: bool | None = None
) -> SourceState:
    """Represent source readiness without asserting a live integration exists."""

    if not provider_configured:
        return SourceState.PROVIDER_NOT_CONFIGURED
    if provider_available is False:
        return SourceState.PROVIDER_UNAVAILABLE
    return SourceState.FIXTURE_ONLY


def ingest_thumbtack_event(
    payload: dict[str, object],
    *,
    authorized_business_id: str | None,
    account_holder_authorized: bool,
    received_at: datetime,
) -> tuple[SourceState, OpportunityRecord | None]:
    """Map one synthetic event to the manual inbox contract; never opens a receiver."""

    if authorized_business_id is None:
        return thumbtack_source_state(provider_configured=False), None
    if not authorized_business_id.strip():
        return thumbtack_source_state(provider_configured=False), None
    if not account_holder_authorized:
        raise InvalidLiveContract(
            "Thumbtack ingestion requires account-holder authorization"
        )
    if received_at.tzinfo is None:
        raise InvalidLiveContract("received_at must be timezone-aware")
    if payload.get("eventType") != "NegotiationCreatedV4":
        raise InvalidLiveContract("unsupported Thumbtack event type")
    negotiation_id = _required_text(payload, "negotiationID")
    business_id = _required_text(payload, "businessID")
    if business_id != authorized_business_id:
        raise InvalidLiveContract(
            "event business does not match the authorized account"
        )
    created_at = _required_text(payload, "createTime")
    created = _parse_datetime(created_at)
    category = payload.get("category")
    if isinstance(category, dict):
        service = _required_text(cast(dict[str, object], category), "name")
    elif isinstance(category, str) and category.strip():
        service = category.strip()
    else:
        raise InvalidLiveContract("Thumbtack event must include a service category")
    customer = payload.get("customer")
    location: dict[str, object] = {}
    if isinstance(customer, dict):
        raw_location = cast(dict[str, object], customer).get("location")
        if isinstance(raw_location, dict):
            location = cast(dict[str, object], raw_location)
    city = location.get("city")
    state = location.get("state")
    if not isinstance(city, str) or not city.strip():
        city = None
    if not isinstance(state, str) or not state.strip():
        state = None
    digest = hashlib.sha256(negotiation_id.encode("utf-8")).hexdigest()[:20]
    opportunity_id = f"thumbtack-{digest}"
    # Description, customer name, contact data, attachments, and messages are
    # intentionally discarded. Only the minimum allowlisted lead attributes remain.
    evidence: list[dict[str, object]] = [
        {"field": "source_event_ref", "value": negotiation_id, "kind": "OBSERVED"},
        {"field": "service_requested", "value": service, "kind": "OBSERVED"},
        {"field": "explicit_intent", "value": True, "kind": "OBSERVED"},
        {
            "field": "response_method",
            "value": "Thumbtack Pro account",
            "kind": "OBSERVED",
        },
    ]
    if city:
        evidence.append({"field": "city", "value": city, "kind": "OBSERVED"})
    if state:
        evidence.append({"field": "state", "value": state, "kind": "OBSERVED"})
    evidence.append(
        {
            "field": "publication_date",
            "value": created.date().isoformat(),
            "kind": "OBSERVED",
        }
    )
    for evidence_item in evidence:
        evidence_item["confidence"] = 0.95
    mapping: dict[str, object] = {
        "opportunity_id": opportunity_id,
        "title": f"Lead privado de Thumbtack: {service}",
        "source_platform": "Thumbtack Pro",
        "demand_type": DemandType.MARKETPLACE_LEAD.value,
        "publication_date": created.date().isoformat(),
        "discovered_at": received_at.isoformat(),
        "service_requested": service,
        "summary": "El titular revisa los detalles dentro de la cuenta de Thumbtack.",
        "source_url": None,
        "source_event_ref": negotiation_id,
        "city": city,
        "state": state,
        "explicit_intent": True,
        "is_open": None,
        "response_method": "Responder dentro de la cuenta Pro de Thumbtack",
        "publicly_accessible": False,
        "business_authorized": True,
        "account_holder_authorized": True,
        "source_provenance": SourceProvenance.SYNTHETIC.value,
        "permission_basis": PermissionBasis.AUTHORIZED_ACCOUNT.value,
        "source_terms_note": "Solo cuenta propia autorizada; evento webhook no firmado; contrato offline sintético.",
        "procurement_status": None,
        "official_deadline": None,
        "eligibility_requirements": [],
        "expected_jobs_per_day": None,
        "ongoing_need": False,
        "limitations": [
            "Contrato sintético offline; sin endpoint conectado.",
            "El estado abierto requiere confirmación manual.",
        ],
        "evidence": evidence,
    }
    record = import_record(mapping, imported_at=received_at)
    return SourceState.FIXTURE_ONLY, record


def _record_key(record: OpportunityRecord) -> str:
    from aeos.live.domain.opportunity_inbox import duplicate_key

    return duplicate_key(record.opportunity)


def _jsonable(value: object) -> object:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: _jsonable(getattr(value, item.name)) for item in fields(value)
        }
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def _record_from_dict(payload: dict[str, object]) -> OpportunityRecord:
    try:
        raw_opportunity = cast(dict[str, object], payload["opportunity"])
        evidence_raw = cast(list[dict[str, object]], raw_opportunity["evidence"])
        evidence = tuple(
            SourceEvidence(
                evidence_id=str(item["evidence_id"]),
                kind=EvidenceKind(str(item["kind"])),
                subject=str(item["subject"]),
                field=str(item["field"]),
                value=cast(str | int | float | bool | None, item.get("value")),
                source_name=str(item["source_name"]),
                source_url=_as_optional_str(item.get("source_url")),
                retrieved_at=_parse_optional_datetime(
                    _as_optional_str(item.get("retrieved_at"))
                ),
                excerpt=_as_optional_str(item.get("excerpt")),
                confidence=_as_optional_float(item.get("confidence")),
                assumptions=tuple(cast(list[str], item.get("assumptions", []))),
                owner_entity_id=_as_optional_str(item.get("owner_entity_id")),
            )
            for item in evidence_raw
        )
        opportunity = Opportunity(
            opportunity_id=str(raw_opportunity["opportunity_id"]),
            title=str(raw_opportunity["title"]),
            source_platform=str(raw_opportunity["source_platform"]),
            demand_type=DemandType(str(raw_opportunity["demand_type"])),
            publication_date=_as_date(raw_opportunity.get("publication_date")),
            discovered_at=_parse_datetime(str(raw_opportunity["discovered_at"])),
            service_requested=str(raw_opportunity["service_requested"]),
            summary=str(raw_opportunity["summary"]),
            source_url=_as_optional_str(raw_opportunity.get("source_url")),
            source_event_ref=_as_optional_str(raw_opportunity.get("source_event_ref")),
            city=_as_optional_str(raw_opportunity.get("city")),
            state=_as_optional_str(raw_opportunity.get("state")),
            explicit_intent=bool(raw_opportunity["explicit_intent"]),
            is_open=_as_optional_bool(raw_opportunity.get("is_open")),
            response_method=_as_optional_str(raw_opportunity.get("response_method")),
            publicly_accessible=bool(raw_opportunity["publicly_accessible"]),
            business_authorized=bool(raw_opportunity["business_authorized"]),
            account_holder_authorized=bool(
                raw_opportunity["account_holder_authorized"]
            ),
            permission_basis=PermissionBasis(str(raw_opportunity["permission_basis"])),
            source_terms_note=str(raw_opportunity["source_terms_note"]),
            procurement_status=(
                _procurement(raw_opportunity.get("procurement_status"))
            ),
            official_deadline=_as_date(raw_opportunity.get("official_deadline")),
            eligibility_requirements=tuple(
                cast(list[str], raw_opportunity.get("eligibility_requirements", []))
            ),
            expected_jobs_per_day=_as_optional_int(
                raw_opportunity.get("expected_jobs_per_day")
            ),
            ongoing_need=bool(raw_opportunity["ongoing_need"]),
            limitations=tuple(cast(list[str], raw_opportunity.get("limitations", []))),
            evidence=evidence,
            stable_request_id=_as_optional_str(
                raw_opportunity.get("stable_request_id")
            ),
            procurement_scope=_as_optional_str(
                raw_opportunity.get("procurement_scope")
            ),
            eligibility_reviewed=_as_bool(
                raw_opportunity.get("eligibility_reviewed", False),
                "eligibility_reviewed",
            ),
            source_provenance=SourceProvenance(
                str(raw_opportunity.get("source_provenance", "UNKNOWN"))
            ),
        )
        raw_events = cast(list[dict[str, object]], payload.get("events", []))
        events = tuple(
            OpportunityEvent(
                event_id=str(item["event_id"]),
                action=OpportunityEventAction(str(item["action"])),
                actor=str(item["actor"]),
                note=str(item["note"]),
                occurred_at=_parse_datetime(str(item["occurred_at"])),
                scope_id=_as_optional_str(item.get("scope_id")),
                related_event_id=_as_optional_str(item.get("related_event_id")),
                from_status=_optional_status(item.get("from_status")),
                to_status=_optional_status(item.get("to_status")),
            )
            for item in raw_events
        )
        return OpportunityRecord(
            opportunity=opportunity,
            status=OpportunityStatus(str(payload["status"])),
            events=events,
            next_action=_as_optional_str(payload.get("next_action")),
            follow_up_date=_as_date(payload.get("follow_up_date")),
            duplicate_of=_as_optional_str(payload.get("duplicate_of")),
            duplicate_match=(
                DuplicateMatchType(str(payload["duplicate_match"]))
                if payload.get("duplicate_match") is not None
                else None
            ),
            duplicate_source_ids=tuple(
                cast(list[str], payload.get("duplicate_source_ids", []))
            ),
            possible_duplicate_ids=tuple(
                cast(list[str], payload.get("possible_duplicate_ids", []))
            ),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise InvalidLiveContract(
            f"invalid stored opportunity record: {error}"
        ) from error


def _required_text(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise InvalidLiveContract(f"Thumbtack event {key} is required")
    return value.strip()


def _parse_datetime(value: str | None) -> datetime:
    if value is None:
        raise InvalidLiveContract("stored event timestamp is missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise InvalidLiveContract("timestamp must be ISO-8601") from error
    if parsed.tzinfo is None:
        raise InvalidLiveContract("timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def _parse_optional_datetime(value: str | None) -> datetime | None:
    return _parse_datetime(value) if value is not None else None


def _as_date(value: object) -> date | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise InvalidLiveContract("stored date must be a string")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise InvalidLiveContract("stored date must be YYYY-MM-DD") from error


def _as_optional_str(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise InvalidLiveContract("stored optional string has invalid type")
    return value


def _as_optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidLiveContract("stored confidence must be numeric")
    return float(value)


def _as_optional_bool(value: object) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise InvalidLiveContract("stored open status must be boolean")
    return value


def _as_optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidLiveContract("stored capacity must be an integer")
    return value


def _as_bool(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise InvalidLiveContract(f"stored {field} must be boolean")
    return value


def _optional_status(value: object) -> OpportunityStatus | None:
    return OpportunityStatus(str(value)) if value is not None else None


def _procurement(value: object) -> ProcurementStatus | None:
    return ProcurementStatus(str(value)) if value is not None else None


def _same_source_observation(
    incoming: OpportunityRecord, stored: OpportunityRecord
) -> bool:
    left = incoming.opportunity
    right = stored.opportunity
    return (
        left.source_url == right.source_url
        and left.source_event_ref == right.source_event_ref
        and left.stable_request_id == right.stable_request_id
        and left.source_platform.casefold() == right.source_platform.casefold()
        and left.title.casefold() == right.title.casefold()
        and left.summary.casefold() == right.summary.casefold()
        and left.publication_date == right.publication_date
        and tuple(
            (
                evidence.field,
                evidence.value,
                evidence.kind,
                evidence.confidence,
                evidence.source_name,
            )
            for evidence in left.evidence
        )
        == tuple(
            (
                evidence.field,
                evidence.value,
                evidence.kind,
                evidence.confidence,
                evidence.source_name,
            )
            for evidence in right.evidence
        )
    )
