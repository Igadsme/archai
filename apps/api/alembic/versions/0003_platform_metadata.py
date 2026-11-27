"""Create identity, dataset, and checkpoint metadata tables."""
import sqlalchemy as sa
from alembic import op

revision = "0003_platform_metadata"
down_revision = "0002_experiment_provenance"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("users",
        sa.Column("user_id", sa.String(64), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True))
    op.create_table("api_credentials",
        sa.Column("credential_id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("key_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table("datasets",
        sa.Column("dataset_id", sa.String(128), primary_key=True),
        sa.Column("version", sa.String(128), primary_key=True),
        sa.Column("checksum", sa.String(128), nullable=False),
        sa.Column("uri", sa.Text(), nullable=False),
        sa.Column("license", sa.String(256), nullable=True))
    op.create_table("model_checkpoints",
        sa.Column("checkpoint_id", sa.String(64), primary_key=True),
        sa.Column("model_kind", sa.String(32), nullable=False),
        sa.Column("version", sa.String(128), nullable=False),
        sa.Column("artifact_uri", sa.Text(), nullable=False),
        sa.Column("checksum", sa.String(128), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"))


def downgrade():
    op.drop_table("model_checkpoints")
    op.drop_table("datasets")
    op.drop_table("api_credentials")
    op.drop_table("users")
