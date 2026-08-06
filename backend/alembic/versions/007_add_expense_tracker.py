"""Add expense_categories, receipts, receipt_line_items, and expenses tables.

Revision ID: 007
Revises: 006
Create Date: 2026-08-03

Creates the four tables backing the Expense Tracker module (Phase 3, per
docs/phase3-plan.md): `expense_categories`, `receipts`, `receipt_line_items`,
and `expenses`. All four are brand new, so every enum column here
(`receipts.processing_status`, `receipts.extraction_method`) is declared
inline inside `op.create_table`, where SQLAlchemy's DDL compiler auto-emits
`CREATE TYPE` before the table itself - no `create_type=False` gotcha here
since neither `receiptprocessingstatus` nor `extractionmethod` exists yet in
any prior migration (unlike migration 006's `contributionfrequency` reuse).

Creation order matters for foreign keys: `expense_categories` and `receipts`
first (both only depend on `users`, already created in migration 001), then
`receipt_line_items` (depends on `receipts`), then `expenses` last (depends
on `users`, `receipts`, `expense_categories`, and `bank_accounts`, all
already present by this point).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '007'
down_revision: Union[str, None] = '006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PROCESSING_STATUS_VALUES = ['pending', 'processing', 'completed', 'needs_review', 'failed']
EXTRACTION_METHOD_VALUES = ['tesseract', 'pdf_text', 'pdf_ocr', 'manual']


def upgrade() -> None:
    op.create_table(
        'expense_categories',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('color', sa.String(7), nullable=True),
        sa.Column('icon', sa.String(50), nullable=True),
        sa.Column('monthly_budget', sa.Numeric(12, 2), nullable=True),
        sa.Column('is_system', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'name', name='uq_expense_category_user_name'),
    )

    op.create_table(
        'receipts',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('original_filename', sa.String(255), nullable=False),
        sa.Column('file_key', sa.String(512), nullable=False),
        sa.Column('file_type', sa.String(50), nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=True),
        sa.Column(
            'processing_status',
            sa.Enum(*PROCESSING_STATUS_VALUES, name='receiptprocessingstatus'),
            nullable=False,
            server_default='pending',
        ),
        sa.Column('processing_error', sa.Text(), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('raw_extracted_text', sa.Text(), nullable=True),
        sa.Column(
            'extraction_method',
            sa.Enum(*EXTRACTION_METHOD_VALUES, name='extractionmethod'),
            nullable=True,
        ),
        sa.Column('merchant_name', sa.String(255), nullable=True),
        sa.Column('merchant_name_confidence', sa.Numeric(3, 2), nullable=True),
        sa.Column('total_amount', sa.Numeric(12, 2), nullable=True),
        sa.Column('total_amount_confidence', sa.Numeric(3, 2), nullable=True),
        sa.Column('transaction_date', sa.Date(), nullable=True),
        sa.Column('transaction_date_confidence', sa.Numeric(3, 2), nullable=True),
        sa.Column('tax_amount', sa.Numeric(12, 2), nullable=True),
        sa.Column('subtotal_amount', sa.Numeric(12, 2), nullable=True),
        sa.Column('payment_method', sa.String(50), nullable=True),
        sa.Column('receipt_number', sa.String(100), nullable=True),
        sa.Column('user_verified', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'receipt_line_items',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('receipt_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('description', sa.String(255), nullable=True),
        sa.Column('quantity', sa.Numeric(10, 3), nullable=True),
        sa.Column('unit_price', sa.Numeric(12, 2), nullable=True),
        sa.Column('total_price', sa.Numeric(12, 2), nullable=True),
        sa.Column('line_order', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['receipt_id'], ['receipts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'expenses',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('receipt_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column('merchant_name', sa.String(255), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('expense_date', sa.Date(), nullable=False),
        sa.Column('category_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column('bank_account_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('is_recurring', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('recurrence_pattern', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['receipt_id'], ['receipts.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['category_id'], ['expense_categories.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['bank_account_id'], ['bank_accounts.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('expenses')
    op.drop_table('receipt_line_items')
    op.drop_table('receipts')
    op.execute('DROP TYPE IF EXISTS extractionmethod')
    op.execute('DROP TYPE IF EXISTS receiptprocessingstatus')
    op.drop_table('expense_categories')
