"""Add tenant-owned LIVE business profiles."""

from alembic import op
import sqlalchemy as sa


revision = "0002_org_business_profiles"
down_revision = "0001_initial_persistence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organization_business_profiles",
        sa.Column("organization_id", sa.String(length=255), nullable=False),
        sa.Column("profile_data", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_organization_business_profiles_organization_id_organizations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id", name="pk_organization_business_profiles"
        ),
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE organization_business_profiles ENABLE ROW LEVEL SECURITY"
        )
        op.execute(
            "ALTER TABLE organization_business_profiles FORCE ROW LEVEL SECURITY"
        )
        op.execute(
            """
            CREATE POLICY tenant_business_profile_isolation
            ON organization_business_profiles
            USING (
                organization_id = current_setting('aeos.organization_id', true)
            )
            WITH CHECK (
                organization_id = current_setting('aeos.organization_id', true)
            )
            """
        )


def downgrade() -> None:
    op.drop_table("organization_business_profiles")
