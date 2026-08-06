"""Make receipts.file_key nullable for storage-less OCR.

Revision ID: 013
Revises: 012_add_scheduler_idempotency_fields
Create Date: 2024-08-05

With the migration to cloud hosting, receipt files are no longer stored in S3/MinIO.
OCR extraction runs synchronously during upload and only the extracted fields are
persisted. The file_key column is kept for schema compatibility but is always NULL
for new uploads.
"""

from alembic import op
import sqlalchemy as sa


revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "receipts",
        "file_key",
        existing_type=sa.String(512),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "receipts",
        "file_key",
        existing_type=sa.String(512),
        nullable=False,
    )
