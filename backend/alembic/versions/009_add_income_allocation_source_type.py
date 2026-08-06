"""Add income_allocations.source_type.

Revision ID: 009
Revises: 008
Create Date: 2026-08-04

Backs Phase 4.6's "Option A" pre-tax-deduction UX (see
docs/phase4.6-money-flow-plan.md's "Next Steps" §8 and models/income.py's IncomeAllocation
docstring): a nullable column letting one allocation of a recurring Income be marked
`pre_tax_salary`, so logging that income also auto-posts a retirement/education
contribution for that allocation's share instead of a plain income transaction.

Reuses the `contributionsourcetype` Postgres enum type migration 008 already created for
`transactions.source_type` - `create_type=False` here, same "type already exists" pattern
migration 008's own docstring calls out for `allocationdestinationtype`.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '009'
down_revision: Union[str, None] = '008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CONTRIBUTION_SOURCE_TYPE_VALUES = ['bank_account', 'pre_tax_salary', 'track_only']


def upgrade() -> None:
    op.add_column(
        'income_allocations',
        sa.Column(
            'source_type',
            postgresql.ENUM(
                *CONTRIBUTION_SOURCE_TYPE_VALUES,
                name='contributionsourcetype',
                create_type=False,
            ),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column('income_allocations', 'source_type')
