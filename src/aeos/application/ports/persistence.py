"""Narrow persistence contracts; implementations live in Infrastructure."""

from __future__ import annotations

from typing import Protocol

from aeos.agents.domain import AgentDefinition, AgentInvocation
from aeos.core import (
    ActorRef,
    AgentDefinitionId,
    AgentInvocationId,
    EconomicTransactionId,
    ExperimentId,
    OrganizationId,
    VersionRef,
    WorkflowDefinitionId,
    WorkflowRunId,
)
from aeos.economics.domain import EconomicTransaction
from aeos.experiments.domain import Experiment
from aeos.organization.domain import Organization
from aeos.workflows.domain import WorkflowDefinition, WorkflowRun


class OrganizationRepository(Protocol):
    def add(self, organization: Organization) -> None: ...

    def get(self, organization_id: OrganizationId) -> Organization | None: ...

    def list_for_actor(self, actor: ActorRef) -> tuple[Organization, ...]: ...


class EconomicTransactionRepository(Protocol):
    def append(self, transaction: EconomicTransaction) -> None: ...

    def get(
        self, transaction_id: EconomicTransactionId
    ) -> EconomicTransaction | None: ...


class ExperimentRepository(Protocol):
    def add(self, experiment: Experiment) -> None: ...

    def save(self, experiment: Experiment) -> None: ...

    def get(self, experiment_id: ExperimentId) -> Experiment | None: ...


class WorkflowDefinitionRepository(Protocol):
    def add(self, definition: WorkflowDefinition) -> None: ...

    def get(self, definition_id: WorkflowDefinitionId) -> WorkflowDefinition | None: ...


class WorkflowRunRepository(Protocol):
    def add(self, run: WorkflowRun) -> None: ...

    def save(self, run: WorkflowRun) -> None: ...

    def get(self, run_id: WorkflowRunId) -> WorkflowRun | None: ...


class AgentDefinitionRepository(Protocol):
    def add(self, definition: AgentDefinition) -> None: ...

    def get(
        self, definition_id: AgentDefinitionId, version_ref: VersionRef
    ) -> AgentDefinition | None: ...


class AgentInvocationRepository(Protocol):
    def append(self, invocation: AgentInvocation) -> None: ...

    def get(self, invocation_id: AgentInvocationId) -> AgentInvocation | None: ...


class RepositoryUnitOfWork(Protocol):
    organizations: OrganizationRepository
    economic_transactions: EconomicTransactionRepository
    experiments: ExperimentRepository
    workflow_definitions: WorkflowDefinitionRepository
    workflow_runs: WorkflowRunRepository
    agent_definitions: AgentDefinitionRepository
    agent_invocations: AgentInvocationRepository

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def __enter__(self) -> "RepositoryUnitOfWork": ...

    def __exit__(
        self, exc_type: object, exc_value: object, traceback: object
    ) -> None: ...
