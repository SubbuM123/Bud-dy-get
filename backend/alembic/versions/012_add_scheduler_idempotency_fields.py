"""Add idempotency tracking fields for the V2 background scheduler.

Revision ID: 012
Revises: 011
Create Date: 2026-08-04

Adds last_executed_date to recurring rules (income, retirement/education contributions,
recurring expenses) and last_interest_applied_date to accounts that accrue interest
(bank, retirement, education). These fields let the daily scheduler task know which
rules have already been executed for the current period, preventing double-posting if
the task runs more than once on the same day - see docs/future-plan.md's V2 scheduler
section and services/scheduler.py.

Also extends the existing `transactiontype` Postgres enum (created by migration 008,
already extended once by migration 010) with `interest`, via `ALTER TYPE ... ADD VALUE` -
safe inside this migration's own transaction on Postgres 12+ as long as nothing in this
same migration *uses* the new value, same reasoning migration 010's docstring gives for
its own enum extensions.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '012'
down_revision: Union[str, None] = '011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE transactiontype ADD VALUE IF NOT EXISTS 'interest'")

    # Recurring rules: track when they last executed
    op.add_column(
        'incomes',
        sa.Column('last_executed_date', sa.Date(), nullable=True),
    )
    op.add_column(
        'retirement_recurring_contributions',
        sa.Column('last_executed_date', sa.Date(), nullable=True),
    )
    op.add_column(
        'education_recurring_contributions',
        sa.Column('last_executed_date', sa.Date(), nullable=True),
    )
    op.add_column(
        'expenses',
        sa.Column('last_executed_date', sa.Date(), nullable=True),
    )

    # Accounts that accrue interest: track when interest was last applied
    op.add_column(
        'bank_accounts',
        sa.Column('last_interest_applied_date', sa.Date(), nullable=True),
    )
    op.add_column(
        'retirement_accounts',
        sa.Column('last_interest_applied_date', sa.Date(), nullable=True),
    )
    op.add_column(
        'education_accounts',
        sa.Column('last_interest_applied_date', sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('education_accounts', 'last_interest_applied_date')
    op.drop_column('retirement_accounts', 'last_interest_applied_date')
    op.drop_column('bank_accounts', 'last_interest_applied_date')
    op.drop_column('expenses', 'last_executed_date')
    op.drop_column('education_recurring_contributions', 'last_executed_date')
    op.drop_column('retirement_recurring_contributions', 'last_executed_date')
    op.drop_column('incomes', 'last_executed_date')

    # Postgres has no "ALTER TYPE ... DROP VALUE" - the 'interest' transactiontype enum
    # label is left in place on downgrade, same documented limitation migration 010's
    # downgrade() already notes for its own enum extensions.
