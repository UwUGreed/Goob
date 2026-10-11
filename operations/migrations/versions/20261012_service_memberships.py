"""Add service plans and explicit portal metadata; retain existing records."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision = "20261012_service_memberships"
down_revision = "20261011_portal_dispatch"
branch_labels = None
depends_on = None

def upgrade():
    for table in ["records_v1", "agreements_v1"]:
        op.add_column(table, sa.Column("portal_meta", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.create_table("service_plans_v1", sa.Column("tenant_id", sa.String(), primary_key=True), sa.Column("id", sa.String(), primary_key=True), sa.Column("branch_id", sa.String(), nullable=False), sa.Column("name", sa.String(), nullable=False), sa.Column("configuration", JSONB(), nullable=False), sa.Column("revision", sa.Integer(), nullable=False, server_default="1"), sa.ForeignKeyConstraint(["tenant_id", "branch_id"], ["branches_v1.tenant_id", "branches_v1.id"]))
    op.execute("""WITH numbered AS (
        SELECT tenant_id,id,2000+row_number() OVER (PARTITION BY tenant_id ORDER BY created_at,id) AS number
        FROM records_v1 WHERE kind='jobs'
    ) UPDATE records_v1 AS r SET portal_meta=r.portal_meta || jsonb_build_object('displayNumber',n.number::text)
      FROM numbered AS n WHERE r.tenant_id=n.tenant_id AND r.id=n.id AND NOT (r.portal_meta ? 'displayNumber')""")

def downgrade():
    raise RuntimeError("Retain membership and audit history; use a reviewed forward migration.")
