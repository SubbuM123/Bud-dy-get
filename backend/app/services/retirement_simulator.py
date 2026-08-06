"""Business logic for projecting retirement account growth over time.

Mirrors services/bank_simulator.py's structure and reuses the same
core/calculations/compound_interest.py math for the growth portion, but adds
monthly employee contributions plus an employer match computed via
services/retirement_rules.calculate_employer_match for 401(k)/Roth 401(k)
accounts. Growth always compounds monthly regardless of account type, since
RetirementAccount (unlike BankAccount) has no user-selectable compounding
frequency - only a single expected_return_rate field. Invoked from
POST /retirement-accounts/{id}/simulate in api/v1/retirement_accounts.py.

Recurring contributions (RetirementRecurringContribution rows) are folded in
the same way bank_simulator.py folds RecurringAction rows: each is
normalized to a flat monthly-equivalent amount (a yearly contribution
divided by 12) and applied identically every month of the simulation,
regardless of its own start_date/end_date - the same documented
simplification bank_simulator.py already makes for its recurring actions,
kept consistent here rather than reimplementing per-month date-window logic
for one grid and not the other.
"""

from decimal import Decimal
from datetime import date
from dateutil.relativedelta import relativedelta
from dataclasses import dataclass

from app.models.retirement_accounts import RetirementAccount, RetirementRecurringContribution
from app.models.enums import CompoundingFrequency, RetirementAccountType, ContributionFrequency
from app.core.calculations.compound_interest import calculate_monthly_interest
from app.services.retirement_rules import calculate_employer_match

_401K_TYPES = {RetirementAccountType.TRADITIONAL_401K, RetirementAccountType.ROTH_401K}


# One row of a growth projection: the account's projected state at a given month offset.
@dataclass
class RetirementProjectionPoint:
    month: int
    date: date
    balance: Decimal
    employee_contributions: Decimal
    employer_contributions: Decimal
    growth: Decimal


class RetirementSimulatorService:
    """Generates month-by-month balance projections for a single retirement account."""

    def _monthly_recurring_amount(
        self, contributions: list[RetirementRecurringContribution]
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

    def _monthly_employer_match(
        self, account: RetirementAccount, monthly_employee_contribution: Decimal
    ) -> Decimal:
        """Employer match for one month's employee contribution (0 for non-401(k) accounts)."""
        if account.account_type not in _401K_TYPES:
            return Decimal("0")
        if not account.annual_salary or not account.employer_match_percent or not account.employer_match_limit_percent:
            return Decimal("0")

        monthly_salary = account.annual_salary / Decimal("12")
        return calculate_employer_match(
            salary=monthly_salary,
            employee_contribution=monthly_employee_contribution,
            match_percent=account.employer_match_percent,
            match_limit_percent=account.employer_match_limit_percent,
        )

    def generate_projection(
        self,
        account: RetirementAccount,
        months: int,
        monthly_employee_contribution: Decimal = Decimal("0"),
        recurring_contributions: list[RetirementRecurringContribution] | None = None,
        start_date: date | None = None,
    ) -> list[RetirementProjectionPoint]:
        """Build the month-by-month balance/contribution/growth series for an account.

        `monthly_employee_contribution` is an extra hypothetical amount on top of whatever
        `recurring_contributions` already contribute each month - see
        schemas/retirement_accounts.py:RetirementSimulationRequest for why both exist.
        """
        if start_date is None:
            start_date = date.today()

        monthly_recurring = self._monthly_recurring_amount(recurring_contributions or [])
        total_monthly_employee_contribution = monthly_employee_contribution + monthly_recurring

        monthly_employer_match = self._monthly_employer_match(
            account, total_monthly_employee_contribution
        )

        projections = []
        balance = account.balance
        total_employee = Decimal("0")
        total_employer = Decimal("0")
        total_growth = Decimal("0")

        annual_rate = account.expected_return_rate or Decimal("0")

        for month in range(months + 1):
            current_date = start_date + relativedelta(months=month)

            # Month 0 is the starting snapshot - no growth or contributions applied yet.
            if month == 0:
                projections.append(
                    RetirementProjectionPoint(
                        month=month,
                        date=current_date,
                        balance=balance,
                        employee_contributions=Decimal("0"),
                        employer_contributions=Decimal("0"),
                        growth=Decimal("0"),
                    )
                )
                continue

            monthly_growth = calculate_monthly_interest(
                balance, annual_rate, CompoundingFrequency.MONTHLY
            )
            total_growth += monthly_growth

            balance += monthly_growth
            balance += total_monthly_employee_contribution
            balance += monthly_employer_match

            total_employee += total_monthly_employee_contribution
            total_employer += monthly_employer_match

            projections.append(
                RetirementProjectionPoint(
                    month=month,
                    date=current_date,
                    balance=balance.quantize(Decimal("0.01")),
                    employee_contributions=total_employee.quantize(Decimal("0.01")),
                    employer_contributions=total_employer.quantize(Decimal("0.01")),
                    growth=total_growth.quantize(Decimal("0.01")),
                )
            )

        return projections
