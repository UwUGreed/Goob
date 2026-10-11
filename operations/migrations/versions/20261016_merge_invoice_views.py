"""Join invoice and main workspace histories without editing business records."""
revision = "20261016_merge_invoice_views"
down_revision = ("20261015_merge_workspace_views", "20261013_invoice_editor")
branch_labels = depends_on = None


def upgrade():
    pass


def downgrade():
    raise RuntimeError("Preserve invoice and workspace history; use a forward migration.")
