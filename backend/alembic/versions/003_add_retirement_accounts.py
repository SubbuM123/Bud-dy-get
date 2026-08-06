"""Add retirement_accounts table and user profile fields for Phase 4.

Revision ID: 003
Revises: 002
Create Date: 2026-08-03

Creates the `retirement_accounts` table (401(k)/Roth 401(k)/Traditional
IRA/Roth IRA/SEP IRA/SIMPLE IRA/HSA tracking) and adds four profile columns
to the existing `users` table (birth_date, filing_status, annual_income,
has_employer_retirement_plan) that services/retirement_rules.py reads to
compute 2026 IRS contribution limits and eligibility.

`retirement_accounts` is a brand-new table, so its two enum columns
(account_type, vesting_type) are declared inline inside `op.create_table`,
where SQLAlchemy's DDL compiler auto-emits `CREATE TYPE` before the table
itself - same as `bank_accounts`/`recurring_actions` in 001_initial.py.
`users.filing_status`, however, is a column added to an *existing* table via
`op.add_column`, which does NOT get that same automatic behavior (see
002_recurring_action_category_and_cd_auto_renew.py's docstring for the full
explanation) - its backing Postgres enum type is created explicitly first.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RETIREMENT_ACCOUNT_TYPE_VALUES = [
    'traditional_401k', 'roth_401k', 'traditional_ira', 'roth_ira',
    'sep_ira', 'simple_ira', 'hsa',
]
VESTING_TYPE_VALUES = ['immediate', 'cliff', 'graded']
FILING_STATUS_VALUES = [
    'single', 'married_filing_jointly', 'married_filing_separately', 'head_of_household',
]


def upgrade() -> None:
    op.create_table(
        'retirement_accounts',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('account_name', sa.String(255), nullable=False),
        sa.Column(
            'account_type',
            sa.Enum(*RETIREMENT_ACCOUNT_TYPE_VALUES, name='retirementaccounttype'),
            nullable=False,
        ),
        sa.Column('balance', sa.Numeric(15, 2), nullable=False),
        sa.Column('contribution_ytd', sa.Numeric(15, 2), nullable=False, server_default='0'),
        sa.Column('employer_name', sa.String(255), nullable=True),
        sa.Column('annual_salary', sa.Numeric(15, 2), nullable=True),
        sa.Column('employer_match_percent', sa.Numeric(6, 4), nullable=True),
        sa.Column('employer_match_limit_percent', sa.Numeric(6, 4), nullable=True),
        sa.Column(
            'vesting_type',
            sa.Enum(*VESTING_TYPE_VALUES, name='vestingtype'),
            nullable=True,
        ),
        sa.Column('vesting_years', sa.Integer(), nullable=True),
        sa.Column('vested_percent', sa.Numeric(5, 2), nullable=False, server_default='100'),
        sa.Column('expected_return_rate', sa.Numeric(6, 4), nullable=False, server_default='0.07'),
        sa.Column('is_simulation', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    filing_status_enum = postgresql.ENUM(*FILING_STATUS_VALUES, name='filingstatus')
    filing_status_enum.create(op.get_bind(), checkfirst=True)

    op.add_column('users', sa.Column('birth_date', sa.Date(), nullable=True))
    op.add_column(
        'users',
        sa.Column(
            'filing_status',
            postgresql.ENUM(*FILING_STATUS_VALUES, name='filingstatus', create_type=False),
            nullable=True,
        ),
    )
    op.add_column('users', sa.Column('annual_income', sa.Numeric(15, 2), nullable=True))
    op.add_column(
        'users',
        sa.Column(
            'has_employer_retirement_plan', sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )


def downgrade() -> None:
    op.drop_column('users', 'has_employer_retirement_plan')
    op.drop_column('users', 'annual_income')
    op.drop_column('users', 'filing_status')
    op.drop_column('users', 'birth_date')
    op.execute('DROP TYPE IF EXISTS filingstatus')

    op.drop_table('retirement_accounts')
    op.execute('DROP TYPE IF EXISTS retirementaccounttype')
    op.execute('DROP TYPE IF EXISTS vestingtype')
