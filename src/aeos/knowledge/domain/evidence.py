"""Immutable support claims over explicit domain sources."""

from dataclasses import dataclass
from datetime import datetime

from aeos.core import (
    ArtifactId,
    EvidenceId,
    ApprovalDecisionId,
    AuditEventId,
    DomainEventId,
    EconomicTransactionId,
    GovernanceDecisionId,
    ProvenanceLinkId,
    OrganizationId,
    TraceContext,
    UtcTimestamp,
    normalize_utc,
)
from aeos.knowledge.domain.errors import EvidenceWithoutSource, InvalidEvidence


FactId = (
    DomainEventId
    | GovernanceDecisionId
    | ApprovalDecisionId
    | EconomicTransactionId
    | AuditEventId
    | ProvenanceLinkId
)
_FACT_ID_TYPES: tuple[type[object], ...] = (
    DomainEventId,
    GovernanceDecisionId,
    ApprovalDecisionId,
    EconomicTransactionId,
    AuditEventId,
    ProvenanceLinkId,
)


@dataclass(frozen=True, slots=True)
class FactRef:
    """A typed reference to an already existing material fact."""

    fact_id: FactId

    def __post_init__(self) -> None:
        if not isinstance(self.fact_id, _FACT_ID_TYPES):
            raise InvalidEvidence("fact_id is not an approved material fact ID")


@dataclass(frozen=True, slots=True)
class Evidence:
    """An immutable claim supported by one or more explicit sources."""

    evidence_id: EvidenceId
    statement: str
    created_at: UtcTimestamp
    artifact_ids: tuple[ArtifactId, ...] = ()
    fact_refs: tuple[FactRef, ...] = ()
    organization_id: OrganizationId | None = None
    trace_context: TraceContext | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.evidence_id, EvidenceId):
            raise InvalidEvidence("evidence_id must be an EvidenceId")
        if not isinstance(self.statement, str) or not self.statement.strip():
            raise InvalidEvidence("statement must be a non-blank string")
        if not isinstance(self.artifact_ids, tuple) or any(
            not isinstance(value, ArtifactId) for value in self.artifact_ids
        ):
            raise InvalidEvidence("artifact_ids must be a tuple of ArtifactId values")
        if len(set(self.artifact_ids)) != len(self.artifact_ids):
            raise InvalidEvidence("artifact_ids must not contain duplicates")
        if not isinstance(self.fact_refs, tuple) or any(
            not isinstance(value, FactRef) for value in self.fact_refs
        ):
            raise InvalidEvidence("fact_refs must be a tuple of FactRef values")
        if len(set(self.fact_refs)) != len(self.fact_refs):
            raise InvalidEvidence("fact_refs must not contain duplicates")
        if not self.artifact_ids and not self.fact_refs:
            raise EvidenceWithoutSource()
        if self.organization_id is not None and not isinstance(
            self.organization_id, OrganizationId
        ):
            raise InvalidEvidence("organization_id must be an OrganizationId")
        if not isinstance(self.created_at, datetime):
            raise InvalidEvidence("created_at must be a datetime")
        object.__setattr__(self, "created_at", normalize_utc(self.created_at))
        if self.trace_context is not None and not isinstance(
            self.trace_context, TraceContext
        ):
            raise InvalidEvidence("trace_context must be a TraceContext or None")
        object.__setattr__(self, "statement", self.statement.strip())
