"""Unit tests for the pure IRS-rule functions in app/services/retirement_rules.py.

These need no database or FastAPI app, so unlike most of this suite they run under plain
`pytest` with no fixtures - the numbers themselves are asserted against the 2026 figures
researched and recorded in docs/phase4-plan.md, so a future change to those limits should
update both this file and that doc together.
"""

from decimal import Decimal

from app.models.enums import FilingStatus, VestingType, RetirementAccountType
from app.services import retirement_rules as rules


class TestFourOhOneKLimits:
    def test_employee_limit_under_50(self):
        assert rules.get_401k_employee_limit(35) == Decimal("24500")

    def test_employee_limit_50_to_59_gets_standard_catch_up(self):
        assert rules.get_401k_employee_limit(55) == Decimal("32500")

    def test_employee_limit_64_plus_gets_standard_catch_up_not_super(self):
        assert rules.get_401k_employee_limit(65) == Decimal("32500")

    def test_employee_limit_60_to_63_gets_super_catch_up(self):
        assert rules.get_401k_employee_limit(61) == Decimal("35750")

    def test_total_limit_under_50(self):
        assert rules.get_401k_total_limit(35) == Decimal("72000")

    def test_total_limit_60_to_63(self):
        assert rules.get_401k_total_limit(62) == Decimal("83250")

    def test_catch_up_amount_zero_under_50(self):
        assert rules.get_401k_catch_up_amount(40) == Decimal("0")


class TestEmployerMatch:
    def test_matches_contribution_up_to_limit(self):
        # 50% match up to 6% of a $120,000 salary = up to $7,200/yr matchable at 50c/$.
        match = rules.calculate_employer_match(
            salary=Decimal("120000"),
            employee_contribution=Decimal("5000"),
            match_percent=Decimal("0.5"),
            match_limit_percent=Decimal("0.06"),
        )
        assert match == Decimal("2500.00")

    def test_caps_match_at_the_salary_based_limit(self):
        # Employee contributes far more than the 6%-of-salary matchable cap ($7,200).
        match = rules.calculate_employer_match(
            salary=Decimal("120000"),
            employee_contribution=Decimal("20000"),
            match_percent=Decimal("0.5"),
            match_limit_percent=Decimal("0.06"),
        )
        assert match == Decimal("3600.00")

    def test_zero_when_no_match_configured(self):
        match = rules.calculate_employer_match(
            salary=Decimal("120000"),
            employee_contribution=Decimal("5000"),
            match_percent=Decimal("0"),
            match_limit_percent=Decimal("0"),
        )
        assert match == Decimal("0")


class TestIraLimit:
    def test_under_50(self):
        assert rules.get_ira_limit(30) == Decimal("7500")

    def test_50_plus_gets_catch_up(self):
        assert rules.get_ira_limit(52) == Decimal("8600")


class TestRothIraEligibility:
    def test_full_contribution_below_phaseout_floor(self):
        eligible, limit = rules.get_roth_ira_eligibility(
            Decimal("100000"), FilingStatus.SINGLE, age=30
        )
        assert eligible is True
        assert limit == Decimal("7500.00")

    def test_reduced_contribution_inside_phaseout_band(self):
        # Halfway through the $153k-$168k Single phaseout band.
        eligible, limit = rules.get_roth_ira_eligibility(
            Decimal("160500"), FilingStatus.SINGLE, age=30
        )
        assert eligible is True
        assert limit == Decimal("3750.00")

    def test_ineligible_at_or_above_phaseout_ceiling(self):
        eligible, limit = rules.get_roth_ira_eligibility(
            Decimal("168000"), FilingStatus.SINGLE, age=30
        )
        assert eligible is False
        assert limit == Decimal("0")

    def test_married_filing_jointly_uses_the_higher_band(self):
        eligible, limit = rules.get_roth_ira_eligibility(
            Decimal("200000"), FilingStatus.MARRIED_FILING_JOINTLY, age=30
        )
        assert eligible is True
        assert limit == Decimal("7500.00")


class TestTraditionalIraDeduction:
    def test_fully_deductible_with_no_employer_plan_regardless_of_income(self):
        deduction = rules.get_traditional_ira_deduction_limit(
            magi=Decimal("500000"),
            filing_status=FilingStatus.SINGLE,
            age=30,
            has_employer_plan=False,
        )
        assert deduction == Decimal("7500")

    def test_phased_out_when_covered_by_employer_plan(self):
        # Halfway through the $81k-$91k Single covered-phaseout band.
        deduction = rules.get_traditional_ira_deduction_limit(
            magi=Decimal("86000"),
            filing_status=FilingStatus.SINGLE,
            age=30,
            has_employer_plan=True,
        )
        assert deduction == Decimal("3750.00")

    def test_spouse_covered_uses_the_higher_mfj_band(self):
        deduction = rules.get_traditional_ira_deduction_limit(
            magi=Decimal("200000"),
            filing_status=FilingStatus.MARRIED_FILING_JOINTLY,
            age=30,
            has_employer_plan=False,
            spouse_has_employer_plan=True,
        )
        assert deduction == Decimal("7500")


class TestHsaLimit:
    def test_self_only(self):
        assert rules.get_hsa_limit("self_only", age=30) == Decimal("4400")

    def test_family(self):
        assert rules.get_hsa_limit("family", age=30) == Decimal("8750")

    def test_self_only_with_55_plus_catch_up(self):
        assert rules.get_hsa_limit("self_only", age=56) == Decimal("5400")


class TestVesting:
    def test_immediate_is_always_fully_vested(self):
        amount = rules.calculate_vested_amount(
            Decimal("1000"), VestingType.IMMEDIATE, years_employed=0, vesting_years=0
        )
        assert amount == Decimal("1000")

    def test_cliff_before_the_cliff_is_zero(self):
        amount = rules.calculate_vested_amount(
            Decimal("1000"), VestingType.CLIFF, years_employed=2, vesting_years=3
        )
        assert amount == Decimal("0")

    def test_cliff_at_the_cliff_is_full(self):
        amount = rules.calculate_vested_amount(
            Decimal("1000"), VestingType.CLIFF, years_employed=3, vesting_years=3
        )
        assert amount == Decimal("1000.00")

    def test_graded_vests_linearly(self):
        amount = rules.calculate_vested_amount(
            Decimal("1200"), VestingType.GRADED, years_employed=3, vesting_years=6
        )
        assert amount == Decimal("600.00")

    def test_graded_caps_at_full_vesting(self):
        amount = rules.calculate_vested_amount(
            Decimal("1200"), VestingType.GRADED, years_employed=10, vesting_years=6
        )
        assert amount == Decimal("1200.00")


class TestContributionLimitInfo:
    def test_401k_under_50_no_catch_up(self):
        info = rules.get_contribution_limit_info(
            account_type=RetirementAccountType.TRADITIONAL_401K,
            age=35,
            contribution_ytd=Decimal("10000"),
        )
        assert info["employee_limit"] == Decimal("24500")
        assert info["total_limit"] == Decimal("72000")
        assert info["catch_up_eligible"] is False
        assert info["remaining_contribution"] == Decimal("14500")
        assert info["eligible"] is True

    def test_roth_ira_over_income_limit_is_ineligible(self):
        info = rules.get_contribution_limit_info(
            account_type=RetirementAccountType.ROTH_IRA,
            age=30,
            contribution_ytd=Decimal("0"),
            magi=Decimal("200000"),
            filing_status=FilingStatus.SINGLE,
        )
        assert info["eligible"] is False
        assert info["employee_limit"] == Decimal("0")
        assert info["eligibility_note"] is not None

    def test_remaining_contribution_never_negative_when_ytd_exceeds_limit(self):
        info = rules.get_contribution_limit_info(
            account_type=RetirementAccountType.TRADITIONAL_401K,
            age=35,
            contribution_ytd=Decimal("999999"),
        )
        assert info["remaining_contribution"] == Decimal("0")
