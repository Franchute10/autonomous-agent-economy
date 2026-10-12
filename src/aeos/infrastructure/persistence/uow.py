"""Minimal transaction boundary for persistence adapters."""

from __future__ import annotations

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from aeos.infrastructure.persistence.database import create_engine
from aeos.infrastructure.persistence.repositories import (
    AgentDefinitionRepository,
    AgentInvocationRepository,
    BudgetRepository,
    ConstitutionVersionRepository,
    EconomicTransactionRepository,
    ExperimentRepository,
    NodeAttemptRepository,
    NodeRunRepository,
    OrganizationRepository,
    PolicyVersionRepository,
    ReservationRepository,
    ResourceAccountRepository,
    ResourceRepository,
    WorkflowDefinitionRepository,
    WorkflowRunRepository,
)
from aeos.infrastructure.persistence.governance import (
    ApprovalDecisionRepository,
    ApprovalRequestRepository,
    GovernanceDecisionRepository,
    PermissionGrantRepository,
)


class SqlAlchemyUnitOfWork:
    """Own one session and its transaction; repositories never commit."""

    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine or create_engine()
        self._session_factory = sessionmaker(bind=self._engine, expire_on_commit=False)
        self._session: Session | None = None

    @property
    def session(self) -> Session:
        if self._session is None:
            raise RuntimeError("UnitOfWork is not active")
        return self._session

    def __enter__(self) -> "SqlAlchemyUnitOfWork":
        if self._session is not None:
            raise RuntimeError("UnitOfWork cannot be entered twice")
        self._session = self._session_factory()
        self.organizations = OrganizationRepository(self.session)
        self.constitution_versions = ConstitutionVersionRepository(self.session)
        self.policy_versions = PolicyVersionRepository(self.session)
        self.permission_grants = PermissionGrantRepository(self.session)
        self.governance_decisions = GovernanceDecisionRepository(self.session)
        self.approval_requests = ApprovalRequestRepository(self.session)
        self.approval_decisions = ApprovalDecisionRepository(self.session)
        self.resources = ResourceRepository(self.session)
        self.resource_accounts = ResourceAccountRepository(self.session)
        self.budgets = BudgetRepository(self.session)
        self.reservations = ReservationRepository(self.session)
        self.economic_transactions = EconomicTransactionRepository(self.session)
        self.experiments = ExperimentRepository(self.session)
        self.workflow_definitions = WorkflowDefinitionRepository(self.session)
        self.workflow_runs = WorkflowRunRepository(self.session)
        self.node_runs = NodeRunRepository(self.session)
        self.node_attempts = NodeAttemptRepository(self.session)
        self.agent_definitions = AgentDefinitionRepository(self.session)
        self.agent_invocations = AgentInvocationRepository(self.session)
        return self

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        if self._session is None:
            return
        try:
            if exc_type is not None:
                self._session.rollback()
        finally:
            self._session.close()
            self._session = None


__all__ = ["SqlAlchemyUnitOfWork"]
