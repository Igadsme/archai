"""Make experiment start timestamps durable and non-null."""
from alembic import op
import sqlalchemy as sa


revision = "0006_experiment_started_at"
down_revision = "0005_integrity_constraints"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(sa.text("UPDATE experiments SET started_at = CURRENT_TIMESTAMP WHERE started_at IS NULL"))
    with op.batch_alter_table("experiments") as batch:
        batch.alter_column("started_at", existing_type=sa.DateTime(timezone=True),
                           nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"))


def downgrade():
    with op.batch_alter_table("experiments") as batch:
        batch.alter_column("started_at", existing_type=sa.DateTime(timezone=True),
                           nullable=True, server_default=None)
