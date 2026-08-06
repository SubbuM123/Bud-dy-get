"""Unit tests for the pure functions in app/services/investment_calculator.py.

These need no database or FastAPI app, so - like test_retirement_rules.py - they run
under plain pytest with no fixtures.
"""

from datetime import date
from decimal import Decimal

from app.models.enums import BondPaymentFrequency, VestingType
from app.services import investment_calculator as calc


class TestAverageCost:
    def test_first_buy_collapses_to_purchase_price(self):
        result = calc.calculate_average_cost(
            existing_shares=Decimal("0"),
            existing_avg_cost=Decimal("0"),
            new_shares=Decimal("10"),
            new_price_per_share=Decimal("100.00"),
        )
        assert result == Decimal("100.00")

    def test_second_buy_at_different_price_averages(self):
        # 10 shares @ $100 + 10 shares @ $200 -> weighted average $150.
        result = calc.calculate_average_cost(
            existing_shares=Decimal("10"),
            existing_avg_cost=Decimal("100.00"),
            new_shares=Decimal("10"),
            new_price_per_share=Decimal("200.00"),
        )
        assert result == Decimal("150.00")


class TestRealizedPnl:
    def test_profit_when_sale_price_exceeds_cost(self):
        pnl = calc.calculate_realized_pnl(
            shares_sold=Decimal("10"),
            sale_price_per_share=Decimal("150.00"),
            average_cost_per_share=Decimal("100.00"),
        )
        assert pnl == Decimal("500.00")

    def test_loss_when_sale_price_below_cost(self):
        pnl = calc.calculate_realized_pnl(
            shares_sold=Decimal("10"),
            sale_price_per_share=Decimal("80.00"),
            average_cost_per_share=Decimal("100.00"),
        )
        assert pnl == Decimal("-200.00")


class TestBondAmortization:
    def test_schedule_sums_to_face_value_minus_purchase_price(self):
        schedule = calc.calculate_bond_amortization_schedule(
            purchase_price=Decimal("9500.00"),
            face_value=Decimal("10000.00"),
            coupon_rate=Decimal("0.05"),
            payment_frequency=BondPaymentFrequency.SEMI_ANNUALLY,
            purchase_date=date(2026, 1, 1),
            maturity_date=date(2028, 1, 1),
        )
        total_amortization = sum((p["amortization_amount"] for p in schedule), Decimal("0"))
        assert total_amortization == Decimal("500.00")

    def test_schedule_ends_exactly_at_face_value(self):
        schedule = calc.calculate_bond_amortization_schedule(
            purchase_price=Decimal("9500.00"),
            face_value=Decimal("10000.00"),
            coupon_rate=Decimal("0.05"),
            payment_frequency=BondPaymentFrequency.SEMI_ANNUALLY,
            purchase_date=date(2026, 1, 1),
            maturity_date=date(2028, 1, 1),
        )
        assert schedule[-1]["book_value"] == Decimal("10000.00")
        assert schedule[-1]["period_date"] == date(2028, 1, 1)

    def test_schedule_has_four_semi_annual_periods_over_two_years(self):
        schedule = calc.calculate_bond_amortization_schedule(
            purchase_price=Decimal("9500.00"),
            face_value=Decimal("10000.00"),
            coupon_rate=Decimal("0.05"),
            payment_frequency=BondPaymentFrequency.SEMI_ANNUALLY,
            purchase_date=date(2026, 1, 1),
            maturity_date=date(2028, 1, 1),
        )
        assert len(schedule) == 4

    def test_coupon_payment_is_face_value_times_rate_over_payments_per_year(self):
        schedule = calc.calculate_bond_amortization_schedule(
            purchase_price=Decimal("10000.00"),
            face_value=Decimal("10000.00"),
            coupon_rate=Decimal("0.06"),
            payment_frequency=BondPaymentFrequency.SEMI_ANNUALLY,
            purchase_date=date(2026, 1, 1),
            maturity_date=date(2027, 1, 1),
        )
        # $10,000 face * 6% / 2 payments per year = $300 per period.
        assert schedule[0]["coupon_payment"] == Decimal("300.00")

    def test_current_book_value_before_purchase_is_purchase_price(self):
        value = calc.calculate_bond_current_book_value(
            purchase_price=Decimal("9500.00"),
            face_value=Decimal("10000.00"),
            coupon_rate=Decimal("0.05"),
            payment_frequency=BondPaymentFrequency.SEMI_ANNUALLY,
            purchase_date=date(2026, 1, 1),
            maturity_date=date(2028, 1, 1),
            as_of_date=date(2025, 6, 1),
        )
        assert value == Decimal("9500.00")

    def test_current_book_value_after_maturity_is_face_value(self):
        value = calc.calculate_bond_current_book_value(
            purchase_price=Decimal("9500.00"),
            face_value=Decimal("10000.00"),
            coupon_rate=Decimal("0.05"),
            payment_frequency=BondPaymentFrequency.SEMI_ANNUALLY,
            purchase_date=date(2026, 1, 1),
            maturity_date=date(2028, 1, 1),
            as_of_date=date(2029, 1, 1),
        )
        assert value == Decimal("10000.00")

    def test_current_book_value_midlife_is_between_purchase_and_face(self):
        value = calc.calculate_bond_current_book_value(
            purchase_price=Decimal("9500.00"),
            face_value=Decimal("10000.00"),
            coupon_rate=Decimal("0.05"),
            payment_frequency=BondPaymentFrequency.SEMI_ANNUALLY,
            purchase_date=date(2026, 1, 1),
            maturity_date=date(2028, 1, 1),
            as_of_date=date(2027, 1, 2),
        )
        assert Decimal("9500.00") < value < Decimal("10000.00")


class TestPropertyValue:
    def test_value_before_purchase_is_cost(self):
        value = calc.calculate_property_current_value(
            cost=Decimal("100000.00"),
            expected_return_rate=Decimal("0.05"),
            purchase_date=date(2026, 1, 1),
            as_of_date=date(2025, 1, 1),
        )
        assert value == Decimal("100000.00")

    def test_value_grows_with_compound_return(self):
        value = calc.calculate_property_current_value(
            cost=Decimal("100000.00"),
            expected_return_rate=Decimal("0.05"),
            purchase_date=date(2026, 1, 1),
            as_of_date=date(2027, 1, 1),
        )
        # ~5% growth over one year.
        assert Decimal("104900") < value < Decimal("105100")


class TestRsuVesting:
    def test_immediate_vests_everything_remaining_at_once(self):
        vested = calc.calculate_rsu_vested_shares(
            total_shares=Decimal("100"),
            shares_already_vested=Decimal("0"),
            vesting_type=VestingType.IMMEDIATE,
            grant_date=date(2026, 1, 1),
            vesting_years=None,
            cliff_date=None,
            as_of_date=date(2026, 1, 1),
        )
        assert vested == Decimal("100")

    def test_cliff_vests_nothing_before_cliff_date(self):
        vested = calc.calculate_rsu_vested_shares(
            total_shares=Decimal("100"),
            shares_already_vested=Decimal("0"),
            vesting_type=VestingType.CLIFF,
            grant_date=date(2026, 1, 1),
            vesting_years=1,
            cliff_date=date(2027, 1, 1),
            as_of_date=date(2026, 6, 1),
        )
        assert vested == Decimal("0")

    def test_cliff_vests_everything_on_cliff_date(self):
        vested = calc.calculate_rsu_vested_shares(
            total_shares=Decimal("100"),
            shares_already_vested=Decimal("0"),
            vesting_type=VestingType.CLIFF,
            grant_date=date(2026, 1, 1),
            vesting_years=1,
            cliff_date=date(2027, 1, 1),
            as_of_date=date(2027, 1, 1),
        )
        assert vested == Decimal("100")

    def test_graded_vests_proportionally_over_time(self):
        # 100 shares over 4 years, 1 year elapsed -> ~25 shares vested.
        vested = calc.calculate_rsu_vested_shares(
            total_shares=Decimal("100"),
            shares_already_vested=Decimal("0"),
            vesting_type=VestingType.GRADED,
            grant_date=date(2026, 1, 1),
            vesting_years=4,
            cliff_date=None,
            as_of_date=date(2027, 1, 1),
        )
        assert Decimal("24") < vested < Decimal("26")

    def test_graded_second_call_only_returns_newly_vested_shares(self):
        # After year 1 (~25 already vested), year 2 should report only the incremental
        # ~25 newly vested, not the cumulative ~50.
        vested_year_2 = calc.calculate_rsu_vested_shares(
            total_shares=Decimal("100"),
            shares_already_vested=Decimal("25"),
            vesting_type=VestingType.GRADED,
            grant_date=date(2026, 1, 1),
            vesting_years=4,
            cliff_date=None,
            as_of_date=date(2028, 1, 1),
        )
        assert Decimal("24") < vested_year_2 < Decimal("26")

    def test_fully_vested_grant_returns_zero(self):
        vested = calc.calculate_rsu_vested_shares(
            total_shares=Decimal("100"),
            shares_already_vested=Decimal("100"),
            vesting_type=VestingType.GRADED,
            grant_date=date(2026, 1, 1),
            vesting_years=4,
            cliff_date=None,
            as_of_date=date(2030, 1, 1),
        )
        assert vested == Decimal("0")
