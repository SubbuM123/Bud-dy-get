"""SQLAlchemy ORM model for categorized expense records (Expense Tracker module).

An Expense is the thing this module is actually for - a categorized, chartable spending
record - as distinct from a Receipt (models/receipts.py), which is just the source
document extraction ran against. `receipt_id` is nullable and ON DELETE SET NULL: deleting
a receipt (or never having one - manual entries have receipt_id=None from the start) must
never delete the expense record itself, since that's the user's actual spending history.
merchant_name/amount/expense_date are duplicated onto Expense rather than always joined
from Receipt because a manually-entered expense has no receipt at all, and because a user
correcting a receipt's extracted fields shouldn't retroactively rewrite an already-created
expense's own values out from under them - see api/v1/expenses.py's create_expense_from_receipt.
"""

from datetime import datetime, date
from uuid import uuid4
from decimal import Decimal
from sqlalchemy import String, Boolean, DateTime, Date, Numeric, Text, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Expense(Base):
    """A single categorized spending record, optionally sourced from a Receipt."""

    __tablename__ = "expenses"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    receipt_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("receipts.id", ondelete="SET NULL"), nullable=True
    )

    # Core fields - copied from the receipt at creation time (see this module's docstring
    # for why), or entered directly for a manual, receipt-less expense.
    merchant_name: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)

    category_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("expense_categories.id", ondelete="SET NULL"), nullable=True
    )
    # Optional link to the bank_accounts module (see models/bank_accounts.py) - for a
    # manually-entered expense this is purely a tag ("this expense came out of this
    # account") with no balance effect. For a recurring expense's auto-created occurrence
    # (see this module's docstring on last_executed_date, and services/scheduler.py), it
    # IS debited from this account for real via apply_effect - the manual/tag-only
    # behavior stays unchanged, this only applies to scheduler-created rows.
    bank_account_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("bank_accounts.id", ondelete="SET NULL"), nullable=True
    )

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # A plain JSON array of strings rather than Postgres's native ARRAY type, so the same
    # column works against both the real Postgres database and the in-memory SQLite engine
    # tests/conftest.py runs the test suite against (SQLAlchemy's ARRAY type has no SQLite
    # DDL compiler) - the same cross-database-testability reasoning already applied
    # elsewhere in this project (e.g. vesting fields as plain columns, not JSONB, per
    # plan.md's Phase 4 deviation note).
    tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    recurrence_pattern: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Only meaningful when is_recurring=True: set by the V2 background scheduler
    # (services/scheduler.py) after it auto-creates a new Expense row for this rule's next
    # occurrence, so the next run knows this period is already covered. This field lives
    # on the *original* recurring Expense row (the "rule"), not on the auto-created
    # occurrence rows themselves, which are plain one-time expenses
    # (is_recurring=False) - see services/scheduler.py's recurring-expense handling.
    last_executed_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = relationship("User", back_populates="expenses")
    receipt = relationship("Receipt", back_populates="expenses")
    category = relationship("ExpenseCategory", back_populates="expenses")
    bank_account = relationship("BankAccount")
