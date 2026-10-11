"""Restore the additive service-plan schema already present in Tiger Cloud.

This revision was reconstructed from the live database schema because its source
had not been pushed to GitHub. It does not modify existing records or plans.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "20261012_service_memberships"
down_revision = "20261011_portal_dispatch"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("records_v1", sa.Column("portal_meta", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.add_column("agreements_v1", sa.Column("portal_meta", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.create_table(
        "service_plans_v1",
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("branch_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("configuration", JSONB(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["tenant_id", "branch_id"], ["branches_v1.tenant_id", "branches_v1.id"]),
        sa.PrimaryKeyConstraint("tenant_id", "id"),
    )


def downgrade():
    raise RuntimeError("Service plans and portal metadata may contain user records; use a reviewed forward migration.")
