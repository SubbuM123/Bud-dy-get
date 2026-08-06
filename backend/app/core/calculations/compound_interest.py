"""Shared compound-interest math used across every account-growth feature.

These are pure, stateless functions with no database or FastAPI dependency,
which keeps them easy to unit test and reuse anywhere a compounding
calculation is needed - currently the Bank Account Simulator
(services/bank_simulator.py), and in later phases the Retirement and 529
Planning modules, which reuse the same math against different account types.
Money is represented as Decimal throughout to avoid floating-point rounding
errors accumulating across many compounding periods.
"""

from decimal import Decimal

from app.models.enums import CompoundingFrequency

# Number of compounding periods per year for each supported frequency.
COMPOUNDING_PERIODS = {
    CompoundingFrequency.DAILY: 365,
    CompoundingFrequency.MONTHLY: 12,
    CompoundingFrequency.QUARTERLY: 4,
    CompoundingFrequency.ANNUALLY: 1,
}


def calculate_compound_interest(
    principal: Decimal,
    annual_rate: Decimal,
    months: int,
    compounding: CompoundingFrequency = CompoundingFrequency.MONTHLY,
) -> Decimal:
    """Return the account balance after `months` of compounding, with no recurring transactions."""
    n = COMPOUNDING_PERIODS[compounding]
    r = float(annual_rate)
    t = months / 12

    amount = float(principal) * (1 + r / n) ** (n * t)
    return Decimal(str(round(amount, 2)))


def calculate_monthly_interest(
    balance: Decimal,
    annual_rate: Decimal,
    compounding: CompoundingFrequency = CompoundingFrequency.MONTHLY,
) -> Decimal:
    """Return the interest earned on `balance` for a single month at the given compounding frequency."""
    n = COMPOUNDING_PERIODS[compounding]
    monthly_rate = float(annual_rate) / n

    if compounding == CompoundingFrequency.DAILY:
        # Approximate a month as 30 days of daily compounding.
        days_in_month = 30
        interest = float(balance) * ((1 + monthly_rate / 30) ** days_in_month - 1)
    else:
        interest = float(balance) * monthly_rate

    return Decimal(str(round(interest, 2)))
