"""SQLAlchemy ORM model for application users.

This is the root entity that every other domain object (bank accounts,
retirement accounts, and in future phases: expenses, investments) hangs off
of via a user_id foreign key. It stores login credentials and profile info
only - all financial data lives in its own module-specific tables. The
profile fields added for Phase 4 (birth_date, filing_status, annual_income,
has_employer_retirement_plan) live directly on User rather than a separate
UserProfile table since they're a handful of nullable scalar fields with no
independent lifecycle of their own - retirement_rules.py reads them to
compute catch-up eligibility, Roth IRA income phaseouts, and Traditional IRA
deductibility. The relationships to BankAccount/RetirementAccount are
declared here with cascade delete so that removing a user cleans up their
accounts automatically.
"""

from datetime import datetime, date
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import String, Boolean, DateTime, Date, Numeric, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import FilingStatus


# SQLAlchemy's Enum(SomeEnum) binds using the Python enum member's *name* by default, not
# its *value* - see models/bank_accounts.py's _enum_values for the full explanation of why
# this is required for every SQLEnum(...) column in the app.
def _enum_values(enum_cls):
    return [member.value for member in enum_cls]


class User(Base):
    """A registered user account, identified by a unique email address."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Profile fields consumed by retirement_rules.py: birth_date for age-based catch-up
    # contribution eligibility, filing_status + annual_income for Roth IRA income
    # phaseouts and Traditional IRA deductibility, has_employer_retirement_plan because
    # Traditional IRA deductibility depends on whether the filer is covered by a workplace
    # plan. All nullable since a user may not have filled out their profile yet.
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    filing_status: Mapped[FilingStatus | None] = mapped_column(
        SQLEnum(FilingStatus, values_callable=_enum_values), nullable=True
    )
    annual_income: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    has_employer_retirement_plan: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    bank_accounts = relationship("BankAccount", back_populates="user", cascade="all, delete-orphan")
    retirement_accounts = relationship(
        "RetirementAccount", back_populates="user", cascade="all, delete-orphan"
    )
    education_accounts = relationship(
        "EducationAccount", back_populates="user", cascade="all, delete-orphan"
    )
    receipts = relationship("Receipt", back_populates="user", cascade="all, delete-orphan")
    expenses = relationship("Expense", back_populates="user", cascade="all, delete-orphan")
    expense_categories = relationship(
        "ExpenseCategory", back_populates="user", cascade="all, delete-orphan"
    )
    incomes = relationship("Income", back_populates="user", cascade="all, delete-orphan")
    transactions = relationship(
        "Transaction", back_populates="user", cascade="all, delete-orphan"
    )
    stock_positions = relationship(
        "StockPosition", back_populates="user", cascade="all, delete-orphan"
    )
    bond_holdings = relationship(
        "BondHolding", back_populates="user", cascade="all, delete-orphan"
    )
    property_investments = relationship(
        "PropertyInvestment", back_populates="user", cascade="all, delete-orphan"
    )
