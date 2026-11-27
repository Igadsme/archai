"""User accounts and managed, scoped API keys on the existing identity tables."""
import sqlalchemy as sa
from alembic import op

revision = "0008_identity"
down_revision = "0007_research_projects"
branch_labels = None
depends_on = None

_NOW = sa.text("CURRENT_TIMESTAMP")


def upgrade():
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("display_name", sa.String(128), nullable=False, server_default=""))
        batch.add_column(sa.Column("role", sa.String(16), nullable=False, server_default="member"))
        batch.add_column(sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_NOW))
        batch.add_column(sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True))
    with op.batch_alter_table("api_credentials") as batch:
        batch.add_column(sa.Column("name", sa.String(128), nullable=False, server_default=""))
        batch.add_column(sa.Column("key_prefix", sa.String(16), nullable=False, server_default=""))
        batch.add_column(sa.Column("scopes", sa.JSON(), nullable=False, server_default='["read"]'))
        batch.add_column(sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_NOW))
        batch.add_column(sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("rotated_from", sa.String(64), nullable=True))


def downgrade():
    with op.batch_alter_table("api_credentials") as batch:
        for column in ("rotated_from", "expires_at", "last_used_at", "created_at", "scopes", "key_prefix", "name"):
            batch.drop_column(column)
    with op.batch_alter_table("users") as batch:
        for column in ("disabled_at", "created_at", "role", "display_name"):
            batch.drop_column(column)
