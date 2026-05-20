"""Store imported log source content.

Revision ID: 0003_log_source_content
Revises: 0002_source_artifact_content
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0003_log_source_content"
down_revision = "0002_source_artifact_content"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing_columns = {column["name"] for column in inspect(op.get_bind()).get_columns("log_sources")}
    if "content" in existing_columns:
        return
    with op.batch_alter_table("log_sources") as batch_op:
        batch_op.add_column(sa.Column("content", sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    existing_columns = {column["name"] for column in inspect(op.get_bind()).get_columns("log_sources")}
    if "content" not in existing_columns:
        return
    with op.batch_alter_table("log_sources") as batch_op:
        batch_op.drop_column("content")
