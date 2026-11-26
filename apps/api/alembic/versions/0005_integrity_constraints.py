"""Enforce metadata ownership relationships."""
from alembic import op

revision = "0005_integrity_constraints"
down_revision = "0004_model_identifiers"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("api_credentials") as batch:
        batch.create_foreign_key("fk_api_credentials_user", "users", ["user_id"], ["user_id"], ondelete="CASCADE")
    with op.batch_alter_table("experiments") as batch:
        batch.create_foreign_key("fk_experiments_architecture", "architectures",
                                 ["architecture_id"], ["architecture_id"])
        batch.create_foreign_key("fk_experiments_dataset", "datasets",
                                 ["dataset_id", "dataset_version"], ["dataset_id", "version"])


def downgrade():
    with op.batch_alter_table("experiments") as batch:
        batch.drop_constraint("fk_experiments_dataset", type_="foreignkey")
        batch.drop_constraint("fk_experiments_architecture", type_="foreignkey")
    with op.batch_alter_table("api_credentials") as batch:
        batch.drop_constraint("fk_api_credentials_user", type_="foreignkey")
