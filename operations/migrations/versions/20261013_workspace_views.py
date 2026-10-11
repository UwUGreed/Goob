"""Add personal workspace views and owner-published defaults; retain CRM records."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "20261013_workspace_views"
down_revision = "20261012_service_memberships"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("workspace_views_v1",
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants_v1.id"), primary_key=True),
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("subject", sa.String(), nullable=False),
        sa.Column("page", sa.String(), nullable=False),
        sa.Column("scope", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("configuration", JSONB(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("page IN ('overview','dispatch')"),
        sa.CheckConstraint("scope IN ('personal','team')"))
    op.create_table("workspace_selections_v1",
        sa.Column("tenant_id", sa.String(), primary_key=True),
        sa.Column("subject", sa.String(), primary_key=True),
        sa.Column("page", sa.String(), primary_key=True),
        sa.Column("view_id", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id", "subject"], ["memberships_v1.tenant_id", "memberships_v1.subject"]),
        sa.ForeignKeyConstraint(["tenant_id", "view_id"], ["workspace_views_v1.tenant_id", "workspace_views_v1.id"]),
        sa.CheckConstraint("page IN ('overview','dispatch')"))


def downgrade():
    raise RuntimeError("Preserve saved workspace views; use a reviewed forward migration.")
