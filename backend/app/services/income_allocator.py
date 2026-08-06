"""Folds active recurring Income allocations into the monthly-equivalent recurring stubs
that bank_simulator.py, retirement_simulator.py, and education_simulator.py already know
how to consume - so a user's salary split (see models/income.py) shows up in every
account's growth projection without any of those three simulators needing to know Income
exists at all.

Each simulator already accepts a plain list of "recurring rule"-shaped objects
(RecurringAction, RetirementRecurringContribution, EducationRecurringContribution) and
only reads a handful of duck-typed attributes off each one - see this module's
`IncomeAllocationStub`, which carries every attribute any of the three simulators might
read, so the very same stub instances can be merged into whichever list applies. The
caller (api/v1/bank_accounts.py, api/v1/retirement_accounts.py, and
api/v1/education_accounts.py's simulate endpoints) is responsible for picking `stubs_for`
results out for the specific account(s) it's projecting.

Converting each Income's per-occurrence `amount` into a flat monthly-equivalent figure
before splitting it by allocation percentage is the same simplification those three
simulators already make for their own native recurring rules (a yearly retirement
contribution folded to amount/12, a weekly bank RecurringAction folded via a 4.33
weeks/month average) - kept consistent here rather than teaching every simulator's
month-by-month loop about weekly/biweekly/semi-monthly calendars it doesn't otherwise
need to understand.
"""

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from app.models.income import Income
from app.models.enums import (
    AllocationDestinationType,
    ActionType,
    FrequencyUnit,
    ContributionFrequency,
)

# How many times a year an income at each frequency is received, divided by 12 to get a
# monthly-equivalent occurrence count. Semi-monthly (the 1st/15th, or similar) is exactly
# 2/month by definition rather than a calendar average, unlike the other three.
_OCCURRENCES_PER_MONTH = {
    "weekly": Decimal("52") / Decimal("12"),
    "biweekly": Decimal("26") / Decimal("12"),
    "semi_monthly": Decimal("2"),
    "monthly": Decimal("1"),
}


# Duck-typed stand-in carrying every attribute any of the three simulators' recurring-rule
# readers might access (see this module's docstring) - action_type/frequency_value/
# frequency_unit for BankSimulatorService, frequency for
# RetirementSimulatorService/EducationSimulatorService. Always a monthly-equivalent
# DEPOSIT of `amount`, since that's what it already was by the time this is built - see
# `_monthly_equivalent` below.
@dataclass
class IncomeAllocationStub:
    amount: Decimal
    is_active: bool = True
    action_type: ActionType = ActionType.DEPOSIT
    frequency_value: int = 1
    frequency_unit: FrequencyUnit = FrequencyUnit.MONTHS
    frequency: ContributionFrequency = ContributionFrequency.MONTHLY


def _monthly_equivalent(income: Income) -> Decimal:
    occurrences = _OCCURRENCES_PER_MONTH.get(
        income.frequency.value if income.frequency else "monthly", Decimal("1")
    )
    return (income.amount * occurrences).quantize(Decimal("0.01"))


# Build one IncomeAllocationStub per (active, recurring) income allocation, grouped by
# the destination it feeds - ready to be extended onto whatever recurring_actions/
# recurring_contributions list a simulate endpoint already builds for that same account.
def build_allocation_stubs(
    incomes: list[Income],
) -> dict[tuple[AllocationDestinationType, str], list[IncomeAllocationStub]]:
    stubs: dict[tuple[AllocationDestinationType, str], list[IncomeAllocationStub]] = defaultdict(list)

    for income in incomes:
        if not income.is_active or not income.is_recurring:
            continue
        monthly_total = _monthly_equivalent(income)

        for allocation in income.allocations:
            share = (monthly_total * allocation.percentage / Decimal("100")).quantize(Decimal("0.01"))
            if share <= 0:
                continue
            stubs[(allocation.destination_type, allocation.destination_id)].append(
                IncomeAllocationStub(amount=share)
            )

    return stubs
