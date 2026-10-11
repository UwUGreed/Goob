"""Extend the existing invoice ledger for independent reviewed invoices."""
from alembic import op
import sqlalchemy as sa

revision = "20261013_invoice_editor"
down_revision = "20261012_service_memberships"
branch_labels = depends_on = None


def upgrade():
    # A cloud database may already contain this schema under the historical
    # preference revision. Reconcile it without replacing invoices or numbers.
    inspector = sa.inspect(op.get_bind())
    columns = {c["name"] for c in inspector.get_columns("invoices_v1")}
    foreign_keys = {c["name"] for c in inspector.get_foreign_keys("invoices_v1")}
    unique = {c["name"] for c in inspector.get_unique_constraints("invoices_v1")}
    op.execute("CREATE SEQUENCE IF NOT EXISTS invoice_number_v1")
    op.alter_column("invoices_v1", "job_id", nullable=True)
    op.alter_column("invoices_v1", "proposal_id", nullable=True)
    for name in ("customer_id", "property_id", "number"):
        if name not in columns:
            op.add_column("invoices_v1", sa.Column(name, sa.String(), nullable=True))
    if "status" not in columns:
        op.add_column("invoices_v1", sa.Column("status", sa.String(), nullable=False, server_default="approved_draft"))
    if "revision" not in columns:
        op.add_column("invoices_v1", sa.Column("revision", sa.Integer(), nullable=False, server_default="1"))
    for name in ("customer_id", "property_id"):
        constraint = "invoice_"+name+"_fk"
        if constraint not in foreign_keys:
            op.create_foreign_key(constraint, "invoices_v1", "records_v1", ["tenant_id", name], ["tenant_id", "id"])
    if "invoice_number_unique" not in unique:
        op.create_unique_constraint("invoice_number_unique", "invoices_v1", ["tenant_id", "number"])


def downgrade():
    raise RuntimeError("Invoice history must be preserved; use a forward migration.")
