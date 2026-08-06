"""CRUD, buy/sell, and market-data endpoints for the Investments module (Phase 5).

Three asset types share this router: StockPosition (an aggregate per-ticker holding,
built up over possibly-many buys/sells - see models/investments.py), and BondHolding/
PropertyInvestment (each row is one bought-once, sold-once holding, no aggregation).
Every route scopes its query to the authenticated user via the three `_get_owned_*`
helpers below, matching every other module's ownership-scoping pattern.

Buying a stock/bond/property optionally debits a real bank account
(`source_bank_account_id`, mirroring retirement/education's contribution `source_type`
pattern) via services/transaction_effects.apply_effect, and always posts a Transaction row
to the unified log - but see api/v1/transactions.py's docstring for why those rows can't
be edited/deleted from that generic endpoint (apply_effect has no share-aware reversal
logic). Correcting a mistaken buy/sell means using this router's own endpoints again
(e.g. a follow-up sell to undo an over-large buy), not the transaction log.
"""

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.dependencies import DBSession, CurrentUser
from app.models.bank_accounts import BankAccount
from app.models.investments import StockPosition, StockTransaction, BondHolding, PropertyInvestment
from app.models.transactions import Transaction
from app.models.enums import (
    AllocationDestinationType,
    TransactionType,
    StockTransactionType,
)
from app.schemas.investments import (
    StockPositionCreate,
    StockPositionResponse,
    StockBuyRequest,
    StockSellRequest,
    StockTransactionResponse,
    StockPriceResponse,
    StockHistoryResponse,
    StockHistoryPoint,
    BondHoldingCreate,
    BondHoldingUpdate,
    BondHoldingResponse,
    BondSellRequest,
    BondAmortizationScheduleResponse,
    BondAmortizationPeriod,
    PropertyInvestmentCreate,
    PropertyInvestmentUpdate,
    PropertyInvestmentResponse,
    PropertySellRequest,
    InvestmentSummaryResponse,
)
from app.services import stock_price
from app.services.investment_calculator import (
    calculate_average_cost,
    calculate_realized_pnl,
    calculate_bond_amortization_schedule,
    calculate_bond_current_book_value,
    calculate_property_current_value,
)
from app.services.transaction_effects import apply_effect

router = APIRouter()


# --- Ownership helpers -----------------------------------------------------------------

async def _get_owned_position(db: DBSession, position_id: str, user_id: str) -> StockPosition:
    result = await db.execute(
        select(StockPosition).where(
            StockPosition.id == position_id, StockPosition.user_id == user_id
        )
    )
    position = result.scalar_one_or_none()
    if not position:
        raise HTTPException(status_code=404, detail="Stock position not found")
    return position


async def _get_owned_bond(db: DBSession, bond_id: str, user_id: str) -> BondHolding:
    result = await db.execute(
        select(BondHolding).where(BondHolding.id == bond_id, BondHolding.user_id == user_id)
    )
    bond = result.scalar_one_or_none()
    if not bond:
        raise HTTPException(status_code=404, detail="Bond holding not found")
    return bond


async def _get_owned_property(db: DBSession, property_id: str, user_id: str) -> PropertyInvestment:
    result = await db.execute(
        select(PropertyInvestment).where(
            PropertyInvestment.id == property_id, PropertyInvestment.user_id == user_id
        )
    )
    investment = result.scalar_one_or_none()
    if not investment:
        raise HTTPException(status_code=404, detail="Property investment not found")
    return investment


async def _get_owned_bank_account(db: DBSession, bank_account_id: str, user_id: str) -> BankAccount:
    result = await db.execute(
        select(BankAccount).where(
            BankAccount.id == bank_account_id, BankAccount.user_id == user_id
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Source bank account not found")
    return account


# Refresh a position's cached current_price/last_price_update from
# services/stock_price.py (itself already in-process-cached for CACHE_TTL_MINUTES, so this
# is cheap to call on every list/get - no separate "refresh" action needed). Silently
# leaves the existing cached price in place if the fetch fails (invalid ticker, network
# issue) - a stale price is a better fallback than losing it entirely. Caller is
# responsible for `await db.commit()`.
async def _refresh_current_price(position: StockPosition) -> None:
    price = stock_price.get_current_price(position.ticker_symbol)
    if price is not None:
        position.current_price = price
        position.last_price_update = datetime.utcnow()


# --- Response builders (computed fields - see schemas/investments.py's module docstring) -

def _position_to_response(position: StockPosition) -> StockPositionResponse:
    market_value = None
    unrealized_pnl = None
    if position.current_price is not None:
        market_value = (position.shares * position.current_price).quantize(Decimal("0.01"))
        cost_basis = position.shares * position.average_cost_per_share
        unrealized_pnl = (market_value - cost_basis).quantize(Decimal("0.01"))
    return StockPositionResponse(
        id=position.id,
        user_id=position.user_id,
        ticker_symbol=position.ticker_symbol,
        shares=position.shares,
        average_cost_per_share=position.average_cost_per_share,
        current_price=position.current_price,
        last_price_update=position.last_price_update,
        market_value=market_value,
        unrealized_pnl=unrealized_pnl,
        funding_bank_account_id=position.funding_bank_account_id,
        is_simulation=position.is_simulation,
        created_at=position.created_at,
        updated_at=position.updated_at,
    )


def _bond_to_response(bond: BondHolding) -> BondHoldingResponse:
    # Once sold, the amortization schedule no longer describes a holding the user still
    # has - freeze current_book_value at whatever it was on the sale date rather than
    # continuing to advance it toward face_value for a bond that's no longer owned.
    current_book_value = calculate_bond_current_book_value(
        purchase_price=bond.purchase_price,
        face_value=bond.face_value,
        coupon_rate=bond.coupon_rate,
        payment_frequency=bond.payment_frequency,
        purchase_date=bond.purchase_date,
        maturity_date=bond.maturity_date,
        as_of_date=bond.sale_date if not bond.is_active else None,
    )
    return BondHoldingResponse(
        id=bond.id,
        user_id=bond.user_id,
        name=bond.name,
        purchase_price=bond.purchase_price,
        face_value=bond.face_value,
        coupon_rate=bond.coupon_rate,
        payment_frequency=bond.payment_frequency,
        purchase_date=bond.purchase_date,
        maturity_date=bond.maturity_date,
        is_simulation=bond.is_simulation,
        is_active=bond.is_active,
        sale_price=bond.sale_price,
        sale_date=bond.sale_date,
        realized_pnl=bond.realized_pnl,
        current_book_value=current_book_value,
        created_at=bond.created_at,
        updated_at=bond.updated_at,
    )


def _property_to_response(investment: PropertyInvestment) -> PropertyInvestmentResponse:
    current_value = investment.sale_price if not investment.is_active else calculate_property_current_value(
        cost=investment.cost,
        expected_return_rate=investment.expected_return_rate,
        purchase_date=investment.purchase_date,
    )
    return PropertyInvestmentResponse(
        id=investment.id,
        user_id=investment.user_id,
        name=investment.name,
        cost=investment.cost,
        expected_return_rate=investment.expected_return_rate,
        purchase_date=investment.purchase_date,
        is_simulation=investment.is_simulation,
        is_active=investment.is_active,
        sale_price=investment.sale_price,
        sale_date=investment.sale_date,
        realized_pnl=investment.realized_pnl,
        current_value=current_value,
        created_at=investment.created_at,
        updated_at=investment.updated_at,
    )


# --- Market data (still behind auth, like every other route in this app) ---------------

@router.get("/market/{ticker}/price", response_model=StockPriceResponse)
async def get_market_price(ticker: str, current_user: CurrentUser):
    return StockPriceResponse(ticker=ticker.upper(), price=stock_price.get_current_price(ticker))


@router.get("/market/{ticker}/history", response_model=StockHistoryResponse)
async def get_market_history(ticker: str, current_user: CurrentUser, period: str = "3mo"):
    raw_points = stock_price.get_price_history(ticker, period)
    return StockHistoryResponse(
        ticker=ticker.upper(),
        period=period,
        data=[StockHistoryPoint(**point) for point in raw_points],
    )


# --- Stock positions ---------------------------------------------------------------------

@router.get("/stocks", response_model=list[StockPositionResponse])
async def list_stock_positions(current_user: CurrentUser, db: DBSession):
    result = await db.execute(
        select(StockPosition).where(StockPosition.user_id == current_user.id)
    )
    positions = result.scalars().all()
    for position in positions:
        await _refresh_current_price(position)
    if positions:
        await db.commit()
    return [_position_to_response(p) for p in positions]


# Get-or-create by ticker: a user can only ever have one aggregate position per ticker
# (see models/investments.py's StockPosition docstring) - creating a second "buy" for a
# ticker already held returns the existing position rather than a duplicate row.
@router.post("/stocks", response_model=StockPositionResponse, status_code=status.HTTP_201_CREATED)
async def create_stock_position(
    position_data: StockPositionCreate, current_user: CurrentUser, db: DBSession
):
    ticker = position_data.ticker_symbol.upper().strip()
    existing = await db.execute(
        select(StockPosition).where(
            StockPosition.user_id == current_user.id, StockPosition.ticker_symbol == ticker
        )
    )
    position = existing.scalar_one_or_none()
    if position is not None:
        return _position_to_response(position)

    position = StockPosition(
        user_id=current_user.id,
        ticker_symbol=ticker,
        is_simulation=position_data.is_simulation,
    )
    db.add(position)
    await db.commit()
    await db.refresh(position)
    return _position_to_response(position)


@router.get("/stocks/{position_id}", response_model=StockPositionResponse)
async def get_stock_position(position_id: str, current_user: CurrentUser, db: DBSession):
    position = await _get_owned_position(db, position_id, current_user.id)
    await _refresh_current_price(position)
    await db.commit()
    return _position_to_response(position)


@router.delete("/stocks/{position_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_stock_position(position_id: str, current_user: CurrentUser, db: DBSession):
    position = await _get_owned_position(db, position_id, current_user.id)
    if position.shares > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sell every share before deleting this position.",
        )
    await db.delete(position)
    await db.commit()


@router.get("/stocks/{position_id}/transactions", response_model=list[StockTransactionResponse])
async def list_stock_transactions(position_id: str, current_user: CurrentUser, db: DBSession):
    await _get_owned_position(db, position_id, current_user.id)
    result = await db.execute(
        select(StockTransaction)
        .where(StockTransaction.stock_position_id == position_id)
        .order_by(StockTransaction.transaction_date.desc(), StockTransaction.created_at.desc())
    )
    return result.scalars().all()


@router.post("/stocks/{position_id}/buy", response_model=StockTransactionResponse, status_code=status.HTTP_201_CREATED)
async def buy_stock(
    position_id: str,
    buy_data: StockBuyRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    position = await _get_owned_position(db, position_id, current_user.id)

    if buy_data.source_bank_account_id is not None:
        await _get_owned_bank_account(db, buy_data.source_bank_account_id, current_user.id)

    transaction_date = buy_data.transaction_date or date.today()
    cost = (buy_data.shares * buy_data.price_per_share).quantize(Decimal("0.01"))

    position.average_cost_per_share = calculate_average_cost(
        existing_shares=position.shares,
        existing_avg_cost=position.average_cost_per_share,
        new_shares=buy_data.shares,
        new_price_per_share=buy_data.price_per_share,
    )
    position.shares += buy_data.shares
    if buy_data.source_bank_account_id is not None:
        # Remembered so a later sell can credit proceeds back here automatically - see
        # models/investments.py:StockPosition's docstring on funding_bank_account_id.
        position.funding_bank_account_id = buy_data.source_bank_account_id

    stock_transaction = StockTransaction(
        stock_position_id=position.id,
        transaction_type=StockTransactionType.BUY,
        shares=buy_data.shares,
        price_per_share=buy_data.price_per_share,
        transaction_date=transaction_date,
        source_bank_account_id=buy_data.source_bank_account_id,
        notes=buy_data.notes,
    )
    db.add(stock_transaction)

    db.add(
        Transaction(
            user_id=current_user.id,
            transaction_type=TransactionType.STOCK_PURCHASE,
            amount=cost,
            transaction_date=transaction_date,
            description=f"Bought {buy_data.shares} {position.ticker_symbol} @ {buy_data.price_per_share}",
            account_type=AllocationDestinationType.STOCK_POSITION,
            account_id=position.id,
            source_bank_account_id=buy_data.source_bank_account_id,
        )
    )

    if buy_data.source_bank_account_id is not None:
        await apply_effect(
            db,
            account_type=None,
            account_id=None,
            transaction_type=TransactionType.STOCK_PURCHASE,
            source_bank_account_id=buy_data.source_bank_account_id,
            amount=cost,
        )

    await db.commit()
    await db.refresh(stock_transaction)
    return stock_transaction


@router.post("/stocks/{position_id}/sell", response_model=StockTransactionResponse, status_code=status.HTTP_201_CREATED)
async def sell_stock(
    position_id: str,
    sell_data: StockSellRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    position = await _get_owned_position(db, position_id, current_user.id)

    if sell_data.shares > position.shares:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot sell {sell_data.shares} shares - position only holds {position.shares}.",
        )

    transaction_date = sell_data.transaction_date or date.today()
    realized_pnl = calculate_realized_pnl(
        shares_sold=sell_data.shares,
        sale_price_per_share=sell_data.price_per_share,
        average_cost_per_share=position.average_cost_per_share,
    )
    proceeds = (sell_data.shares * sell_data.price_per_share).quantize(Decimal("0.01"))

    position.shares -= sell_data.shares
    # Credit the sale back into whichever account most recently funded a buy on this
    # position - see models/investments.py:StockPosition's docstring on
    # funding_bank_account_id. A position never bought with a bank account (or bought
    # with one that's since been unlinked) has nowhere to credit, so proceeds just aren't
    # tracked anywhere else, same as a buy made without a source account.
    credit_account_id = position.funding_bank_account_id

    stock_transaction = StockTransaction(
        stock_position_id=position.id,
        transaction_type=StockTransactionType.SELL,
        shares=sell_data.shares,
        price_per_share=sell_data.price_per_share,
        transaction_date=transaction_date,
        realized_pnl=realized_pnl,
        source_bank_account_id=credit_account_id,
        notes=sell_data.notes,
    )
    db.add(stock_transaction)

    db.add(
        Transaction(
            user_id=current_user.id,
            transaction_type=TransactionType.STOCK_SALE,
            amount=proceeds,
            transaction_date=transaction_date,
            description=f"Sold {sell_data.shares} {position.ticker_symbol} @ {sell_data.price_per_share}",
            account_type=AllocationDestinationType.STOCK_POSITION,
            account_id=position.id,
            source_bank_account_id=credit_account_id,
        )
    )

    if credit_account_id is not None:
        # Negative amount: apply_effect's source-account branch does `-= amount`, so a
        # negative amount here nets to `+= proceeds` - the same reversal-style credit
        # api/v1/transactions.py's delete_transaction already uses.
        await apply_effect(
            db,
            account_type=None,
            account_id=None,
            transaction_type=TransactionType.STOCK_SALE,
            source_bank_account_id=credit_account_id,
            amount=-proceeds,
        )

    await db.commit()
    await db.refresh(stock_transaction)
    return stock_transaction


# --- Bonds ---------------------------------------------------------------------------------

@router.get("/bonds", response_model=list[BondHoldingResponse])
async def list_bond_holdings(current_user: CurrentUser, db: DBSession):
    result = await db.execute(select(BondHolding).where(BondHolding.user_id == current_user.id))
    return [_bond_to_response(b) for b in result.scalars().all()]


@router.post("/bonds", response_model=BondHoldingResponse, status_code=status.HTTP_201_CREATED)
async def create_bond_holding(bond_data: BondHoldingCreate, current_user: CurrentUser, db: DBSession):
    if bond_data.source_bank_account_id is not None:
        await _get_owned_bank_account(db, bond_data.source_bank_account_id, current_user.id)

    bond = BondHolding(
        user_id=current_user.id,
        name=bond_data.name,
        purchase_price=bond_data.purchase_price,
        face_value=bond_data.face_value,
        coupon_rate=bond_data.coupon_rate,
        payment_frequency=bond_data.payment_frequency,
        purchase_date=bond_data.purchase_date,
        maturity_date=bond_data.maturity_date,
        is_simulation=bond_data.is_simulation,
    )
    db.add(bond)
    await db.flush()

    db.add(
        Transaction(
            user_id=current_user.id,
            transaction_type=TransactionType.STOCK_PURCHASE,
            amount=bond_data.purchase_price,
            transaction_date=bond_data.purchase_date,
            description=f"Bought bond: {bond_data.name}",
            source_bank_account_id=bond_data.source_bank_account_id,
        )
    )
    if bond_data.source_bank_account_id is not None:
        await apply_effect(
            db,
            account_type=None,
            account_id=None,
            transaction_type=TransactionType.STOCK_PURCHASE,
            source_bank_account_id=bond_data.source_bank_account_id,
            amount=bond_data.purchase_price,
        )

    await db.commit()
    await db.refresh(bond)
    return _bond_to_response(bond)


@router.get("/bonds/{bond_id}", response_model=BondHoldingResponse)
async def get_bond_holding(bond_id: str, current_user: CurrentUser, db: DBSession):
    bond = await _get_owned_bond(db, bond_id, current_user.id)
    return _bond_to_response(bond)


@router.put("/bonds/{bond_id}", response_model=BondHoldingResponse)
async def update_bond_holding(
    bond_id: str, bond_data: BondHoldingUpdate, current_user: CurrentUser, db: DBSession
):
    bond = await _get_owned_bond(db, bond_id, current_user.id)
    update_data = bond_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(bond, field, value)
    await db.commit()
    await db.refresh(bond)
    return _bond_to_response(bond)


@router.delete("/bonds/{bond_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bond_holding(bond_id: str, current_user: CurrentUser, db: DBSession):
    bond = await _get_owned_bond(db, bond_id, current_user.id)
    await db.delete(bond)
    await db.commit()


@router.post("/bonds/{bond_id}/sell", response_model=BondHoldingResponse)
async def sell_bond_holding(
    bond_id: str, sell_data: BondSellRequest, current_user: CurrentUser, db: DBSession
):
    bond = await _get_owned_bond(db, bond_id, current_user.id)
    if not bond.is_active:
        raise HTTPException(status_code=400, detail="This bond has already been sold.")

    sale_date = sell_data.sale_date or date.today()
    bond.is_active = False
    bond.sale_price = sell_data.sale_price
    bond.sale_date = sale_date
    bond.realized_pnl = (sell_data.sale_price - bond.purchase_price).quantize(Decimal("0.01"))

    db.add(
        Transaction(
            user_id=current_user.id,
            transaction_type=TransactionType.STOCK_SALE,
            amount=sell_data.sale_price,
            transaction_date=sale_date,
            description=f"Sold bond: {bond.name}",
        )
    )

    await db.commit()
    await db.refresh(bond)
    return _bond_to_response(bond)


@router.get("/bonds/{bond_id}/amortization", response_model=BondAmortizationScheduleResponse)
async def get_bond_amortization_schedule(bond_id: str, current_user: CurrentUser, db: DBSession):
    bond = await _get_owned_bond(db, bond_id, current_user.id)
    schedule = calculate_bond_amortization_schedule(
        purchase_price=bond.purchase_price,
        face_value=bond.face_value,
        coupon_rate=bond.coupon_rate,
        payment_frequency=bond.payment_frequency,
        purchase_date=bond.purchase_date,
        maturity_date=bond.maturity_date,
    )
    return BondAmortizationScheduleResponse(
        bond_id=bond.id,
        schedule=[BondAmortizationPeriod(**period) for period in schedule],
    )


# --- Property investments -------------------------------------------------------------------

@router.get("/property", response_model=list[PropertyInvestmentResponse])
async def list_property_investments(current_user: CurrentUser, db: DBSession):
    result = await db.execute(
        select(PropertyInvestment).where(PropertyInvestment.user_id == current_user.id)
    )
    return [_property_to_response(p) for p in result.scalars().all()]


@router.post("/property", response_model=PropertyInvestmentResponse, status_code=status.HTTP_201_CREATED)
async def create_property_investment(
    property_data: PropertyInvestmentCreate, current_user: CurrentUser, db: DBSession
):
    if property_data.source_bank_account_id is not None:
        await _get_owned_bank_account(db, property_data.source_bank_account_id, current_user.id)

    investment = PropertyInvestment(
        user_id=current_user.id,
        name=property_data.name,
        cost=property_data.cost,
        expected_return_rate=property_data.expected_return_rate,
        purchase_date=property_data.purchase_date,
        is_simulation=property_data.is_simulation,
    )
    db.add(investment)
    await db.flush()

    db.add(
        Transaction(
            user_id=current_user.id,
            transaction_type=TransactionType.STOCK_PURCHASE,
            amount=property_data.cost,
            transaction_date=property_data.purchase_date,
            description=f"Bought property investment: {property_data.name}",
            source_bank_account_id=property_data.source_bank_account_id,
        )
    )
    if property_data.source_bank_account_id is not None:
        await apply_effect(
            db,
            account_type=None,
            account_id=None,
            transaction_type=TransactionType.STOCK_PURCHASE,
            source_bank_account_id=property_data.source_bank_account_id,
            amount=property_data.cost,
        )

    await db.commit()
    await db.refresh(investment)
    return _property_to_response(investment)


@router.get("/property/{property_id}", response_model=PropertyInvestmentResponse)
async def get_property_investment(property_id: str, current_user: CurrentUser, db: DBSession):
    investment = await _get_owned_property(db, property_id, current_user.id)
    return _property_to_response(investment)


@router.put("/property/{property_id}", response_model=PropertyInvestmentResponse)
async def update_property_investment(
    property_id: str,
    property_data: PropertyInvestmentUpdate,
    current_user: CurrentUser,
    db: DBSession,
):
    investment = await _get_owned_property(db, property_id, current_user.id)
    update_data = property_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(investment, field, value)
    await db.commit()
    await db.refresh(investment)
    return _property_to_response(investment)


@router.delete("/property/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_property_investment(property_id: str, current_user: CurrentUser, db: DBSession):
    investment = await _get_owned_property(db, property_id, current_user.id)
    await db.delete(investment)
    await db.commit()


@router.post("/property/{property_id}/sell", response_model=PropertyInvestmentResponse)
async def sell_property_investment(
    property_id: str,
    sell_data: PropertySellRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    investment = await _get_owned_property(db, property_id, current_user.id)
    if not investment.is_active:
        raise HTTPException(status_code=400, detail="This property investment has already been sold.")

    sale_date = sell_data.sale_date or date.today()
    investment.is_active = False
    investment.sale_price = sell_data.sale_price
    investment.sale_date = sale_date
    investment.realized_pnl = (sell_data.sale_price - investment.cost).quantize(Decimal("0.01"))

    db.add(
        Transaction(
            user_id=current_user.id,
            transaction_type=TransactionType.STOCK_SALE,
            amount=sell_data.sale_price,
            transaction_date=sale_date,
            description=f"Sold property investment: {investment.name}",
        )
    )

    await db.commit()
    await db.refresh(investment)
    return _property_to_response(investment)


# --- Summary (feeds the dashboard's net worth) ----------------------------------------------

@router.get("/summary", response_model=InvestmentSummaryResponse)
async def get_investment_summary(current_user: CurrentUser, db: DBSession):
    stocks_result = await db.execute(
        select(StockPosition).where(StockPosition.user_id == current_user.id)
    )
    positions = stocks_result.scalars().all()
    total_stocks_value = Decimal("0")
    total_unrealized_pnl = Decimal("0")
    for position in positions:
        await _refresh_current_price(position)
    if positions:
        await db.commit()
    for position in positions:
        response = _position_to_response(position)
        if response.market_value is not None:
            total_stocks_value += response.market_value
        if response.unrealized_pnl is not None:
            total_unrealized_pnl += response.unrealized_pnl

    bonds_result = await db.execute(
        select(BondHolding).where(
            BondHolding.user_id == current_user.id, BondHolding.is_active == True
        )
    )
    total_bonds_value = sum(
        (
            calculate_bond_current_book_value(
                purchase_price=b.purchase_price,
                face_value=b.face_value,
                coupon_rate=b.coupon_rate,
                payment_frequency=b.payment_frequency,
                purchase_date=b.purchase_date,
                maturity_date=b.maturity_date,
            )
            for b in bonds_result.scalars().all()
        ),
        Decimal("0"),
    )

    property_result = await db.execute(
        select(PropertyInvestment).where(
            PropertyInvestment.user_id == current_user.id, PropertyInvestment.is_active == True
        )
    )
    total_property_value = sum(
        (
            calculate_property_current_value(
                cost=p.cost,
                expected_return_rate=p.expected_return_rate,
                purchase_date=p.purchase_date,
            )
            for p in property_result.scalars().all()
        ),
        Decimal("0"),
    )

    total_value = total_stocks_value + total_bonds_value + total_property_value
    return InvestmentSummaryResponse(
        total_stocks_value=total_stocks_value,
        total_bonds_value=total_bonds_value,
        total_property_value=total_property_value,
        total_value=total_value,
        total_unrealized_pnl=total_unrealized_pnl,
    )
