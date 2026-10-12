"""Explicit conversions between relational primitives and domain value objects."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping, TypeVar, cast

from aeos.core import (
    ActorKind,
    ActorRef,
    AgentDefinitionId,
    AgentInvocationId,
    ApprovalDecisionId,
    ApprovalRequestId,
    ArtifactId,
    AuditEventId,
    BudgetId,
    CausationId,
    ConstitutionVersionId,
    CorrelationId,
    CostAllocationId,
    DecisionId,
    DomainEventId,
    EdgeDefinitionId,
    EconomicTransactionId,
    EvidenceId,
    ExecutionLeaseId,
    ExperimentAssessmentId,
    ExperimentCriterionId,
    ExperimentId,
    ExternalActionId,
    GovernanceDecisionId,
    HypothesisId,
    IdempotencyKey,
    LearningId,
    MetricDefinitionId,
    ModelCallId,
    NodeAttemptId,
    NodeDefinitionId,
    NodeRunId,
    ObservationId,
    ObjectiveId,
    OrganizationId,
    PermissionGrantId,
    PolicyVersionId,
    PricingVersionId,
    ProvenanceLinkId,
    ReproducibilityManifestId,
    ReservationId,
    ResourceAccountId,
    ResourceId,
    RoleAssignmentId,
    RoleId,
    ResourceQuantity,
    ResourceUnit,
    ToolCallId,
    TraceContext,
    UsageReportId,
    WaitConditionId,
    WorkflowDefinitionId,
    WorkflowRunId,
)
from aeos.core.versioning import VersionRef

SupportedId = (
    AgentDefinitionId
    | AgentInvocationId
    | ApprovalDecisionId
    | ApprovalRequestId
    | ArtifactId
    | AuditEventId
    | BudgetId
    | CausationId
    | ConstitutionVersionId
    | CorrelationId
    | CostAllocationId
    | DecisionId
    | DomainEventId
    | EdgeDefinitionId
    | EconomicTransactionId
    | EvidenceId
    | ExecutionLeaseId
    | ExperimentAssessmentId
    | ExperimentCriterionId
    | ExperimentId
    | ExternalActionId
    | GovernanceDecisionId
    | HypothesisId
    | IdempotencyKey
    | LearningId
    | MetricDefinitionId
    | ModelCallId
    | NodeAttemptId
    | NodeDefinitionId
    | NodeRunId
    | ObservationId
    | ObjectiveId
    | OrganizationId
    | PermissionGrantId
    | PolicyVersionId
    | PricingVersionId
    | ProvenanceLinkId
    | ReproducibilityManifestId
    | ReservationId
    | ResourceAccountId
    | ResourceId
    | RoleAssignmentId
    | RoleId
    | ToolCallId
    | UsageReportId
    | WaitConditionId
    | WorkflowDefinitionId
    | WorkflowRunId
)

ID_CLASSES: dict[str, type[SupportedId]] = {
    "AgentDefinitionId": AgentDefinitionId,
    "AgentInvocationId": AgentInvocationId,
    "ApprovalDecisionId": ApprovalDecisionId,
    "ApprovalRequestId": ApprovalRequestId,
    "ArtifactId": ArtifactId,
    "AuditEventId": AuditEventId,
    "BudgetId": BudgetId,
    "CausationId": CausationId,
    "ConstitutionVersionId": ConstitutionVersionId,
    "CorrelationId": CorrelationId,
    "CostAllocationId": CostAllocationId,
    "DecisionId": DecisionId,
    "DomainEventId": DomainEventId,
    "EdgeDefinitionId": EdgeDefinitionId,
    "EconomicTransactionId": EconomicTransactionId,
    "EvidenceId": EvidenceId,
    "ExecutionLeaseId": ExecutionLeaseId,
    "ExperimentAssessmentId": ExperimentAssessmentId,
    "ExperimentCriterionId": ExperimentCriterionId,
    "ExperimentId": ExperimentId,
    "ExternalActionId": ExternalActionId,
    "GovernanceDecisionId": GovernanceDecisionId,
    "HypothesisId": HypothesisId,
    "IdempotencyKey": IdempotencyKey,
    "LearningId": LearningId,
    "MetricDefinitionId": MetricDefinitionId,
    "ModelCallId": ModelCallId,
    "NodeAttemptId": NodeAttemptId,
    "NodeDefinitionId": NodeDefinitionId,
    "NodeRunId": NodeRunId,
    "ObservationId": ObservationId,
    "ObjectiveId": ObjectiveId,
    "OrganizationId": OrganizationId,
    "PermissionGrantId": PermissionGrantId,
    "PolicyVersionId": PolicyVersionId,
    "PricingVersionId": PricingVersionId,
    "ProvenanceLinkId": ProvenanceLinkId,
    "ReproducibilityManifestId": ReproducibilityManifestId,
    "ReservationId": ReservationId,
    "ResourceAccountId": ResourceAccountId,
    "ResourceId": ResourceId,
    "RoleAssignmentId": RoleAssignmentId,
    "RoleId": RoleId,
    "ToolCallId": ToolCallId,
    "UsageReportId": UsageReportId,
    "WaitConditionId": WaitConditionId,
    "WorkflowDefinitionId": WorkflowDefinitionId,
    "WorkflowRunId": WorkflowRunId,
}
TId = TypeVar("TId", bound=SupportedId)


def id_value(value: SupportedId) -> str:
    if type(value).__name__ not in ID_CLASSES:
        raise ValueError("expected a supported AEOS typed ID")
    return value.value


def id_from_value(value: str, cls: type[TId]) -> TId:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("persisted ID must be a non-blank string")
    return cast(TId, cls.from_string(value))


def version_columns(value: VersionRef) -> tuple[str, str]:
    return value.subject, value.version


def version_ref(subject: str, version: str) -> VersionRef:
    return VersionRef(subject, version)


def utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("persisted datetime must be timezone-aware")
    return value.astimezone(timezone.utc)


def quantity_values(value: ResourceQuantity) -> tuple[Decimal, str]:
    return value.quantity, value.unit.value


def quantity_from_values(amount: Decimal, unit: str) -> ResourceQuantity:
    if not isinstance(amount, Decimal):
        amount = Decimal(str(amount))
    return ResourceQuantity(amount, ResourceUnit.from_string(unit))


def actor_values(actor: ActorRef) -> tuple[str, str, str]:
    actor_type = type(actor.actor_id).__name__
    if actor_type not in ID_CLASSES:
        raise ValueError("unsupported persisted ActorRef ID type")
    return actor.actor_id.value, actor_type, actor.kind.value


def actor_from_values(value: str, type_name: str, kind: str) -> ActorRef:
    try:
        cls = ID_CLASSES[type_name]
        actor_kind = ActorKind(kind)
    except (KeyError, ValueError) as exc:
        raise ValueError("invalid persisted ActorRef") from exc
    return ActorRef(cls.from_string(value), actor_kind)


def trace_values(trace: TraceContext) -> dict[str, str | None]:
    actor_id, actor_type, actor_kind = actor_values(trace.actor)
    return {
        "trace_actor_id": actor_id,
        "trace_actor_type": actor_type,
        "trace_actor_kind": actor_kind,
        "trace_correlation_id": trace.correlation_id.value,
        "trace_idempotency_key": trace.idempotency_key.value,
        "trace_causation_id": None
        if trace.causation_id is None
        else trace.causation_id.value,
    }


def trace_from_values(row: Mapping[str, Any], prefix: str = "trace_") -> TraceContext:
    get = row.__getitem__
    actor = actor_from_values(
        get(f"{prefix}actor_id"),
        get(f"{prefix}actor_type"),
        get(f"{prefix}actor_kind"),
    )
    causation = get(f"{prefix}causation_id")
    return TraceContext(
        actor=actor,
        correlation_id=CorrelationId.from_string(get(f"{prefix}correlation_id")),
        idempotency_key=IdempotencyKey.from_string(get(f"{prefix}idempotency_key")),
        causation_id=None if causation is None else CausationId.from_string(causation),
    )
