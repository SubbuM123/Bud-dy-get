"""Business logic for projecting education savings account growth over time.

Mirrors services/retirement_simulator.py's structure (which itself mirrors
services/bank_simulator.py), but with no employer-match piece - 529 plans
aren't employer-sponsored, so there's no equivalent of
retirement_simulator.py's _monthly_employer_match. Recurring contributions
(EducationRecurringContribution rows) are folded the same way
retirement_simulator.py folds RetirementRecurringContribution rows: each is
normalized to a flat monthly-equivalent amount (a yearly contribution
divided by 12) and applied identically every month of the simulation,
regardless of its own start_date/end_date - the same documented
simplification the other two simulators already make, kept consistent here
rather than reimplementing per-month date-window logic for one module and
not the others. Invoked from POST /education-accounts/{id}/simulate in
api/v1/education_accounts.py.
"""

from decimal import Decimal
from datetime import date
from dateutil.relativedelta import relativedelta
from dataclasses import dataclass

from app.models.education_accounts import EducationAccount, EducationRecurringContribution
from app.models.enums import CompoundingFrequency, ContributionFrequency
from app.core.calculations.compound_interest import calculate_monthly_interest


# One row of a growth projection: the account's projected state at a given month offset.
@dataclass
class EducationProjectionPoint:
    month: int
    date: date
    balance: Decimal
    contributions: Decimal
    growth: Decimal


class EducationSimulatorService:
    """Generates month-by-month balance projections for a single education savings account."""

    def _monthly_recurring_amount(
        self, contributions: list[EducationRecurringContribution]
    ) -> Decimal:
        """Sum a set of active recurring contributions into an equivalent flat monthly amount."""
        total = Decimal("0")
        for contribution in contributions:
            if not contribution.is_active:
                continue
            if contribution.frequency == ContributionFrequency.YEARLY:
                total += contribution.amount / Decimal("12")
            else:
                total += contribution.amount
        return total.quantize(Decimal("0.01"))

    def generate_projection(
        self,
        account: EducationAccount,
        months: int,
        monthly_contribution: Decimal = Decimal("0"),
        recurring_contributions: list[EducationRecurringContribution] | None = None,
        start_date: date | None = None,
    ) -> list[EducationProjectionPoint]:
        """Build the month-by-month balance/contribution/growth series for an account.

        `monthly_contribution` is an extra hypothetical amount on top of whatever
        `recurring_contributions` already contribute each month - see
        schemas/education_accounts.py:EducationSimulationRequest for why both exist.
        """
        if start_date is None:
            start_date = date.today()

        monthly_recurring = self._monthly_recurring_amount(recurring_contributions or [])
        total_monthly_contribution = monthly_contribution + monthly_recurring

        projections = []
        balance = account.balance
        total_contributions = Decimal("0")
        total_growth = Decimal("0")

        annual_rate = account.expected_return_rate or Decimal("0")

        for month in range(months + 1):
            current_date = start_date + relativedelta(months=month)

            # Month 0 is the starting snapshot - no growth or contributions applied yet.
            if month == 0:
                projections.append(
                    EducationProjectionPoint(
                        month=month,
                        date=current_date,
                        balance=balance,
                        contributions=Decimal("0"),
                        growth=Decimal("0"),
                    )
                )
                continue

            monthly_growth = calculate_monthly_interest(
                balance, annual_rate, CompoundingFrequency.MONTHLY
            )
            total_growth += monthly_growth

            balance += monthly_growth
            balance += total_monthly_contribution
            total_contributions += total_monthly_contribution

            projections.append(
                EducationProjectionPoint(
                    month=month,
                    date=current_date,
                    balance=balance.quantize(Decimal("0.01")),
                    contributions=total_contributions.quantize(Decimal("0.01")),
                    growth=total_growth.quantize(Decimal("0.01")),
                )
            )

        return projections
