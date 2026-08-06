"""Initial migration: users and the Bank Account Simulator tables.

Revision ID: 001
Revises:
Create Date: 2024-01-01

Creates the four tables needed for Phase 1 and 2 of the roadmap: `users`
(authentication) and the three Bank Account Simulator tables (`bank_accounts`,
`recurring_actions`, `bank_transactions`). This is the first migration in the
project, so `downgrade()` drops everything including the Postgres ENUM types
that back the SQLAlchemy Enum columns - those types must be dropped
explicitly or `upgrade()` will fail on a second run.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Create the users and bank-account-related tables plus their Postgres ENUM types.
def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    op.create_table(
        'bank_accounts',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('account_name', sa.String(255), nullable=False),
        sa.Column('account_type', sa.Enum('savings', 'checking', 'cd', name='accounttype'), nullable=False),
        sa.Column('principal', sa.Numeric(15, 2), nullable=False),
        sa.Column('current_balance', sa.Numeric(15, 2), nullable=False),
        sa.Column('interest_rate', sa.Numeric(6, 4), nullable=True),
        sa.Column('compounding_frequency', sa.Enum('daily', 'monthly', 'quarterly', 'annually', name='compoundingfrequency'), nullable=False),
        sa.Column('cd_maturity_date', sa.Date(), nullable=True),
        sa.Column('is_simulation', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'recurring_actions',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('bank_account_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('action_type', sa.Enum('deposit', 'withdrawal', name='actiontype'), nullable=False),
        sa.Column('amount', sa.Numeric(15, 2), nullable=False),
        sa.Column('description', sa.String(255), nullable=True),
        sa.Column('frequency_value', sa.Integer(), nullable=False),
        sa.Column('frequency_unit', sa.Enum('days', 'weeks', 'months', name='frequencyunit'), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('next_execution_date', sa.Date(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['bank_account_id'], ['bank_accounts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'bank_transactions',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('bank_account_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('transaction_type', sa.Enum('deposit', 'withdrawal', name='actiontype'), nullable=False),
        sa.Column('amount', sa.Numeric(15, 2), nullable=False),
        sa.Column('description', sa.String(255), nullable=True),
        sa.Column('balance_after', sa.Numeric(15, 2), nullable=False),
        sa.Column('transaction_date', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['bank_account_id'], ['bank_accounts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )


# Drop every table and ENUM type created by upgrade(), in dependency order.
def downgrade() -> None:
    op.drop_table('bank_transactions')
    op.drop_table('recurring_actions')
    op.drop_table('bank_accounts')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')

    op.execute('DROP TYPE IF EXISTS accounttype')
    op.execute('DROP TYPE IF EXISTS compoundingfrequency')
    op.execute('DROP TYPE IF EXISTS actiontype')
    op.execute('DROP TYPE IF EXISTS frequencyunit')
