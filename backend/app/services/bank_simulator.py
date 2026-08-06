"""Business logic for projecting bank account growth over time.

This is the core of the Bank Account Simulator feature: given an account's
current balance, interest rate, and compounding frequency, plus any active
recurring deposits/withdrawals, it produces a month-by-month projection used
to render the growth chart on the frontend. It is invoked from the
POST /bank-accounts/{id}/simulate endpoint in api/v1/bank_accounts.py. All
money math is delegated to core/calculations/compound_interest.py so the
compounding formula itself lives in exactly one place.
"""

from decimal import Decimal
from datetime import date
from dateutil.relativedelta import relativedelta
from dataclasses import dataclass

from app.models.bank_accounts import BankAccount, RecurringAction, ActionType, FrequencyUnit
from app.core.calculations.compound_interest import calculate_monthly_interest


# One row of a growth projection: the account's projected state at a given month offset.
@dataclass
class ProjectionPoint:
    month: int
    date: date
    balance: Decimal
    principal: Decimal
    interest_earned: Decimal
    deposits: Decimal
    withdrawals: Decimal


class BankSimulatorService:
    """Generates month-by-month balance projections for a single bank account."""

    def _get_monthly_recurring_amount(
        self, actions: list[RecurringAction], action_type: ActionType
    ) -> Decimal:
        """Sum a set of recurring actions of one type into an equivalent flat monthly amount."""
        total = Decimal("0")
        for action in actions:
            if action.action_type != action_type or not action.is_active:
                continue

            # Normalize each action's cadence to a monthly-equivalent amount.
            # Weeks and days use average calendar conversions (4.33 weeks/month, 30 days/month)
            # since projections are computed on a monthly grid rather than a daily one.
            if action.frequency_unit == FrequencyUnit.MONTHS:
                monthly = action.amount / action.frequency_value
            elif action.frequency_unit == FrequencyUnit.WEEKS:
                monthly = (action.amount / action.frequency_value) * Decimal("4.33")
            else:
                monthly = (action.amount / action.frequency_value) * Decimal("30")

            total += monthly

        return total.quantize(Decimal("0.01"))

    def generate_projection(
        self,
        account: BankAccount,
        months: int,
        recurring_actions: list[RecurringAction] | None = None,
        start_date: date | None = None,
    ) -> list[ProjectionPoint]:
        """Build the month-by-month balance/interest/deposit/withdrawal series for an account."""
        if start_date is None:
            start_date = date.today()

        if recurring_actions is None:
            recurring_actions = []

        monthly_deposits = self._get_monthly_recurring_amount(
            recurring_actions, ActionType.DEPOSIT
        )
        monthly_withdrawals = self._get_monthly_recurring_amount(
            recurring_actions, ActionType.WITHDRAWAL
        )

        projections = []
        balance = account.current_balance
        total_deposits = Decimal("0")
        total_withdrawals = Decimal("0")
        total_interest = Decimal("0")
        principal = account.principal

        annual_rate = account.interest_rate or Decimal("0")
        compounding = account.compounding_frequency

        for month in range(months + 1):
            current_date = start_date + relativedelta(months=month)

            # Month 0 is the starting snapshot - no interest or recurring actions applied yet.
            if month == 0:
                projections.append(
                    ProjectionPoint(
                        month=month,
                        date=current_date,
                        balance=balance,
                        principal=principal,
                        interest_earned=Decimal("0"),
                        deposits=Decimal("0"),
                        withdrawals=Decimal("0"),
                    )
                )
                continue

            # Apply this month's interest accrual, then the recurring deposit/withdrawal.
            monthly_interest = calculate_monthly_interest(balance, annual_rate, compounding)
            total_interest += monthly_interest

            balance += monthly_interest
            balance += monthly_deposits
            balance -= monthly_withdrawals

            total_deposits += monthly_deposits
            total_withdrawals += monthly_withdrawals

            # A simulated account cannot go negative (e.g. withdrawals exceeding balance).
            balance = max(balance, Decimal("0"))

            projections.append(
                ProjectionPoint(
                    month=month,
                    date=current_date,
                    balance=balance.quantize(Decimal("0.01")),
                    principal=(principal + total_deposits - total_withdrawals).quantize(
                        Decimal("0.01")
                    ),
                    interest_earned=total_interest.quantize(Decimal("0.01")),
                    deposits=total_deposits.quantize(Decimal("0.01")),
                    withdrawals=total_withdrawals.quantize(Decimal("0.01")),
                )
            )

        return projections
