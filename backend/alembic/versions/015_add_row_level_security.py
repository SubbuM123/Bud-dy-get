"""Add Postgres row-level security to every user-owned table.

Revision ID: 015
Revises: 014
Create Date: 2026-08-11

Two problems this closes, both about the same gap - no table in this app enforces
per-user isolation below the application layer:

1. Defense in depth against this app's own bugs: every router already scopes its queries
   to `current_user.id` by hand (see api/v1/*.py's `_get_owned_*` helpers), but that
   discipline lives entirely in Python - one missed filter in a future endpoint would
   silently leak another user's financial data with no error and nothing to catch it.
2. Supabase's Security Advisor `rls_disabled_in_public` finding: Supabase auto-exposes
   every `public`-schema table over its own REST API (PostgREST), authenticated as the
   `anon`/`authenticated` Postgres roles - a path this FastAPI app's JWT auth never sees.
   Enabling RLS (regardless of policies) is what closes that for a non-owner role.

The app's Postgres role owns every table (same DATABASE_URL runs both `alembic upgrade`
and the app itself), and Postgres skips RLS for a table's owner by default - so the 18
tables below need FORCE ROW LEVEL SECURITY for their policies to actually apply to the
app's own queries, not just to PostgREST. Direct tables (a `user_id` column) get a policy
straight on that column; child tables (owned only via a parent FK - e.g. `recurring_actions`
has no `user_id` of its own, only `bank_account_id`) get a policy that checks the parent's
`user_id` through an EXISTS subquery. Every policy also allows a `bypass_rls` escape hatch,
used by exactly one caller (services/scheduler.py's system-wide job, see
app/core/request_context.py's `system_context`).

`users` and `alembic_version` are handled differently: ENABLE ROW LEVEL SECURITY only, no
FORCE and no policy. Since the app's role owns them, "not forced" means the app (and this
migration's own `alembic upgrade`) is completely unaffected, while any other role -
specifically PostgREST's anon/authenticated - gets zero rows by default. `users` doesn't
get a real per-row policy like the 18 tables below because login/register must look a row
up by email before any per-user identity exists (same bypass problem as the scheduler, for
no added protection - see app/core/auth.py and api/v1/auth.py for the only code paths that
touch other rows in this table, both trusted and primary-key/email scoped already).

See app/database.py's `begin` event listener for how `app.current_user_id`/`app.bypass_rls`
reach the database connection, and app/core/request_context.py for who sets them.
"""
from alembic import op

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None

# (table, user_id_column) - tables with their own user_id foreign key.
_DIRECT_TABLES = [
    ("bank_accounts", "user_id"),
    ("retirement_accounts", "user_id"),
    ("education_accounts", "user_id"),
    ("receipts", "user_id"),
    ("expense_categories", "user_id"),
    ("expenses", "user_id"),
    ("incomes", "user_id"),
    ("transactions", "user_id"),
    ("stock_positions", "user_id"),
    ("bond_holdings", "user_id"),
    ("property_investments", "user_id"),
]

# (table, fk_column, parent_table) - tables owned only via a parent row's user_id.
_CHILD_TABLES = [
    ("recurring_actions", "bank_account_id", "bank_accounts"),
    ("bank_transactions", "bank_account_id", "bank_accounts"),
    ("retirement_recurring_contributions", "retirement_account_id", "retirement_accounts"),
    ("education_recurring_contributions", "education_account_id", "education_accounts"),
    ("income_allocations", "income_id", "incomes"),
    ("stock_transactions", "stock_position_id", "stock_positions"),
    ("receipt_line_items", "receipt_id", "receipts"),
]

# Tables that get RLS *enabled* (closes the Supabase PostgREST exposure) but not forced and
# with no policy - the app's own role, which owns them, is therefore completely unaffected.
_OWNER_ONLY_TABLES = ["users", "alembic_version"]

_BYPASS = "current_setting('app.bypass_rls', true) = 'on'"


def _direct_policy_expr(user_id_column: str) -> str:
    return (
        f"{_BYPASS} OR {user_id_column} = current_setting('app.current_user_id', true)::uuid"
    )


def _child_policy_expr(table: str, fk_column: str, parent_table: str) -> str:
    return (
        f"{_BYPASS} OR EXISTS (\n"
        f"        SELECT 1 FROM {parent_table} p\n"
        f"        WHERE p.id = {table}.{fk_column}\n"
        f"          AND p.user_id = current_setting('app.current_user_id', true)::uuid\n"
        f"    )"
    )


def upgrade() -> None:
    for table, user_id_column in _DIRECT_TABLES:
        expr = _direct_policy_expr(user_id_column)
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_user_isolation ON {table}\n"
            f"    USING ({expr})\n"
            f"    WITH CHECK ({expr})"
        )

    for table, fk_column, parent_table in _CHILD_TABLES:
        expr = _child_policy_expr(table, fk_column, parent_table)
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_user_isolation ON {table}\n"
            f"    USING ({expr})\n"
            f"    WITH CHECK ({expr})"
        )

    for table in _OWNER_ONLY_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in _OWNER_ONLY_TABLES:
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    for table, _fk_column, _parent_table in reversed(_CHILD_TABLES):
        op.execute(f"DROP POLICY IF EXISTS {table}_user_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    for table, _user_id_column in reversed(_DIRECT_TABLES):
        op.execute(f"DROP POLICY IF EXISTS {table}_user_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
