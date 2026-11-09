"""Offline local pipeline storage; multi-tenant callers use tenant_storage wrappers."""

from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
import tempfile
from typing import cast

from aeos.core.ids import OrganizationId
from aeos.live.domain.errors import InvalidLiveContract
from aeos.live.domain.opportunity_activation import (
    PipelineEvent,
    PipelineRecord,
    PipelineStatus,
)


class LocalOpportunityPipeline:
    """Persist current prospect state and an append-only event list in one file."""

    def __init__(
        self, path: str | Path, *, organization_id: OrganizationId | None = None
    ) -> None:
        self.path = Path(path)
        self.organization_id = organization_id

    def list_records(self) -> tuple[PipelineRecord, ...]:
        return tuple(self._read().values())

    def get(self, prospect_id: str) -> PipelineRecord | None:
        return self._read().get(prospect_id)

    def put(self, record: PipelineRecord) -> None:
        if not isinstance(record, PipelineRecord):
            raise TypeError("record must be a PipelineRecord")
        records = self._read()
        records[record.prospect_id] = record
        self._write(records)

    def ensure(self, record: PipelineRecord) -> PipelineRecord:
        existing = self.get(record.prospect_id)
        if existing is not None:
            return existing
        self.put(record)
        return record

    def _read(self) -> dict[str, PipelineRecord]:
        self._validate_tenant_path()
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise InvalidLiveContract(
                f"could not read activation pipeline: {error}"
            ) from error
        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            raise InvalidLiveContract("activation pipeline schema_version must be 1")
        stored_organization = payload.get("organization_id")
        if self.organization_id is None:
            if stored_organization is not None:
                raise InvalidLiveContract(
                    "tenant-scoped history requires a tenant-aware adapter"
                )
        elif stored_organization != self.organization_id.value:
            raise InvalidLiveContract("activation history tenant ownership mismatch")
        raw_records = payload.get("records")
        if not isinstance(raw_records, list):
            raise InvalidLiveContract("activation pipeline records must be an array")
        result: dict[str, PipelineRecord] = {}
        for raw in raw_records:
            if not isinstance(raw, dict):
                raise InvalidLiveContract("pipeline record must be an object")
            record = _record_from_dict(cast(dict[str, object], raw))
            if record.prospect_id in result:
                raise InvalidLiveContract("pipeline prospect IDs must be unique")
            result[record.prospect_id] = record
        return result

    def _write(self, records: dict[str, PipelineRecord]) -> None:
        self._validate_tenant_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, object] = {
            "schema_version": 1,
            "records": [
                _record_to_dict(item)
                for item in sorted(
                    records.values(), key=lambda value: value.organization
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
                prefix=".activation-pipeline-",
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
                    "tenant history paths cannot follow symbolic links"
                )
        except (OSError, RuntimeError) as error:
            raise InvalidLiveContract("tenant history path is invalid") from error


def _record_to_dict(record: PipelineRecord) -> dict[str, object]:
    payload = asdict(record)
    payload["status"] = record.status.value
    return payload


def _record_from_dict(payload: dict[str, object]) -> PipelineRecord:
    try:
        status = PipelineStatus(str(payload["status"]))
    except (KeyError, ValueError) as error:
        raise InvalidLiveContract("pipeline status is missing or invalid") from error
    raw_events = payload.get("events", [])
    if not isinstance(raw_events, list):
        raise InvalidLiveContract("pipeline events must be an array")
    events = tuple(
        _event_from_dict(cast(dict[str, object], item)) for item in raw_events
    )
    return PipelineRecord(
        prospect_id=_string(payload, "prospect_id"),
        organization=_string(payload, "organization"),
        market=_string(payload, "market"),
        status=status,
        source_evidence_ids=_string_tuple(payload, "source_evidence_ids"),
        contact_channel=_optional_string(payload.get("contact_channel")),
        last_action_date=_optional_date(payload.get("last_action_date")),
        next_action=_optional_string(payload.get("next_action")),
        follow_up_date=_optional_date(payload.get("follow_up_date")),
        owner_notes=_optional_string(payload.get("owner_notes")),
        outcome=_optional_string(payload.get("outcome")),
        events=events,
    )


def _event_from_dict(payload: dict[str, object]) -> PipelineEvent:
    return PipelineEvent(
        event_id=_string(payload, "event_id"),
        action=_string(payload, "action"),
        occurred_at=_string(payload, "occurred_at"),
        actor=_string(payload, "actor"),
        details=_string(payload, "details"),
        source_evidence_ids=_string_tuple(payload, "source_evidence_ids"),
    )


def _string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise InvalidLiveContract(f"{key} must be a non-blank string")
    return value.strip()


def _string_tuple(payload: dict[str, object], key: str) -> tuple[str, ...]:
    value = payload.get(key)
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise InvalidLiveContract(f"{key} must be an array of non-blank strings")
    return tuple(item.strip() for item in value)


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise InvalidLiveContract("optional string field has an invalid type")
    return value


def _optional_date(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise InvalidLiveContract("date field must be an ISO string or null")
    from datetime import date

    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as error:
        raise InvalidLiveContract("date field must be an ISO calendar date") from error
