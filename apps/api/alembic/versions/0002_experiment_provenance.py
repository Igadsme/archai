"""Persist experiment provenance and lifecycle timestamps."""
import sqlalchemy as sa
from alembic import op

revision = "0002_experiment_provenance"
down_revision = "0001_models"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("experiments", sa.Column("provenance", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("experiments", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("experiments", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("experiments", "completed_at")
    op.drop_column("experiments", "started_at")
    op.drop_column("experiments", "provenance")
