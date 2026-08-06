"""List, correct, and delete endpoints for the unified Transaction log.

There is no POST here: every Transaction row is created as a side effect of another
endpoint (POST /income/{id}/log, or the retirement/education `/contribute` endpoints) -
see models/transactions.py's docstring for why. This router only covers what a user needs
to fix a mistake after the fact: list what's been posted, correct an amount/date/
description, or delete an entry entirely - both of the latter two applying the resulting
balance change via services/transaction_effects.apply_effect rather than just editing the
log row in isolation, so the log always stays consistent with the account balances it
produced.

Phase 5's three stock transaction types (STOCK_PURCHASE/STOCK_SALE/RSU_VEST) are excluded
from update/delete here - see `_STOCK_TRANSACTION_TYPES` below and
docs/phase5-plan.md's "Deliberate Scope Limits". `apply_effect` has no branch for
`AllocationDestinationType.STOCK_POSITION` (unlike retirement/education contributions,
"reversing" a stock transaction means unwinding a specific number of shares at a specific
cost basis, which isn't a simple dollar-amount delta apply_effect can express) - allowing
an edit/delete here would silently reverse only the bank-side debit (if any) while leaving
the StockPosition's shares/average_cost untouched, corrupting the position. Use the
position's own buy/sell endpoints (api/v1/investments.py) to correct a mistake instead.
"""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.core.dependencies import DBSession, CurrentUser
from app.models.transactions import Transaction
from app.models.enums import TransactionType, AllocationDestinationType
from app.schemas.transactions import TransactionResponse, TransactionUpdate
from app.services.transaction_effects import apply_effect

router = APIRouter()

_STOCK_TRANSACTION_TYPES = {
    TransactionType.STOCK_PURCHASE,
    TransactionType.STOCK_SALE,
    TransactionType.RSU_VEST,
}


async def _get_owned_transaction(db: DBSession, transaction_id: str, user_id: str) -> Transaction:
    """Fetch a transaction by id, scoped to `user_id`; raise 404 if missing or not owned."""
    result = await db.execute(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == user_id,
        )
    )
    transaction = result.scalar_one_or_none()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


# List the authenticated user's transactions, optionally filtered by type, the destination
# account, and/or a date range - powers the transaction history page's filters. This log
# only grows over an account's lifetime (every posted income, expense, contribution, and
# trade adds a row), so it's paginated - unlike the small, roughly-static account/category
# list endpoints elsewhere in the app.
@router.get("", response_model=list[TransactionResponse])
async def list_transactions(
    current_user: CurrentUser,
    db: DBSession,
    transaction_type: TransactionType | None = None,
    account_type: AllocationDestinationType | None = None,
    account_id: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    query = select(Transaction).where(Transaction.user_id == current_user.id)
    if transaction_type is not None:
        query = query.where(Transaction.transaction_type == transaction_type)
    if account_type is not None:
        query = query.where(Transaction.account_type == account_type)
    if account_id is not None:
        query = query.where(Transaction.account_id == account_id)
    if start_date is not None:
        query = query.where(Transaction.transaction_date >= start_date)
    if end_date is not None:
        query = query.where(Transaction.transaction_date <= end_date)
    query = query.order_by(
        Transaction.transaction_date.desc(), Transaction.created_at.desc()
    ).limit(limit).offset(offset)

    result = await db.execute(query)
    return result.scalars().all()


# Fetch a single transaction owned by the authenticated user.
@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(transaction_id: str, current_user: CurrentUser, db: DBSession):
    return await _get_owned_transaction(db, transaction_id, current_user.id)


# Correct a transaction's amount/date/description. An amount change is applied as just
# the delta (new - old) to whatever account(s) the transaction originally affected, via
# apply_effect - so e.g. correcting a $500 contribution logged as $50 bumps the retirement
# account's balance by the missing $450 rather than requiring the caller to undo and
# re-post the whole thing.
@router.put("/{transaction_id}", response_model=TransactionResponse)
async def update_transaction(
    transaction_id: str,
    transaction_data: TransactionUpdate,
    current_user: CurrentUser,
    db: DBSession,
):
    transaction = await _get_owned_transaction(db, transaction_id, current_user.id)
    if transaction.transaction_type in _STOCK_TRANSACTION_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stock/bond/property transactions can't be edited from the unified "
            "transaction log - correct this via the investment's own buy/sell action.",
        )

    if transaction_data.amount is not None and transaction_data.amount != transaction.amount:
        delta = transaction_data.amount - transaction.amount
        await apply_effect(
            db,
            account_type=transaction.account_type,
            account_id=transaction.account_id,
            transaction_type=transaction.transaction_type,
            source_bank_account_id=transaction.source_bank_account_id,
            amount=delta,
        )
        transaction.amount = transaction_data.amount

    if transaction_data.transaction_date is not None:
        transaction.transaction_date = transaction_data.transaction_date
    if transaction_data.description is not None:
        transaction.description = transaction_data.description

    await db.commit()
    await db.refresh(transaction)
    return transaction


# Delete a transaction, fully reversing its effect on whatever account(s) it affected
# before removing the log row - see services/transaction_effects.apply_effect.
@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(transaction_id: str, current_user: CurrentUser, db: DBSession):
    transaction = await _get_owned_transaction(db, transaction_id, current_user.id)
    if transaction.transaction_type in _STOCK_TRANSACTION_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stock/bond/property transactions can't be deleted from the unified "
            "transaction log - correct this via the investment's own buy/sell action.",
        )

    await apply_effect(
        db,
        account_type=transaction.account_type,
        account_id=transaction.account_id,
        transaction_type=transaction.transaction_type,
        source_bank_account_id=transaction.source_bank_account_id,
        amount=-transaction.amount,
    )
    await db.delete(transaction)
    await db.commit()
