"""Persist Celery task identifiers for lifecycle control."""

from alembic import op
import sqlalchemy as sa

revision = "0003_celery_task_id"
down_revision = "0002_collection_task_parameters"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("collection_tasks", sa.Column("celery_task_id", sa.String(length=255), nullable=True))
    op.create_unique_constraint("uq_collection_tasks_celery_task_id", "collection_tasks", ["celery_task_id"])


def downgrade() -> None:
    op.drop_constraint("uq_collection_tasks_celery_task_id", "collection_tasks", type_="unique")
    op.drop_column("collection_tasks", "celery_task_id")
