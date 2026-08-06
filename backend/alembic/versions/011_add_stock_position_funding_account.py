"""Add stock_positions.funding_bank_account_id.

Revision ID: 011
Revises: 010
Create Date: 2026-08-04

Remembers which bank account most recently funded a buy on a stock position, so a later
sell can credit proceeds back into that account automatically - see
models/investments.py:StockPosition's docstring and api/v1/investments.py's `buy_stock`/
`sell_stock`. Fixes a real gap: selling a stock that was bought with a bank-funded buy
never put the money back anywhere.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '011'
down_revision: Union[str, None] = '010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'stock_positions',
        sa.Column('funding_bank_account_id', postgresql.UUID(as_uuid=False), nullable=True),
    )
    op.create_foreign_key(
        'fk_stock_positions_funding_bank_account_id',
        'stock_positions',
        'bank_accounts',
        ['funding_bank_account_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint(
        'fk_stock_positions_funding_bank_account_id', 'stock_positions', type_='foreignkey'
    )
    op.drop_column('stock_positions', 'funding_bank_account_id')
