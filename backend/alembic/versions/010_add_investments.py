"""Add investments tables: stock_positions, stock_transactions, bond_holdings,
property_investments. Extend allocationdestinationtype/transactiontype for stock
positions and buy/sell/RSU-vest events. Add RSU vesting columns to income_allocations.

Revision ID: 010
Revises: 009
Create Date: 2026-08-04

Creates the four tables backing Phase 5 (see docs/phase5-plan.md): `stock_positions` +
`stock_transactions` (an aggregate per-ticker holding plus its buy/sell/RSU-vest history),
and `bond_holdings`/`property_investments` (simpler bought-once-sold-once holdings storing
their own terminal sale state inline - no side transactions table for either, see
models/investments.py's docstrings for why).

`allocationdestinationtype` (created by migration 008) gains `stock_position` via `ALTER
TYPE ... ADD VALUE` - safe to run inside this migration's own transaction on Postgres 12+
as long as nothing in this same migration *uses* the new value (it doesn't; no data is
inserted here). `transactiontype` (same migration) gains `stock_purchase`/`stock_sale`/
`rsu_vest` the same way. `income_allocations` gains five nullable-except-one RSU columns,
reusing migration 003's `vestingtype` enum via `create_type=False` (the same "type already
exists" pattern migration 008 used for `allocationdestinationtype`/`transactiontype`
crossing multiple columns).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '010'
down_revision: Union[str, None] = '009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BOND_PAYMENT_FREQUENCY_VALUES = ['annually', 'semi_annually']
STOCK_TRANSACTION_TYPE_VALUES = ['buy', 'sell', 'rsu_vest']
VESTING_TYPE_VALUES = ['immediate', 'cliff', 'graded']


def upgrade() -> None:
    # Extend existing enums (migration 008) before anything below might reference them.
    op.execute("ALTER TYPE allocationdestinationtype ADD VALUE IF NOT EXISTS 'stock_position'")
    op.execute("ALTER TYPE transactiontype ADD VALUE IF NOT EXISTS 'stock_purchase'")
    op.execute("ALTER TYPE transactiontype ADD VALUE IF NOT EXISTS 'stock_sale'")
    op.execute("ALTER TYPE transactiontype ADD VALUE IF NOT EXISTS 'rsu_vest'")

    op.create_table(
        'stock_positions',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('ticker_symbol', sa.String(10), nullable=False),
        sa.Column('shares', sa.Numeric(18, 4), nullable=False, server_default='0'),
        sa.Column('average_cost_per_share', sa.Numeric(15, 4), nullable=False, server_default='0'),
        sa.Column('current_price', sa.Numeric(15, 4), nullable=True),
        sa.Column('last_price_update', sa.DateTime(), nullable=True),
        sa.Column('is_simulation', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_stock_positions_user_ticker', 'stock_positions', ['user_id', 'ticker_symbol']
    )

    op.create_table(
        'stock_transactions',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('stock_position_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column(
            'transaction_type',
            sa.Enum(*STOCK_TRANSACTION_TYPE_VALUES, name='stocktransactiontype'),
            nullable=False,
        ),
        sa.Column('shares', sa.Numeric(18, 4), nullable=False),
        sa.Column('price_per_share', sa.Numeric(15, 4), nullable=False),
        sa.Column('transaction_date', sa.Date(), nullable=False),
        sa.Column('realized_pnl', sa.Numeric(15, 2), nullable=True),
        sa.Column('source_bank_account_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['stock_position_id'], ['stock_positions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['source_bank_account_id'], ['bank_accounts.id'], ondelete='SET NULL'
        ),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'bond_holdings',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('purchase_price', sa.Numeric(15, 2), nullable=False),
        sa.Column('face_value', sa.Numeric(15, 2), nullable=False),
        sa.Column('coupon_rate', sa.Numeric(6, 4), nullable=False, server_default='0'),
        sa.Column(
            'payment_frequency',
            sa.Enum(*BOND_PAYMENT_FREQUENCY_VALUES, name='bondpaymentfrequency'),
            nullable=False,
            server_default='semi_annually',
        ),
        sa.Column('purchase_date', sa.Date(), nullable=False),
        sa.Column('maturity_date', sa.Date(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('sale_price', sa.Numeric(15, 2), nullable=True),
        sa.Column('sale_date', sa.Date(), nullable=True),
        sa.Column('realized_pnl', sa.Numeric(15, 2), nullable=True),
        sa.Column('is_simulation', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'property_investments',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('cost', sa.Numeric(15, 2), nullable=False),
        sa.Column('expected_return_rate', sa.Numeric(6, 4), nullable=False, server_default='0.05'),
        sa.Column('purchase_date', sa.Date(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('sale_price', sa.Numeric(15, 2), nullable=True),
        sa.Column('sale_date', sa.Date(), nullable=True),
        sa.Column('realized_pnl', sa.Numeric(15, 2), nullable=True),
        sa.Column('is_simulation', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # RSU vesting fields on income_allocations - see models/income.py:IncomeAllocation's
    # docstring. `vestingtype` already exists (migration 003, for
    # retirement_accounts.vesting_type) - create_type=False reuses it here.
    op.add_column(
        'income_allocations',
        sa.Column(
            'rsu_vesting_type',
            postgresql.ENUM(*VESTING_TYPE_VALUES, name='vestingtype', create_type=False),
            nullable=True,
        ),
    )
    op.add_column('income_allocations', sa.Column('rsu_vesting_years', sa.Integer(), nullable=True))
    op.add_column('income_allocations', sa.Column('rsu_cliff_date', sa.Date(), nullable=True))
    op.add_column(
        'income_allocations', sa.Column('rsu_total_shares', sa.Numeric(18, 4), nullable=True)
    )
    op.add_column(
        'income_allocations',
        sa.Column('rsu_shares_vested', sa.Numeric(18, 4), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    op.drop_column('income_allocations', 'rsu_shares_vested')
    op.drop_column('income_allocations', 'rsu_total_shares')
    op.drop_column('income_allocations', 'rsu_cliff_date')
    op.drop_column('income_allocations', 'rsu_vesting_years')
    op.drop_column('income_allocations', 'rsu_vesting_type')

    op.drop_table('property_investments')
    op.drop_table('bond_holdings')
    op.execute('DROP TYPE IF EXISTS bondpaymentfrequency')

    op.drop_table('stock_transactions')
    op.execute('DROP TYPE IF EXISTS stocktransactiontype')

    op.drop_index('ix_stock_positions_user_ticker', table_name='stock_positions')
    op.drop_table('stock_positions')

    # Postgres has no "ALTER TYPE ... DROP VALUE" - the three added transactiontype/
    # allocationdestinationtype enum labels are left in place on downgrade, same
    # documented limitation as every other enum-extending migration in this app.
