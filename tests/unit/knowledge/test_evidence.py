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
    ResourceId,
    ActorKind,
    ActorRef,
    CorrelationId,
    IdempotencyKey,
    OrganizationId,
    TraceContext,
)
from aeos.knowledge.domain import (
    Evidence,
    EvidenceWithoutSource,
    FactRef,
    InvalidEvidence,
)


WHEN = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_evidence(**changes: object) -> Evidence:
    values: dict[str, object] = {
        "evidence_id": EvidenceId("evidence-1"),
        "statement": "The artifact supports the claim.",
        "created_at": WHEN,
        "artifact_ids": (ArtifactId("artifact-1"),),
    }
    values.update(changes)
    return Evidence(**values)  # type: ignore[arg-type]


def test_evidence_preserves_explicit_immutable_source() -> None:
    evidence = make_evidence()
    assert evidence.artifact_ids == (ArtifactId("artifact-1"),)
    assert evidence.created_at == WHEN
    with pytest.raises(FrozenInstanceError):
        evidence.statement = "changed"  # type: ignore[misc]


def test_evidence_requires_source_and_rejects_duplicates() -> None:
    with pytest.raises(EvidenceWithoutSource):
        make_evidence(artifact_ids=())
    with pytest.raises(InvalidEvidence):
        make_evidence(artifact_ids=(ArtifactId("artifact-1"), ArtifactId("artifact-1")))


def test_evidence_rejects_blank_statement_and_naive_time() -> None:
    with pytest.raises(InvalidEvidence):
        make_evidence(statement=" ")
    with pytest.raises(ValueError, match="timezone-aware"):
        make_evidence(created_at=datetime(2026, 1, 1))
    with pytest.raises(InvalidEvidence):
        make_evidence(created_at=object())


def test_evidence_trims_statement_and_normalizes_time() -> None:
    evidence = make_evidence(
        statement="  supported claim  ",
        created_at=datetime(2026, 1, 1, 3, tzinfo=timezone(timedelta(hours=3))),
    )
    assert evidence.statement == "supported claim"
    assert evidence.created_at == WHEN


@pytest.mark.parametrize(
    "fact_id",
    [
        DomainEventId("domain-event-1"),
        GovernanceDecisionId("governance-1"),
        ApprovalDecisionId("approval-1"),
        EconomicTransactionId("transaction-1"),
        AuditEventId("audit-1"),
        ProvenanceLinkId("link-1"),
    ],
)
def test_fact_ref_accepts_only_approved_material_fact_ids(fact_id: object) -> None:
    assert FactRef(fact_id).fact_id == fact_id  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "fact_id",
    [ArtifactId("artifact-1"), EvidenceId("evidence-1"), ResourceId("resource-1")],
)
def test_fact_ref_rejects_non_fact_ids(fact_id: object) -> None:
    with pytest.raises(InvalidEvidence):
        FactRef(fact_id)  # type: ignore[arg-type]


def test_evidence_accepts_artifact_fact_and_mixed_sources() -> None:
    fact = FactRef(DomainEventId("domain-event-1"))
    assert make_evidence(artifact_ids=(), fact_refs=(fact,)).fact_refs == (fact,)
    assert make_evidence(fact_refs=(fact,)).fact_refs == (fact,)


def test_fact_ref_rejects_duplicates_and_is_immutable() -> None:
    fact = FactRef(DomainEventId("domain-event-1"))
    with pytest.raises(InvalidEvidence):
        make_evidence(artifact_ids=(), fact_refs=(fact, fact))
    with pytest.raises(FrozenInstanceError):
        fact.fact_id = DomainEventId("domain-event-2")  # type: ignore[misc]


def test_evidence_accepts_organization_and_trace_context() -> None:
    trace = TraceContext(
        ActorRef(OrganizationId("actor-1"), ActorKind.SYSTEM),
        CorrelationId("corr-1"),
        IdempotencyKey("idem-1"),
    )
    evidence = make_evidence(
        organization_id=OrganizationId("org-1"), trace_context=trace
    )
    assert evidence.organization_id == OrganizationId("org-1")
    assert evidence.trace_context == trace


def test_evidence_rejects_invalid_collection_and_context_types() -> None:
    with pytest.raises(InvalidEvidence):
        make_evidence(artifact_ids=[ArtifactId("artifact-1")])
    with pytest.raises(InvalidEvidence):
        make_evidence(artifact_ids=(object(),))
    with pytest.raises(InvalidEvidence):
        make_evidence(fact_refs=[FactRef(DomainEventId("domain-event-1"))])
    with pytest.raises(InvalidEvidence):
        make_evidence(fact_refs=(object(),))
    with pytest.raises(InvalidEvidence):
        make_evidence(organization_id=object())
    with pytest.raises(InvalidEvidence):
        make_evidence(trace_context=object())
