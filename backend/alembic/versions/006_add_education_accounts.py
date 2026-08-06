"""Add education_accounts and education_recurring_contributions tables.

Revision ID: 006
Revises: 005
Create Date: 2026-08-03

Creates the two tables backing the Education Savings module (529 plans, per
docs/phase4.5-plan.md): `education_accounts` and
`education_recurring_contributions` - the education-module equivalent of
003/004's `retirement_accounts`/`retirement_recurring_contributions`.

Both tables are brand new, so `education_accounts.account_type`'s enum
column is declared inline inside `op.create_table`, where SQLAlchemy's DDL
compiler auto-emits `CREATE TYPE` before the table itself - same as
`retirement_accounts` in migration 003.

`education_recurring_contributions.frequency`, however, is a real gotcha:
even though this is a brand-new table, it reuses the `contributionfrequency`
Postgres enum type that migration 004 already created for
`retirement_recurring_contributions` - Postgres enum types are schema-global,
not table-scoped. Declaring the column with a plain `sa.Enum(..., name=
'contributionfrequency')` would make SQLAlchemy try to `CREATE TYPE
contributionfrequency` again and fail with "type already exists", even
though this table has never referenced it before. `create_type=False` on a
`postgresql.ENUM(...)` column avoids that - the same fix migration 003
needed for `users.filing_status`, but for a different underlying reason
(there it was "ALTER TABLE doesn't auto-create the type"; here it's "the
type already exists from an earlier migration, even inside a fresh
CREATE TABLE").
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '006'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EDUCATION_ACCOUNT_TYPE_VALUES = ['529_plan', 'coverdell_esa', 'custodial_utma_ugma']
# Must match migration 004's contributionfrequency values exactly - not re-declared as new.
CONTRIBUTION_FREQUENCY_VALUES = ['monthly', 'yearly']


def upgrade() -> None:
    op.create_table(
        'education_accounts',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('account_name', sa.String(255), nullable=False),
        sa.Column(
            'account_type',
            sa.Enum(*EDUCATION_ACCOUNT_TYPE_VALUES, name='educationaccounttype'),
            nullable=False,
            server_default='529_plan',
        ),
        sa.Column('beneficiary_name', sa.String(255), nullable=False),
        sa.Column('beneficiary_birth_date', sa.Date(), nullable=True),
        sa.Column('plan_provider', sa.String(255), nullable=True),
        sa.Column('balance', sa.Numeric(15, 2), nullable=False),
        sa.Column('contribution_ytd', sa.Numeric(15, 2), nullable=False, server_default='0'),
        sa.Column('expected_return_rate', sa.Numeric(6, 4), nullable=False, server_default='0.07'),
        sa.Column('is_simulation', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'education_recurring_contributions',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('education_account_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('amount', sa.Numeric(15, 2), nullable=False),
        sa.Column(
            'frequency',
            postgresql.ENUM(
                *CONTRIBUTION_FREQUENCY_VALUES, name='contributionfrequency', create_type=False
            ),
            nullable=False,
        ),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ['education_account_id'], ['education_accounts.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('education_recurring_contributions')
    # Do NOT drop the contributionfrequency type here - it's shared with
    # retirement_recurring_contributions (migration 004) and dropping it would break Phase 4.
    op.drop_table('education_accounts')
    op.execute('DROP TYPE IF EXISTS educationaccounttype')
