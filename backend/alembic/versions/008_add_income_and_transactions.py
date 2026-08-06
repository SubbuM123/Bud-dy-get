"""Add incomes, income_allocations, and transactions tables.

Revision ID: 008
Revises: 007
Create Date: 2026-08-04

Creates the three tables backing the unified money-flow reform (see
docs/plan.md's "Unified Money Flow Reform"): `incomes` (a recurring salary/side-income
source or a one-time bonus/gift), `income_allocations` (the percentage split of an Income
across one or more destination accounts), and `transactions` (the posted, editable/
deletable log of real income occurrences and retirement/education contributions - see
models/transactions.py's docstring for why expenses don't get a row here).

All three enum columns declared inline below (`incomes.frequency`,
`income_allocations.destination_type`, `transactions.transaction_type`,
`transactions.account_type`, `transactions.source_type`) are brand new types, so
SQLAlchemy's DDL compiler auto-emits `CREATE TYPE` before each table - no
`create_type=False` gotcha here, unlike migration 006's reuse of `contributionfrequency`.
`transactions.account_type` and `income_allocations.destination_type` share the same
Python enum (AllocationDestinationType) but get two separate Postgres enum types
(`allocationdestinationtype` is created once and reused via `create_type=False` on the
second column - the same "type already exists" gotcha migration 006 hit, but within a
single migration instead of across two).

Creation order: `incomes` first (only depends on `users`), then `income_allocations`
(depends on `incomes`), then `transactions` last (depends on `users`, `incomes`, and
`bank_accounts`, all already present).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '008'
down_revision: Union[str, None] = '007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INCOME_FREQUENCY_VALUES = ['weekly', 'biweekly', 'semi_monthly', 'monthly']
ALLOCATION_DESTINATION_TYPE_VALUES = ['bank_account', 'retirement_account', 'education_account']
CONTRIBUTION_SOURCE_TYPE_VALUES = ['bank_account', 'pre_tax_salary', 'track_only']
TRANSACTION_TYPE_VALUES = ['income', 'retirement_contribution', 'education_contribution']


def upgrade() -> None:
    op.create_table(
        'incomes',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('amount', sa.Numeric(15, 2), nullable=False),
        sa.Column('is_recurring', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            'frequency',
            sa.Enum(*INCOME_FREQUENCY_VALUES, name='incomefrequency'),
            nullable=True,
        ),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('income_date', sa.Date(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'income_allocations',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('income_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column(
            'destination_type',
            sa.Enum(*ALLOCATION_DESTINATION_TYPE_VALUES, name='allocationdestinationtype'),
            nullable=False,
        ),
        sa.Column('destination_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('percentage', sa.Numeric(5, 2), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['income_id'], ['incomes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'transactions',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column(
            'transaction_type',
            sa.Enum(*TRANSACTION_TYPE_VALUES, name='transactiontype'),
            nullable=False,
        ),
        sa.Column('amount', sa.Numeric(15, 2), nullable=False),
        sa.Column('transaction_date', sa.Date(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column(
            'account_type',
            postgresql.ENUM(
                *ALLOCATION_DESTINATION_TYPE_VALUES,
                name='allocationdestinationtype',
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column('account_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column('income_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column(
            'source_type',
            sa.Enum(*CONTRIBUTION_SOURCE_TYPE_VALUES, name='contributionsourcetype'),
            nullable=True,
        ),
        sa.Column('source_bank_account_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['income_id'], ['incomes.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(
            ['source_bank_account_id'], ['bank_accounts.id'], ondelete='SET NULL'
        ),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('transactions')
    op.execute('DROP TYPE IF EXISTS contributionsourcetype')
    op.execute('DROP TYPE IF EXISTS transactiontype')
    op.drop_table('income_allocations')
    # allocationdestinationtype is shared between income_allocations.destination_type and
    # transactions.account_type - safe to drop only now that both tables are gone.
    op.execute('DROP TYPE IF EXISTS allocationdestinationtype')
    op.drop_table('incomes')
    op.execute('DROP TYPE IF EXISTS incomefrequency')
