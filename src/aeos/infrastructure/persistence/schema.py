"""Module-owned relational tables for the first PostgreSQL persistence baseline."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    MetaData,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Table,
    UniqueConstraint,
)


metadata = MetaData(
    naming_convention={
        "ix": "ix_%(table_name)s_%(column_0_name)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)
ID = String(255)
VERSION = String(255)
TS = DateTime(timezone=True)
AMOUNT = Numeric(38, 18, asdecimal=True)


organizations = Table(
    "organizations",
    metadata,
    Column("id", ID, primary_key=True),
    Column("name", String(255), nullable=False),
    Column("status", String(32), nullable=False),
    Column("current_constitution_subject", VERSION),
    Column("current_constitution_version", VERSION),
)
roles = Table(
    "roles",
    metadata,
    Column("id", ID, primary_key=True),
    Column("organization_id", ID, ForeignKey("organizations.id"), nullable=False),
    Column("name", String(255), nullable=False),
    Column("responsibilities", String(4000)),
    UniqueConstraint("organization_id", "id"),
)
role_assignments = Table(
    "role_assignments",
    metadata,
    Column("id", ID, primary_key=True),
    Column("organization_id", ID, ForeignKey("organizations.id"), nullable=False),
    Column("role_id", ID, ForeignKey("roles.id"), nullable=False),
    Column("actor_id", ID, nullable=False),
    Column("actor_type", String(64), nullable=False),
    Column("actor_kind", String(32), nullable=False),
    Column("starts_at", TS, nullable=False),
    Column("ends_at", TS),
)

constitution_versions = Table(
    "constitution_versions",
    metadata,
    Column("id", ID, primary_key=True),
    Column("organization_id", ID, ForeignKey("organizations.id"), nullable=False),
    Column("version_subject", VERSION, nullable=False),
    Column("version", VERSION, nullable=False),
    Column("content_algorithm", String(32), nullable=False),
    Column("content_digest", String(128), nullable=False),
    Column("title", String(255), nullable=False),
    Column("published_at", TS, nullable=False),
    UniqueConstraint("organization_id", "version_subject", "version"),
)
policy_versions = Table(
    "policy_versions",
    metadata,
    Column("id", ID, primary_key=True),
    Column("organization_id", ID, ForeignKey("organizations.id"), nullable=False),
    Column("version_subject", VERSION, nullable=False),
    Column("version", VERSION, nullable=False),
    Column("content_algorithm", String(32), nullable=False),
    Column("content_digest", String(128), nullable=False),
    Column("policy_key", String(255), nullable=False),
    Column("published_at", TS, nullable=False),
    UniqueConstraint("organization_id", "version_subject", "version"),
)
permission_grants = Table(
    "permission_grants",
    metadata,
    Column("id", ID, primary_key=True),
    Column("organization_id", ID, ForeignKey("organizations.id"), nullable=False),
    Column("grantee_id", ID, nullable=False),
    Column("grantee_type", String(64), nullable=False),
    Column("grantee_kind", String(32)),
    Column("capability", String(255), nullable=False),
    Column("scope_kind", String(64), nullable=False),
    Column("policy_subject", VERSION, nullable=False),
    Column("policy_version", VERSION, nullable=False),
    Column("constitution_subject", VERSION),
    Column("constitution_version", VERSION),
    Column("valid_from", TS, nullable=False),
    Column("valid_until", TS),
    Column("created_at", TS, nullable=False),
    Column("trace_actor_id", ID, nullable=False),
    Column("trace_actor_type", String(64), nullable=False),
    Column("trace_actor_kind", String(32), nullable=False),
    Column("trace_correlation_id", ID, nullable=False),
    Column("trace_idempotency_key", ID, nullable=False),
    Column("trace_causation_id", ID),
)

governance_decisions = Table(
    "governance_decisions",
    metadata,
    Column("id", ID, primary_key=True),
    Column("organization_id", ID, ForeignKey("organizations.id"), nullable=False),
    Column("result", String(32), nullable=False),
    Column("reason", String(4000), nullable=False),
    Column("constitution_subject", VERSION, nullable=False),
    Column("constitution_version", VERSION, nullable=False),
    Column("decided_at", TS, nullable=False),
    Column("evaluated_actor_id", ID),
    Column("evaluated_actor_type", String(64)),
    Column("evaluated_actor_kind", String(32)),
    Column("trace_actor_id", ID, nullable=False),
    Column("trace_actor_type", String(64), nullable=False),
    Column("trace_actor_kind", String(32), nullable=False),
    Column("trace_correlation_id", ID, nullable=False),
    Column("trace_idempotency_key", ID, nullable=False),
    Column("trace_causation_id", ID),
)
governance_decision_policies = Table(
    "governance_decision_policies",
    metadata,
    Column(
        "governance_decision_id",
        ID,
        ForeignKey("governance_decisions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("ordinal", Integer, nullable=False),
    Column("version_subject", VERSION, nullable=False),
    Column("version", VERSION, nullable=False),
)
approval_requests = Table(
    "approval_requests",
    metadata,
    Column("id", ID, primary_key=True),
    Column("organization_id", ID, ForeignKey("organizations.id"), nullable=False),
    Column("requester_id", ID, nullable=False),
    Column("requester_type", String(64), nullable=False),
    Column("requester_kind", String(32), nullable=False),
    Column("capability", String(255), nullable=False),
    Column("reason", String(4000), nullable=False),
    Column("requested_at", TS, nullable=False),
    Column("expires_at", TS),
    Column("constitution_subject", VERSION),
    Column("constitution_version", VERSION),
    Column("governance_decision_id", ID, ForeignKey("governance_decisions.id")),
    Column("required_role_id", ID, ForeignKey("roles.id")),
    Column("state", String(32), nullable=False),
    Column("trace_actor_id", ID, nullable=False),
    Column("trace_actor_type", String(64), nullable=False),
    Column("trace_actor_kind", String(32), nullable=False),
    Column("trace_correlation_id", ID, nullable=False),
    Column("trace_idempotency_key", ID, nullable=False),
    Column("trace_causation_id", ID),
)
approval_request_policies = Table(
    "approval_request_policies",
    metadata,
    Column(
        "approval_request_id",
        ID,
        ForeignKey("approval_requests.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("ordinal", Integer, primary_key=True),
    Column("version_subject", VERSION, nullable=False),
    Column("version", VERSION, nullable=False),
)
approval_decisions = Table(
    "approval_decisions",
    metadata,
    Column("id", ID, primary_key=True),
    Column(
        "approval_request_id", ID, ForeignKey("approval_requests.id"), nullable=False
    ),
    Column("organization_id", ID, ForeignKey("organizations.id"), nullable=False),
    Column("decision", String(32), nullable=False),
    Column("decided_by_id", ID, nullable=False),
    Column("decided_by_type", String(64), nullable=False),
    Column("decided_by_kind", String(32), nullable=False),
    Column("reason", String(4000), nullable=False),
    Column("decided_at", TS, nullable=False),
    Column("constitution_subject", VERSION),
    Column("constitution_version", VERSION),
    Column("trace_actor_id", ID, nullable=False),
    Column("trace_actor_type", String(64), nullable=False),
    Column("trace_actor_kind", String(32), nullable=False),
    Column("trace_correlation_id", ID, nullable=False),
    Column("trace_idempotency_key", ID, nullable=False),
    Column("trace_causation_id", ID),
)
approval_decision_policies = Table(
    "approval_decision_policies",
    metadata,
    Column(
        "approval_decision_id",
        ID,
        ForeignKey("approval_decisions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("ordinal", Integer, primary_key=True),
    Column("version_subject", VERSION, nullable=False),
    Column("version", VERSION, nullable=False),
)

resources = Table(
    "resources",
    metadata,
    Column("id", ID, primary_key=True),
    Column("organization_id", ID, ForeignKey("organizations.id"), nullable=False),
    Column("name", String(255), nullable=False),
    Column("unit", String(255), nullable=False),
    Column("description", String(4000)),
)
resource_accounts = Table(
    "resource_accounts",
    metadata,
    Column("id", ID, primary_key=True),
    Column("organization_id", ID, ForeignKey("organizations.id"), nullable=False),
    Column("resource_id", ID, ForeignKey("resources.id"), nullable=False),
    Column("account_type", String(64), nullable=False),
    Column("name", String(255)),
)
budgets = Table(
    "budgets",
    metadata,
    Column("id", ID, primary_key=True),
    Column("organization_id", ID, ForeignKey("organizations.id"), nullable=False),
    Column("purpose", String(4000), nullable=False),
    Column("valid_from", TS, nullable=False),
    Column("valid_until", TS),
    Column("trace_actor_id", ID, nullable=False),
    Column("trace_actor_type", String(64), nullable=False),
    Column("trace_actor_kind", String(32), nullable=False),
    Column("trace_correlation_id", ID, nullable=False),
    Column("trace_idempotency_key", ID, nullable=False),
    Column("trace_causation_id", ID),
)
budget_limits = Table(
    "budget_limits",
    metadata,
    Column(
        "budget_id", ID, ForeignKey("budgets.id", ondelete="CASCADE"), primary_key=True
    ),
    Column("ordinal", Integer, primary_key=True),
    Column("resource_id", ID, ForeignKey("resources.id"), nullable=False),
    Column("quantity", AMOUNT, nullable=False),
    Column("unit", String(255), nullable=False),
    Column("period_start", TS, nullable=False),
    Column("period_end", TS),
    CheckConstraint("quantity > 0", name="positive_quantity"),
)
reservations = Table(
    "reservations",
    metadata,
    Column("id", ID, primary_key=True),
    Column("budget_id", ID, ForeignKey("budgets.id"), nullable=False),
    Column("organization_id", ID, ForeignKey("organizations.id"), nullable=False),
    Column("resource_id", ID, ForeignKey("resources.id"), nullable=False),
    Column("quantity", AMOUNT, nullable=False),
    Column("unit", String(255), nullable=False),
    Column("reserved_at", TS, nullable=False),
    Column("expires_at", TS),
    Column("state", String(32), nullable=False),
    Column("resolved_at", TS),
    Column("trace_actor_id", ID, nullable=False),
    Column("trace_actor_type", String(64), nullable=False),
    Column("trace_actor_kind", String(32), nullable=False),
    Column("trace_correlation_id", ID, nullable=False),
    Column("trace_idempotency_key", ID, nullable=False),
    Column("trace_causation_id", ID),
    CheckConstraint("quantity > 0", name="positive_quantity"),
)
economic_transactions = Table(
    "economic_transactions",
    metadata,
    Column("id", ID, primary_key=True),
    Column("organization_id", ID, ForeignKey("organizations.id"), nullable=False),
    Column("transaction_type", String(64), nullable=False),
    Column("occurred_at", TS, nullable=False),
    Column("effective_at", TS, nullable=False),
    Column("trace_actor_id", ID, nullable=False),
    Column("trace_actor_type", String(64), nullable=False),
    Column("trace_actor_kind", String(32), nullable=False),
    Column("trace_correlation_id", ID, nullable=False),
    Column("trace_idempotency_key", ID, nullable=False),
    Column("trace_causation_id", ID),
)
ledger_postings = Table(
    "ledger_postings",
    metadata,
    Column(
        "economic_transaction_id",
        ID,
        ForeignKey("economic_transactions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("ordinal", Integer, primary_key=True),
    Column("resource_id", ID, ForeignKey("resources.id"), nullable=False),
    Column(
        "resource_account_id", ID, ForeignKey("resource_accounts.id"), nullable=False
    ),
    Column("quantity", AMOUNT, nullable=False),
    Column("unit", String(255), nullable=False),
    CheckConstraint("quantity <> 0", name="nonzero_quantity"),
)

experiment_preregistrations = Table(
    "experiment_preregistrations",
    metadata,
    Column("id", ID, primary_key=True),
    Column("organization_id", ID, ForeignKey("organizations.id"), nullable=False),
    Column("hypothesis", String(4000), nullable=False),
    Column("objective", String(4000), nullable=False),
    Column("preregistered_at", TS, nullable=False),
    Column("trace_actor_id", ID),
    Column("trace_actor_type", String(64)),
    Column("trace_actor_kind", String(32)),
    Column("trace_correlation_id", ID),
    Column("trace_idempotency_key", ID),
    Column("trace_causation_id", ID),
)
experiment_criteria = Table(
    "experiment_criteria",
    metadata,
    Column(
        "experiment_id",
        ID,
        ForeignKey("experiment_preregistrations.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("criterion_kind", String(16), primary_key=True),
    Column("ordinal", Integer, primary_key=True),
    Column("text", String(4000), nullable=False),
)
experiment_exposures = Table(
    "experiment_exposures",
    metadata,
    Column(
        "experiment_id",
        ID,
        ForeignKey("experiment_preregistrations.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("ordinal", Integer, primary_key=True),
    Column("resource_id", ID, ForeignKey("resources.id"), nullable=False),
    Column("quantity", AMOUNT, nullable=False),
    Column("unit", String(255), nullable=False),
    CheckConstraint("quantity > 0", name="positive_quantity"),
)
experiments = Table(
    "experiments",
    metadata,
    Column("id", ID, ForeignKey("experiment_preregistrations.id"), primary_key=True),
    Column("status", String(32), nullable=False),
    Column("started_at", TS),
    Column("finished_at", TS),
)

workflow_definitions = Table(
    "workflow_definitions",
    metadata,
    Column("id", ID, primary_key=True),
    Column("organization_id", ID, ForeignKey("organizations.id"), nullable=False),
    Column("version_subject", VERSION, nullable=False),
    Column("version", VERSION, nullable=False),
    Column("name", String(255), nullable=False),
    UniqueConstraint("organization_id", "version_subject", "version"),
)
workflow_nodes = Table(
    "workflow_nodes",
    metadata,
    Column(
        "workflow_definition_id",
        ID,
        ForeignKey("workflow_definitions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("ordinal", Integer, primary_key=True),
    Column("id", ID, nullable=False),
    Column("name", String(255), nullable=False),
    Column("kind", String(32), nullable=False),
    Column("description", String(4000)),
    UniqueConstraint("workflow_definition_id", "id"),
)
workflow_edges = Table(
    "workflow_edges",
    metadata,
    Column(
        "workflow_definition_id",
        ID,
        ForeignKey("workflow_definitions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("ordinal", Integer, primary_key=True),
    Column("id", ID, nullable=False),
    Column("source_node_id", ID, nullable=False),
    Column("target_node_id", ID, nullable=False),
    UniqueConstraint("workflow_definition_id", "id"),
)
workflow_entries = Table(
    "workflow_entries",
    metadata,
    Column(
        "workflow_definition_id",
        ID,
        ForeignKey("workflow_definitions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("ordinal", Integer, primary_key=True),
    Column("node_id", ID, nullable=False),
)
workflow_runs = Table(
    "workflow_runs",
    metadata,
    Column("id", ID, primary_key=True),
    Column("organization_id", ID, ForeignKey("organizations.id"), nullable=False),
    Column(
        "workflow_definition_id",
        ID,
        ForeignKey("workflow_definitions.id"),
        nullable=False,
    ),
    Column("status", String(32), nullable=False),
    Column("created_at", TS, nullable=False),
    Column("started_at", TS),
    Column("finished_at", TS),
    Column("trace_actor_id", ID),
    Column("trace_actor_type", String(64)),
    Column("trace_actor_kind", String(32)),
    Column("trace_correlation_id", ID),
    Column("trace_idempotency_key", ID),
    Column("trace_causation_id", ID),
)
node_runs = Table(
    "node_runs",
    metadata,
    Column("id", ID, primary_key=True),
    Column(
        "workflow_run_id",
        ID,
        ForeignKey("workflow_runs.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("node_definition_id", ID, nullable=False),
    Column("status", String(32), nullable=False),
    Column("created_at", TS, nullable=False),
    Column("started_at", TS),
    Column("finished_at", TS),
)
node_attempts = Table(
    "node_attempts",
    metadata,
    Column("id", ID, primary_key=True),
    Column(
        "node_run_id",
        ID,
        ForeignKey("node_runs.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("attempt_number", Integer, nullable=False),
    Column("status", String(32), nullable=False),
    Column("created_at", TS, nullable=False),
    Column("started_at", TS),
    Column("finished_at", TS),
    Column("trace_actor_id", ID),
    Column("trace_actor_type", String(64)),
    Column("trace_actor_kind", String(32)),
    Column("trace_correlation_id", ID),
    Column("trace_idempotency_key", ID),
    Column("trace_causation_id", ID),
    UniqueConstraint("node_run_id", "attempt_number"),
    CheckConstraint("attempt_number >= 1", name="positive_attempt_number"),
)

agent_definitions = Table(
    "agent_definitions",
    metadata,
    Column("id", ID, nullable=False),
    Column("organization_id", ID, ForeignKey("organizations.id"), nullable=False),
    Column("version_subject", VERSION, nullable=False),
    Column("version", VERSION, nullable=False),
    Column("name", String(255), nullable=False),
    Column("purpose", String(4000), nullable=False),
    PrimaryKeyConstraint("id", "version_subject", "version"),
)
agent_capabilities = Table(
    "agent_capabilities",
    metadata,
    Column("agent_definition_id", ID, nullable=False),
    Column("version_subject", VERSION, nullable=False),
    Column("version", VERSION, nullable=False),
    Column("ordinal", Integer, nullable=False),
    Column("identifier", String(255), nullable=False),
    ForeignKeyConstraint(
        ["agent_definition_id", "version_subject", "version"],
        [
            "agent_definitions.id",
            "agent_definitions.version_subject",
            "agent_definitions.version",
        ],
        name="fk_agent_capabilities_exact_definition",
        ondelete="CASCADE",
    ),
    PrimaryKeyConstraint(
        "agent_definition_id", "version_subject", "version", "ordinal"
    ),
)
agent_invocations = Table(
    "agent_invocations",
    metadata,
    Column("id", ID, primary_key=True),
    Column("agent_definition_id", ID, nullable=False),
    Column("version_subject", VERSION, nullable=False),
    Column("version", VERSION, nullable=False),
    Column("invoked_at", TS, nullable=False),
    Column("trace_actor_id", ID, nullable=False),
    Column("trace_actor_type", String(64), nullable=False),
    Column("trace_actor_kind", String(32), nullable=False),
    Column("trace_correlation_id", ID, nullable=False),
    Column("trace_idempotency_key", ID, nullable=False),
    Column("trace_causation_id", ID),
    ForeignKeyConstraint(
        ["agent_definition_id", "version_subject", "version"],
        [
            "agent_definitions.id",
            "agent_definitions.version_subject",
            "agent_definitions.version",
        ],
        name="fk_agent_invocations_exact_definition",
    ),
)


__all__ = ["metadata"]
