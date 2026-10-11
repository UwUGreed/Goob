"""Add portal sessions and database dispatch metadata; retain all existing records."""
from alembic import op
import sqlalchemy as sa

revision = "20261011_portal_dispatch"
down_revision = "2558cea32be8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("portal_users_v1", sa.Column("id", sa.String(), primary_key=True), sa.Column("identifier", sa.String(), nullable=False, unique=True), sa.Column("password_hash", sa.String(), nullable=False), sa.Column("tenant_id", sa.String(), nullable=False), sa.Column("subject", sa.String(), nullable=False), sa.Column("demo", sa.Boolean(), nullable=False, server_default=sa.false()), sa.ForeignKeyConstraint(["tenant_id", "subject"], ["memberships_v1.tenant_id", "memberships_v1.subject"]))
    op.create_table("portal_sessions_v1", sa.Column("token_hash", sa.String(), primary_key=True), sa.Column("user_id", sa.String(), sa.ForeignKey("portal_users_v1.id"), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_portal_sessions_v1_expires_at", "portal_sessions_v1", ["expires_at"])
    op.create_table("portal_login_attempts_v1", sa.Column("key", sa.String(), primary_key=True), sa.Column("attempts", sa.Integer(), nullable=False), sa.Column("window_start", sa.DateTime(timezone=True), nullable=False))
    op.create_table("dispatch_technicians_v1", sa.Column("tenant_id", sa.String(), primary_key=True), sa.Column("id", sa.String(), primary_key=True), sa.Column("branch_id", sa.String(), nullable=False), sa.Column("name", sa.String(), nullable=False), sa.Column("trade", sa.String(), nullable=False), sa.Column("location_id", sa.String(), nullable=False), sa.Column("node", sa.String(), nullable=False), sa.Column("status", sa.String(), nullable=False), sa.Column("job_id", sa.String()), sa.ForeignKeyConstraint(["tenant_id", "branch_id"], ["branches_v1.tenant_id", "branches_v1.id"]), sa.ForeignKeyConstraint(["tenant_id", "location_id"], ["records_v1.tenant_id", "records_v1.id"]), sa.ForeignKeyConstraint(["tenant_id", "job_id"], ["records_v1.tenant_id", "records_v1.id"]), sa.CheckConstraint("trade IN ('Plumbing', 'HVAC', 'Electrical')"))
    op.create_table("dispatch_visits_v1", sa.Column("tenant_id", sa.String(), primary_key=True), sa.Column("id", sa.String(), primary_key=True), sa.Column("branch_id", sa.String(), nullable=False), sa.Column("job_id", sa.String(), nullable=False), sa.Column("technician_id", sa.String()), sa.Column("status", sa.String(), nullable=False), sa.Column("node", sa.String(), nullable=False), sa.Column("description", sa.String(), nullable=False), sa.Column("urgent", sa.Boolean(), nullable=False), sa.Column("requested", sa.String(), nullable=False), sa.Column("date", sa.String()), sa.Column("start", sa.BigInteger()), sa.Column("end", sa.BigInteger()), sa.Column("travel_start", sa.BigInteger()), sa.ForeignKeyConstraint(["tenant_id", "branch_id"], ["branches_v1.tenant_id", "branches_v1.id"]), sa.ForeignKeyConstraint(["tenant_id", "job_id"], ["records_v1.tenant_id", "records_v1.id"]), sa.ForeignKeyConstraint(["tenant_id", "technician_id"], ["dispatch_technicians_v1.tenant_id", "dispatch_technicians_v1.id"]), sa.UniqueConstraint("tenant_id", "job_id"), sa.CheckConstraint("status IN ('Unassigned','Assigned','En route','Arrived','Working','Completed')"))


def downgrade():
    raise RuntimeError("This additive release preserves user records; use a reviewed forward migration.")
