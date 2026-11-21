"""Allow named model IDs independent of model kind."""
from alembic import op
import sqlalchemy as sa


revision = "0004_model_identifiers"
down_revision = "0003_platform_metadata"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("model_checkpoints", sa.Column("model_id", sa.String(128), nullable=True))
    op.execute(sa.text("UPDATE model_checkpoints SET model_id = model_kind WHERE model_id IS NULL"))
    op.create_index("uq_model_checkpoints_model_id_version", "model_checkpoints",
                    ["model_id", "version"], unique=True)


def downgrade():
    op.drop_index("uq_model_checkpoints_model_id_version", table_name="model_checkpoints")
    op.drop_column("model_checkpoints", "model_id")
