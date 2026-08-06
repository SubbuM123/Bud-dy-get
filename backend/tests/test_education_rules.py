"""Unit tests for the pure gift-tax/rollover guidance functions in
app/services/education_rules.py. These need no database or FastAPI app, so unlike most of
this suite they run under plain `pytest` with no fixtures - the numbers themselves are
asserted against the 2026 figures researched and recorded in docs/phase4.5-plan.md, so a
future change to those figures should update both this file and that doc together.
"""

from decimal import Decimal

from app.services import education_rules as rules


class TestGiftTaxExclusion:
    def test_single_giver_2026(self):
        assert rules.get_annual_gift_tax_exclusion() == Decimal("19000")

    def test_gift_splitting_doubles_it(self):
        assert rules.get_annual_gift_tax_exclusion(gift_splitting=True) == Decimal("38000")

    def test_superfunding_lump_sum_is_five_times_the_exclusion(self):
        assert rules.get_superfunding_lump_sum() == Decimal("95000")

    def test_superfunding_lump_sum_with_gift_splitting(self):
        assert rules.get_superfunding_lump_sum(gift_splitting=True) == Decimal("190000")


class TestGiftTaxInfo:
    def test_never_raises_when_well_under_the_exclusion(self):
        info = rules.get_gift_tax_info(
            beneficiary_name="Jordan",
            beneficiary_contribution_ytd=Decimal("5000"),
        )
        assert info["would_exceed_exclusion"] is False
        assert info["remaining_before_exclusion"] == Decimal("14000")
        assert info["annual_exclusion"] == Decimal("19000")
        assert "Form 709" not in info["note"]

    def test_never_raises_when_over_the_exclusion_but_flags_it(self):
        info = rules.get_gift_tax_info(
            beneficiary_name="Jordan",
            beneficiary_contribution_ytd=Decimal("25000"),
        )
        assert info["would_exceed_exclusion"] is True
        assert info["remaining_before_exclusion"] == Decimal("0")
        assert "Form 709" in info["note"]
        assert "Jordan" in info["note"]

    def test_prospective_new_contribution_pushes_it_over(self):
        info = rules.get_gift_tax_info(
            beneficiary_name="Jordan",
            beneficiary_contribution_ytd=Decimal("15000"),
            new_contribution_amount=Decimal("5000"),
        )
        assert info["would_exceed_exclusion"] is True
        # remaining_before_exclusion reflects YTD only, not the prospective amount.
        assert info["remaining_before_exclusion"] == Decimal("4000")

    def test_remaining_never_goes_negative(self):
        info = rules.get_gift_tax_info(
            beneficiary_name="Jordan",
            beneficiary_contribution_ytd=Decimal("999999"),
        )
        assert info["remaining_before_exclusion"] == Decimal("0")

    def test_gift_splitting_raises_the_exclusion_used(self):
        info = rules.get_gift_tax_info(
            beneficiary_name="Jordan",
            beneficiary_contribution_ytd=Decimal("25000"),
            gift_splitting=True,
        )
        assert info["would_exceed_exclusion"] is False
        assert info["annual_exclusion"] == Decimal("38000")


class TestRothRolloverEligibility:
    def test_eligible_when_all_conditions_met(self):
        info = rules.get_roth_rollover_eligibility(
            account_opened_years_ago=16,
            oldest_eligible_funds_years_ago=6,
            beneficiary_has_earned_income=True,
            lifetime_amount_already_rolled_over=Decimal("0"),
        )
        assert info["eligible"] is True
        assert info["max_rollover_this_year"] == Decimal("7500")
        assert info["ineligibility_reasons"] == []

    def test_ineligible_account_too_young(self):
        info = rules.get_roth_rollover_eligibility(
            account_opened_years_ago=10,
            oldest_eligible_funds_years_ago=6,
            beneficiary_has_earned_income=True,
            lifetime_amount_already_rolled_over=Decimal("0"),
        )
        assert info["eligible"] is False
        assert info["max_rollover_this_year"] == Decimal("0")
        assert any("15 years" in reason for reason in info["ineligibility_reasons"])

    def test_ineligible_funds_too_young(self):
        info = rules.get_roth_rollover_eligibility(
            account_opened_years_ago=16,
            oldest_eligible_funds_years_ago=2,
            beneficiary_has_earned_income=True,
            lifetime_amount_already_rolled_over=Decimal("0"),
        )
        assert info["eligible"] is False
        assert any("5 years" in reason for reason in info["ineligibility_reasons"])

    def test_ineligible_no_earned_income(self):
        info = rules.get_roth_rollover_eligibility(
            account_opened_years_ago=16,
            oldest_eligible_funds_years_ago=6,
            beneficiary_has_earned_income=False,
            lifetime_amount_already_rolled_over=Decimal("0"),
        )
        assert info["eligible"] is False
        assert any("earned income" in reason for reason in info["ineligibility_reasons"])

    def test_lifetime_remaining_is_capped_at_35000(self):
        info = rules.get_roth_rollover_eligibility(
            account_opened_years_ago=16,
            oldest_eligible_funds_years_ago=6,
            beneficiary_has_earned_income=True,
            lifetime_amount_already_rolled_over=Decimal("30000"),
        )
        assert info["lifetime_remaining"] == Decimal("5000")
        assert info["max_rollover_this_year"] == Decimal("5000")  # capped by remaining, not IRA limit

    def test_lifetime_remaining_never_goes_negative(self):
        info = rules.get_roth_rollover_eligibility(
            account_opened_years_ago=16,
            oldest_eligible_funds_years_ago=6,
            beneficiary_has_earned_income=True,
            lifetime_amount_already_rolled_over=Decimal("999999"),
        )
        assert info["lifetime_remaining"] == Decimal("0")
        assert info["max_rollover_this_year"] == Decimal("0")

    def test_catch_up_eligible_beneficiary_gets_higher_annual_ira_limit(self):
        info = rules.get_roth_rollover_eligibility(
            account_opened_years_ago=16,
            oldest_eligible_funds_years_ago=6,
            beneficiary_has_earned_income=True,
            lifetime_amount_already_rolled_over=Decimal("0"),
            beneficiary_age=55,
        )
        assert info["max_rollover_this_year"] == Decimal("8600")
