"""SQLAlchemy ORM models for the Retirement Accounts module.

This file defines the two tables backing the module: RetirementAccount
(401(k)/Roth 401(k)/Traditional IRA/Roth IRA/SEP IRA/SIMPLE IRA/HSA
tracking - contribution totals, the employer-match and vesting fields
needed to compute employer contributions, and the expected-return-rate
field used by retirement_simulator.py for growth projections), and
RetirementRecurringContribution (a scheduled monthly or yearly
contribution, e.g. "$500/month via payroll" or "$7,500/year lump sum
before the tax deadline" - the retirement-module equivalent of
bank_accounts.py's RecurringAction, feeding retirement_simulator.py's
growth projections the same way). Both follow the same shape as
models/bank_accounts.py (UUID primary key, FK to parent, created_at) so the
retirement module stays structurally consistent with the bank account
module it was modeled after. Enum types are imported from models.enums so
the allowed values stay in sync with the Pydantic schemas used at the API
layer.
"""

from datetime import datetime, date
from uuid import uuid4
from decimal import Decimal
from sqlalchemy import String, Boolean, DateTime, Date, Numeric, Integer, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import RetirementAccountType, VestingType, ContributionFrequency


# SQLAlchemy's Enum(SomeEnum) binds using the Python enum member's *name* by default, not
# its *value* - see models/bank_accounts.py's _enum_values for the full explanation.
def _enum_values(enum_cls):
    return [member.value for member in enum_cls]


class RetirementAccount(Base):
    """A 401(k), IRA, or HSA account owned by a user, real or simulated."""

    __tablename__ = "retirement_accounts"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[RetirementAccountType] = mapped_column(
        SQLEnum(RetirementAccountType, values_callable=_enum_values), nullable=False
    )
    balance: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    contribution_ytd: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0"))

    # Employer-sponsored plan fields (401k/Roth 401k). Nullable since they're meaningless
    # for an IRA or HSA, which has no employer match.
    employer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    annual_salary: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    employer_match_percent: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    employer_match_limit_percent: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 4), nullable=True
    )

    # Vesting schedule for employer contributions. vesting_years is the cliff length or the
    # number of years a graded schedule takes to reach 100%; vested_percent is the current
    # snapshot, recomputed by retirement_rules.calculate_vested_amount as time passes.
    vesting_type: Mapped[VestingType | None] = mapped_column(
        SQLEnum(VestingType, values_callable=_enum_values), nullable=True
    )
    vesting_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vested_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("100"))

    expected_return_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0.07"))
    is_simulation: Mapped[bool] = mapped_column(Boolean, default=True)
    # Set by the V2 background scheduler (services/scheduler.py) after applying this
    # account's monthly expected return (expected_return_rate / 12) to `balance`, so the
    # next run knows this month is already covered. Null until the scheduler has run at
    # least once for this account - see models/bank_accounts.py's
    # last_interest_applied_date for the same pattern applied to bank accounts.
    last_interest_applied_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = relationship("User", back_populates="retirement_accounts")
    recurring_contributions = relationship(
        "RetirementRecurringContribution",
        back_populates="retirement_account",
        cascade="all, delete-orphan",
    )


class RetirementRecurringContribution(Base):
    """A scheduled monthly or yearly employee contribution to a retirement account.

    Mirrors bank_accounts.py's RecurringAction: it feeds retirement_simulator.py's growth
    projections (see that module's `_monthly_recurring_amount`). The V2 background
    scheduler (services/scheduler.py) can now also auto-post real occurrences of this rule
    - see `last_executed_date` below - but recording one manually still goes through
    POST /retirement-accounts/{id}/contribute at any time.
    """

    __tablename__ = "retirement_recurring_contributions"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    retirement_account_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("retirement_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    frequency: Mapped[ContributionFrequency] = mapped_column(
        SQLEnum(ContributionFrequency, values_callable=_enum_values), nullable=False
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Set by the V2 background scheduler after auto-posting an occurrence of this rule, so
    # the next run knows this period is already covered. Null if this rule has only ever
    # been contributed to manually (POST /retirement-accounts/{id}/contribute doesn't
    # touch this field - it's not tied to any particular recurring rule).
    last_executed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    retirement_account = relationship("RetirementAccount", back_populates="recurring_contributions")
