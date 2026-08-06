"""Pure functions surfacing 2026 gift-tax guidance for 529 education savings accounts.

Every figure here was researched and documented in docs/phase4.5-plan.md before this
module was written, per docs/claude.md's instruction to research external-rule features
thoroughly and record the rules for future maintenance when they change (the IRS
re-indexes the gift tax exclusion annually). Unlike services/retirement_rules.py, nothing
here is a hard limit - a 529 has no IRS-imposed contribution cap, only a gift-tax
*reporting* threshold, so every function here is informational only and nothing raises or
blocks a contribution. Functions are pure (no database/FastAPI dependency) and
Decimal-based throughout, matching core/calculations/compound_interest.py's approach to
avoiding float rounding error, and are unit-tested directly in
tests/test_education_rules.py.
"""

from decimal import Decimal

# ---------------------------------------------------------------------------
# 2026 figures (see docs/phase4.5-plan.md "2026 529 Plan Rules (Researched)")
# ---------------------------------------------------------------------------

GIFT_TAX_ANNUAL_EXCLUSION_2026 = Decimal("19000")  # per giver, per beneficiary
SUPERFUNDING_YEARS = 5  # the 5-year gift-tax averaging election

ROTH_ROLLOVER_LIFETIME_LIMIT = Decimal("35000")  # per beneficiary, lifetime (SECURE 2.0 S126)
ROTH_ROLLOVER_MIN_ACCOUNT_AGE_YEARS = 15
ROTH_ROLLOVER_MIN_FUND_AGE_YEARS = 5
# Same 2026 IRA limit figures used by retirement_rules.py - the annual rollover amount
# counts toward the beneficiary's own regular IRA contribution limit for that year.
_IRA_LIMIT_UNDER_50 = Decimal("7500")
_IRA_LIMIT_50_PLUS = Decimal("8600")

STUDENT_LOAN_REPAYMENT_LIFETIME_LIMIT = Decimal("10000")  # per borrower, not inflation-indexed
K12_WITHDRAWAL_ANNUAL_LIMIT_2026 = Decimal("20000")  # per student, per year (raised from $10k by OBBBA)


def get_annual_gift_tax_exclusion(gift_splitting: bool = False, year: int = 2026) -> Decimal:
    """$19,000 per beneficiary; doubled to $38,000 if a married couple elects gift-splitting."""
    exclusion = GIFT_TAX_ANNUAL_EXCLUSION_2026
    return exclusion * 2 if gift_splitting else exclusion


def get_superfunding_lump_sum(gift_splitting: bool = False, year: int = 2026) -> Decimal:
    """5x the annual exclusion - the max a donor can front-load in one year under the
    5-year election (IRS Form 709) without triggering gift tax beyond the filing itself."""
    return get_annual_gift_tax_exclusion(gift_splitting, year) * SUPERFUNDING_YEARS


def get_gift_tax_info(
    beneficiary_name: str,
    beneficiary_contribution_ytd: Decimal,
    new_contribution_amount: Decimal | None = None,
    gift_splitting: bool = False,
    year: int = 2026,
) -> dict:
    """Never raises. Compares this beneficiary's YTD contributions (optionally plus a
    prospective new contribution) against the annual gift-tax exclusion and returns a
    human-readable note - rather than blocking - since exceeding the exclusion just means
    the excess counts against the giver's lifetime gift/estate tax exemption, not that the
    contribution itself is disallowed.
    """
    annual_exclusion = get_annual_gift_tax_exclusion(gift_splitting, year)
    superfunding_lump_sum = get_superfunding_lump_sum(gift_splitting, year)
    total_after_new = beneficiary_contribution_ytd + (new_contribution_amount or Decimal("0"))
    remaining = max(annual_exclusion - beneficiary_contribution_ytd, Decimal("0"))
    would_exceed = total_after_new > annual_exclusion

    if would_exceed:
        note = (
            f"This would bring {beneficiary_name}'s gifts this year to "
            f"{total_after_new.quantize(Decimal('0.01'))}, over the {annual_exclusion} annual "
            f"gift-tax exclusion. This doesn't block the contribution - it just means the "
            f"excess counts against your lifetime gift/estate tax exemption and should be "
            f"reported on IRS Form 709. Consider a 5-year 'superfunding' election "
            f"(up to {superfunding_lump_sum}) if you're making one large contribution."
        )
    else:
        note = (
            f"{beneficiary_name} has {remaining.quantize(Decimal('0.01'))} of this year's "
            f"{annual_exclusion} gift-tax exclusion remaining."
        )

    return {
        "beneficiary_name": beneficiary_name,
        "annual_exclusion": annual_exclusion,
        "superfunding_lump_sum": superfunding_lump_sum,
        "beneficiary_contribution_ytd": beneficiary_contribution_ytd,
        "remaining_before_exclusion": remaining,
        "would_exceed_exclusion": would_exceed,
        "note": note,
    }


def get_roth_rollover_eligibility(
    account_opened_years_ago: float,
    oldest_eligible_funds_years_ago: float,
    beneficiary_has_earned_income: bool,
    lifetime_amount_already_rolled_over: Decimal,
    beneficiary_age: int | None = None,
) -> dict:
    """Checks SECURE 2.0 S126 requirements (15-year account age, 5-year fund age, earned
    income) for rolling unused 529 funds into the beneficiary's own Roth IRA, and computes
    remaining lifetime rollover room under the $35,000 cap, further capped by the
    beneficiary's own annual IRA contribution limit as the effective single-year rollable
    amount. Not wired to an API endpoint yet (no UI consumes it in v1) - available here for
    future use and exercised directly by tests/test_education_rules.py.
    """
    account_old_enough = account_opened_years_ago >= ROTH_ROLLOVER_MIN_ACCOUNT_AGE_YEARS
    funds_old_enough = oldest_eligible_funds_years_ago >= ROTH_ROLLOVER_MIN_FUND_AGE_YEARS
    eligible = account_old_enough and funds_old_enough and beneficiary_has_earned_income

    lifetime_remaining = max(
        ROTH_ROLLOVER_LIFETIME_LIMIT - lifetime_amount_already_rolled_over, Decimal("0")
    )
    annual_ira_limit = (
        _IRA_LIMIT_50_PLUS if beneficiary_age is not None and beneficiary_age >= 50
        else _IRA_LIMIT_UNDER_50
    )
    max_rollover_this_year = min(lifetime_remaining, annual_ira_limit) if eligible else Decimal("0")

    ineligibility_reasons = []
    if not account_old_enough:
        ineligibility_reasons.append(
            f"the 529 account must be open at least {ROTH_ROLLOVER_MIN_ACCOUNT_AGE_YEARS} years"
        )
    if not funds_old_enough:
        ineligibility_reasons.append(
            f"the funds being rolled over must be at least {ROTH_ROLLOVER_MIN_FUND_AGE_YEARS} years old"
        )
    if not beneficiary_has_earned_income:
        ineligibility_reasons.append("the beneficiary must have earned income")

    return {
        "eligible": eligible,
        "lifetime_limit": ROTH_ROLLOVER_LIFETIME_LIMIT,
        "lifetime_remaining": lifetime_remaining,
        "max_rollover_this_year": max_rollover_this_year,
        "ineligibility_reasons": ineligibility_reasons,
    }
