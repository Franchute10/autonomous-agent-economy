"""Immutable, concrete identity primitives for AEOS."""

from dataclasses import dataclass
from typing import Self
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class _AeosId:
    """Base implementation; subclasses remain distinct identity types."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self.value.strip():
            raise ValueError("ID value must be a non-blank string")

    @classmethod
    def new(cls: type[Self]) -> Self:
        return cls(uuid4().hex)

    @classmethod
    def from_string(cls: type[Self], value: str) -> Self:
        return cls(value)

    def __str__(self) -> str:
        return self.value


class OrganizationId(_AeosId):
    pass


class RoleId(_AeosId):
    pass


class RoleAssignmentId(_AeosId):
    pass


class AgentDefinitionId(_AeosId):
    pass


class AgentInvocationId(_AeosId):
    pass


class ConstitutionVersionId(_AeosId):
    pass


class PolicyVersionId(_AeosId):
    pass


class PermissionGrantId(_AeosId):
    pass


class ApprovalRequestId(_AeosId):
    pass


class ApprovalDecisionId(_AeosId):
    pass


class GovernanceDecisionId(_AeosId):
    pass


class ResourceId(_AeosId):
    pass


class ResourceAccountId(_AeosId):
    pass


class BudgetId(_AeosId):
    pass


class ReservationId(_AeosId):
    pass


class EconomicTransactionId(_AeosId):
    pass


class UsageReportId(_AeosId):
    pass


class PricingVersionId(_AeosId):
    pass


class CostAllocationId(_AeosId):
    pass


class ObjectiveId(_AeosId):
    pass


class ExperimentId(_AeosId):
    pass


class HypothesisId(_AeosId):
    pass


class MetricDefinitionId(_AeosId):
    pass


class ExperimentCriterionId(_AeosId):
    pass


class ObservationId(_AeosId):
    pass


class ExperimentAssessmentId(_AeosId):
    pass


class DecisionId(_AeosId):
    pass


class LearningId(_AeosId):
    pass


class WorkflowDefinitionId(_AeosId):
    pass


class NodeDefinitionId(_AeosId):
    pass


class EdgeDefinitionId(_AeosId):
    pass


class WorkflowRunId(_AeosId):
    pass


class NodeRunId(_AeosId):
    pass


class NodeAttemptId(_AeosId):
    pass


class WaitConditionId(_AeosId):
    pass


class ExecutionLeaseId(_AeosId):
    pass


class ExternalActionId(_AeosId):
    pass


class ArtifactId(_AeosId):
    pass


class EvidenceId(_AeosId):
    pass


class ProvenanceLinkId(_AeosId):
    pass


class AuditEventId(_AeosId):
    pass


class ReproducibilityManifestId(_AeosId):
    pass


class ModelCallId(_AeosId):
    pass


class ToolCallId(_AeosId):
    pass


class CorrelationId(_AeosId):
    pass


class CausationId(_AeosId):
    pass


class IdempotencyKey(_AeosId):
    pass
