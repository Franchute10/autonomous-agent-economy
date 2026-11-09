"""Concrete module-owned repositories using explicit SQLAlchemy Core mappings."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Select, select, update
from sqlalchemy.orm import Session

from aeos.agents.domain import AgentCapability, AgentDefinition, AgentInvocation
from aeos.core import ActorRef, ContentHash, OrganizationId, ResourceUnit, VersionRef
from aeos.economics.domain import (
    Budget,
    BudgetLimit,
    EconomicTransaction,
    LedgerPosting,
    Reservation,
    ReservationState,
    Resource,
    ResourceAccount,
)
from aeos.experiments.domain import (
    Experiment,
    ExperimentCriterion,
    ExperimentPreregistration,
    ExperimentResourceExposureLimit,
)
from aeos.governance.domain import ConstitutionVersion, PolicyVersion
from aeos.organization.domain import Organization, Role, RoleAssignment
from aeos.workflows.domain import (
    EdgeDefinition,
    NodeAttempt,
    NodeRun,
    NodeDefinition,
    WorkflowDefinition,
    WorkflowRun,
)
from aeos.infrastructure.persistence import schema
from aeos.infrastructure.persistence.types import (
    actor_from_values,
    actor_values,
    id_value,
    quantity_from_values,
    quantity_values,
    trace_from_values,
    trace_values,
)


def _one(session: Session, statement: Select[Any]) -> Any | None:
    return session.execute(statement).mappings().first()


def _rows(session: Session, table: Any, **filters: Any) -> list[Any]:
    statement = select(table)
    for key, value in filters.items():
        statement = statement.where(table.c[key] == value)
    return list(
        session.execute(statement.order_by(*[table.c[k] for k in filters])).mappings()
    )


def _insert(session: Session, table: Any, values: dict[str, Any]) -> None:
    session.execute(table.insert().values(**values))


def _trace_values(trace: Any) -> dict[str, Any]:
    return trace_values(trace)


class OrganizationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, organization: Organization) -> None:
        constitution = organization.current_constitution
        _insert(
            self._session,
            schema.organizations,
            {
                "id": id_value(organization.organization_id),
                "name": organization.name,
                "status": organization.status.value,
                "current_constitution_subject": None
                if constitution is None
                else constitution.subject,
                "current_constitution_version": None
                if constitution is None
                else constitution.version,
            },
        )
        for role in organization.roles.values():
            _insert(
                self._session,
                schema.roles,
                {
                    "id": id_value(role.role_id),
                    "organization_id": id_value(role.organization_id),
                    "name": role.name,
                    "responsibilities": role.responsibilities,
                },
            )
        for assignment in organization.assignments.values():
            actor_id, actor_type, actor_kind = actor_values(assignment.actor)
            _insert(
                self._session,
                schema.role_assignments,
                {
                    "id": id_value(assignment.role_assignment_id),
                    "organization_id": id_value(assignment.organization_id),
                    "role_id": id_value(assignment.role_id),
                    "actor_id": actor_id,
                    "actor_type": actor_type,
                    "actor_kind": actor_kind,
                    "starts_at": assignment.starts_at,
                    "ends_at": assignment.ends_at,
                },
            )

    def get(self, organization_id: Any) -> Organization | None:
        row = _one(
            self._session,
            select(schema.organizations).where(
                schema.organizations.c.id == id_value(organization_id)
            ),
        )
        if row is None:
            return None
        from aeos.core import OrganizationId, RoleAssignmentId, RoleId
        from aeos.organization.domain import OrganizationStatus

        constitution = None
        if row["current_constitution_subject"] is not None:
            constitution = VersionRef(
                row["current_constitution_subject"], row["current_constitution_version"]
            )
        result = Organization(
            OrganizationId.from_string(row["id"]),
            row["name"],
            OrganizationStatus(row["status"]),
            constitution,
        )
        role_rows = _rows(self._session, schema.roles, organization_id=row["id"])
        for item in role_rows:
            result.add_role(
                Role(
                    RoleId.from_string(item["id"]),
                    OrganizationId.from_string(item["organization_id"]),
                    item["name"],
                    item["responsibilities"],
                )
            )
        assignment_rows = _rows(
            self._session, schema.role_assignments, organization_id=row["id"]
        )
        for item in assignment_rows:
            result.add_assignment(
                RoleAssignment(
                    RoleAssignmentId.from_string(item["id"]),
                    OrganizationId.from_string(item["organization_id"]),
                    RoleId.from_string(item["role_id"]),
                    actor_from_values(
                        item["actor_id"], item["actor_type"], item["actor_kind"]
                    ),
                    item["starts_at"],
                    item["ends_at"],
                )
            )
        return result

    def list_for_actor(self, actor: ActorRef) -> tuple[Organization, ...]:
        actor_id, actor_type, actor_kind = actor_values(actor)
        rows = self._session.execute(
            select(schema.organizations.c.id)
            .join(
                schema.role_assignments,
                schema.role_assignments.c.organization_id == schema.organizations.c.id,
            )
            .where(
                schema.role_assignments.c.actor_id == actor_id,
                schema.role_assignments.c.actor_type == actor_type,
                schema.role_assignments.c.actor_kind == actor_kind,
            )
            .distinct()
            .order_by(schema.organizations.c.name, schema.organizations.c.id)
        ).all()
        organizations = []
        for row in rows:
            organization = self.get(OrganizationId.from_string(row[0]))
            if organization is not None:
                organizations.append(organization)
        return tuple(organizations)


class ConstitutionVersionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, value: ConstitutionVersion) -> None:
        _insert(
            self._session,
            schema.constitution_versions,
            {
                "id": id_value(value.constitution_version_id),
                "organization_id": id_value(value.organization_id),
                "version_subject": value.version_ref.subject,
                "version": value.version_ref.version,
                "content_algorithm": value.content_hash.algorithm,
                "content_digest": value.content_hash.digest,
                "title": value.title,
                "published_at": value.published_at,
            },
        )

    def get(self, value_id: Any) -> ConstitutionVersion | None:
        row = _one(
            self._session,
            select(schema.constitution_versions).where(
                schema.constitution_versions.c.id == id_value(value_id)
            ),
        )
        if row is None:
            return None
        from aeos.core import ConstitutionVersionId, OrganizationId

        return ConstitutionVersion(
            ConstitutionVersionId.from_string(row["id"]),
            OrganizationId.from_string(row["organization_id"]),
            VersionRef(row["version_subject"], row["version"]),
            ContentHash(row["content_algorithm"], row["content_digest"]),
            row["title"],
            row["published_at"],
        )


class PolicyVersionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, value: PolicyVersion) -> None:
        _insert(
            self._session,
            schema.policy_versions,
            {
                "id": id_value(value.policy_version_id),
                "organization_id": id_value(value.organization_id),
                "version_subject": value.version_ref.subject,
                "version": value.version_ref.version,
                "content_algorithm": value.content_hash.algorithm,
                "content_digest": value.content_hash.digest,
                "policy_key": value.policy_key,
                "published_at": value.published_at,
            },
        )

    def get(self, value_id: Any) -> PolicyVersion | None:
        row = _one(
            self._session,
            select(schema.policy_versions).where(
                schema.policy_versions.c.id == id_value(value_id)
            ),
        )
        if row is None:
            return None
        from aeos.core import OrganizationId, PolicyVersionId

        return PolicyVersion(
            PolicyVersionId.from_string(row["id"]),
            OrganizationId.from_string(row["organization_id"]),
            VersionRef(row["version_subject"], row["version"]),
            ContentHash(row["content_algorithm"], row["content_digest"]),
            row["policy_key"],
            row["published_at"],
        )


class ResourceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, value: Resource) -> None:
        _insert(
            self._session,
            schema.resources,
            {
                "id": id_value(value.resource_id),
                "organization_id": id_value(value.organization_id),
                "name": value.name,
                "unit": value.unit.value,
                "description": value.description,
            },
        )

    def get(self, value_id: Any) -> Resource | None:
        row = _one(
            self._session,
            select(schema.resources).where(schema.resources.c.id == id_value(value_id)),
        )
        if row is None:
            return None
        from aeos.core import OrganizationId, ResourceId

        return Resource(
            ResourceId.from_string(row["id"]),
            OrganizationId.from_string(row["organization_id"]),
            row["name"],
            ResourceUnit(row["unit"]),
            row["description"],
        )


class ResourceAccountRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, value: ResourceAccount) -> None:
        _insert(
            self._session,
            schema.resource_accounts,
            {
                "id": id_value(value.resource_account_id),
                "organization_id": id_value(value.organization_id),
                "resource_id": id_value(value.resource_id),
                "account_type": value.account_type.value,
                "name": value.name,
            },
        )

    def get(self, value_id: Any) -> ResourceAccount | None:
        row = _one(
            self._session,
            select(schema.resource_accounts).where(
                schema.resource_accounts.c.id == id_value(value_id)
            ),
        )
        if row is None:
            return None
        from aeos.core import OrganizationId, ResourceAccountId, ResourceId
        from aeos.economics.domain import ResourceAccountType

        return ResourceAccount(
            ResourceAccountId.from_string(row["id"]),
            OrganizationId.from_string(row["organization_id"]),
            ResourceId.from_string(row["resource_id"]),
            ResourceAccountType(row["account_type"]),
            row["name"],
        )


class BudgetRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, value: Budget) -> None:
        trace = _trace_values(value.trace)
        _insert(
            self._session,
            schema.budgets,
            {
                "id": id_value(value.budget_id),
                "organization_id": id_value(value.organization_id),
                "purpose": value.purpose,
                "valid_from": value.valid_from,
                "valid_until": value.valid_until,
                **trace,
            },
        )
        for ordinal, limit in enumerate(value.limits):
            amount, unit = quantity_values(limit.quantity)
            _insert(
                self._session,
                schema.budget_limits,
                {
                    "budget_id": id_value(value.budget_id),
                    "ordinal": ordinal,
                    "resource_id": id_value(limit.resource_id),
                    "quantity": amount,
                    "unit": unit,
                    "period_start": limit.period_start,
                    "period_end": limit.period_end,
                },
            )

    def get(self, value_id: Any) -> Budget | None:
        row = _one(
            self._session,
            select(schema.budgets).where(schema.budgets.c.id == id_value(value_id)),
        )
        if row is None:
            return None
        from aeos.core import BudgetId, OrganizationId, ResourceId

        limits = tuple(
            BudgetLimit(
                ResourceId.from_string(item["resource_id"]),
                quantity_from_values(item["quantity"], item["unit"]),
                item["period_start"],
                item["period_end"],
            )
            for item in self._session.execute(
                select(schema.budget_limits)
                .where(schema.budget_limits.c.budget_id == row["id"])
                .order_by(schema.budget_limits.c.ordinal)
            ).mappings()
        )
        return Budget(
            BudgetId.from_string(row["id"]),
            OrganizationId.from_string(row["organization_id"]),
            row["purpose"],
            limits,
            row["valid_from"],
            row["valid_until"],
            trace_from_values(row),
        )


class ReservationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, value: Reservation) -> None:
        amount, unit = quantity_values(value.quantity)
        _insert(
            self._session,
            schema.reservations,
            {
                "id": id_value(value.reservation_id),
                "budget_id": id_value(value.budget_id),
                "organization_id": id_value(value.organization_id),
                "resource_id": id_value(value.resource_id),
                "quantity": amount,
                "unit": unit,
                "reserved_at": value.reserved_at,
                "expires_at": value.expires_at,
                "state": value.state.value,
                "resolved_at": value.resolved_at,
                **_trace_values(value.trace),
            },
        )

    def get(self, value_id: Any) -> Reservation | None:
        row = _one(
            self._session,
            select(schema.reservations).where(
                schema.reservations.c.id == id_value(value_id)
            ),
        )
        if row is None:
            return None
        from aeos.core import BudgetId, OrganizationId, ReservationId, ResourceId

        result = Reservation(
            ReservationId.from_string(row["id"]),
            BudgetId.from_string(row["budget_id"]),
            OrganizationId.from_string(row["organization_id"]),
            ResourceId.from_string(row["resource_id"]),
            quantity_from_values(row["quantity"], row["unit"]),
            row["reserved_at"],
            row["expires_at"],
            trace_from_values(row),
        )
        state = ReservationState(row["state"])
        if state is ReservationState.ACTIVE:
            if row["resolved_at"] is not None:
                raise ValueError("active reservation has resolved_at")
            return result
        if row["resolved_at"] is None:
            raise ValueError("resolved reservation lacks resolved_at")
        return {
            ReservationState.RELEASED: result.released,
            ReservationState.COMMITTED: result.committed,
            ReservationState.EXPIRED: result.expired,
        }[state](row["resolved_at"])


class EconomicTransactionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def append(self, value: EconomicTransaction) -> None:
        _insert(
            self._session,
            schema.economic_transactions,
            {
                "id": id_value(value.economic_transaction_id),
                "organization_id": id_value(value.organization_id),
                "transaction_type": value.transaction_type.value,
                "occurred_at": value.occurred_at,
                "effective_at": value.effective_at,
                **_trace_values(value.trace),
            },
        )
        for ordinal, posting in enumerate(value.postings):
            amount, unit = quantity_values(posting.quantity)
            _insert(
                self._session,
                schema.ledger_postings,
                {
                    "economic_transaction_id": id_value(value.economic_transaction_id),
                    "ordinal": ordinal,
                    "resource_id": id_value(posting.resource_id),
                    "resource_account_id": id_value(posting.resource_account_id),
                    "quantity": amount,
                    "unit": unit,
                },
            )

    def get(self, value_id: Any) -> EconomicTransaction | None:
        row = _one(
            self._session,
            select(schema.economic_transactions).where(
                schema.economic_transactions.c.id == id_value(value_id)
            ),
        )
        if row is None:
            return None
        from aeos.core import (
            EconomicTransactionId,
            OrganizationId,
            ResourceAccountId,
            ResourceId,
        )

        postings = tuple(
            LedgerPosting(
                ResourceId.from_string(item["resource_id"]),
                ResourceAccountId.from_string(item["resource_account_id"]),
                quantity_from_values(item["quantity"], item["unit"]),
            )
            for item in self._session.execute(
                select(schema.ledger_postings)
                .where(schema.ledger_postings.c.economic_transaction_id == row["id"])
                .order_by(schema.ledger_postings.c.ordinal)
            ).mappings()
        )
        from aeos.economics.domain import EconomicTransactionType

        return EconomicTransaction(
            EconomicTransactionId.from_string(row["id"]),
            OrganizationId.from_string(row["organization_id"]),
            EconomicTransactionType(row["transaction_type"]),
            row["occurred_at"],
            row["effective_at"],
            trace_from_values(row),
            postings,
        )


class ExperimentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, value: Experiment) -> None:
        prereg = value.preregistration
        trace = (
            {} if prereg.trace_context is None else _trace_values(prereg.trace_context)
        )
        _insert(
            self._session,
            schema.experiment_preregistrations,
            {
                "id": id_value(prereg.experiment_id),
                "organization_id": id_value(prereg.organization_id),
                "hypothesis": prereg.hypothesis,
                "objective": prereg.objective,
                "preregistered_at": prereg.preregistered_at,
                **{f"{k}": v for k, v in trace.items()},
            },
        )
        for kind, criteria in (
            ("success", prereg.success_criteria),
            ("kill", prereg.kill_criteria),
        ):
            for ordinal, criterion in enumerate(criteria):
                _insert(
                    self._session,
                    schema.experiment_criteria,
                    {
                        "experiment_id": id_value(prereg.experiment_id),
                        "criterion_kind": kind,
                        "ordinal": ordinal,
                        "text": criterion.text,
                    },
                )
        for ordinal, exposure in enumerate(prereg.maximum_resource_exposure):
            amount, unit = quantity_values(exposure.quantity)
            _insert(
                self._session,
                schema.experiment_exposures,
                {
                    "experiment_id": id_value(prereg.experiment_id),
                    "ordinal": ordinal,
                    "resource_id": id_value(exposure.resource_id),
                    "quantity": amount,
                    "unit": unit,
                },
            )
        _insert(
            self._session,
            schema.experiments,
            {
                "id": id_value(value.experiment_id),
                "status": value.status.value,
                "started_at": value.started_at,
                "finished_at": value.finished_at,
            },
        )

    def save(self, value: Experiment) -> None:
        result = self._session.execute(
            update(schema.experiments)
            .where(schema.experiments.c.id == id_value(value.experiment_id))
            .values(
                status=value.status.value,
                started_at=value.started_at,
                finished_at=value.finished_at,
            )
        )
        if int(getattr(result, "rowcount", -1)) != 1:
            raise KeyError(value.experiment_id)

    def get(self, value_id: Any) -> Experiment | None:
        row = _one(
            self._session,
            select(schema.experiment_preregistrations).where(
                schema.experiment_preregistrations.c.id == id_value(value_id)
            ),
        )
        lifecycle = _one(
            self._session,
            select(schema.experiments).where(
                schema.experiments.c.id == id_value(value_id)
            ),
        )
        if row is None or lifecycle is None:
            return None
        from aeos.core import ExperimentId, OrganizationId, ResourceId

        criteria = self._session.execute(
            select(schema.experiment_criteria)
            .where(schema.experiment_criteria.c.experiment_id == row["id"])
            .order_by(
                schema.experiment_criteria.c.criterion_kind,
                schema.experiment_criteria.c.ordinal,
            )
        ).mappings()
        success = tuple(
            ExperimentCriterion(item["text"])
            for item in criteria
            if item["criterion_kind"] == "success"
        )
        criteria = self._session.execute(
            select(schema.experiment_criteria)
            .where(schema.experiment_criteria.c.experiment_id == row["id"])
            .order_by(
                schema.experiment_criteria.c.criterion_kind,
                schema.experiment_criteria.c.ordinal,
            )
        ).mappings()
        kill = tuple(
            ExperimentCriterion(item["text"])
            for item in criteria
            if item["criterion_kind"] == "kill"
        )
        exposures = tuple(
            ExperimentResourceExposureLimit(
                ResourceId.from_string(item["resource_id"]),
                quantity_from_values(item["quantity"], item["unit"]),
            )
            for item in self._session.execute(
                select(schema.experiment_exposures)
                .where(schema.experiment_exposures.c.experiment_id == row["id"])
                .order_by(schema.experiment_exposures.c.ordinal)
            ).mappings()
        )
        trace = None if row["trace_actor_id"] is None else trace_from_values(row)
        prereg = ExperimentPreregistration(
            ExperimentId.from_string(row["id"]),
            OrganizationId.from_string(row["organization_id"]),
            row["hypothesis"],
            row["objective"],
            success,
            kill,
            exposures,
            row["preregistered_at"],
            trace,
        )
        from aeos.experiments.domain import ExperimentStatus

        return Experiment(
            prereg,
            ExperimentStatus(lifecycle["status"]),
            lifecycle["started_at"],
            lifecycle["finished_at"],
        )


class WorkflowDefinitionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, value: WorkflowDefinition) -> None:
        _insert(
            self._session,
            schema.workflow_definitions,
            {
                "id": id_value(value.workflow_definition_id),
                "organization_id": id_value(value.organization_id),
                "version_subject": value.version_ref.subject,
                "version": value.version_ref.version,
                "name": value.name,
            },
        )
        for ordinal, node in enumerate(value.nodes):
            _insert(
                self._session,
                schema.workflow_nodes,
                {
                    "workflow_definition_id": id_value(value.workflow_definition_id),
                    "ordinal": ordinal,
                    "id": id_value(node.node_definition_id),
                    "name": node.name,
                    "kind": node.kind.value,
                    "description": node.description,
                },
            )
        for ordinal, edge in enumerate(value.edges):
            _insert(
                self._session,
                schema.workflow_edges,
                {
                    "workflow_definition_id": id_value(value.workflow_definition_id),
                    "ordinal": ordinal,
                    "id": id_value(edge.edge_definition_id),
                    "source_node_id": id_value(edge.source_node_id),
                    "target_node_id": id_value(edge.target_node_id),
                },
            )
        for ordinal, entry in enumerate(value.entry_node_ids):
            _insert(
                self._session,
                schema.workflow_entries,
                {
                    "workflow_definition_id": id_value(value.workflow_definition_id),
                    "ordinal": ordinal,
                    "node_id": id_value(entry),
                },
            )

    def get(self, value_id: Any) -> WorkflowDefinition | None:
        row = _one(
            self._session,
            select(schema.workflow_definitions).where(
                schema.workflow_definitions.c.id == id_value(value_id)
            ),
        )
        if row is None:
            return None
        from aeos.core import (
            EdgeDefinitionId,
            NodeDefinitionId,
            OrganizationId,
            WorkflowDefinitionId,
        )

        nodes = tuple(
            NodeDefinition(
                NodeDefinitionId.from_string(item["id"]),
                item["name"],
                __import__("aeos.workflows.domain", fromlist=["NodeKind"]).NodeKind(
                    item["kind"]
                ),
                item["description"],
            )
            for item in self._session.execute(
                select(schema.workflow_nodes)
                .where(schema.workflow_nodes.c.workflow_definition_id == row["id"])
                .order_by(schema.workflow_nodes.c.ordinal)
            ).mappings()
        )
        edges = tuple(
            EdgeDefinition(
                EdgeDefinitionId.from_string(item["id"]),
                NodeDefinitionId.from_string(item["source_node_id"]),
                NodeDefinitionId.from_string(item["target_node_id"]),
            )
            for item in self._session.execute(
                select(schema.workflow_edges)
                .where(schema.workflow_edges.c.workflow_definition_id == row["id"])
                .order_by(schema.workflow_edges.c.ordinal)
            ).mappings()
        )
        entries = tuple(
            NodeDefinitionId.from_string(item["node_id"])
            for item in self._session.execute(
                select(schema.workflow_entries)
                .where(schema.workflow_entries.c.workflow_definition_id == row["id"])
                .order_by(schema.workflow_entries.c.ordinal)
            ).mappings()
        )
        return WorkflowDefinition(
            WorkflowDefinitionId.from_string(row["id"]),
            OrganizationId.from_string(row["organization_id"]),
            VersionRef(row["version_subject"], row["version"]),
            row["name"],
            nodes,
            edges,
            entries,
        )


class WorkflowRunRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, value: WorkflowRun) -> None:
        trace = (
            {} if value.trace_context is None else _trace_values(value.trace_context)
        )
        _insert(
            self._session,
            schema.workflow_runs,
            {
                "id": id_value(value.workflow_run_id),
                "organization_id": id_value(value.organization_id),
                "workflow_definition_id": id_value(value.workflow_definition_id),
                "status": value.status.value,
                "created_at": value.created_at,
                "started_at": value.started_at,
                "finished_at": value.finished_at,
                **trace,
            },
        )

    def save(self, value: WorkflowRun) -> None:
        trace = (
            {} if value.trace_context is None else _trace_values(value.trace_context)
        )
        result = self._session.execute(
            update(schema.workflow_runs)
            .where(schema.workflow_runs.c.id == id_value(value.workflow_run_id))
            .values(
                status=value.status.value,
                created_at=value.created_at,
                started_at=value.started_at,
                finished_at=value.finished_at,
                **trace,
            )
        )
        if int(getattr(result, "rowcount", -1)) != 1:
            raise KeyError(value.workflow_run_id)

    def get(self, value_id: Any) -> WorkflowRun | None:
        row = _one(
            self._session,
            select(schema.workflow_runs).where(
                schema.workflow_runs.c.id == id_value(value_id)
            ),
        )
        if row is None:
            return None
        from aeos.core import OrganizationId, WorkflowDefinitionId, WorkflowRunId
        from aeos.workflows.domain import WorkflowRunStatus

        trace = None if row["trace_actor_id"] is None else trace_from_values(row)
        return WorkflowRun(
            WorkflowRunId.from_string(row["id"]),
            OrganizationId.from_string(row["organization_id"]),
            WorkflowDefinitionId.from_string(row["workflow_definition_id"]),
            WorkflowRunStatus(row["status"]),
            row["created_at"],
            row["started_at"],
            row["finished_at"],
            trace,
        )


class NodeRunRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, value: NodeRun) -> None:
        _insert(
            self._session,
            schema.node_runs,
            {
                "id": id_value(value.node_run_id),
                "workflow_run_id": id_value(value.workflow_run_id),
                "node_definition_id": id_value(value.node_definition_id),
                "status": value.status.value,
                "created_at": value.created_at,
                "started_at": value.started_at,
                "finished_at": value.finished_at,
            },
        )

    def save(self, value: NodeRun) -> None:
        result = self._session.execute(
            update(schema.node_runs)
            .where(schema.node_runs.c.id == id_value(value.node_run_id))
            .values(
                status=value.status.value,
                created_at=value.created_at,
                started_at=value.started_at,
                finished_at=value.finished_at,
            )
        )
        if int(getattr(result, "rowcount", -1)) != 1:
            raise KeyError(value.node_run_id)

    def get(self, value_id: Any) -> NodeRun | None:
        row = _one(
            self._session,
            select(schema.node_runs).where(schema.node_runs.c.id == id_value(value_id)),
        )
        if row is None:
            return None
        from aeos.core import NodeDefinitionId, NodeRunId, WorkflowRunId
        from aeos.workflows.domain import NodeRunStatus

        return NodeRun(
            NodeRunId.from_string(row["id"]),
            WorkflowRunId.from_string(row["workflow_run_id"]),
            NodeDefinitionId.from_string(row["node_definition_id"]),
            NodeRunStatus(row["status"]),
            row["created_at"],
            row["started_at"],
            row["finished_at"],
        )


class NodeAttemptRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, value: NodeAttempt) -> None:
        trace = (
            {} if value.trace_context is None else _trace_values(value.trace_context)
        )
        _insert(
            self._session,
            schema.node_attempts,
            {
                "id": id_value(value.node_attempt_id),
                "node_run_id": id_value(value.node_run_id),
                "attempt_number": value.attempt_number,
                "status": value.status.value,
                "created_at": value.created_at,
                "started_at": value.started_at,
                "finished_at": value.finished_at,
                **trace,
            },
        )

    def save(self, value: NodeAttempt) -> None:
        trace = (
            {} if value.trace_context is None else _trace_values(value.trace_context)
        )
        result = self._session.execute(
            update(schema.node_attempts)
            .where(schema.node_attempts.c.id == id_value(value.node_attempt_id))
            .values(
                status=value.status.value,
                created_at=value.created_at,
                started_at=value.started_at,
                finished_at=value.finished_at,
                **trace,
            )
        )
        if int(getattr(result, "rowcount", -1)) != 1:
            raise KeyError(value.node_attempt_id)

    def get(self, value_id: Any) -> NodeAttempt | None:
        row = _one(
            self._session,
            select(schema.node_attempts).where(
                schema.node_attempts.c.id == id_value(value_id)
            ),
        )
        if row is None:
            return None
        from aeos.core import NodeAttemptId, NodeRunId
        from aeos.workflows.domain import NodeAttemptStatus

        trace = None if row["trace_actor_id"] is None else trace_from_values(row)
        return NodeAttempt(
            NodeAttemptId.from_string(row["id"]),
            NodeRunId.from_string(row["node_run_id"]),
            row["attempt_number"],
            NodeAttemptStatus(row["status"]),
            row["created_at"],
            row["started_at"],
            row["finished_at"],
            trace,
        )


class AgentDefinitionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, value: AgentDefinition) -> None:
        _insert(
            self._session,
            schema.agent_definitions,
            {
                "id": id_value(value.agent_definition_id),
                "organization_id": id_value(value.organization_id),
                "version_subject": value.version_ref.subject,
                "version": value.version_ref.version,
                "name": value.name,
                "purpose": value.purpose,
            },
        )
        for ordinal, capability in enumerate(value.capabilities):
            _insert(
                self._session,
                schema.agent_capabilities,
                {
                    "agent_definition_id": id_value(value.agent_definition_id),
                    "version_subject": value.version_ref.subject,
                    "version": value.version_ref.version,
                    "ordinal": ordinal,
                    "identifier": capability.identifier,
                },
            )

    def get(
        self, value_id: Any, version_ref_value: VersionRef
    ) -> AgentDefinition | None:
        row = _one(
            self._session,
            select(schema.agent_definitions).where(
                schema.agent_definitions.c.id == id_value(value_id),
                schema.agent_definitions.c.version_subject == version_ref_value.subject,
                schema.agent_definitions.c.version == version_ref_value.version,
            ),
        )
        if row is None:
            return None
        from aeos.core import AgentDefinitionId, OrganizationId

        capabilities = tuple(
            AgentCapability(item["identifier"])
            for item in self._session.execute(
                select(schema.agent_capabilities)
                .where(
                    schema.agent_capabilities.c.agent_definition_id == row["id"],
                    schema.agent_capabilities.c.version_subject
                    == row["version_subject"],
                    schema.agent_capabilities.c.version == row["version"],
                )
                .order_by(schema.agent_capabilities.c.ordinal)
            ).mappings()
        )
        return AgentDefinition(
            AgentDefinitionId.from_string(row["id"]),
            OrganizationId.from_string(row["organization_id"]),
            VersionRef(row["version_subject"], row["version"]),
            row["name"],
            row["purpose"],
            capabilities,
        )


class AgentInvocationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def append(self, value: AgentInvocation) -> None:
        _insert(
            self._session,
            schema.agent_invocations,
            {
                "id": id_value(value.agent_invocation_id),
                "agent_definition_id": id_value(value.agent_definition_id),
                "version_subject": value.agent_definition_version.subject,
                "version": value.agent_definition_version.version,
                "invoked_at": value.invoked_at,
                **_trace_values(value.trace_context),
            },
        )

    def get(self, value_id: Any) -> AgentInvocation | None:
        row = _one(
            self._session,
            select(schema.agent_invocations).where(
                schema.agent_invocations.c.id == id_value(value_id)
            ),
        )
        if row is None:
            return None
        from aeos.core import AgentDefinitionId, AgentInvocationId

        return AgentInvocation(
            AgentInvocationId.from_string(row["id"]),
            AgentDefinitionId.from_string(row["agent_definition_id"]),
            VersionRef(row["version_subject"], row["version"]),
            row["invoked_at"],
            trace_from_values(row),
        )


__all__ = [name for name in globals() if name.endswith("Repository")]
