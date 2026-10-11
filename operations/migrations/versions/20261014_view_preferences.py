"""Personal and company presentation settings; SKU images use existing JSON data."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision = "20261014_view_preferences"
down_revision = "20261013_invoice_editor"
branch_labels = depends_on = None
def upgrade():
    op.create_table("view_preferences_v1",
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants_v1.id"), primary_key=True),
        sa.Column("subject", sa.String(), primary_key=True),
        sa.Column("page", sa.String(), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("settings", JSONB, nullable=False))
def downgrade():
    raise RuntimeError("Preserve saved views; use a forward migration.")
