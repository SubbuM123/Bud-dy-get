"""Add recurring_actions.category and bank_accounts.cd_auto_renew.

Revision ID: 002
Revises: 001
Create Date: 2026-08-01

Two independent additive columns for the Bank Account Simulator: a predetermined
category tag on recurring actions (for future spend/income analysis, e.g. salary vs.
housing vs. investment) and a CD-specific auto-renew flag (whether a matured CD rolls
into a new CD term instead of depositing into savings). Both are nullable/defaulted so
existing rows don't need backfilling.

Unlike 001_initial.py's enum columns, which were created inline as part of
`op.create_table` (where SQLAlchemy's DDL compiler auto-emits `CREATE TYPE` before the
table itself), `op.add_column` on an existing table does NOT create the backing Postgres
enum type on its own - it has to be created explicitly first, or the `ALTER TABLE ...
ADD COLUMN` fails with `UndefinedObjectError: type "actioncategory" does not exist`.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ACTION_CATEGORY_VALUES = [
    'salary', 'housing', 'utilities', 'insurance', 'retirement',
    'investment', 'healthcare', 'entertainment', 'transportation', 'other',
]


# Add the two new columns, explicitly creating the Postgres ENUM type `category` relies
# on first since `add_column` (unlike `create_table`) won't create it implicitly.
def upgrade() -> None:
    op.add_column(
        'bank_accounts',
        sa.Column('cd_auto_renew', sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    action_category_enum = postgresql.ENUM(*ACTION_CATEGORY_VALUES, name='actioncategory')
    action_category_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        'recurring_actions',
        sa.Column(
            'category',
            postgresql.ENUM(*ACTION_CATEGORY_VALUES, name='actioncategory', create_type=False),
            nullable=True,
        ),
    )


# Drop both columns and the ENUM type added by upgrade(), in dependency order (the
# column referencing the type must go before the type itself).
def downgrade() -> None:
    op.drop_column('recurring_actions', 'category')
    op.drop_column('bank_accounts', 'cd_auto_renew')
    op.execute('DROP TYPE IF EXISTS actioncategory')
