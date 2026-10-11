"""Merge cloud preference history with saved workspace views, without data edits."""
revision = "20261015_merge_workspace_views"
down_revision = ("20261013_workspace_views", "20261014_view_preferences")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    raise RuntimeError("Preserve workspace history; use a reviewed forward migration.")
