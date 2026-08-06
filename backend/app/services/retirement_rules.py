"""Pure functions enforcing 2026 IRS rules for retirement accounts.

Every limit and phaseout range here was researched and documented in
docs/phase4-plan.md before this module was written, per claude.md's
instruction to research external-rule features thoroughly and record the
rules for future maintenance when they change (the IRS re-indexes most of
these figures annually). Functions are pure (no database/FastAPI
dependency) and Decimal-based throughout, matching
core/calculations/compound_interest.py's approach to avoiding float
rounding error, and are unit-tested directly in tests/test_retirement_rules.py.
"""

from decimal import Decimal

from app.models.enums import FilingStatus, VestingType, RetirementAccountType

# ---------------------------------------------------------------------------
# 2026 IRS limits (see docs/phase4-plan.md "2026 Retirement Account Rules")
# ---------------------------------------------------------------------------

_401K_EMPLOYEE_LIMIT_UNDER_50 = Decimal("24500")
_401K_CATCH_UP_50_TO_59_AND_64_PLUS = Decimal("8000")
_401K_SUPER_CATCH_UP_60_TO_63 = Decimal("11250")
_401K_TOTAL_LIMIT_UNDER_50 = Decimal("72000")
_401K_TOTAL_LIMIT_50_TO_59_AND_64_PLUS = Decimal("80000")
_401K_TOTAL_LIMIT_60_TO_63 = Decimal("83250")
_401K_COMPENSATION_LIMIT = Decimal("360000")

_IRA_LIMIT_UNDER_50 = Decimal("7500")
_IRA_CATCH_UP_50_PLUS = Decimal("1100")

_HSA_SELF_ONLY_LIMIT = Decimal("4400")
_HSA_FAMILY_LIMIT = Decimal("8750")
_HSA_CATCH_UP_55_PLUS = Decimal("1000")

# Roth IRA MAGI phaseout ranges. MARRIED_FILING_SEPARATELY and HEAD_OF_HOUSEHOLD aren't
# broken out in docs/phase4-plan.md's research table (which only covers Single/MFJ) - HOH
# uses the same range as Single per IRS rules, and MFS uses the well-known near-zero
# $0-$10,000 range (not inflation-adjusted, unchanged for many years) rather than being
# left unhandled.
_ROTH_IRA_PHASEOUT = {
    FilingStatus.SINGLE: (Decimal("153000"), Decimal("168000")),
    FilingStatus.HEAD_OF_HOUSEHOLD: (Decimal("153000"), Decimal("168000")),
    FilingStatus.MARRIED_FILING_JOINTLY: (Decimal("242000"), Decimal("252000")),
    FilingStatus.MARRIED_FILING_SEPARATELY: (Decimal("0"), Decimal("10000")),
}

# Traditional IRA deduction phaseout when the filer IS covered by an employer plan.
_TRADITIONAL_IRA_COVERED_PHASEOUT = {
    FilingStatus.SINGLE: (Decimal("81000"), Decimal("91000")),
    FilingStatus.HEAD_OF_HOUSEHOLD: (Decimal("81000"), Decimal("91000")),
    FilingStatus.MARRIED_FILING_JOINTLY: (Decimal("129000"), Decimal("149000")),
    FilingStatus.MARRIED_FILING_SEPARATELY: (Decimal("0"), Decimal("10000")),
}

# Traditional IRA deduction phaseout for a filer who is NOT covered by an employer plan
# but whose spouse is (MFJ only - the other filing statuses don't have this case).
_TRADITIONAL_IRA_SPOUSE_COVERED_PHASEOUT = (Decimal("242000"), Decimal("252000"))


def _phaseout_fraction(magi: Decimal, low: Decimal, high: Decimal) -> Decimal:
    """Fraction of the limit remaining at `magi` within a [low, high] phaseout band.

    1 at or below `low`, 0 at or above `high`, linearly interpolated between.
    """
    if magi <= low:
        return Decimal("1")
    if magi >= high:
        return Decimal("0")
    return (high - magi) / (high - low)


# ---------------------------------------------------------------------------
# 401(k) / Roth 401(k)
# ---------------------------------------------------------------------------

def get_401k_employee_limit(age: int, year: int = 2026) -> Decimal:
    """Employee elective-deferral limit for a 401(k)/Roth 401(k), including any catch-up."""
    if 60 <= age <= 63:
        return _401K_EMPLOYEE_LIMIT_UNDER_50 + _401K_SUPER_CATCH_UP_60_TO_63
    if age >= 50:
        return _401K_EMPLOYEE_LIMIT_UNDER_50 + _401K_CATCH_UP_50_TO_59_AND_64_PLUS
    return _401K_EMPLOYEE_LIMIT_UNDER_50


def get_401k_total_limit(age: int, year: int = 2026) -> Decimal:
    """Combined employee + employer contribution limit for a 401(k)/Roth 401(k)."""
    if 60 <= age <= 63:
        return _401K_TOTAL_LIMIT_60_TO_63
    if age >= 50:
        return _401K_TOTAL_LIMIT_50_TO_59_AND_64_PLUS
    return _401K_TOTAL_LIMIT_UNDER_50


def get_401k_catch_up_amount(age: int, year: int = 2026) -> Decimal:
    """The catch-up portion alone (0 if the age isn't eligible for one)."""
    if 60 <= age <= 63:
        return _401K_SUPER_CATCH_UP_60_TO_63
    if age >= 50:
        return _401K_CATCH_UP_50_TO_59_AND_64_PLUS
    return Decimal("0")


def calculate_employer_match(
    salary: Decimal,
    employee_contribution: Decimal,
    match_percent: Decimal,
    match_limit_percent: Decimal,
) -> Decimal:
    """Employer match for a given employee contribution.

    `match_percent` is how much of each matched dollar the employer contributes (e.g.
    0.5 = 50 cents per dollar); `match_limit_percent` caps how much of salary is eligible
    to be matched (e.g. 0.06 = up to 6% of salary). Only the employee's contribution up to
    that salary-based cap is matched - contributing beyond it earns no additional match.
    """
    if salary <= 0 or match_percent <= 0 or match_limit_percent <= 0:
        return Decimal("0")

    matchable_contribution = min(employee_contribution, salary * match_limit_percent)
    return (matchable_contribution * match_percent).quantize(Decimal("0.01"))


# ---------------------------------------------------------------------------
# IRA (Traditional + Roth share one contribution limit)
# ---------------------------------------------------------------------------

def get_ira_limit(age: int, year: int = 2026) -> Decimal:
    """Combined Traditional + Roth IRA contribution limit for the given age."""
    if age >= 50:
        return _IRA_LIMIT_UNDER_50 + _IRA_CATCH_UP_50_PLUS
    return _IRA_LIMIT_UNDER_50


def get_roth_ira_eligibility(
    magi: Decimal,
    filing_status: FilingStatus,
    age: int,
    year: int = 2026,
) -> tuple[bool, Decimal | None]:
    """Whether/how much of the IRA limit is available for a Roth IRA at this MAGI.

    Returns (eligible, contribution_limit). `contribution_limit` is the full age-based IRA
    limit when MAGI is below the phaseout floor, a reduced amount within the phaseout band,
    or Decimal("0") (with eligible=False) once MAGI reaches/exceeds the phaseout ceiling.
    """
    base_limit = get_ira_limit(age, year)
    low, high = _ROTH_IRA_PHASEOUT[filing_status]
    fraction = _phaseout_fraction(magi, low, high)

    if fraction <= 0:
        return False, Decimal("0")

    limit = (base_limit * fraction).quantize(Decimal("0.01"))
    return True, limit


def get_traditional_ira_deduction_limit(
    magi: Decimal,
    filing_status: FilingStatus,
    age: int,
    has_employer_plan: bool,
    spouse_has_employer_plan: bool = False,
    year: int = 2026,
) -> Decimal:
    """The deductible portion of a Traditional IRA contribution at this MAGI/coverage.

    Contributions are always allowed up to get_ira_limit() regardless of income - this
    answers the separate question of how much of that contribution is tax-deductible.
    Not covered by any employer plan (including a spouse's, for MFJ) is always fully
    deductible; being covered (directly, or via a spouse on a joint return) phases the
    deduction out over the relevant income band.
    """
    base_limit = get_ira_limit(age, year)

    if has_employer_plan:
        low, high = _TRADITIONAL_IRA_COVERED_PHASEOUT[filing_status]
    elif spouse_has_employer_plan and filing_status == FilingStatus.MARRIED_FILING_JOINTLY:
        low, high = _TRADITIONAL_IRA_SPOUSE_COVERED_PHASEOUT
    else:
        return base_limit

    fraction = _phaseout_fraction(magi, low, high)
    return (base_limit * fraction).quantize(Decimal("0.01"))


# ---------------------------------------------------------------------------
# HSA
# ---------------------------------------------------------------------------

def get_hsa_limit(coverage: str, age: int, year: int = 2026) -> Decimal:
    """HSA contribution limit for `coverage` ("self_only" or "family"), with 55+ catch-up."""
    base = _HSA_FAMILY_LIMIT if coverage == "family" else _HSA_SELF_ONLY_LIMIT
    if age >= 55:
        return base + _HSA_CATCH_UP_55_PLUS
    return base


# ---------------------------------------------------------------------------
# Vesting
# ---------------------------------------------------------------------------

def calculate_vested_amount(
    employer_contributions: Decimal,
    vesting_type: VestingType,
    years_employed: int,
    vesting_years: int,
) -> Decimal:
    """The portion of `employer_contributions` the employee actually owns.

    Immediate: 100% vested from day one. Cliff: 0% until `vesting_years` have elapsed,
    then 100%. Graded: vests linearly, 1/vesting_years per year, capped at 100%.
    """
    if vesting_type == VestingType.IMMEDIATE or vesting_years <= 0:
        return employer_contributions

    if vesting_type == VestingType.CLIFF:
        fraction = Decimal("1") if years_employed >= vesting_years else Decimal("0")
    else:  # GRADED
        fraction = min(Decimal(years_employed) / Decimal(vesting_years), Decimal("1"))

    return (employer_contributions * fraction).quantize(Decimal("0.01"))


def calculate_vested_percent(
    vesting_type: VestingType | None,
    years_employed: int,
    vesting_years: int | None,
) -> Decimal:
    """The vesting percentage (0-100) for display, given no vesting schedule means fully vested."""
    if vesting_type is None or not vesting_years:
        return Decimal("100")

    fraction = calculate_vested_amount(Decimal("100"), vesting_type, years_employed, vesting_years)
    return fraction.quantize(Decimal("0.01"))


# ---------------------------------------------------------------------------
# Combined contribution-limit summary (used by the /retirement-accounts/limits and
# /retirement-accounts/{id}/contribute endpoints)
# ---------------------------------------------------------------------------

# 401(k)-family account types that draw from the 401(k) employee limit rather than the
# IRA limit.
_401K_TYPES = {RetirementAccountType.TRADITIONAL_401K, RetirementAccountType.ROTH_401K}
_IRA_TYPES = {RetirementAccountType.TRADITIONAL_IRA, RetirementAccountType.ROTH_IRA}


def get_contribution_limit_info(
    account_type: RetirementAccountType,
    age: int,
    contribution_ytd: Decimal,
    magi: Decimal | None = None,
    filing_status: FilingStatus | None = None,
    has_employer_plan: bool = False,
    spouse_has_employer_plan: bool = False,
    year: int = 2026,
) -> dict:
    """Compute the full limit picture for one account, used to build ContributionLimitInfo.

    Returns a plain dict (rather than the Pydantic schema itself) so this module stays
    free of any dependency on the API layer's schemas - the router assembles the response
    model from this.
    """
    catch_up_eligible = age >= 50
    eligible = True
    eligibility_note: str | None = None

    if account_type in _401K_TYPES:
        employee_limit = get_401k_employee_limit(age, year)
        total_limit = get_401k_total_limit(age, year)
        catch_up_amount = get_401k_catch_up_amount(age, year)
    elif account_type == RetirementAccountType.ROTH_IRA:
        total_limit = None
        catch_up_amount = _IRA_CATCH_UP_50_PLUS if catch_up_eligible else Decimal("0")
        if magi is not None and filing_status is not None:
            eligible, employee_limit = get_roth_ira_eligibility(magi, filing_status, age, year)
            if not eligible:
                eligibility_note = "MAGI exceeds the Roth IRA income limit for this filing status."
            elif employee_limit < get_ira_limit(age, year):
                eligibility_note = "Contribution limit reduced by the Roth IRA income phaseout."
        else:
            employee_limit = get_ira_limit(age, year)
    elif account_type == RetirementAccountType.TRADITIONAL_IRA:
        total_limit = None
        employee_limit = get_ira_limit(age, year)
        catch_up_amount = _IRA_CATCH_UP_50_PLUS if catch_up_eligible else Decimal("0")
        if magi is not None and filing_status is not None:
            deductible = get_traditional_ira_deduction_limit(
                magi, filing_status, age, has_employer_plan, spouse_has_employer_plan, year
            )
            if deductible < employee_limit:
                eligibility_note = (
                    "Full contribution allowed, but only "
                    f"${deductible} of it is tax-deductible given income/employer-plan coverage."
                )
    else:
        # SEP IRA, SIMPLE IRA, HSA: contribution rules not yet enforced (see phase4-plan.md's
        # scope - only 401(k)/IRA/HSA limits were researched, and HSA has its own coverage-tier
        # limit computed separately via get_hsa_limit rather than through this shared helper).
        employee_limit = Decimal("0")
        total_limit = None
        catch_up_amount = Decimal("0")
        eligibility_note = "Contribution limit tracking isn't implemented for this account type yet."

    remaining = max(employee_limit - contribution_ytd, Decimal("0"))

    return {
        "account_type": account_type,
        "employee_limit": employee_limit,
        "total_limit": total_limit,
        "catch_up_eligible": catch_up_eligible,
        "catch_up_amount": catch_up_amount,
        "contribution_ytd": contribution_ytd,
        "remaining_contribution": remaining,
        "eligible": eligible,
        "eligibility_note": eligibility_note,
    }
