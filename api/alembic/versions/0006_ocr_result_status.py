"""Store OCR provider status and errors.

Revision ID: 0006_ocr_result_status
Revises: 0005_source_version_error
Create Date: 2026-05-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0006_ocr_result_status"
down_revision = "0005_source_version_error"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing_columns = {column["name"] for column in inspect(op.get_bind()).get_columns("ocr_results")}
    with op.batch_alter_table("ocr_results") as batch_op:
        if "status" not in existing_columns:
            batch_op.add_column(sa.Column("status", sa.String(length=40), nullable=False, server_default="completed"))
        if "error_message" not in existing_columns:
            batch_op.add_column(sa.Column("error_message", sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    existing_columns = {column["name"] for column in inspect(op.get_bind()).get_columns("ocr_results")}
    with op.batch_alter_table("ocr_results") as batch_op:
        if "error_message" in existing_columns:
            batch_op.drop_column("error_message")
        if "status" in existing_columns:
            batch_op.drop_column("status")
