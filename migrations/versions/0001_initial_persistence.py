"""Initial PostgreSQL persistence baseline.

This revision is intentionally frozen. It describes the historical database
shape directly instead of importing the mutable runtime table metadata.
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial_persistence"
down_revision = None
branch_labels = None
depends_on = None

ID = sa.String(length=255)
VERSION = sa.String(length=255)
TS = sa.TIMESTAMP(timezone=True)
AMOUNT = sa.Numeric(precision=38, scale=18, asdecimal=True)


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", ID, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_constitution_subject", VERSION),
        sa.Column("current_constitution_version", VERSION),
        sa.PrimaryKeyConstraint("id", name="pk_organizations"),
    )
    op.create_table(
        "roles",
        sa.Column("id", ID, nullable=False),
        sa.Column(
            "organization_id",
            ID,
            sa.ForeignKey(
                "organizations.id",
                name="fk_roles_organization_id_organizations",
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("responsibilities", sa.String(length=4000)),
        sa.PrimaryKeyConstraint("id", name="pk_roles"),
        sa.UniqueConstraint("organization_id", "id", name="uq_roles_organization_id"),
    )
    op.create_table(
        "role_assignments",
        sa.Column("id", ID, nullable=False),
        sa.Column(
            "organization_id",
            ID,
            sa.ForeignKey(
                "organizations.id",
                name="fk_role_assignments_organization_id_organizations",
            ),
            nullable=False,
        ),
        sa.Column(
            "role_id",
            ID,
            sa.ForeignKey("roles.id", name="fk_role_assignments_role_id_roles"),
            nullable=False,
        ),
        sa.Column("actor_id", ID, nullable=False),
        sa.Column("actor_type", sa.String(length=64), nullable=False),
        sa.Column("actor_kind", sa.String(length=32), nullable=False),
        sa.Column("starts_at", TS, nullable=False),
        sa.Column("ends_at", TS),
        sa.PrimaryKeyConstraint("id", name="pk_role_assignments"),
    )
    op.create_table(
        "constitution_versions",
        sa.Column("id", ID, nullable=False),
        sa.Column(
            "organization_id",
            ID,
            sa.ForeignKey(
                "organizations.id",
                name="fk_constitution_versions_organization_id_organizations",
            ),
            nullable=False,
        ),
        sa.Column("version_subject", VERSION, nullable=False),
        sa.Column("version", VERSION, nullable=False),
        sa.Column("content_algorithm", sa.String(length=32), nullable=False),
        sa.Column("content_digest", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("published_at", TS, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_constitution_versions"),
        sa.UniqueConstraint(
            "organization_id",
            "version_subject",
            "version",
            name="uq_constitution_versions_organization_id",
        ),
    )
    op.create_table(
        "policy_versions",
        sa.Column("id", ID, nullable=False),
        sa.Column(
            "organization_id",
            ID,
            sa.ForeignKey(
                "organizations.id",
                name="fk_policy_versions_organization_id_organizations",
            ),
            nullable=False,
        ),
        sa.Column("version_subject", VERSION, nullable=False),
        sa.Column("version", VERSION, nullable=False),
        sa.Column("content_algorithm", sa.String(length=32), nullable=False),
        sa.Column("content_digest", sa.String(length=128), nullable=False),
        sa.Column("policy_key", sa.String(length=255), nullable=False),
        sa.Column("published_at", TS, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_policy_versions"),
        sa.UniqueConstraint(
            "organization_id",
            "version_subject",
            "version",
            name="uq_policy_versions_organization_id",
        ),
    )
    op.create_table(
        "permission_grants",
        sa.Column("id", ID, nullable=False),
        sa.Column(
            "organization_id",
            ID,
            sa.ForeignKey(
                "organizations.id",
                name="fk_permission_grants_organization_id_organizations",
            ),
            nullable=False,
        ),
        sa.Column("grantee_id", ID, nullable=False),
        sa.Column("grantee_type", sa.String(length=64), nullable=False),
        sa.Column("grantee_kind", sa.String(length=32)),
        sa.Column("capability", sa.String(length=255), nullable=False),
        sa.Column("scope_kind", sa.String(length=64), nullable=False),
        sa.Column("policy_subject", VERSION, nullable=False),
        sa.Column("policy_version", VERSION, nullable=False),
        sa.Column("constitution_subject", VERSION),
        sa.Column("constitution_version", VERSION),
        sa.Column("valid_from", TS, nullable=False),
        sa.Column("valid_until", TS),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("trace_actor_id", ID, nullable=False),
        sa.Column("trace_actor_type", sa.String(length=64), nullable=False),
        sa.Column("trace_actor_kind", sa.String(length=32), nullable=False),
        sa.Column("trace_correlation_id", ID, nullable=False),
        sa.Column("trace_idempotency_key", ID, nullable=False),
        sa.Column("trace_causation_id", ID),
        sa.PrimaryKeyConstraint("id", name="pk_permission_grants"),
    )
    op.create_table(
        "governance_decisions",
        sa.Column("id", ID, nullable=False),
        sa.Column(
            "organization_id",
            ID,
            sa.ForeignKey(
                "organizations.id",
                name="fk_governance_decisions_organization_id_organizations",
            ),
            nullable=False,
        ),
        sa.Column("result", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=4000), nullable=False),
        sa.Column("constitution_subject", VERSION, nullable=False),
        sa.Column("constitution_version", VERSION, nullable=False),
        sa.Column("decided_at", TS, nullable=False),
        sa.Column("evaluated_actor_id", ID),
        sa.Column("evaluated_actor_type", sa.String(length=64)),
        sa.Column("evaluated_actor_kind", sa.String(length=32)),
        sa.Column("trace_actor_id", ID, nullable=False),
        sa.Column("trace_actor_type", sa.String(length=64), nullable=False),
        sa.Column("trace_actor_kind", sa.String(length=32), nullable=False),
        sa.Column("trace_correlation_id", ID, nullable=False),
        sa.Column("trace_idempotency_key", ID, nullable=False),
        sa.Column("trace_causation_id", ID),
        sa.PrimaryKeyConstraint("id", name="pk_governance_decisions"),
    )
    op.create_table(
        "governance_decision_policies",
        sa.Column("governance_decision_id", ID, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("version_subject", VERSION, nullable=False),
        sa.Column("version", VERSION, nullable=False),
        sa.ForeignKeyConstraint(
            ["governance_decision_id"],
            ["governance_decisions.id"],
            name="fk_governance_decision_policies_governance_decision_id__2ad8",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "governance_decision_id",
            "ordinal",
            name="pk_governance_decision_policies",
        ),
    )
    op.create_table(
        "approval_requests",
        sa.Column("id", ID, nullable=False),
        sa.Column(
            "organization_id",
            ID,
            sa.ForeignKey(
                "organizations.id",
                name="fk_approval_requests_organization_id_organizations",
            ),
            nullable=False,
        ),
        sa.Column("requester_id", ID, nullable=False),
        sa.Column("requester_type", sa.String(length=64), nullable=False),
        sa.Column("requester_kind", sa.String(length=32), nullable=False),
        sa.Column("capability", sa.String(length=255), nullable=False),
        sa.Column("reason", sa.String(length=4000), nullable=False),
        sa.Column("requested_at", TS, nullable=False),
        sa.Column("expires_at", TS),
        sa.Column("constitution_subject", VERSION),
        sa.Column("constitution_version", VERSION),
        sa.Column(
            "governance_decision_id",
            ID,
            sa.ForeignKey(
                "governance_decisions.id",
                name="fk_approval_requests_governance_decision_id_governance__6d6a",
            ),
        ),
        sa.Column(
            "required_role_id",
            ID,
            sa.ForeignKey(
                "roles.id", name="fk_approval_requests_required_role_id_roles"
            ),
        ),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("trace_actor_id", ID, nullable=False),
        sa.Column("trace_actor_type", sa.String(length=64), nullable=False),
        sa.Column("trace_actor_kind", sa.String(length=32), nullable=False),
        sa.Column("trace_correlation_id", ID, nullable=False),
        sa.Column("trace_idempotency_key", ID, nullable=False),
        sa.Column("trace_causation_id", ID),
        sa.PrimaryKeyConstraint("id", name="pk_approval_requests"),
    )
    op.create_table(
        "approval_request_policies",
        sa.Column("approval_request_id", ID, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("version_subject", VERSION, nullable=False),
        sa.Column("version", VERSION, nullable=False),
        sa.ForeignKeyConstraint(
            ["approval_request_id"],
            ["approval_requests.id"],
            name="fk_approval_request_policies_approval_request_id_approv_e134",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "approval_request_id", "ordinal", name="pk_approval_request_policies"
        ),
    )
    op.create_table(
        "approval_decisions",
        sa.Column("id", ID, nullable=False),
        sa.Column(
            "approval_request_id",
            ID,
            sa.ForeignKey(
                "approval_requests.id",
                name="fk_approval_decisions_approval_request_id_approval_requests",
            ),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            ID,
            sa.ForeignKey(
                "organizations.id",
                name="fk_approval_decisions_organization_id_organizations",
            ),
            nullable=False,
        ),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("decided_by_id", ID, nullable=False),
        sa.Column("decided_by_type", sa.String(length=64), nullable=False),
        sa.Column("decided_by_kind", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=4000), nullable=False),
        sa.Column("decided_at", TS, nullable=False),
        sa.Column("constitution_subject", VERSION),
        sa.Column("constitution_version", VERSION),
        sa.Column("trace_actor_id", ID, nullable=False),
        sa.Column("trace_actor_type", sa.String(length=64), nullable=False),
        sa.Column("trace_actor_kind", sa.String(length=32), nullable=False),
        sa.Column("trace_correlation_id", ID, nullable=False),
        sa.Column("trace_idempotency_key", ID, nullable=False),
        sa.Column("trace_causation_id", ID),
        sa.PrimaryKeyConstraint("id", name="pk_approval_decisions"),
    )
    op.create_table(
        "approval_decision_policies",
        sa.Column("approval_decision_id", ID, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("version_subject", VERSION, nullable=False),
        sa.Column("version", VERSION, nullable=False),
        sa.ForeignKeyConstraint(
            ["approval_decision_id"],
            ["approval_decisions.id"],
            name="fk_approval_decision_policies_approval_decision_id_appr_6a38",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "approval_decision_id", "ordinal", name="pk_approval_decision_policies"
        ),
    )
    op.create_table(
        "resources",
        sa.Column("id", ID, nullable=False),
        sa.Column(
            "organization_id",
            ID,
            sa.ForeignKey(
                "organizations.id",
                name="fk_resources_organization_id_organizations",
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("unit", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=4000)),
        sa.PrimaryKeyConstraint("id", name="pk_resources"),
    )
    op.create_table(
        "resource_accounts",
        sa.Column("id", ID, nullable=False),
        sa.Column(
            "organization_id",
            ID,
            sa.ForeignKey(
                "organizations.id",
                name="fk_resource_accounts_organization_id_organizations",
            ),
            nullable=False,
        ),
        sa.Column(
            "resource_id",
            ID,
            sa.ForeignKey(
                "resources.id", name="fk_resource_accounts_resource_id_resources"
            ),
            nullable=False,
        ),
        sa.Column("account_type", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255)),
        sa.PrimaryKeyConstraint("id", name="pk_resource_accounts"),
    )
    op.create_table(
        "budgets",
        sa.Column("id", ID, nullable=False),
        sa.Column(
            "organization_id",
            ID,
            sa.ForeignKey(
                "organizations.id", name="fk_budgets_organization_id_organizations"
            ),
            nullable=False,
        ),
        sa.Column("purpose", sa.String(length=4000), nullable=False),
        sa.Column("valid_from", TS, nullable=False),
        sa.Column("valid_until", TS),
        sa.Column("trace_actor_id", ID, nullable=False),
        sa.Column("trace_actor_type", sa.String(length=64), nullable=False),
        sa.Column("trace_actor_kind", sa.String(length=32), nullable=False),
        sa.Column("trace_correlation_id", ID, nullable=False),
        sa.Column("trace_idempotency_key", ID, nullable=False),
        sa.Column("trace_causation_id", ID),
        sa.PrimaryKeyConstraint("id", name="pk_budgets"),
    )
    op.create_table(
        "budget_limits",
        sa.Column("budget_id", ID, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column(
            "resource_id",
            ID,
            sa.ForeignKey(
                "resources.id", name="fk_budget_limits_resource_id_resources"
            ),
            nullable=False,
        ),
        sa.Column("quantity", AMOUNT, nullable=False),
        sa.Column("unit", sa.String(length=255), nullable=False),
        sa.Column("period_start", TS, nullable=False),
        sa.Column("period_end", TS),
        sa.ForeignKeyConstraint(
            ["budget_id"],
            ["budgets.id"],
            name="fk_budget_limits_budget_id_budgets",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("budget_id", "ordinal", name="pk_budget_limits"),
        sa.CheckConstraint("quantity > 0", name="ck_budget_limits_positive_quantity"),
    )
    op.create_table(
        "reservations",
        sa.Column("id", ID, nullable=False),
        sa.Column(
            "budget_id",
            ID,
            sa.ForeignKey("budgets.id", name="fk_reservations_budget_id_budgets"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            ID,
            sa.ForeignKey(
                "organizations.id",
                name="fk_reservations_organization_id_organizations",
            ),
            nullable=False,
        ),
        sa.Column(
            "resource_id",
            ID,
            sa.ForeignKey("resources.id", name="fk_reservations_resource_id_resources"),
            nullable=False,
        ),
        sa.Column("quantity", AMOUNT, nullable=False),
        sa.Column("unit", sa.String(length=255), nullable=False),
        sa.Column("reserved_at", TS, nullable=False),
        sa.Column("expires_at", TS),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("resolved_at", TS),
        sa.Column("trace_actor_id", ID, nullable=False),
        sa.Column("trace_actor_type", sa.String(length=64), nullable=False),
        sa.Column("trace_actor_kind", sa.String(length=32), nullable=False),
        sa.Column("trace_correlation_id", ID, nullable=False),
        sa.Column("trace_idempotency_key", ID, nullable=False),
        sa.Column("trace_causation_id", ID),
        sa.PrimaryKeyConstraint("id", name="pk_reservations"),
        sa.CheckConstraint("quantity > 0", name="ck_reservations_positive_quantity"),
    )
    op.create_table(
        "economic_transactions",
        sa.Column("id", ID, nullable=False),
        sa.Column(
            "organization_id",
            ID,
            sa.ForeignKey(
                "organizations.id",
                name="fk_economic_transactions_organization_id_organizations",
            ),
            nullable=False,
        ),
        sa.Column("transaction_type", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", TS, nullable=False),
        sa.Column("effective_at", TS, nullable=False),
        sa.Column("trace_actor_id", ID, nullable=False),
        sa.Column("trace_actor_type", sa.String(length=64), nullable=False),
        sa.Column("trace_actor_kind", sa.String(length=32), nullable=False),
        sa.Column("trace_correlation_id", ID, nullable=False),
        sa.Column("trace_idempotency_key", ID, nullable=False),
        sa.Column("trace_causation_id", ID),
        sa.PrimaryKeyConstraint("id", name="pk_economic_transactions"),
    )
    op.create_table(
        "ledger_postings",
        sa.Column("economic_transaction_id", ID, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column(
            "resource_id",
            ID,
            sa.ForeignKey(
                "resources.id", name="fk_ledger_postings_resource_id_resources"
            ),
            nullable=False,
        ),
        sa.Column(
            "resource_account_id",
            ID,
            sa.ForeignKey(
                "resource_accounts.id",
                name="fk_ledger_postings_resource_account_id_resource_accounts",
            ),
            nullable=False,
        ),
        sa.Column("quantity", AMOUNT, nullable=False),
        sa.Column("unit", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(
            ["economic_transaction_id"],
            ["economic_transactions.id"],
            name="fk_ledger_postings_economic_transaction_id_economic_tra_13a1",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "economic_transaction_id", "ordinal", name="pk_ledger_postings"
        ),
        sa.CheckConstraint("quantity <> 0", name="ck_ledger_postings_nonzero_quantity"),
    )
    op.create_table(
        "experiment_preregistrations",
        sa.Column("id", ID, nullable=False),
        sa.Column(
            "organization_id",
            ID,
            sa.ForeignKey(
                "organizations.id",
                name="fk_experiment_preregistrations_organization_id_organizations",
            ),
            nullable=False,
        ),
        sa.Column("hypothesis", sa.String(length=4000), nullable=False),
        sa.Column("objective", sa.String(length=4000), nullable=False),
        sa.Column("preregistered_at", TS, nullable=False),
        sa.Column("trace_actor_id", ID),
        sa.Column("trace_actor_type", sa.String(length=64)),
        sa.Column("trace_actor_kind", sa.String(length=32)),
        sa.Column("trace_correlation_id", ID),
        sa.Column("trace_idempotency_key", ID),
        sa.Column("trace_causation_id", ID),
        sa.PrimaryKeyConstraint("id", name="pk_experiment_preregistrations"),
    )
    op.create_table(
        "experiment_criteria",
        sa.Column("experiment_id", ID, nullable=False),
        sa.Column("criterion_kind", sa.String(length=16), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(length=4000), nullable=False),
        sa.ForeignKeyConstraint(
            ["experiment_id"],
            ["experiment_preregistrations.id"],
            name="fk_experiment_criteria_experiment_id_experiment_preregi_ea56",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "experiment_id",
            "criterion_kind",
            "ordinal",
            name="pk_experiment_criteria",
        ),
    )
    op.create_table(
        "experiment_exposures",
        sa.Column("experiment_id", ID, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column(
            "resource_id",
            ID,
            sa.ForeignKey(
                "resources.id", name="fk_experiment_exposures_resource_id_resources"
            ),
            nullable=False,
        ),
        sa.Column("quantity", AMOUNT, nullable=False),
        sa.Column("unit", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(
            ["experiment_id"],
            ["experiment_preregistrations.id"],
            name="fk_experiment_exposures_experiment_id_experiment_prereg_802c",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "experiment_id", "ordinal", name="pk_experiment_exposures"
        ),
        sa.CheckConstraint(
            "quantity > 0", name="ck_experiment_exposures_positive_quantity"
        ),
    )
    op.create_table(
        "experiments",
        sa.Column("id", ID, nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", TS),
        sa.Column("finished_at", TS),
        sa.ForeignKeyConstraint(
            ["id"],
            ["experiment_preregistrations.id"],
            name="fk_experiments_id_experiment_preregistrations",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_experiments"),
    )
    op.create_table(
        "workflow_definitions",
        sa.Column("id", ID, nullable=False),
        sa.Column(
            "organization_id",
            ID,
            sa.ForeignKey(
                "organizations.id",
                name="fk_workflow_definitions_organization_id_organizations",
            ),
            nullable=False,
        ),
        sa.Column("version_subject", VERSION, nullable=False),
        sa.Column("version", VERSION, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_workflow_definitions"),
        sa.UniqueConstraint(
            "organization_id",
            "version_subject",
            "version",
            name="uq_workflow_definitions_organization_id",
        ),
    )
    op.create_table(
        "workflow_nodes",
        sa.Column("workflow_definition_id", ID, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("id", ID, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("description", sa.String(length=4000)),
        sa.ForeignKeyConstraint(
            ["workflow_definition_id"],
            ["workflow_definitions.id"],
            name="fk_workflow_nodes_workflow_definition_id_workflow_definitions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "workflow_definition_id", "ordinal", name="pk_workflow_nodes"
        ),
        sa.UniqueConstraint(
            "workflow_definition_id",
            "id",
            name="uq_workflow_nodes_workflow_definition_id",
        ),
    )
    op.create_table(
        "workflow_edges",
        sa.Column("workflow_definition_id", ID, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("id", ID, nullable=False),
        sa.Column("source_node_id", ID, nullable=False),
        sa.Column("target_node_id", ID, nullable=False),
        sa.ForeignKeyConstraint(
            ["workflow_definition_id"],
            ["workflow_definitions.id"],
            name="fk_workflow_edges_workflow_definition_id_workflow_definitions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "workflow_definition_id", "ordinal", name="pk_workflow_edges"
        ),
        sa.UniqueConstraint(
            "workflow_definition_id",
            "id",
            name="uq_workflow_edges_workflow_definition_id",
        ),
    )
    op.create_table(
        "workflow_entries",
        sa.Column("workflow_definition_id", ID, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("node_id", ID, nullable=False),
        sa.ForeignKeyConstraint(
            ["workflow_definition_id"],
            ["workflow_definitions.id"],
            name="fk_workflow_entries_workflow_definition_id_workflow_definitions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "workflow_definition_id", "ordinal", name="pk_workflow_entries"
        ),
    )
    op.create_table(
        "workflow_runs",
        sa.Column("id", ID, nullable=False),
        sa.Column(
            "organization_id",
            ID,
            sa.ForeignKey(
                "organizations.id",
                name="fk_workflow_runs_organization_id_organizations",
            ),
            nullable=False,
        ),
        sa.Column(
            "workflow_definition_id",
            ID,
            sa.ForeignKey(
                "workflow_definitions.id",
                name="fk_workflow_runs_workflow_definition_id_workflow_definitions",
            ),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("started_at", TS),
        sa.Column("finished_at", TS),
        sa.Column("trace_actor_id", ID),
        sa.Column("trace_actor_type", sa.String(length=64)),
        sa.Column("trace_actor_kind", sa.String(length=32)),
        sa.Column("trace_correlation_id", ID),
        sa.Column("trace_idempotency_key", ID),
        sa.Column("trace_causation_id", ID),
        sa.PrimaryKeyConstraint("id", name="pk_workflow_runs"),
    )
    op.create_table(
        "node_runs",
        sa.Column("id", ID, nullable=False),
        sa.Column(
            "workflow_run_id",
            ID,
            sa.ForeignKey(
                "workflow_runs.id",
                name="fk_node_runs_workflow_run_id_workflow_runs",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column("node_definition_id", ID, nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("started_at", TS),
        sa.Column("finished_at", TS),
        sa.PrimaryKeyConstraint("id", name="pk_node_runs"),
    )
    op.create_table(
        "node_attempts",
        sa.Column("id", ID, nullable=False),
        sa.Column(
            "node_run_id",
            ID,
            sa.ForeignKey(
                "node_runs.id",
                name="fk_node_attempts_node_run_id_node_runs",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("started_at", TS),
        sa.Column("finished_at", TS),
        sa.Column("trace_actor_id", ID),
        sa.Column("trace_actor_type", sa.String(length=64)),
        sa.Column("trace_actor_kind", sa.String(length=32)),
        sa.Column("trace_correlation_id", ID),
        sa.Column("trace_idempotency_key", ID),
        sa.Column("trace_causation_id", ID),
        sa.PrimaryKeyConstraint("id", name="pk_node_attempts"),
        sa.UniqueConstraint(
            "node_run_id", "attempt_number", name="uq_node_attempts_node_run_id"
        ),
        sa.CheckConstraint(
            "attempt_number >= 1", name="ck_node_attempts_positive_attempt_number"
        ),
    )
    op.create_table(
        "agent_definitions",
        sa.Column("id", ID, nullable=False),
        sa.Column(
            "organization_id",
            ID,
            sa.ForeignKey(
                "organizations.id",
                name="fk_agent_definitions_organization_id_organizations",
            ),
            nullable=False,
        ),
        sa.Column("version_subject", VERSION, nullable=False),
        sa.Column("version", VERSION, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("purpose", sa.String(length=4000), nullable=False),
        sa.PrimaryKeyConstraint(
            "id", "version_subject", "version", name="pk_agent_definitions"
        ),
    )
    op.create_table(
        "agent_capabilities",
        sa.Column("agent_definition_id", ID, nullable=False),
        sa.Column("version_subject", VERSION, nullable=False),
        sa.Column("version", VERSION, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("identifier", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(
            ["agent_definition_id", "version_subject", "version"],
            [
                "agent_definitions.id",
                "agent_definitions.version_subject",
                "agent_definitions.version",
            ],
            name="fk_agent_capabilities_exact_definition",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "agent_definition_id",
            "version_subject",
            "version",
            "ordinal",
            name="pk_agent_capabilities",
        ),
    )
    op.create_table(
        "agent_invocations",
        sa.Column("id", ID, nullable=False),
        sa.Column(
            "agent_definition_id",
            ID,
            nullable=False,
        ),
        sa.Column("version_subject", VERSION, nullable=False),
        sa.Column("version", VERSION, nullable=False),
        sa.Column("invoked_at", TS, nullable=False),
        sa.Column("trace_actor_id", ID, nullable=False),
        sa.Column("trace_actor_type", sa.String(length=64), nullable=False),
        sa.Column("trace_actor_kind", sa.String(length=32), nullable=False),
        sa.Column("trace_correlation_id", ID, nullable=False),
        sa.Column("trace_idempotency_key", ID, nullable=False),
        sa.Column("trace_causation_id", ID),
        sa.ForeignKeyConstraint(
            ["agent_definition_id", "version_subject", "version"],
            [
                "agent_definitions.id",
                "agent_definitions.version_subject",
                "agent_definitions.version",
            ],
            name="fk_agent_invocations_exact_definition",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_agent_invocations"),
    )


def downgrade() -> None:
    op.drop_table("agent_invocations")
    op.drop_table("agent_capabilities")
    op.drop_table("agent_definitions")
    op.drop_table("node_attempts")
    op.drop_table("node_runs")
    op.drop_table("workflow_runs")
    op.drop_table("workflow_entries")
    op.drop_table("workflow_edges")
    op.drop_table("workflow_nodes")
    op.drop_table("workflow_definitions")
    op.drop_table("experiments")
    op.drop_table("experiment_exposures")
    op.drop_table("experiment_criteria")
    op.drop_table("experiment_preregistrations")
    op.drop_table("ledger_postings")
    op.drop_table("economic_transactions")
    op.drop_table("reservations")
    op.drop_table("budget_limits")
    op.drop_table("budgets")
    op.drop_table("resource_accounts")
    op.drop_table("resources")
    op.drop_table("approval_decision_policies")
    op.drop_table("approval_decisions")
    op.drop_table("approval_request_policies")
    op.drop_table("approval_requests")
    op.drop_table("governance_decision_policies")
    op.drop_table("governance_decisions")
    op.drop_table("permission_grants")
    op.drop_table("policy_versions")
    op.drop_table("constitution_versions")
    op.drop_table("role_assignments")
    op.drop_table("roles")
    op.drop_table("organizations")
