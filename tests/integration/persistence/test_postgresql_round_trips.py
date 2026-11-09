"""Real-PostgreSQL persistence and Alembic lifecycle tests."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from ipaddress import ip_address
from os import environ
from pathlib import Path
from collections.abc import Iterator, Sequence
from unittest.mock import patch

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Connection, Engine, make_url
from sqlalchemy.exc import DBAPIError, IntegrityError

from aeos.agents.domain import AgentCapability, AgentDefinition, AgentInvocation
from aeos.application.tenancy import (
    GetBusinessProfile,
    RegisterBusinessProfile,
    RegisterOrganization,
    TenantContextResolver,
)
from aeos.core import (
    ActorKind,
    ActorRef,
    AgentDefinitionId,
    AgentInvocationId,
    ApprovalDecisionId,
    ApprovalRequestId,
    BudgetId,
    ContentHash,
    ConstitutionVersionId,
    CorrelationId,
    EdgeDefinitionId,
    EconomicTransactionId,
    ExperimentId,
    GovernanceDecisionId,
    IdempotencyKey,
    NodeAttemptId,
    NodeDefinitionId,
    NodeRunId,
    OrganizationId,
    PermissionGrantId,
    PolicyVersionId,
    ReservationId,
    ResourceAccountId,
    ResourceId,
    ResourceQuantity,
    ResourceUnit,
    RoleAssignmentId,
    RoleId,
    TraceContext,
    VersionRef,
    WorkflowDefinitionId,
    WorkflowRunId,
)
from aeos.economics.domain import (
    Budget,
    BudgetLimit,
    EconomicTransaction,
    EconomicTransactionType,
    LedgerPosting,
    Reservation,
    Resource,
    ResourceAccount,
    ResourceAccountType,
)
from aeos.experiments.domain import (
    Experiment,
    ExperimentCriterion,
    ExperimentPreregistration,
    ExperimentResourceExposureLimit,
    ExperimentStatus,
)
from aeos.governance.domain import (
    ApprovalDecision,
    ApprovalDecisionResult,
    ApprovalRequest,
    ApprovalRequestState,
    GovernanceDecision,
    GovernanceDecisionResult,
    PermissionCapability,
    PermissionGrant,
    PermissionScope,
    PolicyVersion,
    ConstitutionVersion,
)
from aeos.infrastructure.persistence.uow import SqlAlchemyUnitOfWork
from aeos.infrastructure.persistence import schema
from aeos.infrastructure.persistence.schema import metadata
from aeos.live.domain.profile import BusinessModel, BusinessProfile, RadiusUnit
from aeos.organization.domain import (
    Organization,
    OrganizationStatus,
    Role,
    RoleAssignment,
)
from aeos.workflows.domain import (
    EdgeDefinition,
    NodeAttempt,
    NodeAttemptStatus,
    NodeDefinition,
    NodeKind,
    NodeRun,
    NodeRunStatus,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowRunStatus,
)
from aeos.tenancy.domain import TenantPrincipal


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
HEAD_REVISION = "0002_org_business_profiles"
BASE_REVISION = "0001_initial_persistence"
TEST_DATABASE_NAME = "aeos_test"
APPLICATION_ROLE = "aeos_app"
MIGRATION_ROLE = "aeos_migrator"
TEST_ORGANIZATION_ID = "org-pg"
TEST_AGENT_DEFINITION_ID = "agent-definition-pg"
TEST_INVOCATION_ID = "invocation-pg"
TEST_EXACT_AGENT_DEFINITION_ID = "agent-definition-exact-pg"
TEST_EXACT_INVOCATION_ID = "invocation-exact-pg"
APPLICATION_TABLES = (
    "organization_business_profiles",
    "agent_invocations",
    "agent_capabilities",
    "agent_definitions",
    "node_attempts",
    "node_runs",
    "workflow_runs",
    "workflow_entries",
    "workflow_edges",
    "workflow_nodes",
    "workflow_definitions",
    "experiments",
    "experiment_exposures",
    "experiment_criteria",
    "experiment_preregistrations",
    "ledger_postings",
    "economic_transactions",
    "reservations",
    "budget_limits",
    "budgets",
    "resource_accounts",
    "resources",
    "approval_decision_policies",
    "approval_decisions",
    "approval_request_policies",
    "approval_requests",
    "governance_decision_policies",
    "governance_decisions",
    "permission_grants",
    "policy_versions",
    "constitution_versions",
    "role_assignments",
    "roles",
    "organizations",
)


def _alembic_config(dsn: str) -> Config:
    config = Config(str(REPOSITORY_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", dsn.replace("%", "%%"))
    return config


def _upgrade(dsn: str, revision: str) -> None:
    with patch.dict(
        environ,
        {
            "AEOS_DATABASE_URL": dsn,
            "DATABASE_URL": "",
            "PGUSER": MIGRATION_ROLE,
        },
    ):
        command.upgrade(_alembic_config(dsn), revision)


def _downgrade(dsn: str, revision: str) -> None:
    with patch.dict(
        environ,
        {
            "AEOS_DATABASE_URL": dsn,
            "DATABASE_URL": "",
            "PGUSER": MIGRATION_ROLE,
        },
    ):
        command.downgrade(_alembic_config(dsn), revision)


def _current_revision(engine) -> str | None:  # type: ignore[no-untyped-def]
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def _is_loopback_host(host: str | None) -> bool:
    if host is None:
        return False
    if host.casefold() == "localhost":
        return True
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False


def _cleanup_test_data(engine: Engine) -> None:
    inspector = inspect(engine)
    existing_tables = [
        table_name
        for table_name in APPLICATION_TABLES
        if inspector.has_table(table_name)
    ]
    if not existing_tables:
        return
    table_list = ", ".join(existing_tables)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            f"TRUNCATE TABLE {table_list} RESTART IDENTITY CASCADE"
        )


@pytest.fixture()
def postgres_engine() -> Iterator[Engine]:
    application_dsn = environ.get("AEOS_TEST_DATABASE_URL")
    if not application_dsn:
        pytest.skip("AEOS_TEST_DATABASE_URL is required for PostgreSQL tests")
    migration_dsn = environ.get("AEOS_MIGRATION_DATABASE_URL")
    if not migration_dsn:
        pytest.fail("AEOS_MIGRATION_DATABASE_URL is required for PostgreSQL tests")

    app_url = make_url(application_dsn)
    migration_url = make_url(migration_dsn)
    app_host = app_url.host.casefold() if app_url.host is not None else ""
    migration_host = (
        migration_url.host.casefold() if migration_url.host is not None else ""
    )
    credential_free = all(
        url.username is None and url.password is None
        for url in (app_url, migration_url)
    )
    password_authenticated = (
        app_url.username == APPLICATION_ROLE
        and bool(app_url.password)
        and migration_url.username == MIGRATION_ROLE
        and bool(migration_url.password)
    )
    if (
        app_url.database != TEST_DATABASE_NAME
        or migration_url.database != TEST_DATABASE_NAME
        or not _is_loopback_host(app_url.host)
        or not _is_loopback_host(migration_url.host)
        or app_host != migration_host
        or (app_url.port or 5432) != (migration_url.port or 5432)
        or not (credential_free or password_authenticated)
    ):
        pytest.fail(
            "PostgreSQL tests require the isolated aeos_test database, "
            "matching loopback endpoints, and separate expected test roles"
        )

    # The transaction-boundary test holds one UoW connection while a second
    # connection observes that the uncommitted write is not visible.
    application_engine = create_engine(
        application_dsn,
        connect_args={"user": APPLICATION_ROLE},
        pool_size=2,
        max_overflow=0,
    )
    migration_engine = create_engine(
        migration_dsn,
        connect_args={"user": MIGRATION_ROLE},
        pool_size=1,
        max_overflow=0,
    )
    migrated = False
    try:
        _upgrade(migration_dsn, "head")
        migrated = True
        _cleanup_test_data(migration_engine)
        yield application_engine
    finally:
        try:
            if migrated:
                _cleanup_test_data(migration_engine)
        finally:
            application_engine.dispose()
            migration_engine.dispose()


def _assert_migrated_schema(engine: Engine) -> None:
    assert _current_revision(engine) == HEAD_REVISION
    inspector = inspect(engine)
    for table_name in (
        "organizations",
        "organization_business_profiles",
        "agent_definitions",
        "agent_invocations",
        "node_attempts",
    ):
        assert inspector.has_table(table_name)
    assert inspector.get_pk_constraint("organization_business_profiles")[
        "constrained_columns"
    ] == ["organization_id"]
    foreign_keys = inspector.get_foreign_keys("organization_business_profiles")
    assert len(foreign_keys) == 1
    profile_foreign_key = foreign_keys[0]
    assert (
        profile_foreign_key["name"]
        == "fk_organization_business_profiles_organization_id_organizations"
    )
    assert profile_foreign_key["constrained_columns"] == ["organization_id"]
    assert profile_foreign_key["referred_table"] == "organizations"
    assert profile_foreign_key["referred_columns"] == ["id"]
    assert profile_foreign_key.get("options", {}).get("ondelete") == "CASCADE"


def _assert_schema_parity(engine: Engine) -> None:
    with engine.connect() as connection:
        context = MigrationContext.configure(
            connection,
            opts={"compare_type": True, "compare_server_default": True},
        )
        assert compare_metadata(context, metadata) == []


def _assert_agent_round_trip(engine: Engine) -> None:
    organization_id = OrganizationId("org-pg")
    organization = Organization(
        organization_id,
        "PostgreSQL Test Organization",
        OrganizationStatus.ACTIVE,
    )
    with SqlAlchemyUnitOfWork(engine) as unit_of_work:
        unit_of_work.organizations.add(organization)
        definition = AgentDefinition(
            AgentDefinitionId("agent-definition-pg"),
            organization_id,
            VersionRef("agent", "2026.10.1"),
            "executor",
            "executes declared work",
            (AgentCapability("workflow.execute"), AgentCapability("resource.read")),
        )
        unit_of_work.agent_definitions.add(definition)
        trace = TraceContext(
            ActorRef(organization_id, ActorKind.SYSTEM),
            CorrelationId("corr-pg"),
            IdempotencyKey("idem-pg"),
        )
        invocation = AgentInvocation(
            AgentInvocationId("invocation-pg"),
            definition.agent_definition_id,
            definition.version_ref,
            datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc),
            trace,
        )
        unit_of_work.agent_invocations.append(invocation)
        unit_of_work.commit()
        assert (
            unit_of_work.agent_definitions.get(
                definition.agent_definition_id, definition.version_ref
            )
            == definition
        )
        assert (
            unit_of_work.agent_invocations.get(invocation.agent_invocation_id)
            == invocation
        )


def test_agent_exact_versions_and_composite_reference(postgres_engine: Engine) -> None:
    organization_id = OrganizationId("org-pg-exact")
    definition_id = AgentDefinitionId(TEST_EXACT_AGENT_DEFINITION_ID)
    first = AgentDefinition(
        definition_id,
        organization_id,
        VersionRef("agent", "2026.10.1"),
        "executor-v1",
        "first exact version",
        (AgentCapability("workflow.execute"),),
    )
    second = AgentDefinition(
        definition_id,
        organization_id,
        VersionRef("agent", "2026.10.2"),
        "executor-v2",
        "second exact version",
        (AgentCapability("resource.read"),),
    )
    trace = TraceContext(
        ActorRef(organization_id, ActorKind.SYSTEM),
        CorrelationId("corr-pg-exact"),
        IdempotencyKey("idem-pg-exact"),
    )
    correct_invocation = AgentInvocation(
        AgentInvocationId(TEST_EXACT_INVOCATION_ID),
        definition_id,
        second.version_ref,
        datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc),
        trace,
    )
    with SqlAlchemyUnitOfWork(postgres_engine) as unit_of_work:
        unit_of_work.organizations.add(
            Organization(
                organization_id,
                "PostgreSQL Exact-Version Organization",
                OrganizationStatus.ACTIVE,
            )
        )
        unit_of_work.agent_definitions.add(first)
        unit_of_work.agent_definitions.add(second)
        unit_of_work.agent_invocations.append(correct_invocation)
        unit_of_work.commit()
        assert (
            unit_of_work.agent_definitions.get(definition_id, first.version_ref)
            == first
        )
        assert (
            unit_of_work.agent_definitions.get(definition_id, second.version_ref)
            == second
        )
        assert (
            unit_of_work.agent_definitions.get(
                definition_id, VersionRef("agent", "missing")
            )
            is None
        )
        assert (
            unit_of_work.agent_invocations.get(correct_invocation.agent_invocation_id)
            == correct_invocation
        )

    mismatched_invocation = AgentInvocation(
        AgentInvocationId("invocation-exact-mismatch-pg"),
        definition_id,
        VersionRef("agent", "does-not-exist"),
        datetime(2026, 10, 11, 12, 1, tzinfo=timezone.utc),
        trace,
    )
    with pytest.raises(IntegrityError):
        with SqlAlchemyUnitOfWork(postgres_engine) as unit_of_work:
            unit_of_work.agent_invocations.append(mismatched_invocation)
            unit_of_work.commit()


def test_unit_of_work_transaction_boundaries(postgres_engine: Engine) -> None:
    committed = Organization(
        OrganizationId("org-uow-commit"),
        "Committed Organization",
        OrganizationStatus.ACTIVE,
    )
    with SqlAlchemyUnitOfWork(postgres_engine) as unit_of_work:
        unit_of_work.organizations.add(committed)
        unit_of_work.commit()
    with SqlAlchemyUnitOfWork(postgres_engine) as unit_of_work:
        loaded = unit_of_work.organizations.get(committed.organization_id)
        assert loaded is not None
        assert loaded.organization_id == committed.organization_id
        assert loaded.name == committed.name
        assert loaded.status is committed.status
        assert loaded.current_constitution == committed.current_constitution
        assert not loaded.roles
        assert not loaded.assignments

    rolled_back = Organization(
        OrganizationId("org-uow-rollback"),
        "Rolled Back Organization",
        OrganizationStatus.ACTIVE,
    )
    with SqlAlchemyUnitOfWork(postgres_engine) as unit_of_work:
        unit_of_work.organizations.add(rolled_back)
        unit_of_work.rollback()
    with SqlAlchemyUnitOfWork(postgres_engine) as unit_of_work:
        assert unit_of_work.organizations.get(rolled_back.organization_id) is None

    raised = Organization(
        OrganizationId("org-uow-exception"),
        "Exception Organization",
        OrganizationStatus.ACTIVE,
    )
    with pytest.raises(RuntimeError):
        with SqlAlchemyUnitOfWork(postgres_engine) as unit_of_work:
            unit_of_work.organizations.add(raised)
            raise RuntimeError("force rollback")
    with SqlAlchemyUnitOfWork(postgres_engine) as unit_of_work:
        assert unit_of_work.organizations.get(raised.organization_id) is None

    no_commit = Organization(
        OrganizationId("org-uow-no-commit"),
        "No Commit Organization",
        OrganizationStatus.ACTIVE,
    )
    with SqlAlchemyUnitOfWork(postgres_engine) as unit_of_work:
        unit_of_work.organizations.add(no_commit)
        # This independent observer needs a second pool checkout while the UoW
        # retains its connection and transaction.
        with postgres_engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT COUNT(*) FROM organizations WHERE id = :id"),
                    {"id": no_commit.organization_id.value},
                ).scalar_one()
                == 0
            )
    with SqlAlchemyUnitOfWork(postgres_engine) as unit_of_work:
        assert unit_of_work.organizations.get(no_commit.organization_id) is None


def _trace(organization_id: OrganizationId, suffix: str) -> TraceContext:
    return TraceContext(
        ActorRef(organization_id, ActorKind.SYSTEM),
        CorrelationId(f"aeos-infra-001-correlation-{suffix}"),
        IdempotencyKey(f"aeos-infra-001-idempotency-{suffix}"),
    )


def test_organization_and_governance_round_trips(postgres_engine: Engine) -> None:
    organization_id = OrganizationId("aeos-infra-001-governance-org")
    role_id = RoleId("aeos-infra-001-role")
    assignment_id = RoleAssignmentId("aeos-infra-001-assignment")
    constitution = ConstitutionVersion(
        ConstitutionVersionId("aeos-infra-001-constitution"),
        organization_id,
        VersionRef("constitution", "1"),
        ContentHash.from_bytes(b"aeos-infra-001-constitution"),
        "Test Constitution",
        datetime(2026, 10, 11, tzinfo=timezone.utc),
    )
    organization = Organization(
        organization_id,
        "Governance Integration Organization",
        OrganizationStatus.ACTIVE,
        constitution.version_ref,
    )
    role = Role(role_id, organization_id, "approver", "reviews requests")
    assignment = RoleAssignment(
        assignment_id,
        organization_id,
        role_id,
        ActorRef(OrganizationId("aeos-infra-001-human"), ActorKind.HUMAN),
        datetime(2026, 10, 11, tzinfo=timezone.utc),
        datetime(2026, 10, 12, tzinfo=timezone.utc),
    )
    organization.add_role(role)
    organization.add_assignment(assignment)
    policy_one = PolicyVersion(
        PolicyVersionId("aeos-infra-001-policy-1"),
        organization_id,
        VersionRef("policy", "1"),
        ContentHash.from_bytes(b"aeos-infra-001-policy-1"),
        "spending",
        datetime(2026, 10, 11, tzinfo=timezone.utc),
    )
    policy_two = PolicyVersion(
        PolicyVersionId("aeos-infra-001-policy-2"),
        organization_id,
        VersionRef("policy", "2"),
        ContentHash.from_bytes(b"aeos-infra-001-policy-2"),
        "approval",
        datetime(2026, 10, 11, tzinfo=timezone.utc),
    )
    trace = _trace(organization_id, "governance")
    grant = PermissionGrant(
        PermissionGrantId("aeos-infra-001-grant"),
        organization_id,
        role_id,
        PermissionCapability("resource.read"),
        PermissionScope(),
        policy_one.version_ref,
        constitution.version_ref,
        datetime(2026, 10, 11, tzinfo=timezone.utc),
        datetime(2026, 10, 12, tzinfo=timezone.utc),
        datetime(2026, 10, 11, tzinfo=timezone.utc),
        trace,
    )
    governance_decision = GovernanceDecision(
        GovernanceDecisionId("aeos-infra-001-governance-decision"),
        organization_id,
        GovernanceDecisionResult.REQUIRE_APPROVAL,
        "approval is required",
        constitution.version_ref,
        (policy_one.version_ref, policy_two.version_ref),
        trace,
        datetime(2026, 10, 11, 1, tzinfo=timezone.utc),
        ActorRef(OrganizationId("aeos-infra-001-human"), ActorKind.HUMAN),
    )
    request = ApprovalRequest(
        ApprovalRequestId("aeos-infra-001-approval-request"),
        organization_id,
        ActorRef(OrganizationId("aeos-infra-001-requester"), ActorKind.HUMAN),
        PermissionCapability("resource.read"),
        "review this request",
        datetime(2026, 10, 11, 2, tzinfo=timezone.utc),
        datetime(2026, 10, 11, 4, tzinfo=timezone.utc),
        constitution.version_ref,
        (policy_one.version_ref, policy_two.version_ref),
        governance_decision.governance_decision_id,
        role_id,
        trace,
    )
    decision = ApprovalDecision(
        ApprovalDecisionId("aeos-infra-001-approval-decision"),
        request.approval_request_id,
        organization_id,
        ApprovalDecisionResult.APPROVE,
        ActorRef(OrganizationId("aeos-infra-001-approver"), ActorKind.HUMAN),
        "approved",
        datetime(2026, 10, 11, 3, tzinfo=timezone.utc),
        constitution.version_ref,
        (policy_one.version_ref, policy_two.version_ref),
        trace,
    )
    request.record_decision(decision)

    with SqlAlchemyUnitOfWork(postgres_engine) as unit_of_work:
        unit_of_work.organizations.add(organization)
        unit_of_work.constitution_versions.add(constitution)
        unit_of_work.policy_versions.add(policy_one)
        unit_of_work.policy_versions.add(policy_two)
        unit_of_work.permission_grants.add(grant)
        unit_of_work.governance_decisions.add(governance_decision)
        unit_of_work.approval_requests.add(request)
        unit_of_work.approval_decisions.add(decision)
        unit_of_work.commit()

    with SqlAlchemyUnitOfWork(postgres_engine) as unit_of_work:
        loaded_organization = unit_of_work.organizations.get(organization_id)
        assert loaded_organization is not None
        assert loaded_organization.current_constitution == constitution.version_ref
        assert loaded_organization.roles[role_id] == role
        assert loaded_organization.assignments[assignment_id] == assignment
        assert (
            unit_of_work.constitution_versions.get(constitution.constitution_version_id)
            == constitution
        )
        assert (
            unit_of_work.policy_versions.get(policy_one.policy_version_id) == policy_one
        )
        assert unit_of_work.permission_grants.get(grant.permission_grant_id) == grant
        assert (
            unit_of_work.governance_decisions.get(
                governance_decision.governance_decision_id
            )
            == governance_decision
        )
        loaded_request = unit_of_work.approval_requests.get(request.approval_request_id)
        assert loaded_request is not None
        assert loaded_request.state is ApprovalRequestState.DECIDED
        assert loaded_request.policy_versions == request.policy_versions
        assert loaded_request.constitution_version == request.constitution_version
        loaded_decision = unit_of_work.approval_decisions.get(
            decision.approval_decision_id
        )
        assert loaded_decision == decision


def test_economics_round_trips_without_balances_or_conversion(
    postgres_engine: Engine,
) -> None:
    organization_id = OrganizationId("aeos-infra-001-economics-org")
    resource_id = ResourceId("aeos-infra-001-resource")
    second_resource_id = ResourceId("aeos-infra-001-resource-other")
    resource = Resource(
        resource_id,
        organization_id,
        "Tokens",
        ResourceUnit("tokens"),
        "exact token units",
    )
    second_resource = Resource(
        second_resource_id,
        organization_id,
        "Credits",
        ResourceUnit("credits"),
    )
    available = ResourceAccount.for_resource(
        ResourceAccountId("aeos-infra-001-account-available"),
        resource,
        ResourceAccountType.AVAILABLE,
    )
    committed = ResourceAccount.for_resource(
        ResourceAccountId("aeos-infra-001-account-committed"),
        resource,
        ResourceAccountType.COMMITTED,
    )
    start = datetime(2026, 10, 11, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    trace = _trace(organization_id, "economics")
    budget = Budget(
        BudgetId("aeos-infra-001-budget"),
        organization_id,
        "integration budget",
        (
            BudgetLimit(
                resource_id,
                ResourceQuantity(Decimal("12.340000000000000001"), "tokens"),
                start,
                end,
            ),
            BudgetLimit(
                second_resource_id,
                ResourceQuantity(Decimal("7.5"), "credits"),
                start,
                end,
            ),
        ),
        start,
        end,
        trace,
    )
    reservation = Reservation(
        ReservationId("aeos-infra-001-reservation"),
        budget.budget_id,
        organization_id,
        resource_id,
        ResourceQuantity(Decimal("2.125"), "tokens"),
        start,
        end,
        trace,
    ).committed(start + timedelta(hours=1))
    transaction = EconomicTransaction.from_definitions(
        economic_transaction_id=EconomicTransactionId("aeos-infra-001-transaction"),
        organization_id=organization_id,
        transaction_type=EconomicTransactionType.COMMIT,
        occurred_at=start,
        effective_at=start,
        trace=trace,
        postings=(
            LedgerPosting(
                resource_id,
                available.resource_account_id,
                ResourceQuantity(Decimal("5.000000000000000001"), "tokens"),
            ),
            LedgerPosting(
                resource_id,
                committed.resource_account_id,
                ResourceQuantity(Decimal("-5.000000000000000001"), "tokens"),
            ),
        ),
        resources={resource_id: resource},
        resource_accounts={
            available.resource_account_id: available,
            committed.resource_account_id: committed,
        },
    )
    organization = Organization(
        organization_id,
        "Economics Integration Organization",
        OrganizationStatus.ACTIVE,
    )

    with SqlAlchemyUnitOfWork(postgres_engine) as unit_of_work:
        unit_of_work.organizations.add(organization)
        unit_of_work.resources.add(resource)
        unit_of_work.resources.add(second_resource)
        unit_of_work.resource_accounts.add(available)
        unit_of_work.resource_accounts.add(committed)
        unit_of_work.budgets.add(budget)
        unit_of_work.reservations.add(reservation)
        unit_of_work.economic_transactions.append(transaction)
        unit_of_work.commit()

    with SqlAlchemyUnitOfWork(postgres_engine) as unit_of_work:
        assert unit_of_work.resources.get(resource_id) == resource
        assert unit_of_work.resources.get(second_resource_id) == second_resource
        assert (
            unit_of_work.resource_accounts.get(available.resource_account_id)
            == available
        )
        assert unit_of_work.budgets.get(budget.budget_id) == budget
        assert unit_of_work.reservations.get(reservation.reservation_id) == reservation
        assert (
            unit_of_work.economic_transactions.get(transaction.economic_transaction_id)
            == transaction
        )
        assert not {
            "balance",
            "remaining",
            "spent",
        }.intersection(schema.resource_accounts.c.keys())
        assert not {"remaining", "spent"}.intersection(schema.budgets.c.keys())


def test_experiment_preregistration_and_lifecycle_round_trip(
    postgres_engine: Engine,
) -> None:
    organization_id = OrganizationId("aeos-infra-001-experiment-org")
    resource_id = ResourceId("aeos-infra-001-experiment-resource")
    start = datetime(2026, 10, 11, tzinfo=timezone.utc)
    preregistration = ExperimentPreregistration(
        ExperimentId("aeos-infra-001-experiment"),
        organization_id,
        "ordered hypothesis",
        "ordered objective",
        (ExperimentCriterion("success one"), ExperimentCriterion("success two")),
        (ExperimentCriterion("kill one"), ExperimentCriterion("kill two")),
        (
            ExperimentResourceExposureLimit(
                resource_id, ResourceQuantity(Decimal("3.25"), "tokens")
            ),
        ),
        start,
        _trace(organization_id, "experiment"),
    )
    preregistered = Experiment(preregistration)
    running = preregistered.start(start + timedelta(hours=1))
    terminal = running.succeed(start + timedelta(hours=2))
    resource = Resource(
        resource_id,
        organization_id,
        "Experiment Tokens",
        ResourceUnit("tokens"),
    )
    organization = Organization(
        organization_id,
        "Experiment Integration Organization",
        OrganizationStatus.ACTIVE,
    )

    with SqlAlchemyUnitOfWork(postgres_engine) as unit_of_work:
        unit_of_work.organizations.add(organization)
        unit_of_work.resources.add(resource)
        unit_of_work.experiments.add(preregistered)
        unit_of_work.experiments.save(running)
        unit_of_work.experiments.save(terminal)
        unit_of_work.commit()

    with SqlAlchemyUnitOfWork(postgres_engine) as unit_of_work:
        loaded = unit_of_work.experiments.get(preregistration.experiment_id)
        assert loaded == terminal
        assert loaded is not None
        assert loaded.preregistration == preregistration
        assert loaded.status is ExperimentStatus.SUCCEEDED
        assert loaded.success_criteria == preregistration.success_criteria
        assert loaded.kill_criteria == preregistration.kill_criteria
        assert (
            loaded.maximum_resource_exposure
            == preregistration.maximum_resource_exposure
        )


def test_workflow_definition_cycle_and_execution_state_round_trip(
    postgres_engine: Engine,
) -> None:
    organization_id = OrganizationId("aeos-infra-001-workflow-org")
    node_one_id = NodeDefinitionId("aeos-infra-001-node-one")
    node_two_id = NodeDefinitionId("aeos-infra-001-node-two")
    definition = WorkflowDefinition(
        WorkflowDefinitionId("aeos-infra-001-workflow"),
        organization_id,
        VersionRef("workflow", "1"),
        "Cyclic Workflow",
        (
            NodeDefinition(node_one_id, "one", NodeKind.ACTION),
            NodeDefinition(node_two_id, "two", NodeKind.DECISION),
        ),
        (
            EdgeDefinition(
                EdgeDefinitionId("aeos-infra-001-edge-one"), node_one_id, node_two_id
            ),
            EdgeDefinition(
                EdgeDefinitionId("aeos-infra-001-edge-two"), node_two_id, node_one_id
            ),
        ),
        (node_one_id,),
    )
    created = datetime(2026, 10, 11, tzinfo=timezone.utc)
    started = created + timedelta(minutes=1)
    finished = created + timedelta(minutes=2)
    trace = _trace(organization_id, "workflow")
    workflow_run = WorkflowRun(
        WorkflowRunId("aeos-infra-001-workflow-run"),
        organization_id,
        definition.workflow_definition_id,
        WorkflowRunStatus.PENDING,
        created,
        trace_context=trace,
    )
    running_workflow = workflow_run.start(started)
    terminal_workflow = running_workflow.succeed(finished)
    node_run = NodeRun(
        NodeRunId("aeos-infra-001-node-run"),
        workflow_run.workflow_run_id,
        node_one_id,
        NodeRunStatus.PENDING,
        created,
    )
    terminal_node_run = node_run.start(started).succeed(finished)
    node_attempt = NodeAttempt(
        NodeAttemptId("aeos-infra-001-node-attempt"),
        node_run.node_run_id,
        1,
        NodeAttemptStatus.PENDING,
        created,
        trace_context=trace,
    )
    terminal_attempt = node_attempt.start(started).succeed(finished)
    organization = Organization(
        organization_id,
        "Workflow Integration Organization",
        OrganizationStatus.ACTIVE,
    )

    with SqlAlchemyUnitOfWork(postgres_engine) as unit_of_work:
        unit_of_work.organizations.add(organization)
        unit_of_work.workflow_definitions.add(definition)
        unit_of_work.workflow_runs.add(workflow_run)
        unit_of_work.workflow_runs.save(terminal_workflow)
        unit_of_work.node_runs.add(node_run)
        unit_of_work.node_runs.save(terminal_node_run)
        unit_of_work.node_attempts.add(node_attempt)
        unit_of_work.node_attempts.save(terminal_attempt)
        unit_of_work.commit()

    with SqlAlchemyUnitOfWork(postgres_engine) as unit_of_work:
        assert (
            unit_of_work.workflow_definitions.get(definition.workflow_definition_id)
            == definition
        )
        assert (
            unit_of_work.workflow_runs.get(workflow_run.workflow_run_id)
            == terminal_workflow
        )
        assert unit_of_work.node_runs.get(node_run.node_run_id) == terminal_node_run
        assert (
            unit_of_work.node_attempts.get(node_attempt.node_attempt_id)
            == terminal_attempt
        )

    duplicate_attempt = NodeAttempt(
        NodeAttemptId("aeos-infra-001-node-attempt-duplicate"),
        node_run.node_run_id,
        1,
        NodeAttemptStatus.PENDING,
        created,
    )
    with pytest.raises(IntegrityError):
        with SqlAlchemyUnitOfWork(postgres_engine) as unit_of_work:
            unit_of_work.node_attempts.add(duplicate_attempt)
            unit_of_work.commit()


def test_alembic_schema_lifecycle_and_repository_round_trip(
    postgres_engine: Engine,
) -> None:
    migration_dsn = environ["AEOS_MIGRATION_DATABASE_URL"]
    _assert_migrated_schema(postgres_engine)
    _assert_schema_parity(postgres_engine)
    _assert_agent_round_trip(postgres_engine)
    _assert_migrated_schema(postgres_engine)
    _assert_schema_parity(postgres_engine)

    _downgrade(migration_dsn, BASE_REVISION)
    assert _current_revision(postgres_engine) == BASE_REVISION
    inspector = inspect(postgres_engine)
    assert inspector.has_table("organizations")
    assert not inspector.has_table("organization_business_profiles")

    _downgrade(migration_dsn, "base")
    assert _current_revision(postgres_engine) is None
    inspector = inspect(postgres_engine)
    assert not inspector.has_table("organizations")
    assert not inspector.has_table("organization_business_profiles")
    assert not inspector.has_table("node_attempts")

    _upgrade(migration_dsn, BASE_REVISION)
    assert _current_revision(postgres_engine) == BASE_REVISION
    inspector = inspect(postgres_engine)
    assert inspector.has_table("organizations")
    assert not inspector.has_table("organization_business_profiles")

    _upgrade(migration_dsn, HEAD_REVISION)
    _assert_migrated_schema(postgres_engine)
    _assert_schema_parity(postgres_engine)
    _assert_agent_round_trip(postgres_engine)
    _assert_migrated_schema(postgres_engine)
    _assert_schema_parity(postgres_engine)


TENANT_FIXTURES = (
    ("org-ci-fictional_cleaning", "Sample Cleaning Company (Fictional)"),
    ("org-ci-hz", "Sample HVAC Company (Fictional)"),
    ("org-ci-fictional_builder", "Sample Builder Company (Fictional)"),
)


def _set_tenant_scope(connection: Connection, organization_id: str) -> None:
    connection.execute(
        text("SELECT set_config('aeos.organization_id', :id, true)"),
        {"id": organization_id},
    )


def _insert_profile(
    connection: Connection, organization_id: str, business_name: str
) -> None:
    connection.execute(
        text(
            "INSERT INTO organization_business_profiles "
            "(organization_id, profile_data) "
            "VALUES (:id, CAST(:payload AS JSON))"
        ),
        {
            "id": organization_id,
            "payload": json.dumps(
                {"organization_id": organization_id, "business_name": business_name}
            ),
        },
    )


def _create_tenant_organizations(engine: Engine) -> None:
    with engine.begin() as connection:
        for organization_id, name in TENANT_FIXTURES:
            connection.execute(
                text(
                    "INSERT INTO organizations (id, name, status) "
                    "VALUES (:id, :name, 'active')"
                ),
                {"id": organization_id, "name": name},
            )


def _create_tenant_profiles(engine: Engine) -> None:
    with engine.begin() as connection:
        for organization_id, name in TENANT_FIXTURES:
            _set_tenant_scope(connection, organization_id)
            _insert_profile(connection, organization_id, name)


def _assert_sqlstate(error: DBAPIError, expected: str) -> None:
    assert getattr(error.orig, "sqlstate", None) == expected


def test_postgresql_application_role_is_restricted(postgres_engine: Engine) -> None:
    with postgres_engine.connect() as connection:
        server_version_num: int = connection.execute(
            text("SELECT current_setting('server_version_num')::integer")
        ).scalar_one()
        assert server_version_num // 10000 == 17
        role = (
            connection.execute(
                text(
                    "SELECT current_user, rolsuper, rolbypassrls, rolcreatedb, "
                    "rolcreaterole, has_database_privilege(current_user, "
                    "current_database(), 'CREATE') AS can_create_database, "
                    "has_schema_privilege(current_user, 'public', 'CREATE') "
                    "AS can_create_schema, pg_has_role(current_user, "
                    "CAST(:migration_role AS name), 'MEMBER') "
                    "AS is_migration_role_member "
                    "FROM pg_roles WHERE rolname = current_user"
                ),
                {"migration_role": MIGRATION_ROLE},
            )
            .mappings()
            .one()
        )
        assert role["current_user"] == APPLICATION_ROLE
        assert not role["rolsuper"]
        assert not role["rolbypassrls"]
        assert not role["rolcreatedb"]
        assert not role["rolcreaterole"]
        assert not role["can_create_database"]
        assert not role["can_create_schema"]
        assert not role["is_migration_role_member"]
        owner: str = connection.execute(
            text(
                "SELECT pg_get_userbyid(relowner) FROM pg_class "
                "WHERE oid = 'organization_business_profiles'::regclass"
            )
        ).scalar_one()
        assert owner == MIGRATION_ROLE
        assert connection.execute(
            text(
                "SELECT has_table_privilege(current_user, "
                "'organization_business_profiles', 'SELECT,INSERT,UPDATE,DELETE')"
            )
        ).scalar_one()
        assert not connection.execute(
            text(
                "SELECT has_table_privilege(current_user, "
                "'organization_business_profiles', 'TRUNCATE')"
            )
        ).scalar_one()


def test_business_profile_repository_create_and_retrieve(
    postgres_engine: Engine,
) -> None:
    organization_id = OrganizationId("org-ci-profile-repository")
    principal = TenantPrincipal(
        ActorRef(OrganizationId("actor-ci-profile-repository"), ActorKind.HUMAN)
    )
    at = datetime.now(timezone.utc)
    profile = BusinessProfile(
        business_name="Synthetic Profile Repository Business",
        industry="Cleaning",
        vertical="HOUSE_CLEANING",
        description="Synthetic PostgreSQL repository fixture.",
        business_model=BusinessModel.B2B,
        country="United States",
        state_region="Example Region",
        city="Sample City One",
        service_radius=20,
        service_radius_unit=RadiusUnit.MILES,
        primary_services=("Commercial cleaning",),
        target_customer_segments=("Local businesses",),
        organization_id=organization_id,
        is_fictional_example=True,
    )

    with SqlAlchemyUnitOfWork(postgres_engine) as unit_of_work:
        RegisterOrganization(unit_of_work.organizations).execute(
            principal,
            "Synthetic Profile Repository Organization",
            at=at,
            organization_id=organization_id,
        )
        unit_of_work.commit()

    with SqlAlchemyUnitOfWork(postgres_engine) as unit_of_work:
        resolver = TenantContextResolver(unit_of_work.organizations)
        RegisterBusinessProfile(resolver, unit_of_work.business_profiles).execute(
            principal, organization_id, profile, at=at
        )
        unit_of_work.commit()
        retrieved = GetBusinessProfile(
            resolver, unit_of_work.business_profiles
        ).execute(principal, organization_id, at=at)
        assert retrieved == profile
        unit_of_work.commit()


def test_postgresql_business_profile_row_level_security(
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as connection:
        row_security, force_row_security = connection.execute(
            text(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                "WHERE oid = 'organization_business_profiles'::regclass"
            )
        ).one()
        assert row_security and force_row_security

    _create_tenant_organizations(postgres_engine)
    tenant_ids = tuple(item[0] for item in TENANT_FIXTURES)
    for source_index, source_id in enumerate(tenant_ids):
        target_id = tenant_ids[(source_index + 1) % len(tenant_ids)]
        with pytest.raises(DBAPIError) as denied_insert:
            with postgres_engine.begin() as connection:
                _set_tenant_scope(connection, source_id)
                _insert_profile(connection, target_id, "Forged synthetic profile")
        _assert_sqlstate(denied_insert.value, "42501")

    _create_tenant_profiles(postgres_engine)

    for organization_id, business_name in TENANT_FIXTURES:
        with postgres_engine.begin() as connection:
            _set_tenant_scope(connection, organization_id)
            visible = connection.execute(
                text(
                    "SELECT organization_id, profile_data->>'business_name' "
                    "FROM organization_business_profiles ORDER BY organization_id"
                )
            ).all()
            assert visible == [(organization_id, business_name)]

            for foreign_id in tenant_ids:
                if foreign_id == organization_id:
                    continue
                assert (
                    connection.execute(
                        text(
                            "SELECT organization_id FROM organization_business_profiles "
                            "WHERE organization_id = :id"
                        ),
                        {"id": foreign_id},
                    ).first()
                    is None
                )
                hidden_update = connection.execute(
                    text(
                        "UPDATE organization_business_profiles "
                        "SET profile_data = CAST(:payload AS JSON) "
                        "WHERE organization_id = :id"
                    ),
                    {"id": foreign_id, "payload": '{"tampered": true}'},
                )
                assert hidden_update.rowcount == 0
                hidden_delete = connection.execute(
                    text(
                        "DELETE FROM organization_business_profiles "
                        "WHERE organization_id = :id"
                    ),
                    {"id": foreign_id},
                )
                assert hidden_delete.rowcount == 0

    with postgres_engine.begin() as connection:
        visible_without_scope: Sequence[str] = (
            connection.execute(
                text("SELECT organization_id FROM organization_business_profiles")
            )
            .scalars()
            .all()
        )
        assert visible_without_scope == []

    with postgres_engine.begin() as connection:
        _set_tenant_scope(connection, "org-ci-invalid-context")
        invalid_context_rows = connection.execute(
            text("SELECT organization_id FROM organization_business_profiles")
        ).all()
        assert invalid_context_rows == []

    first_id = tenant_ids[0]
    with pytest.raises(IntegrityError) as duplicate_profile:
        with postgres_engine.begin() as connection:
            _set_tenant_scope(connection, first_id)
            _insert_profile(connection, first_id, "Duplicate synthetic profile")
    _assert_sqlstate(duplicate_profile.value, "23505")

    missing_organization_id = "org-ci-missing-foreign-key"
    with pytest.raises(IntegrityError) as missing_organization:
        with postgres_engine.begin() as connection:
            _set_tenant_scope(connection, missing_organization_id)
            _insert_profile(connection, missing_organization_id, "Missing org")
    _assert_sqlstate(missing_organization.value, "23503")


def test_transaction_local_tenant_context_is_clean_on_pool_reuse(
    postgres_engine: Engine,
) -> None:
    _create_tenant_organizations(postgres_engine)
    _create_tenant_profiles(postgres_engine)
    pooled_engine = create_engine(
        postgres_engine.url,
        connect_args={"user": APPLICATION_ROLE},
        pool_size=1,
        max_overflow=0,
    )
    tenant_a, tenant_b, tenant_c = (item[0] for item in TENANT_FIXTURES)
    try:
        with pooled_engine.connect() as connection_a:
            with connection_a.begin():
                backend_pid: int = connection_a.execute(
                    text("SELECT pg_backend_pid()")
                ).scalar_one()
                _set_tenant_scope(connection_a, tenant_a)
                visible_a: Sequence[str] = (
                    connection_a.execute(
                        text(
                            "SELECT organization_id FROM organization_business_profiles"
                        )
                    )
                    .scalars()
                    .all()
                )
                assert visible_a == [tenant_a]

        with pooled_engine.connect() as connection_b:
            with connection_b.begin():
                assert (
                    connection_b.execute(text("SELECT pg_backend_pid()")).scalar_one()
                    == backend_pid
                )
                no_context: Sequence[str] = (
                    connection_b.execute(
                        text(
                            "SELECT organization_id FROM organization_business_profiles"
                        )
                    )
                    .scalars()
                    .all()
                )
                assert no_context == []
                _set_tenant_scope(connection_b, tenant_b)
                visible_b: Sequence[str] = (
                    connection_b.execute(
                        text(
                            "SELECT organization_id FROM organization_business_profiles"
                        )
                    )
                    .scalars()
                    .all()
                )
                assert visible_b == [tenant_b]

        with pooled_engine.connect() as connection:
            with pytest.raises(RuntimeError, match="rollback tenant context"):
                with connection.begin():
                    assert (
                        connection.execute(text("SELECT pg_backend_pid()")).scalar_one()
                        == backend_pid
                    )
                    _set_tenant_scope(connection, tenant_c)
                    visible_c: Sequence[str] = (
                        connection.execute(
                            text(
                                "SELECT organization_id "
                                "FROM organization_business_profiles"
                            )
                        )
                        .scalars()
                        .all()
                    )
                    assert visible_c == [tenant_c]
                    raise RuntimeError("rollback tenant context")

        with pooled_engine.connect() as connection:
            with connection.begin():
                assert (
                    connection.execute(text("SELECT pg_backend_pid()")).scalar_one()
                    == backend_pid
                )
                after_rollback: Sequence[str] = (
                    connection.execute(
                        text(
                            "SELECT organization_id FROM organization_business_profiles"
                        )
                    )
                    .scalars()
                    .all()
                )
                assert after_rollback == []
                _set_tenant_scope(connection, tenant_b)
                visible_after_rollback: Sequence[str] = (
                    connection.execute(
                        text(
                            "SELECT organization_id FROM organization_business_profiles"
                        )
                    )
                    .scalars()
                    .all()
                )
                assert visible_after_rollback == [tenant_b]
    finally:
        pooled_engine.dispose()
