"""Immutable append-only audit facts."""

from dataclasses import dataclass
from datetime import datetime
import re

from aeos.core import (
    ArtifactId,
    ApprovalDecisionId,
    AuditEventId,
    EconomicTransactionId,
    EvidenceId,
    GovernanceDecisionId,
    OrganizationId,
    TraceContext,
    UtcTimestamp,
    normalize_utc,
)
from aeos.knowledge.domain.errors import InvalidAuditEvent, InvalidAuditSubject


AuditSubjectId = (
    ArtifactId
    | AuditEventId
    | EconomicTransactionId
    | GovernanceDecisionId
    | ApprovalDecisionId
)
_AUDIT_SUBJECT_ID_TYPES: tuple[type[object], ...] = (
    ArtifactId,
    AuditEventId,
    EconomicTransactionId,
    GovernanceDecisionId,
    ApprovalDecisionId,
)
_CANONICAL_EVENT_TYPE = re.compile(
    r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*(?:\.[a-z][a-z0-9]*(?:_[a-z0-9]+)*)+$"
)


@dataclass(frozen=True, slots=True)
class AuditSubjectRef:
    """Small stable reference to the material subject of an audit fact."""

    subject_id: AuditSubjectId

    def __post_init__(self) -> None:
        if not isinstance(self.subject_id, _AUDIT_SUBJECT_ID_TYPES):
            raise InvalidAuditSubject("subject_id is not an approved audit subject ID")


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """An immutable material historical fact; corrections are new facts."""

    audit_event_id: AuditEventId
    event_type: str
    subject: AuditSubjectRef
    occurred_at: UtcTimestamp
    trace_context: TraceContext
    organization_id: OrganizationId | None = None
    artifact_ids: tuple[ArtifactId, ...] = ()
    evidence_ids: tuple[EvidenceId, ...] = ()
    description: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.audit_event_id, AuditEventId):
            raise InvalidAuditEvent("audit_event_id must be an AuditEventId")
        if not isinstance(self.event_type, str):
            raise InvalidAuditEvent("event_type must be a string")
        if not self.event_type.strip():
            raise InvalidAuditEvent("event_type must be a non-blank string")
        if not _CANONICAL_EVENT_TYPE.fullmatch(self.event_type):
            raise InvalidAuditEvent(
                "event_type must use canonical dot-separated symbolic syntax"
            )
        if not isinstance(self.subject, AuditSubjectRef):
            raise InvalidAuditEvent("subject must be an AuditSubjectRef")
        if not isinstance(self.occurred_at, datetime):
            raise InvalidAuditEvent("occurred_at must be a datetime")
        if not isinstance(self.trace_context, TraceContext):
            raise InvalidAuditEvent("trace_context must be a TraceContext")
        if self.organization_id is not None and not isinstance(
            self.organization_id, OrganizationId
        ):
            raise InvalidAuditEvent("organization_id must be an OrganizationId")
        object.__setattr__(self, "event_type", self.event_type.strip())
        object.__setattr__(self, "occurred_at", normalize_utc(self.occurred_at))
        _validate_ids(self.artifact_ids, ArtifactId, "artifact_ids")
        _validate_ids(self.evidence_ids, EvidenceId, "evidence_ids")
        if self.description is not None and not isinstance(self.description, str):
            raise InvalidAuditEvent("description must be a string or None")


def _validate_ids(
    values: tuple[object, ...], expected: type[object], name: str
) -> None:
    if not isinstance(values, tuple):
        raise InvalidAuditEvent(f"{name} must be an immutable tuple")
    if any(not isinstance(value, expected) for value in values):
        raise InvalidAuditEvent(f"{name} must contain only {expected.__name__} values")
    if len(set(values)) != len(values):
        raise InvalidAuditEvent(f"{name} must not contain duplicates")
