"""SQLAlchemy ORM models for the Investments module (Phase 5).

This file defines four tables covering three separate asset classes: StockPosition (one
row per ticker a user holds, aggregate shares + weighted-average cost basis) with its own
StockTransaction history (buy/sell/RSU-vest events - the only investment type that needs a
per-event history, since a stock position can be partially bought/sold repeatedly), plus
BondHolding and PropertyInvestment, which are simpler "bought once, sold once" holdings
that store their own terminal sale state inline rather than via a side table (see each
class's docstring for why). All three follow the same shape as
models/retirement_accounts.py (UUID primary key, user_id FK, is_simulation flag,
timestamps) so this module stays structurally consistent with the modules it was modeled
after.
"""

from datetime import datetime, date
from uuid import uuid4
from decimal import Decimal
from sqlalchemy import String, Boolean, DateTime, Date, Numeric, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import BondPaymentFrequency, StockTransactionType


# SQLAlchemy's Enum(SomeEnum) binds using the Python enum member's *name* by default, not
# its *value* - see models/bank_accounts.py's _enum_values for the full explanation.
def _enum_values(enum_cls):
    return [member.value for member in enum_cls]


class StockPosition(Base):
    """One user's aggregate holding in a single ticker symbol, real or simulated.

    `shares`/`average_cost_per_share` are running totals updated by every buy/sell/RSU-vest
    (see api/v1/investments.py and api/v1/income.py) - they are not recomputed from
    `transactions` on read, the same "mutate a running total, keep a side history for audit
    and correction" split every other real-money balance in this app already uses (compare
    RetirementAccount.balance vs. its Transaction history). `current_price`/
    `last_price_update` are a cache of the last services/stock_price.py fetch, not
    refreshed on every read - a stale cached price is preferable to blocking a page load on
    an external API call every time.

    `funding_bank_account_id` remembers the most recent bank account a buy was funded
    from (set in api/v1/investments.py's `buy_stock`), so a later sell can credit
    proceeds back into the same account without asking again - see that module's
    `sell_stock`. If a position was ever bought with two different funding accounts
    across separate buys, this holds only the most recent one; a sell always credits
    whichever account is currently remembered, not a per-lot split - a deliberate v1
    simplification consistent with `average_cost_per_share` also being a single
    weighted average rather than per-lot tracking.
    """

    __tablename__ = "stock_positions"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    ticker_symbol: Mapped[str] = mapped_column(String(10), nullable=False)
    shares: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    average_cost_per_share: Mapped[Decimal] = mapped_column(Numeric(15, 4), default=Decimal("0"))
    current_price: Mapped[Decimal | None] = mapped_column(Numeric(15, 4), nullable=True)
    last_price_update: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    funding_bank_account_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("bank_accounts.id", ondelete="SET NULL"), nullable=True
    )
    is_simulation: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = relationship("User", back_populates="stock_positions")
    transactions = relationship(
        "StockTransaction", back_populates="stock_position", cascade="all, delete-orphan"
    )


class StockTransaction(Base):
    """One buy, sell, or RSU-vest event against a StockPosition.

    Deliberately a dedicated table (unlike BondHolding/PropertyInvestment, which store
    their single sale inline) because a stock position can be bought into and sold from
    repeatedly over time - a user needs to see that history, and `realized_pnl` on a SELL
    row is only meaningful per-event, not as a single field on the position itself.
    `source_bank_account_id` is only ever set on a BUY funded from a bank account, mirroring
    Transaction.source_bank_account_id's meaning for a retirement/education contribution.
    """

    __tablename__ = "stock_transactions"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    stock_position_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("stock_positions.id", ondelete="CASCADE"), nullable=False
    )
    transaction_type: Mapped[StockTransactionType] = mapped_column(
        SQLEnum(StockTransactionType, values_callable=_enum_values), nullable=False
    )
    shares: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    price_per_share: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    # Only set on a SELL - see services/investment_calculator.calculate_realized_pnl.
    realized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    # Only set on a BUY funded from a bank account - null for a BUY paid for outside the
    # app's tracking, or for a SELL/RSU_VEST (neither debits a bank account).
    source_bank_account_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("bank_accounts.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    stock_position = relationship("StockPosition", back_populates="transactions")


class BondHolding(Base):
    """A single bond purchase, real or simulated.

    Unlike StockPosition, a bond is bought once and sold once (or held to maturity) - there
    is no partial-sell concept - so the sale result lives directly on this row
    (`is_active`/`sale_price`/`sale_date`/`realized_pnl`) instead of a side transactions
    table. `purchase_price` vs. `face_value` may differ (a premium or discount purchase);
    services/investment_calculator.py's amortization functions use both plus `coupon_rate`/
    `payment_frequency`/`purchase_date`/`maturity_date` to project book value over time -
    see docs/phase5-plan.md §3 for the straight-line method used.
    """

    __tablename__ = "bond_holdings"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    face_value: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    coupon_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0"))
    payment_frequency: Mapped[BondPaymentFrequency] = mapped_column(
        SQLEnum(BondPaymentFrequency, values_callable=_enum_values),
        default=BondPaymentFrequency.SEMI_ANNUALLY,
    )
    purchase_date: Mapped[date] = mapped_column(Date, nullable=False)
    maturity_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sale_price: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    sale_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    realized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    is_simulation: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = relationship("User", back_populates="bond_holdings")


class PropertyInvestment(Base):
    """A single real-estate investment holding, real or simulated.

    Deliberately the simplest schema in this module - just `cost` + `expected_return_rate`
    for compound-growth projection (see services/investment_calculator.py's
    calculate_property_current_value), no amortization concept the way a bond has (a
    property has no face-value-at-maturity to amortize toward). Sale state stored inline,
    same reasoning as BondHolding.
    """

    __tablename__ = "property_investments"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    cost: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    expected_return_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0.05"))
    purchase_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sale_price: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    sale_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    realized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    is_simulation: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = relationship("User", back_populates="property_investments")
