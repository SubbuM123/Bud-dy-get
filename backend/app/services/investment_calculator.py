"""Pure calculation functions for the Investments module (Phase 5): weighted-average cost
basis, realized P/L on a sale, bond amortization (straight-line method), property compound
growth, and RSU vesting math.

No database/FastAPI dependency, Decimal-based throughout - the same separation
services/retirement_rules.py and services/education_rules.py already follow, and
unit-tested directly in tests/test_investment_calculator.py rather than only indirectly
through the API layer.
"""

from datetime import date
from decimal import Decimal

from app.models.enums import BondPaymentFrequency, VestingType

_CENTS = Decimal("0.01")
_PAYMENTS_PER_YEAR = {
    BondPaymentFrequency.ANNUALLY: 1,
    BondPaymentFrequency.SEMI_ANNUALLY: 2,
}


# --- Stocks --------------------------------------------------------------------------------

def calculate_average_cost(
    existing_shares: Decimal,
    existing_avg_cost: Decimal,
    new_shares: Decimal,
    new_price_per_share: Decimal,
) -> Decimal:
    """Weighted-average cost per share after buying `new_shares` at `new_price_per_share`
    on top of an existing holding. Used for every buy, including a position's first (where
    `existing_shares` is 0 and the result collapses to `new_price_per_share`)."""
    total_cost = (existing_shares * existing_avg_cost) + (new_shares * new_price_per_share)
    total_shares = existing_shares + new_shares
    if total_shares <= 0:
        return Decimal("0")
    return (total_cost / total_shares).quantize(_CENTS)


def calculate_realized_pnl(
    shares_sold: Decimal,
    sale_price_per_share: Decimal,
    average_cost_per_share: Decimal,
) -> Decimal:
    """Profit (positive) or loss (negative) realized by selling `shares_sold` at
    `sale_price_per_share` against the position's weighted-average cost basis. A sell never
    changes `average_cost_per_share` itself - only a subsequent buy does."""
    proceeds = shares_sold * sale_price_per_share
    cost_basis = shares_sold * average_cost_per_share
    return (proceeds - cost_basis).quantize(_CENTS)


# --- Bonds ---------------------------------------------------------------------------------

def _amortization_periods(
    purchase_date: date, maturity_date: date, payment_frequency: BondPaymentFrequency
) -> list[date]:
    """Every coupon-payment date from just after `purchase_date` through `maturity_date`
    inclusive, spaced evenly by `payment_frequency` - the straight-line method spreads the
    purchase premium/discount evenly across exactly these periods."""
    payments_per_year = _PAYMENTS_PER_YEAR[payment_frequency]
    months_between = 12 // payments_per_year

    periods: list[date] = []
    year = purchase_date.year
    month = purchase_date.month
    day = purchase_date.day
    while True:
        month += months_between
        year += (month - 1) // 12
        month = ((month - 1) % 12) + 1
        # Clamp the day for months shorter than the purchase day (e.g. Jan 31 -> Feb 28).
        for candidate_day in range(day, 0, -1):
            try:
                period_date = date(year, month, candidate_day)
                break
            except ValueError:
                continue
        periods.append(period_date)
        if period_date >= maturity_date:
            break
    return periods


def calculate_bond_amortization_schedule(
    purchase_price: Decimal,
    face_value: Decimal,
    coupon_rate: Decimal,
    payment_frequency: BondPaymentFrequency,
    purchase_date: date,
    maturity_date: date,
) -> list[dict]:
    """Straight-line amortization: the total premium (`purchase_price > face_value`) or
    discount (`purchase_price < face_value`) is spread evenly across every coupon period
    between `purchase_date` and `maturity_date`, so book value moves from `purchase_price`
    to exactly `face_value` by the final period. Each period's coupon payment is
    `face_value * coupon_rate / payments_per_year`, paid regardless of the bond's
    premium/discount status (coupon and amortization are independent cash flows).

    Returns a list of dicts (not a dataclass - directly matches
    schemas/investments.py:BondAmortizationPeriod's field names) ordered earliest-first.
    """
    payments_per_year = _PAYMENTS_PER_YEAR[payment_frequency]
    periods = _amortization_periods(purchase_date, maturity_date, payment_frequency)
    if not periods:
        return []

    total_adjustment = face_value - purchase_price
    per_period_adjustment = (total_adjustment / len(periods)).quantize(_CENTS)
    coupon_payment = (face_value * coupon_rate / payments_per_year).quantize(_CENTS)

    schedule: list[dict] = []
    book_value = purchase_price
    for index, period_date in enumerate(periods):
        is_last = index == len(periods) - 1
        # The final period lands exactly on face_value, absorbing any rounding remainder
        # left over from quantizing per_period_adjustment.
        if is_last:
            amortization_amount = face_value - book_value
        else:
            amortization_amount = per_period_adjustment
        book_value = (book_value + amortization_amount).quantize(_CENTS)
        schedule.append(
            {
                "period_date": period_date,
                "coupon_payment": coupon_payment,
                "amortization_amount": amortization_amount,
                "book_value": book_value,
            }
        )
    return schedule


def calculate_bond_current_book_value(
    purchase_price: Decimal,
    face_value: Decimal,
    coupon_rate: Decimal,
    payment_frequency: BondPaymentFrequency,
    purchase_date: date,
    maturity_date: date,
    as_of_date: date | None = None,
) -> Decimal:
    """Book value as of `as_of_date` (default today): `purchase_price` before the bond is
    purchased, `face_value` on/after maturity, otherwise the most recently passed period's
    book value from the same amortization schedule `calculate_bond_amortization_schedule`
    builds - the two never drift apart since this calls that function directly."""
    if as_of_date is None:
        as_of_date = date.today()
    if as_of_date <= purchase_date:
        return purchase_price
    if as_of_date >= maturity_date:
        return face_value

    schedule = calculate_bond_amortization_schedule(
        purchase_price, face_value, coupon_rate, payment_frequency, purchase_date, maturity_date
    )
    book_value = purchase_price
    for period in schedule:
        if period["period_date"] > as_of_date:
            break
        book_value = period["book_value"]
    return book_value


# --- Property ------------------------------------------------------------------------------

def calculate_property_current_value(
    cost: Decimal,
    expected_return_rate: Decimal,
    purchase_date: date,
    as_of_date: date | None = None,
) -> Decimal:
    """Compound annual growth from `cost` at `expected_return_rate`, elapsed from
    `purchase_date` to `as_of_date` (default today) - the same compound-growth shape
    services/education_rules.py and the retirement/education simulators already use for
    projecting a balance forward, applied here to a single lump sum with no contributions."""
    if as_of_date is None:
        as_of_date = date.today()
    if as_of_date <= purchase_date:
        return cost

    years = Decimal(str((as_of_date - purchase_date).days)) / Decimal("365.25")
    growth_factor = (Decimal("1") + expected_return_rate) ** years
    return (cost * growth_factor).quantize(_CENTS)


# --- RSU vesting ---------------------------------------------------------------------------

def calculate_rsu_vested_shares(
    total_shares: Decimal,
    shares_already_vested: Decimal,
    vesting_type: VestingType,
    grant_date: date,
    vesting_years: int | None,
    cliff_date: date | None,
    as_of_date: date | None = None,
) -> Decimal:
    """Additional shares that vest as of `as_of_date` (default today), on top of whatever
    has already vested - mirrors RetirementAccount's three vesting schedules
    (immediate/cliff/graded). Returns 0 rather than negative if nothing new has vested yet
    or the grant is already fully vested. `grant_date` is the income's own `start_date` -
    see docs/phase5-plan.md's "Deliberate Scope Limits" for why there's no separate field.
    """
    if as_of_date is None:
        as_of_date = date.today()

    remaining = total_shares - shares_already_vested
    if remaining <= 0:
        return Decimal("0")

    if vesting_type == VestingType.IMMEDIATE:
        return remaining

    if vesting_type == VestingType.CLIFF:
        if cliff_date is not None and as_of_date >= cliff_date:
            return remaining
        return Decimal("0")

    if vesting_type == VestingType.GRADED:
        if not vesting_years or as_of_date <= grant_date:
            return Decimal("0")
        years_elapsed = Decimal(str((as_of_date - grant_date).days)) / Decimal("365.25")
        vested_fraction = min(years_elapsed / Decimal(str(vesting_years)), Decimal("1"))
        total_should_be_vested = (total_shares * vested_fraction).quantize(Decimal("0.0001"))
        newly_vested = total_should_be_vested - shares_already_vested
        return max(newly_vested, Decimal("0")).quantize(Decimal("0.0001"))

    return Decimal("0")
