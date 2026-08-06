"""Splits a real Income occurrence across its allocations and posts Transaction rows.

Extracted from api/v1/income.py (where `_post_income_transactions` originally lived,
called only from `create_income`'s one-time-income path and `log_income`'s manual
POST /income/{id}/log) so the exact same logic can also be called from
services/scheduler.py's V2 background scheduler (see docs/future-plan.md) - the scheduler
auto-calls this for a recurring Income's next due occurrence the same way a user manually
calling POST /income/{id}/log already does, so the two paths can never drift apart on how
a paycheck is split into postings.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.income import Income, IncomeAllocation
from app.models.transactions import Transaction
from app.models.investments import StockPosition, StockTransaction
from app.models.enums import (
    AllocationDestinationType,
    TransactionType,
    ContributionSourceType,
    StockTransactionType,
)
from app.services.transaction_effects import apply_effect
from app.services import stock_price
from app.services.investment_calculator import calculate_rsu_vested_shares, calculate_average_cost

# Which TransactionType an allocation posts as, given its destination and (optional)
# pre-tax source_type - see models/income.py:IncomeAllocation's docstring for the "Option
# A" design this implements. A retirement/education destination allocated with
# source_type=PRE_TAX_SALARY posts as a real contribution (bumping contribution_ytd via
# apply_effect) instead of a plain INCOME transaction, closing the gap where recording a
# 401(k) payroll deduction used to require a second, separate manual /contribute call.
_CONTRIBUTION_TRANSACTION_TYPE = {
    AllocationDestinationType.RETIREMENT_ACCOUNT: TransactionType.RETIREMENT_CONTRIBUTION,
    AllocationDestinationType.EDUCATION_ACCOUNT: TransactionType.EDUCATION_CONTRIBUTION,
}


def _transaction_type_for_allocation(allocation: IncomeAllocation) -> TransactionType:
    if allocation.source_type == ContributionSourceType.PRE_TAX_SALARY:
        contribution_type = _CONTRIBUTION_TRANSACTION_TYPE.get(allocation.destination_type)
        if contribution_type is not None:
            return contribution_type
    return TransactionType.INCOME


# Post an RSU_VEST Transaction (+ a StockTransaction on the position) for one allocation,
# if anything actually vests as of `log_date`. Unlike every other destination type,
# `amount`/`percentage` play no role here - see models/income.py:IncomeAllocation's
# docstring for why a real RSU grant vests a fixed share count on a schedule, not a
# percentage of each paycheck. Returns None (posts nothing) if this occurrence vests 0
# shares (e.g. before a cliff date).
async def _post_rsu_vesting(
    db: AsyncSession, *, income: Income, allocation: IncomeAllocation, log_date: date
) -> Transaction | None:
    position = await db.get(StockPosition, allocation.destination_id)
    if position is None:
        return None

    newly_vested = calculate_rsu_vested_shares(
        total_shares=allocation.rsu_total_shares,
        shares_already_vested=allocation.rsu_shares_vested,
        vesting_type=allocation.rsu_vesting_type,
        grant_date=income.start_date or log_date,
        vesting_years=allocation.rsu_vesting_years,
        cliff_date=allocation.rsu_cliff_date,
        as_of_date=log_date,
    )
    if newly_vested <= 0:
        return None

    # `or` would be wrong here: Decimal("0") is falsy, so a (real-world impossible but
    # not type-impossible) $0 price would incorrectly fall back to average_cost_per_share.
    fetched_price = stock_price.get_current_price(position.ticker_symbol)
    vest_price = fetched_price if fetched_price is not None else position.average_cost_per_share

    position.average_cost_per_share = calculate_average_cost(
        existing_shares=position.shares,
        existing_avg_cost=position.average_cost_per_share,
        new_shares=newly_vested,
        new_price_per_share=vest_price,
    )
    position.shares += newly_vested
    allocation.rsu_shares_vested += newly_vested

    db.add(
        StockTransaction(
            stock_position_id=position.id,
            transaction_type=StockTransactionType.RSU_VEST,
            shares=newly_vested,
            price_per_share=vest_price,
            transaction_date=log_date,
        )
    )

    transaction = Transaction(
        user_id=income.user_id,
        transaction_type=TransactionType.RSU_VEST,
        amount=(newly_vested * vest_price).quantize(Decimal("0.01")),
        transaction_date=log_date,
        description=f"{income.name}: {newly_vested} {position.ticker_symbol} shares vested",
        account_type=AllocationDestinationType.STOCK_POSITION,
        account_id=position.id,
        income_id=income.id,
    )
    db.add(transaction)
    return transaction


# Split `amount` across `income`'s allocations, posting one Transaction + one real
# balance bump per destination. Shared by api/v1/income.py's create_income (one-time
# income) and log_income (a recurring income's manually-logged occurrence), and
# services/scheduler.py (a recurring income's auto-posted occurrence), so none of the
# three ever drift apart on how a split is turned into postings. A stock_position
# allocation with RSU vesting fields set is handled by `_post_rsu_vesting` instead of the
# percentage-of-amount path every other destination type uses - see that function's
# docstring.
async def post_income_transactions(
    db: AsyncSession, *, income: Income, amount: Decimal, log_date: date
) -> list[Transaction]:
    await db.refresh(income, attribute_names=["allocations"])

    transactions: list[Transaction] = []
    for allocation in income.allocations:
        if (
            allocation.destination_type == AllocationDestinationType.STOCK_POSITION
            and allocation.rsu_vesting_type is not None
        ):
            rsu_transaction = await _post_rsu_vesting(
                db, income=income, allocation=allocation, log_date=log_date
            )
            if rsu_transaction is not None:
                transactions.append(rsu_transaction)
            continue

        share = (amount * allocation.percentage / Decimal("100")).quantize(Decimal("0.01"))
        transaction_type = _transaction_type_for_allocation(allocation)
        is_pretax_contribution = transaction_type != TransactionType.INCOME
        transaction = Transaction(
            user_id=income.user_id,
            transaction_type=transaction_type,
            amount=share,
            transaction_date=log_date,
            description=f"{income.name} ({allocation.percentage}%)",
            account_type=allocation.destination_type,
            account_id=allocation.destination_id,
            income_id=income.id,
            source_type=ContributionSourceType.PRE_TAX_SALARY if is_pretax_contribution else None,
        )
        db.add(transaction)
        await apply_effect(
            db,
            account_type=allocation.destination_type,
            account_id=allocation.destination_id,
            transaction_type=transaction_type,
            source_bank_account_id=None,
            amount=share,
        )
        transactions.append(transaction)

    return transactions
