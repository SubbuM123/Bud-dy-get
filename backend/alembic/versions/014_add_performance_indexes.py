"""Add indexes on frequently-filtered columns.

Revision ID: 014
Revises: 013
Create Date: 2024-08-06

Every list/detail endpoint in this app filters by `user_id` (ownership scoping) and,
for several tables, an `is_active`/`is_recurring` flag - none of these columns had an
index before this migration, so every such query was a sequential scan. Only `users.email`
had an index (its `unique=True` implicitly creates one). Skips the `receipts` table
(out of scope for this pass - see api/v1/receipts.py's synchronous-OCR rework instead)
and the scheduler's own migration 012 fields, which are read alongside `user_id`/
`is_active` here rather than needing their own separate index.
"""

from alembic import op


revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_bank_accounts_user_id", "bank_accounts", ["user_id"])
    op.create_index(
        "ix_recurring_actions_bank_account_id_is_active",
        "recurring_actions",
        ["bank_account_id", "is_active"],
    )
    op.create_index("ix_bank_transactions_bank_account_id", "bank_transactions", ["bank_account_id"])

    op.create_index("ix_retirement_accounts_user_id", "retirement_accounts", ["user_id"])
    op.create_index(
        "ix_retirement_recurring_contributions_account_id_is_active",
        "retirement_recurring_contributions",
        ["retirement_account_id", "is_active"],
    )

    op.create_index("ix_education_accounts_user_id", "education_accounts", ["user_id"])
    op.create_index(
        "ix_education_recurring_contributions_account_id_is_active",
        "education_recurring_contributions",
        ["education_account_id", "is_active"],
    )

    op.create_index("ix_expenses_user_id_expense_date", "expenses", ["user_id", "expense_date"])
    op.create_index("ix_expenses_is_recurring", "expenses", ["is_recurring"])

    op.create_index(
        "ix_incomes_user_id_is_active_is_recurring",
        "incomes",
        ["user_id", "is_active", "is_recurring"],
    )

    op.create_index(
        "ix_transactions_user_id_transaction_date", "transactions", ["user_id", "transaction_date"]
    )

    op.create_index("ix_stock_positions_user_id", "stock_positions", ["user_id"])
    op.create_index("ix_stock_transactions_stock_position_id", "stock_transactions", ["stock_position_id"])
    op.create_index("ix_bond_holdings_user_id_is_active", "bond_holdings", ["user_id", "is_active"])
    op.create_index(
        "ix_property_investments_user_id_is_active", "property_investments", ["user_id", "is_active"]
    )


def downgrade() -> None:
    op.drop_index("ix_property_investments_user_id_is_active", table_name="property_investments")
    op.drop_index("ix_bond_holdings_user_id_is_active", table_name="bond_holdings")
    op.drop_index("ix_stock_transactions_stock_position_id", table_name="stock_transactions")
    op.drop_index("ix_stock_positions_user_id", table_name="stock_positions")

    op.drop_index("ix_transactions_user_id_transaction_date", table_name="transactions")

    op.drop_index("ix_incomes_user_id_is_active_is_recurring", table_name="incomes")

    op.drop_index("ix_expenses_is_recurring", table_name="expenses")
    op.drop_index("ix_expenses_user_id_expense_date", table_name="expenses")

    op.drop_index(
        "ix_education_recurring_contributions_account_id_is_active",
        table_name="education_recurring_contributions",
    )
    op.drop_index("ix_education_accounts_user_id", table_name="education_accounts")

    op.drop_index(
        "ix_retirement_recurring_contributions_account_id_is_active",
        table_name="retirement_recurring_contributions",
    )
    op.drop_index("ix_retirement_accounts_user_id", table_name="retirement_accounts")

    op.drop_index("ix_bank_transactions_bank_account_id", table_name="bank_transactions")
    op.drop_index("ix_recurring_actions_bank_account_id_is_active", table_name="recurring_actions")
    op.drop_index("ix_bank_accounts_user_id", table_name="bank_accounts")
