"""SQLAlchemy ORM model for the unified real-money transaction log.

A Transaction is the persisted, editable/deletable record of one real (not simulated)
money movement this app has actually posted: an income occurrence being logged (see
api/v1/income.py's `log_income`), or a retirement/education contribution being recorded
(see api/v1/retirement_accounts.py and api/v1/education_accounts.py's
`record_contribution`). It exists because, before this module, those two contribute
endpoints only ever *mutated a running total* (balance, contribution_ytd) with no
individual record of the event itself - so a mis-entered amount or a contribution the user
wants to undo had no way to be corrected short of hand-editing the account's balance.
Every Transaction row therefore doubles as an audit trail and as the one place a user can
fix a mistake: editing `amount` (see api/v1/transactions.py's `update_transaction`) applies
just the delta to whatever account(s) the original posting affected, and deleting a row
fully reverses its effect before removing it - see that same module's `_apply_effect`.

Expenses deliberately do NOT get a Transaction row: models/expenses.py's Expense already
*is* a fully editable/deletable record of its own event (see api/v1/expenses.py), so
mirroring it here would just be a second, redundant ledger for the same money.

`account_type`/`account_id` name the *destination* the transaction posted into (a bank
account for INCOME, a retirement/education account for the two CONTRIBUTION types) as a
plain enum + id pair rather than a real foreign key, for the same polymorphic-target reason
as IncomeAllocation.destination_id - see models/income.py's docstring and
models/enums.py:AllocationDestinationType. `source_bank_account_id` is a real foreign key
since it only ever points at one table: the bank account debited when a contribution's
`source_type` is BANK_ACCOUNT (see models/enums.py:ContributionSourceType) - null whenever
the money came from pre-tax salary or wasn't tracked to a source at all.
"""

from datetime import datetime, date
from uuid import uuid4
from decimal import Decimal
from sqlalchemy import String, DateTime, Date, Numeric, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import TransactionType, AllocationDestinationType, ContributionSourceType


# SQLAlchemy's Enum(SomeEnum) binds using the Python enum member's *name* by default, not
# its *value* - see models/bank_accounts.py's _enum_values for the full explanation.
def _enum_values(enum_cls):
    return [member.value for member in enum_cls]


class Transaction(Base):
    """One posted, editable/deletable real-money event - see this module's docstring."""

    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    transaction_type: Mapped[TransactionType] = mapped_column(
        SQLEnum(TransactionType, values_callable=_enum_values), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # The destination account this transaction posted into - see this module's docstring.
    account_type: Mapped[AllocationDestinationType | None] = mapped_column(
        SQLEnum(AllocationDestinationType, values_callable=_enum_values), nullable=True
    )
    account_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)

    # Which Income rule (if any) generated this row via log_income - null for a
    # contribution-type transaction, or for an income logged without a saved Income rule.
    income_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("incomes.id", ondelete="SET NULL"), nullable=True
    )

    # Only meaningful for the two *_CONTRIBUTION transaction types - see
    # models/enums.py:ContributionSourceType.
    source_type: Mapped[ContributionSourceType | None] = mapped_column(
        SQLEnum(ContributionSourceType, values_callable=_enum_values), nullable=True
    )
    source_bank_account_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("bank_accounts.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = relationship("User", back_populates="transactions")
