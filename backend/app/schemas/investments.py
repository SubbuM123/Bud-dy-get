"""Pydantic request/response schemas for the Investments API (Phase 5).

Defines the exact shape of JSON accepted and returned by the /investments endpoints in
api/v1/investments.py, independent of the SQLAlchemy models in models/investments.py - the
same separation used by every other module's schemas. Computed values that aren't real
columns (StockPositionResponse.market_value/unrealized_pnl, BondHoldingResponse's
current_book_value, PropertyInvestmentResponse's current_value) are plain required fields
here, built by the API layer rather than read via `from_attributes` off the ORM row - the
same "manually construct a response model for a computed view" pattern
schemas/retirement_accounts.py's ContributionLimitInfo and schemas/education_accounts.py's
GiftTaxInfo already use, rather than a from_attributes mirror of one row.
"""

from pydantic import BaseModel, Field, model_validator
from datetime import datetime, date
from decimal import Decimal

from app.models.enums import BondPaymentFrequency, StockTransactionType


# --- Stock positions --------------------------------------------------------------------

# Payload for POST /investments/stocks - a position starts empty; shares are added via a
# subsequent /buy. Creating a second position for a ticker the user already holds reuses
# the existing row rather than creating a duplicate - see api/v1/investments.py's
# `_get_or_create_position`.
class StockPositionCreate(BaseModel):
    ticker_symbol: str = Field(..., max_length=10)
    is_simulation: bool = True


# Shape returned for a single stock position. `market_value`/`unrealized_pnl` are computed
# by the endpoint from `current_price` (this position's own cached price - null if never
# fetched, in which case both computed fields are also null rather than assumed zero).
# `funding_bank_account_id` is the account a sell's proceeds will be credited back into -
# see models/investments.py:StockPosition's docstring.
class StockPositionResponse(BaseModel):
    id: str
    user_id: str
    ticker_symbol: str
    shares: Decimal
    average_cost_per_share: Decimal
    current_price: Decimal | None
    last_price_update: datetime | None
    market_value: Decimal | None
    unrealized_pnl: Decimal | None
    funding_bank_account_id: str | None
    is_simulation: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Payload for POST /investments/stocks/{id}/buy.
class StockBuyRequest(BaseModel):
    shares: Decimal = Field(..., gt=0)
    price_per_share: Decimal = Field(..., gt=0)
    transaction_date: date | None = None
    source_bank_account_id: str | None = None
    notes: str | None = None


# Payload for POST /investments/stocks/{id}/sell. Rejected with 400 if `shares` exceeds
# the position's current holding - see api/v1/investments.py's `sell_stock`.
class StockSellRequest(BaseModel):
    shares: Decimal = Field(..., gt=0)
    price_per_share: Decimal = Field(..., gt=0)
    transaction_date: date | None = None
    notes: str | None = None


class StockTransactionResponse(BaseModel):
    id: str
    stock_position_id: str
    transaction_type: StockTransactionType
    shares: Decimal
    price_per_share: Decimal
    transaction_date: date
    realized_pnl: Decimal | None
    source_bank_account_id: str | None
    notes: str | None
    created_at: datetime

    class Config:
        from_attributes = True


# --- Market data -------------------------------------------------------------------------

class StockPriceResponse(BaseModel):
    ticker: str
    price: Decimal | None


class StockHistoryPoint(BaseModel):
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


class StockHistoryResponse(BaseModel):
    ticker: str
    period: str
    data: list[StockHistoryPoint]


# --- Bonds ---------------------------------------------------------------------------------

# Fields shared by both the create request and the read response for a bond holding.
class BondHoldingBase(BaseModel):
    name: str = Field(..., max_length=255)
    purchase_price: Decimal = Field(..., gt=0)
    face_value: Decimal = Field(..., gt=0)
    coupon_rate: Decimal = Field(Decimal("0"), ge=0, le=1)
    payment_frequency: BondPaymentFrequency = BondPaymentFrequency.SEMI_ANNUALLY
    purchase_date: date
    maturity_date: date
    is_simulation: bool = True

    @model_validator(mode="after")
    def _validate_maturity_after_purchase(self) -> "BondHoldingBase":
        if self.maturity_date <= self.purchase_date:
            raise ValueError("maturity_date must be after purchase_date")
        return self


# `source_bank_account_id` is optional, like StockBuyRequest's - buying a bond can debit a
# bank account for real (see api/v1/investments.py's `create_bond_holding`), same "where
# is this money coming from" pattern the stock buy flow uses.
class BondHoldingCreate(BondHoldingBase):
    source_bank_account_id: str | None = None


class BondHoldingUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    coupon_rate: Decimal | None = Field(None, ge=0, le=1)
    payment_frequency: BondPaymentFrequency | None = None
    maturity_date: date | None = None


# `current_book_value` is computed by the endpoint via
# services/investment_calculator.calculate_bond_current_book_value.
class BondHoldingResponse(BondHoldingBase):
    id: str
    user_id: str
    is_active: bool
    sale_price: Decimal | None
    sale_date: date | None
    realized_pnl: Decimal | None
    current_book_value: Decimal
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BondSellRequest(BaseModel):
    sale_price: Decimal = Field(..., gt=0)
    sale_date: date | None = None


# One period of a bond's straight-line amortization schedule - see
# services/investment_calculator.calculate_bond_amortization_schedule.
class BondAmortizationPeriod(BaseModel):
    period_date: date
    coupon_payment: Decimal
    amortization_amount: Decimal
    book_value: Decimal


class BondAmortizationScheduleResponse(BaseModel):
    bond_id: str
    schedule: list[BondAmortizationPeriod]


# --- Property investments -------------------------------------------------------------------

class PropertyInvestmentBase(BaseModel):
    name: str = Field(..., max_length=255)
    cost: Decimal = Field(..., gt=0)
    expected_return_rate: Decimal = Field(Decimal("0.05"), ge=0, le=1)
    purchase_date: date
    is_simulation: bool = True


class PropertyInvestmentCreate(PropertyInvestmentBase):
    source_bank_account_id: str | None = None


class PropertyInvestmentUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    expected_return_rate: Decimal | None = Field(None, ge=0, le=1)


# `current_value` is computed by the endpoint via
# services/investment_calculator.calculate_property_current_value.
class PropertyInvestmentResponse(PropertyInvestmentBase):
    id: str
    user_id: str
    is_active: bool
    sale_price: Decimal | None
    sale_date: date | None
    realized_pnl: Decimal | None
    current_value: Decimal
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PropertySellRequest(BaseModel):
    sale_price: Decimal = Field(..., gt=0)
    sale_date: date | None = None


# --- Summary -----------------------------------------------------------------------------

# Powers the dashboard's net-worth aggregation - see api/v1/investments.py's
# `get_investment_summary`.
class InvestmentSummaryResponse(BaseModel):
    total_stocks_value: Decimal
    total_bonds_value: Decimal
    total_property_value: Decimal
    total_value: Decimal
    total_unrealized_pnl: Decimal
