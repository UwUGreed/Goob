"""Extend the existing invoice ledger for independent reviewed invoices."""
from alembic import op
import sqlalchemy as sa

revision = "20261013_invoice_editor"
down_revision = "20261012_service_memberships"
branch_labels = depends_on = None


def upgrade():
    op.execute("CREATE SEQUENCE invoice_number_v1")
    op.alter_column("invoices_v1", "job_id", nullable=True)
    op.alter_column("invoices_v1", "proposal_id", nullable=True)
    for name in ("customer_id", "property_id", "number"):
        op.add_column("invoices_v1", sa.Column(name, sa.String(), nullable=True))
    op.add_column("invoices_v1", sa.Column("status", sa.String(), nullable=False, server_default="approved_draft"))
    op.add_column("invoices_v1", sa.Column("revision", sa.Integer(), nullable=False, server_default="1"))
    for name in ("customer_id", "property_id"):
        op.create_foreign_key("invoice_"+name+"_fk", "invoices_v1", "records_v1", ["tenant_id", name], ["tenant_id", "id"])
    op.create_unique_constraint("invoice_number_unique", "invoices_v1", ["tenant_id", "number"])


def downgrade():
    raise RuntimeError("Invoice history must be preserved; use a forward migration.")
