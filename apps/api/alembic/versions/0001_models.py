"""Create core ArchAI metadata tables."""
from alembic import op
import sqlalchemy as sa

revision = "0001_models"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("architectures",
        sa.Column("architecture_id", sa.String(64), primary_key=True),
        sa.Column("schema_version", sa.String(16), nullable=False),
        sa.Column("search_space", sa.String(128), nullable=False),
        sa.Column("canonical_json", sa.JSON(), nullable=False),
        sa.Column("generator_version", sa.String(128), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=True))
    op.create_table("search_sessions",
        sa.Column("search_id", sa.String(64), primary_key=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("algorithm", sa.String(64), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("budget_evaluations", sa.Integer(), nullable=False),
        sa.Column("consumed_evaluations", sa.Integer(), nullable=False, server_default="0"))
    op.create_table("experiments",
        sa.Column("experiment_id", sa.String(64), primary_key=True),
        sa.Column("architecture_id", sa.String(64), nullable=False),
        sa.Column("dataset_id", sa.String(128), nullable=False),
        sa.Column("dataset_version", sa.String(128), nullable=False),
        sa.Column("evidence_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("failure_detail", sa.Text(), nullable=True))


def downgrade():
    op.drop_table("experiments")
    op.drop_table("search_sessions")
    op.drop_table("architectures")
