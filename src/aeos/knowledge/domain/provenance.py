"""Immutable, directed provenance relations."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from aeos.core import (
    ArtifactId,
    ApprovalDecisionId,
    AuditEventId,
    DomainEventId,
    EconomicTransactionId,
    EvidenceId,
    GovernanceDecisionId,
    OrganizationId,
    ProvenanceLinkId,
    TraceContext,
    UtcTimestamp,
    normalize_utc,
)
from aeos.knowledge.domain.errors import InvalidProvenanceLink, ProvenanceSelfReference


DomainFactId = (
    DomainEventId
    | GovernanceDecisionId
    | ApprovalDecisionId
    | EconomicTransactionId
    | ProvenanceLinkId
)
_DOMAIN_FACT_ID_TYPES: tuple[type[object], ...] = (
    DomainEventId,
    GovernanceDecisionId,
    ApprovalDecisionId,
    EconomicTransactionId,
    ProvenanceLinkId,
)
_ARTIFACT_ID_TYPES: tuple[type[object], ...] = (ArtifactId,)
_EVIDENCE_ID_TYPES: tuple[type[object], ...] = (EvidenceId,)
_AUDIT_EVENT_ID_TYPES: tuple[type[object], ...] = (AuditEventId,)
ProvenanceIdentifier = ArtifactId | EvidenceId | AuditEventId | DomainFactId


class ProvenanceKind(StrEnum):
    ARTIFACT = "artifact"
    EVIDENCE = "evidence"
    AUDIT_EVENT = "audit_event"
    DOMAIN_FACT = "domain_fact"


class ProvenanceRelation(StrEnum):
    DERIVED_FROM = "derived_from"
    SUPPORTED_BY = "supported_by"


@dataclass(frozen=True, slots=True)
class ProvenanceRef:
    """Closed, minimal endpoint reference for a provenance relation."""

    kind: ProvenanceKind
    identifier: ProvenanceIdentifier

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ProvenanceKind):
            raise InvalidProvenanceLink("kind must be a ProvenanceKind")
        expected_types: tuple[type[object], ...]
        if self.kind is ProvenanceKind.ARTIFACT:
            expected_types = _ARTIFACT_ID_TYPES
        elif self.kind is ProvenanceKind.EVIDENCE:
            expected_types = _EVIDENCE_ID_TYPES
        elif self.kind is ProvenanceKind.AUDIT_EVENT:
            expected_types = _AUDIT_EVENT_ID_TYPES
        else:
            expected_types = _DOMAIN_FACT_ID_TYPES
        if not isinstance(self.identifier, expected_types):
            raise InvalidProvenanceLink("identifier does not match provenance kind")


@dataclass(frozen=True, slots=True)
class ProvenanceLink:
    """A directed source -> target fact: the target derives from the source."""

    provenance_link_id: ProvenanceLinkId
    source: ProvenanceRef
    target: ProvenanceRef
    relation: ProvenanceRelation
    created_at: UtcTimestamp
    organization_id: OrganizationId | None = None
    trace_context: TraceContext | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.provenance_link_id, ProvenanceLinkId):
            raise InvalidProvenanceLink("provenance_link_id must be a ProvenanceLinkId")
        if not isinstance(self.source, ProvenanceRef):
            raise InvalidProvenanceLink("source must be a ProvenanceRef")
        if not isinstance(self.target, ProvenanceRef):
            raise InvalidProvenanceLink("target must be a ProvenanceRef")
        if self.source == self.target:
            raise ProvenanceSelfReference()
        if not isinstance(self.relation, ProvenanceRelation):
            raise InvalidProvenanceLink("relation must be a ProvenanceRelation")
        if not isinstance(self.created_at, datetime):
            raise InvalidProvenanceLink("created_at must be a datetime")
        if self.organization_id is not None and not isinstance(
            self.organization_id, OrganizationId
        ):
            raise InvalidProvenanceLink("organization_id must be an OrganizationId")
        if self.trace_context is not None and not isinstance(
            self.trace_context, TraceContext
        ):
            raise InvalidProvenanceLink("trace_context must be a TraceContext or None")
        object.__setattr__(self, "created_at", normalize_utc(self.created_at))
