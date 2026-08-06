"""Regression test for a real bug found in practice: creating a bank account raised
`asyncpg.exceptions.InvalidTextRepresentationError: invalid input value for enum
accounttype: "SAVINGS"`.

SQLAlchemy's `Enum(SomeEnum)` binds using the Python enum member's *name*
("SAVINGS") by default, not its *value* ("savings") - `values_callable` is required to
bind on `.value` instead. The Postgres enum types created by
`alembic/versions/001_initial.py` only contain the lowercase values, so every model column
backed by one of these enums must pass `values_callable`, or every insert fails against a
real Postgres database. These are cheap to check directly against the column's compiled
`.enums` list - no database needed - which also means they'd have caught this bug, unlike
the API-level tests in test_bank_accounts.py, which run against SQLite and can't see this
class of migration-vs-model drift (SQLite recreates its schema from the current model on
every test run, so it's always self-consistent even when the model itself is wrong).
"""

from app.models.bank_accounts import BankAccount, BankTransaction, RecurringAction

# Must match the literal enum labels in alembic/versions/001_initial.py exactly.
EXPECTED_ACCOUNT_TYPES = ["savings", "checking", "cd"]
EXPECTED_COMPOUNDING_FREQUENCIES = ["daily", "monthly", "quarterly", "annually"]
EXPECTED_ACTION_TYPES = ["deposit", "withdrawal"]
EXPECTED_FREQUENCY_UNITS = ["days", "weeks", "months"]

# Must match the literal enum labels in alembic/versions/002_recurring_action_category_and_cd_auto_renew.py.
EXPECTED_ACTION_CATEGORIES = [
    "salary", "housing", "utilities", "insurance", "retirement",
    "investment", "healthcare", "entertainment", "transportation", "other",
]


def test_account_type_binds_lowercase_values_matching_the_migration():
    assert BankAccount.__table__.c.account_type.type.enums == EXPECTED_ACCOUNT_TYPES


def test_compounding_frequency_binds_lowercase_values_matching_the_migration():
    assert (
        BankAccount.__table__.c.compounding_frequency.type.enums
        == EXPECTED_COMPOUNDING_FREQUENCIES
    )


def test_recurring_action_type_binds_lowercase_values_matching_the_migration():
    assert RecurringAction.__table__.c.action_type.type.enums == EXPECTED_ACTION_TYPES


def test_recurring_action_frequency_unit_binds_lowercase_values_matching_the_migration():
    assert (
        RecurringAction.__table__.c.frequency_unit.type.enums == EXPECTED_FREQUENCY_UNITS
    )


def test_bank_transaction_type_binds_lowercase_values_matching_the_migration():
    assert BankTransaction.__table__.c.transaction_type.type.enums == EXPECTED_ACTION_TYPES


def test_recurring_action_category_binds_lowercase_values_matching_the_migration():
    assert RecurringAction.__table__.c.category.type.enums == EXPECTED_ACTION_CATEGORIES


def test_bank_account_has_cd_auto_renew_boolean_column():
    column = BankAccount.__table__.c.cd_auto_renew
    assert column.type.python_type is bool
    assert column.nullable is False
