from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from aeos.core import (
    ActorKind,
    ActorRef,
    ArtifactId,
    ApprovalDecisionId,
    AuditEventId,
    CorrelationId,
    DomainEvent,
    EconomicTransactionId,
    GovernanceDecisionId,
    IdempotencyKey,
    TraceContext,
)
from aeos.knowledge.domain import (
    AuditEvent,
    AuditSubjectRef,
    InvalidAuditEvent,
    InvalidAuditSubject,
)
from aeos.core.ids import EvidenceId, OrganizationId


WHEN = datetime(2026, 1, 1, tzinfo=timezone.utc)
TRACE = TraceContext(
    ActorRef(OrganizationId("actor-1"), ActorKind.SYSTEM),
    CorrelationId("corr-1"),
    IdempotencyKey("idem-1"),
)


def make_event(**changes: object) -> AuditEvent:
    values: dict[str, object] = {
        "audit_event_id": AuditEventId("audit-1"),
        "event_type": "artifact.created",
        "subject": AuditSubjectRef(ArtifactId("artifact-1")),
        "occurred_at": WHEN,
        "trace_context": TRACE,
        "artifact_ids": (ArtifactId("artifact-1"),),
        "evidence_ids": (EvidenceId("evidence-1"),),
    }
    values.update(changes)
    return AuditEvent(**values)  # type: ignore[arg-type]


def test_audit_event_is_distinct_and_immutable() -> None:
    event = make_event()
    assert event.event_type == "artifact.created"
    assert event.occurred_at == WHEN
    assert event.artifact_ids == (ArtifactId("artifact-1"),)
    assert not isinstance(event, DomainEvent)
    with pytest.raises(FrozenInstanceError):
        event.event_type = "changed"  # type: ignore[misc]


@pytest.mark.parametrize("event_type", ["", "   "])
def test_audit_event_rejects_blank_type(event_type: str) -> None:
    with pytest.raises(InvalidAuditEvent):
        make_event(event_type=event_type)


@pytest.mark.parametrize(
    "event_type",
    [
        "Artifact.Created",
        "artifact created",
        "artifact",
        "artifact.",
        " artifact.created",
    ],
)
def test_audit_event_rejects_noncanonical_type(event_type: str) -> None:
    with pytest.raises(InvalidAuditEvent):
        make_event(event_type=event_type)


def test_audit_event_accepts_canonical_type_and_approved_subject_ids() -> None:
    for subject_id in (
        ArtifactId("artifact-1"),
        AuditEventId("audit-2"),
        EconomicTransactionId("transaction-1"),
        GovernanceDecisionId("decision-1"),
        ApprovalDecisionId("approval-1"),
    ):
        assert AuditSubjectRef(subject_id).subject_id == subject_id


def test_audit_event_rejects_invalid_subject_and_field_types() -> None:
    with pytest.raises(InvalidAuditSubject):
        AuditSubjectRef(object())  # type: ignore[arg-type]
    with pytest.raises(InvalidAuditEvent):
        make_event(subject=object())
    with pytest.raises(InvalidAuditEvent):
        make_event(audit_event_id=object())
    with pytest.raises(InvalidAuditEvent):
        make_event(event_type=object())
    with pytest.raises(InvalidAuditEvent):
        make_event(occurred_at=object())
    with pytest.raises(InvalidAuditEvent):
        make_event(trace_context=None)
    with pytest.raises(InvalidAuditEvent):
        make_event(organization_id=object())
    with pytest.raises(InvalidAuditEvent):
        make_event(artifact_ids=[ArtifactId("artifact-1")])
    with pytest.raises(InvalidAuditEvent):
        make_event(artifact_ids=(object(),))
    with pytest.raises(InvalidAuditEvent):
        make_event(evidence_ids=[EvidenceId("evidence-1")])
    with pytest.raises(InvalidAuditEvent):
        make_event(evidence_ids=(object(),))
    assert make_event(description=None).description is None
    assert make_event(description="human note").description == "human note"
    with pytest.raises(InvalidAuditEvent):
        make_event(description=object())


def test_audit_event_rejects_naive_time_and_duplicate_references() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        make_event(occurred_at=datetime(2026, 1, 1))
    with pytest.raises(InvalidAuditEvent):
        make_event(artifact_ids=(ArtifactId("artifact-1"), ArtifactId("artifact-1")))
    with pytest.raises(InvalidAuditEvent):
        make_event(evidence_ids=(EvidenceId("evidence-1"), EvidenceId("evidence-1")))


def test_audit_event_normalizes_non_utc_time_and_accepts_organization() -> None:
    event = make_event(
        occurred_at=datetime(2026, 1, 1, 3, tzinfo=timezone(timedelta(hours=3))),
        organization_id=OrganizationId("org-1"),
    )
    assert event.occurred_at == WHEN
    assert event.organization_id == OrganizationId("org-1")
