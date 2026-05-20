"""Store source version ingestion error messages.

Revision ID: 0005_source_version_error_message
Revises: 0004_flexible_chunk_embedding_vectors
Create Date: 2026-05-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0005_source_version_error_message"
down_revision = "0004_flexible_chunk_embedding_vectors"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing_columns = {column["name"] for column in inspect(op.get_bind()).get_columns("source_versions")}
    if "error_message" in existing_columns:
        return
    with op.batch_alter_table("source_versions") as batch_op:
        batch_op.add_column(sa.Column("error_message", sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    existing_columns = {column["name"] for column in inspect(op.get_bind()).get_columns("source_versions")}
    if "error_message" not in existing_columns:
        return
    with op.batch_alter_table("source_versions") as batch_op:
        batch_op.drop_column("error_message")
