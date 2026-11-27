"""Measured inference latencies per architecture."""
import sqlalchemy as sa
from alembic import op

revision = "0009_latency_measurements"
down_revision = "0008_identity"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "latency_measurements",
        sa.Column("measurement_id", sa.String(64), primary_key=True),
        sa.Column("architecture_id", sa.String(64), sa.ForeignKey(
            "architectures.architecture_id", name="fk_latency_architecture", ondelete="CASCADE"), nullable=False),
        sa.Column("device", sa.String(16), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
    )
    op.create_index("ix_latency_measurements_architecture_id", "latency_measurements", ["architecture_id"])


def downgrade():
    op.drop_index("ix_latency_measurements_architecture_id", table_name="latency_measurements")
    op.drop_table("latency_measurements")
