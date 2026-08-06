"""SQLAlchemy ORM models for the Education Savings module.

This file defines the two tables backing 529 college savings plan tracking
(per docs/phase4.5-plan.md): EducationAccount, and
EducationRecurringContribution - the education-module equivalent of
retirement_accounts.py's RetirementRecurringContribution, reusing the same
ContributionFrequency enum rather than redeclaring it. The key structural
difference from RetirementAccount: a 529 has a distinct beneficiary (the
student) separate from the owning user, so this model carries
beneficiary_name/beneficiary_birth_date fields that retirement accounts
don't need. Enum types are imported from models.enums so the allowed values
stay in sync with the Pydantic schemas used at the API layer.
"""

from datetime import datetime, date
from uuid import uuid4
from decimal import Decimal
from sqlalchemy import String, Boolean, DateTime, Date, Numeric, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import EducationAccountType, ContributionFrequency


# SQLAlchemy's Enum(SomeEnum) binds using the Python enum member's *name* by default, not
# its *value* - see models/bank_accounts.py's _enum_values for the full explanation.
def _enum_values(enum_cls):
    return [member.value for member in enum_cls]


class EducationAccount(Base):
    """A 529 (or other education-savings) account owned by a user for a beneficiary."""

    __tablename__ = "education_accounts"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[EducationAccountType] = mapped_column(
        SQLEnum(EducationAccountType, values_callable=_enum_values),
        default=EducationAccountType.FIVE_TWENTY_NINE,
    )

    # The student the account is for - distinct from user_id (the account owner), unlike
    # RetirementAccount where the account holder and the beneficiary are the same person.
    beneficiary_name: Mapped[str] = mapped_column(String(255), nullable=False)
    beneficiary_birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # The state program administering the account (e.g. "NY 529", "Utah my529") - purely
    # informational, not tied to any calculation (parallels employer_name in spirit only).
    plan_provider: Mapped[str | None] = mapped_column(String(255), nullable=True)

    balance: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    contribution_ytd: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0"))
    expected_return_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0.07"))
    is_simulation: Mapped[bool] = mapped_column(Boolean, default=True)
    # Set by the V2 background scheduler (services/scheduler.py) after applying this
    # account's monthly expected return (expected_return_rate / 12) to `balance` - same
    # pattern as models/retirement_accounts.py's last_interest_applied_date.
    last_interest_applied_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = relationship("User", back_populates="education_accounts")
    recurring_contributions = relationship(
        "EducationRecurringContribution",
        back_populates="education_account",
        cascade="all, delete-orphan",
    )


class EducationRecurringContribution(Base):
    """A scheduled monthly or yearly contribution to an education savings account.

    Mirrors retirement_accounts.py's RetirementRecurringContribution: it feeds
    education_simulator.py's growth projections, and the V2 background scheduler
    (services/scheduler.py) can auto-post real occurrences of this rule - see
    `last_executed_date` below. Recording one manually still goes through
    POST /education-accounts/{id}/contribute at any time.
    """

    __tablename__ = "education_recurring_contributions"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    education_account_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("education_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    frequency: Mapped[ContributionFrequency] = mapped_column(
        SQLEnum(ContributionFrequency, values_callable=_enum_values), nullable=False
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Set by the V2 background scheduler after auto-posting an occurrence of this rule -
    # see retirement_accounts.py's RetirementRecurringContribution.last_executed_date for
    # the identical pattern.
    last_executed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    education_account = relationship("EducationAccount", back_populates="recurring_contributions")
