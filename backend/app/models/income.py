"""SQLAlchemy ORM models for the Income module.

This file defines the two tables backing income tracking: Income (a recurring salary/
side-income source, or a one-time bonus/gift/refund) and IncomeAllocation (the percentage
split of an Income across one or more destination accounts - a bank account, a retirement
account, or an education account). Income itself never moves money; it's the *rule*, same
as bank_accounts.RecurringAction or retirement_accounts.RetirementRecurringContribution -
see api/v1/income.py's `log_income` for the endpoint that actually posts a Transaction
(models/transactions.py) and bumps a destination account's real balance for one occurrence
of a recurring Income, or for a one-time Income at creation time.

IncomeAllocation.destination_id is a plain UUID string, not a foreign key, because it can
point at any one of three different tables depending on destination_type - see
models/enums.py:AllocationDestinationType for why that's a plain enum + id pair rather than
a real polymorphic FK.
"""

from datetime import datetime, date
from uuid import uuid4
from decimal import Decimal
from sqlalchemy import String, Boolean, DateTime, Date, Numeric, Integer, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import (
    IncomeFrequency,
    AllocationDestinationType,
    ContributionSourceType,
    VestingType,
)


# SQLAlchemy's Enum(SomeEnum) binds using the Python enum member's *name* by default, not
# its *value* - see models/bank_accounts.py's _enum_values for the full explanation.
def _enum_values(enum_cls):
    return [member.value for member in enum_cls]


class Income(Base):
    """A recurring income source (salary, side gig) or a one-time payment (bonus, gift).

    `amount` is always post-tax: the app doesn't model tax withholding (see
    api/v1/income.py's docstring), so the user enters what actually lands in their pocket
    per occurrence (recurring) or in total (one-time).
    """

    __tablename__ = "incomes"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=True)
    # Required when is_recurring=True; null for a one-time payment.
    frequency: Mapped[IncomeFrequency | None] = mapped_column(
        SQLEnum(IncomeFrequency, values_callable=_enum_values), nullable=True
    )
    # Required when is_recurring=True (when the recurring income started, for projection
    # purposes only - see services/income_allocator.py); null for a one-time payment.
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Required when is_recurring=False: the date the one-time payment was received.
    income_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Set by the V2 background scheduler (services/scheduler.py) after auto-posting an
    # occurrence for this recurring Income, so the next scheduler run knows this period is
    # already covered and won't double-post. Null for a one-time payment (never scheduled)
    # or a recurring Income that has only ever been logged manually via POST
    # /income/{id}/log, which does not touch this field.
    last_executed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = relationship("User", back_populates="incomes")
    allocations = relationship(
        "IncomeAllocation", back_populates="income", cascade="all, delete-orphan"
    )


class IncomeAllocation(Base):
    """One destination's percentage slice of an Income - every Income's allocations must
    sum to exactly 100% (enforced in schemas/income.py, not at the database level, since
    Postgres can't validate a sum across sibling rows via a column constraint).

    `source_type` is the Phase 4.6 "Option A" pre-tax-deduction field (see
    docs/phase4.6-money-flow-plan.md's "Next Steps" §8): null for every ordinary
    allocation, or `PRE_TAX_SALARY` for an allocation into a retirement/education account
    that represents a payroll deduction rather than post-tax money landing in a bank
    account first. When set, logging this Income's occurrence posts a
    RETIREMENT_CONTRIBUTION/EDUCATION_CONTRIBUTION transaction for that allocation's share
    (bumping the destination's `contribution_ytd` too) instead of a plain INCOME
    transaction - see services/income_posting.py's `post_income_transactions`. Only `PRE_TAX_SALARY`
    is meaningful here: `BANK_ACCOUNT` would need a source bank account to debit, which an
    income allocation - money arriving, not leaving - has no field for, and `TRACK_ONLY` is
    already what a null `source_type` means for a non-retirement/education destination.

    `rsu_vesting_type`/`rsu_vesting_years`/`rsu_cliff_date`/`rsu_total_shares`/
    `rsu_shares_vested` are the Phase 5 equivalent for an allocation whose
    `destination_type` is `STOCK_POSITION`: an employer stock grant (RSU) that vests over
    time, mirroring `RetirementAccount.vesting_type`'s existing immediate/cliff/graded
    schedule. `percentage`/`amount`-based share calculation (used by every other
    destination type) does NOT apply here - a real RSU grant is a fixed number of shares
    vesting on a schedule, not a percentage of each paycheck's dollar amount, so
    `rsu_total_shares` is the grant size and `rsu_shares_vested` is a running total this
    app updates each time vesting is logged (mirroring how a real account's balance is a
    running total). When RSU fields are set, logging this Income's occurrence calculates
    newly-vested shares (see services/investment_calculator.calculate_rsu_vested_shares,
    using this Income's own `start_date` as the grant date - see docs/phase5-plan.md's
    "Deliberate Scope Limits" for why there's no separate grant-date field) and posts an
    RSU_VEST transaction instead of a plain INCOME one - same "extend IncomeAllocation"
    approach as `source_type` above.
    """

    __tablename__ = "income_allocations"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    income_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("incomes.id", ondelete="CASCADE"), nullable=False
    )
    destination_type: Mapped[AllocationDestinationType] = mapped_column(
        SQLEnum(AllocationDestinationType, values_callable=_enum_values), nullable=False
    )
    # Not a foreign key - see this module's docstring.
    destination_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    source_type: Mapped[ContributionSourceType | None] = mapped_column(
        SQLEnum(ContributionSourceType, values_callable=_enum_values), nullable=True
    )
    rsu_vesting_type: Mapped[VestingType | None] = mapped_column(
        SQLEnum(VestingType, values_callable=_enum_values), nullable=True
    )
    rsu_vesting_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rsu_cliff_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    rsu_total_shares: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    rsu_shares_vested: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    income = relationship("Income", back_populates="allocations")
