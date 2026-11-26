"""Add the research_projects table (Studio project entity)."""
import sqlalchemy as sa
from alembic import op

revision = "0007_research_projects"
down_revision = "0006_experiment_started_at"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "research_projects",
        sa.Column("project_id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("task", sa.String(128), nullable=False),
        sa.Column("dataset_id", sa.String(128), nullable=True),
        sa.Column("dataset_version", sa.String(128), nullable=True),
        sa.Column("constraints", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"),
                  nullable=False),
    )


def downgrade():
    op.drop_table("research_projects")
