"""Allow provider-specific chunk embedding dimensions.

Revision ID: 0004_flexible_chunk_embedding_vectors
Revises: 0003_log_source_content
Create Date: 2026-05-20
"""

from alembic import op

revision = "0004_flexible_chunk_embedding_vectors"
down_revision = "0003_log_source_content"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE chunk_embeddings ALTER COLUMN vector TYPE vector")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE chunk_embeddings ALTER COLUMN vector TYPE vector(1536)")
