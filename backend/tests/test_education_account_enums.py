"""Regression-style check for the enum-binding bug documented in docs/progress.md
(session 2026-07-31/08-01, #8): SQLAlchemy's `Enum(SomeEnum)` binds using the Python enum
member's *name* by default, not its *value* - `values_callable` is required, or every
insert fails against a real Postgres database once the column's bound values
("529_PLAN") don't match the Postgres enum type's actual labels (lowercase, per
alembic/versions/006_add_education_accounts.py). Checked directly against each column's
compiled `.enums` list - no database needed - same approach as
test_retirement_account_enums.py. Also confirms the reused `contributionfrequency` type
(created by migration 004 for retirement) binds correctly on this module's table too.
"""

from decimal import Decimal

from app.models.education_accounts import EducationAccount, EducationRecurringContribution

# Must match the literal enum labels in alembic/versions/006_add_education_accounts.py.
EXPECTED_EDUCATION_ACCOUNT_TYPES = ["529_plan", "coverdell_esa", "custodial_utma_ugma"]
EXPECTED_CONTRIBUTION_FREQUENCIES = ["monthly", "yearly"]


def test_education_account_type_binds_lowercase_values_matching_the_migration():
    assert EducationAccount.__table__.c.account_type.type.enums == EXPECTED_EDUCATION_ACCOUNT_TYPES


def test_education_recurring_contribution_frequency_binds_values_matching_the_migration():
    assert (
        EducationRecurringContribution.__table__.c.frequency.type.enums
        == EXPECTED_CONTRIBUTION_FREQUENCIES
    )


def test_education_account_contribution_ytd_is_a_numeric_column():
    column = EducationAccount.__table__.c.contribution_ytd
    assert column.type.python_type is Decimal
