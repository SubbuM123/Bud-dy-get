"""Add retirement_recurring_contributions table.

Revision ID: 004
Revises: 003
Create Date: 2026-08-03

Creates the `retirement_recurring_contributions` table (the retirement-module
equivalent of `recurring_actions` from 001_initial.py): a scheduled monthly
or yearly contribution to a `retirement_accounts` row, consumed by
services/retirement_simulator.py to auto-include recurring contributions in
growth projections. Brand-new table, so its `frequency` enum column is
declared inline inside `op.create_table`, where SQLAlchemy's DDL compiler
auto-emits `CREATE TYPE` before the table itself - no separate explicit
`CREATE TYPE` step needed here (contrast with 002/003's `op.add_column` cases,
which needed one since ALTER TABLE doesn't get that same automatic behavior).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CONTRIBUTION_FREQUENCY_VALUES = ['monthly', 'yearly']


def upgrade() -> None:
    op.create_table(
        'retirement_recurring_contributions',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('retirement_account_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('amount', sa.Numeric(15, 2), nullable=False),
        sa.Column(
            'frequency',
            sa.Enum(*CONTRIBUTION_FREQUENCY_VALUES, name='contributionfrequency'),
            nullable=False,
        ),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ['retirement_account_id'], ['retirement_accounts.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('retirement_recurring_contributions')
    op.execute('DROP TYPE IF EXISTS contributionfrequency')
