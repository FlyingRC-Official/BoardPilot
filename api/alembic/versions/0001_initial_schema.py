"""Initial BoardPilot schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-20
"""
from alembic import op
from sqlalchemy.exc import DBAPIError

from app.db.base import Base
import app.models.orm  # noqa: F401

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(Base.metadata.sorted_tables):
        try:
            table.drop(bind=bind, checkfirst=True)
        except DBAPIError:
            # Keep downgrade best-effort across SQLite/Postgres development DBs.
            raise
