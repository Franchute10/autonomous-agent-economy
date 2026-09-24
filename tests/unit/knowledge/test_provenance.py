from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from aeos.core import (
    ApprovalDecisionId,
    ArtifactId,
    AuditEventId,
    DomainEventId,
    EconomicTransactionId,
    EvidenceId,
    GovernanceDecisionId,
    ProvenanceLinkId,
    ReservationId,
    ResourceId,
    RoleId,
    ActorKind,
    ActorRef,
    CorrelationId,
    IdempotencyKey,
    OrganizationId,
    TraceContext,
)
from aeos.knowledge.domain import (
    InvalidProvenanceLink,
    ProvenanceKind,
    ProvenanceLink,
    ProvenanceRef,
    ProvenanceRelation,
    ProvenanceSelfReference,
)


WHEN = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_provenance_link_is_directed_and_immutable() -> None:
    source = ProvenanceRef(ProvenanceKind.ARTIFACT, ArtifactId("artifact-a"))
    target = ProvenanceRef(ProvenanceKind.ARTIFACT, ArtifactId("artifact-b"))
    link = ProvenanceLink(
        ProvenanceLinkId("link-1"),
        source,
        target,
        ProvenanceRelation.DERIVED_FROM,
        WHEN,
    )
    assert link.source == source
    assert link.target == target
    assert link.relation is ProvenanceRelation.DERIVED_FROM
    with pytest.raises(FrozenInstanceError):
        link.relation = ProvenanceRelation.SUPPORTED_BY  # type: ignore[misc]


def test_provenance_link_rejects_self_reference_and_naive_time() -> None:
    ref = ProvenanceRef(ProvenanceKind.ARTIFACT, ArtifactId("artifact-a"))
    with pytest.raises(ProvenanceSelfReference):
        ProvenanceLink(
            ProvenanceLinkId("link-1"), ref, ref, ProvenanceRelation.DERIVED_FROM, WHEN
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        ProvenanceLink(
            ProvenanceLinkId("link-1"),
            ref,
            ProvenanceRef(ProvenanceKind.ARTIFACT, ArtifactId("artifact-b")),
            ProvenanceRelation.DERIVED_FROM,
            datetime(2026, 1, 1),
        )


def test_provenance_kind_must_match_typed_id() -> None:
    with pytest.raises(InvalidProvenanceLink):
        ProvenanceRef(ProvenanceKind.ARTIFACT, ProvenanceLinkId("wrong-id"))


@pytest.mark.parametrize(
    ("kind", "identifier"),
    [
        (ProvenanceKind.ARTIFACT, ArtifactId("artifact-1")),
        (ProvenanceKind.EVIDENCE, EvidenceId("evidence-1")),
        (ProvenanceKind.AUDIT_EVENT, AuditEventId("audit-1")),
        (ProvenanceKind.DOMAIN_FACT, DomainEventId("domain-event-1")),
        (ProvenanceKind.DOMAIN_FACT, GovernanceDecisionId("governance-1")),
        (ProvenanceKind.DOMAIN_FACT, ApprovalDecisionId("approval-1")),
        (ProvenanceKind.DOMAIN_FACT, EconomicTransactionId("transaction-1")),
        (ProvenanceKind.DOMAIN_FACT, ProvenanceLinkId("link-2")),
    ],
)
def test_provenance_ref_accepts_typed_endpoints(
    kind: ProvenanceKind, identifier: object
) -> None:
    assert ProvenanceRef(kind, identifier).identifier == identifier  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("kind", "identifier"),
    [
        (ProvenanceKind.ARTIFACT, EvidenceId("wrong-1")),
        (ProvenanceKind.EVIDENCE, ArtifactId("wrong-2")),
        (ProvenanceKind.AUDIT_EVENT, DomainEventId("wrong-3")),
        (ProvenanceKind.DOMAIN_FACT, ResourceId("resource-1")),
        (ProvenanceKind.DOMAIN_FACT, RoleId("role-1")),
        (ProvenanceKind.DOMAIN_FACT, ReservationId("reservation-1")),
        (ProvenanceKind.DOMAIN_FACT, AuditEventId("audit-2")),
    ],
)
def test_provenance_ref_rejects_wrong_endpoint_types(
    kind: ProvenanceKind, identifier: object
) -> None:
    with pytest.raises(InvalidProvenanceLink):
        ProvenanceRef(kind, identifier)  # type: ignore[arg-type]


def test_domain_fact_rejects_audit_event_id() -> None:
    with pytest.raises(InvalidProvenanceLink):
        ProvenanceRef(ProvenanceKind.DOMAIN_FACT, AuditEventId("audit-3"))


def test_provenance_ref_rejects_invalid_kind_and_is_immutable() -> None:
    with pytest.raises(InvalidProvenanceLink):
        ProvenanceRef(object(), ArtifactId("artifact-1"))  # type: ignore[arg-type]
    ref = ProvenanceRef(ProvenanceKind.ARTIFACT, ArtifactId("artifact-1"))
    with pytest.raises(FrozenInstanceError):
        ref.kind = ProvenanceKind.EVIDENCE  # type: ignore[misc]


@pytest.mark.parametrize(
    "relation", [ProvenanceRelation.DERIVED_FROM, ProvenanceRelation.SUPPORTED_BY]
)
def test_provenance_direction_is_source_to_target(relation: ProvenanceRelation) -> None:
    source = ProvenanceRef(ProvenanceKind.ARTIFACT, ArtifactId("artifact-source"))
    target = ProvenanceRef(ProvenanceKind.EVIDENCE, EvidenceId("evidence-target"))
    link = ProvenanceLink(
        ProvenanceLinkId("link-direction"), source, target, relation, WHEN
    )
    assert link.source == source
    assert link.target == target
    assert link.relation is relation


def test_provenance_link_rejects_invalid_field_types() -> None:
    source = ProvenanceRef(ProvenanceKind.ARTIFACT, ArtifactId("artifact-source"))
    target = ProvenanceRef(ProvenanceKind.EVIDENCE, EvidenceId("evidence-target"))
    with pytest.raises(InvalidProvenanceLink):
        ProvenanceLink(object(), source, target, ProvenanceRelation.DERIVED_FROM, WHEN)  # type: ignore[arg-type]
    with pytest.raises(InvalidProvenanceLink):
        ProvenanceLink(
            ProvenanceLinkId("link-3"),
            object(),  # type: ignore[arg-type]
            target,
            ProvenanceRelation.DERIVED_FROM,
            WHEN,
        )


def test_provenance_link_normalizes_time_and_accepts_context() -> None:
    source = ProvenanceRef(ProvenanceKind.ARTIFACT, ArtifactId("artifact-source-2"))
    target = ProvenanceRef(ProvenanceKind.EVIDENCE, EvidenceId("evidence-target-2"))
    trace = TraceContext(
        ActorRef(OrganizationId("actor-1"), ActorKind.SYSTEM),
        CorrelationId("corr-1"),
        IdempotencyKey("idem-1"),
    )
    link = ProvenanceLink(
        ProvenanceLinkId("link-context"),
        source,
        target,
        ProvenanceRelation.SUPPORTED_BY,
        datetime(2026, 1, 1, 3, tzinfo=timezone(timedelta(hours=3))),
        organization_id=OrganizationId("org-1"),
        trace_context=trace,
    )
    assert link.created_at == WHEN
    assert link.organization_id == OrganizationId("org-1")
    assert link.trace_context == trace
    with pytest.raises(InvalidProvenanceLink):
        ProvenanceLink(
            ProvenanceLinkId("link-target"),
            source,
            object(),  # type: ignore[arg-type]
            ProvenanceRelation.DERIVED_FROM,
            WHEN,
        )
    with pytest.raises(InvalidProvenanceLink):
        ProvenanceLink(
            ProvenanceLinkId("link-time"),
            source,
            target,
            ProvenanceRelation.DERIVED_FROM,
            object(),  # type: ignore[arg-type]
        )
    with pytest.raises(InvalidProvenanceLink):
        ProvenanceLink(ProvenanceLinkId("link-4"), source, target, object(), WHEN)  # type: ignore[arg-type]
    with pytest.raises(InvalidProvenanceLink):
        ProvenanceLink(
            ProvenanceLinkId("link-5"),
            source,
            target,
            ProvenanceRelation.DERIVED_FROM,
            WHEN,
            organization_id=object(),  # type: ignore[arg-type]
        )
    with pytest.raises(InvalidProvenanceLink):
        ProvenanceLink(
            ProvenanceLinkId("link-6"),
            source,
            target,
            ProvenanceRelation.DERIVED_FROM,
            WHEN,
            trace_context=object(),  # type: ignore[arg-type]
        )
