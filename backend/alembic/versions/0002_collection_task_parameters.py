"""Add persisted collection task parameters."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_collection_task_parameters"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "collection_tasks",
        sa.Column("parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
    )
    op.alter_column("collection_tasks", "parameters", server_default=None)


def downgrade() -> None:
    op.drop_column("collection_tasks", "parameters")
