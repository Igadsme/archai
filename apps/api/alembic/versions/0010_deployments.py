"""Local model deployments."""
import sqlalchemy as sa
from alembic import op

revision = "0010_deployments"
down_revision = "0009_latency_measurements"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "deployments",
        sa.Column("deployment_id", sa.String(64), primary_key=True),
        sa.Column("architecture_id", sa.String(64), sa.ForeignKey(
            "architectures.architecture_id", name="fk_deployment_architecture", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("record", sa.JSON(), nullable=False),
    )
    op.create_index("ix_deployments_architecture_id", "deployments", ["architecture_id"])


def downgrade():
    op.drop_index("ix_deployments_architecture_id", table_name="deployments")
    op.drop_table("deployments")
