"""Regression-style check for the enum-binding bug documented in docs/progress.md
(session 2026-07-31/08-01, #8): SQLAlchemy's `Enum(SomeEnum)` binds using the Python enum
member's *name* by default, not its *value* - `values_callable` is required on every
SQLEnum(...) column, or every insert fails against a real Postgres database once the
column's bound values ("TRADITIONAL_401K") don't match the Postgres enum type's actual
labels (lowercase, per alembic/versions/003_add_retirement_accounts.py). Checked directly
against each column's compiled `.enums` list - no database needed - same approach as
test_bank_account_enums.py.
"""

from app.models.retirement_accounts import RetirementAccount, RetirementRecurringContribution
from app.models.user import User

# Must match the literal enum labels in alembic/versions/003_add_retirement_accounts.py.
EXPECTED_RETIREMENT_ACCOUNT_TYPES = [
    "traditional_401k", "roth_401k", "traditional_ira", "roth_ira",
    "sep_ira", "simple_ira", "hsa",
]
EXPECTED_VESTING_TYPES = ["immediate", "cliff", "graded"]
EXPECTED_FILING_STATUSES = [
    "single", "married_filing_jointly", "married_filing_separately", "head_of_household",
]

# Must match the literal enum labels in
# alembic/versions/004_add_retirement_recurring_contributions.py.
EXPECTED_CONTRIBUTION_FREQUENCIES = ["monthly", "yearly"]


def test_retirement_account_type_binds_lowercase_values_matching_the_migration():
    assert RetirementAccount.__table__.c.account_type.type.enums == EXPECTED_RETIREMENT_ACCOUNT_TYPES


def test_vesting_type_binds_lowercase_values_matching_the_migration():
    assert RetirementAccount.__table__.c.vesting_type.type.enums == EXPECTED_VESTING_TYPES


def test_user_filing_status_binds_lowercase_values_matching_the_migration():
    assert User.__table__.c.filing_status.type.enums == EXPECTED_FILING_STATUSES


def test_user_has_employer_retirement_plan_is_a_non_nullable_boolean():
    column = User.__table__.c.has_employer_retirement_plan
    assert column.type.python_type is bool
    assert column.nullable is False


def test_recurring_contribution_frequency_binds_lowercase_values_matching_the_migration():
    assert (
        RetirementRecurringContribution.__table__.c.frequency.type.enums
        == EXPECTED_CONTRIBUTION_FREQUENCIES
    )
