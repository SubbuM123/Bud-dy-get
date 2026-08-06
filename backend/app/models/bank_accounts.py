"""SQLAlchemy ORM models for the Bank Account Simulator module.

This file defines the three tables that back the bank account feature: the
accounts themselves (savings/checking/CD), the recurring deposit/withdrawal
rules attached to an account, and the transaction log produced when those
rules (or manual actions) are applied. These models are consumed by the
bank_simulator service for growth projections and by the bank_accounts API
router for CRUD operations. Enum types are imported from models.enums so the
allowed values stay in sync with the Pydantic schemas used at the API layer.
"""

from datetime import datetime, date
from uuid import uuid4
from decimal import Decimal
from sqlalchemy import String, Boolean, DateTime, Date, Numeric, Integer, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import (
    AccountType,
    CompoundingFrequency,
    ActionType,
    FrequencyUnit,
    ActionCategory,
)


# SQLAlchemy's Enum(SomeEnum) binds using the Python enum member's *name* (e.g. "SAVINGS")
# by default, not its *value* ("savings") - but the Postgres enum types created by the
# initial migration only contain the lowercase values. values_callable makes every
# SQLEnum(...) column below bind/read the member's value instead, matching the DB.
def _enum_values(enum_cls):
    return [member.value for member in enum_cls]


class BankAccount(Base):
    """A savings, checking, or CD account owned by a user, real or simulated."""

    __tablename__ = "bank_accounts"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[AccountType] = mapped_column(
        SQLEnum(AccountType, values_callable=_enum_values), nullable=False
    )
    principal: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    current_balance: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    interest_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    compounding_frequency: Mapped[CompoundingFrequency] = mapped_column(
        SQLEnum(CompoundingFrequency, values_callable=_enum_values),
        default=CompoundingFrequency.MONTHLY,
    )
    # CD term is expressed as an explicit start date + length in months, rather than a
    # maturity date, so the term length used to schedule *renewals* (see
    # services/combined_simulator.py) is never ambiguous or re-derived from unrelated
    # data. An earlier version stored only a maturity date and inferred the renewal term
    # from `created_at` (when the row was inserted into this database) to that maturity
    # date - wrong whenever `created_at` didn't match when the CD's current term actually
    # began (e.g. entering a CD that was opened months ago, or editing the maturity date
    # later), which could desync the renewal cadence from what the user actually meant.
    cd_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    cd_term_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Only meaningful when account_type == CD: whether a matured CD rolls into a new
    # CD term of the same length/rate (True) or deposits into a savings account (False).
    cd_auto_renew: Mapped[bool] = mapped_column(Boolean, default=False)
    is_simulation: Mapped[bool] = mapped_column(Boolean, default=True)
    # Set by the V2 background scheduler (services/scheduler.py) after posting interest
    # for this account, so the next run knows this period is already covered - same
    # idempotency role as RecurringAction.next_execution_date below, but per-account
    # rather than per-rule since interest isn't a RecurringAction row. Null until the
    # scheduler has run at least once for this account.
    last_interest_applied_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = relationship("User", back_populates="bank_accounts")
    recurring_actions = relationship(
        "RecurringAction", back_populates="bank_account", cascade="all, delete-orphan"
    )
    transactions = relationship(
        "BankTransaction", back_populates="bank_account", cascade="all, delete-orphan"
    )


class RecurringAction(Base):
    """A scheduled deposit or withdrawal rule (e.g. monthly salary, weekly rent)."""

    __tablename__ = "recurring_actions"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    bank_account_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("bank_accounts.id", ondelete="CASCADE"), nullable=False
    )
    action_type: Mapped[ActionType] = mapped_column(
        SQLEnum(ActionType, values_callable=_enum_values), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Predetermined tag (salary, housing, investment, ...) for future analysis by category.
    category: Mapped[ActionCategory | None] = mapped_column(
        SQLEnum(ActionCategory, values_callable=_enum_values), nullable=True
    )
    frequency_value: Mapped[int] = mapped_column(nullable=False)
    frequency_unit: Mapped[FrequencyUnit] = mapped_column(
        SQLEnum(FrequencyUnit, values_callable=_enum_values), nullable=False
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_execution_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    bank_account = relationship("BankAccount", back_populates="recurring_actions")


class BankTransaction(Base):
    """An individual posted deposit/withdrawal, used to build an account's history."""

    __tablename__ = "bank_transactions"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    bank_account_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("bank_accounts.id", ondelete="CASCADE"), nullable=False
    )
    transaction_type: Mapped[ActionType] = mapped_column(
        SQLEnum(ActionType, values_callable=_enum_values), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    transaction_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    bank_account = relationship("BankAccount", back_populates="transactions")
