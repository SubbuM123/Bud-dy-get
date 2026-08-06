"""Pydantic request/response schemas for the Income API.

These classes define the exact shape of JSON accepted and returned by the /income
endpoints in api/v1/income.py, independent of the SQLAlchemy models in models/income.py -
the same separation used by every other module's schemas. The enums are imported from
models.enums rather than redefined here, so the API layer and the database layer can
never drift out of sync on allowed values.
"""

from pydantic import BaseModel, Field, model_validator
from datetime import datetime, date
from decimal import Decimal

from app.models.enums import (
    IncomeFrequency,
    AllocationDestinationType,
    ContributionSourceType,
    VestingType,
)
from app.schemas.transactions import TransactionResponse

# Allocation percentages across one Income must sum to exactly 100 - tolerance accounts
# for the rounding a UI slider/input might introduce (e.g. three-way 33.33/33.33/33.34).
_ALLOCATION_SUM_TOLERANCE = Decimal("0.02")


# One destination's percentage slice of an Income - shared shape for both the create
# request and the read response. `source_type` is the "Option A" pre-tax-deduction field
# (see docs/phase4.6-money-flow-plan.md's "Next Steps" §8 and models/income.py's
# IncomeAllocation docstring) - only ever PRE_TAX_SALARY, on a retirement/education
# destination, or left unset entirely. `rsu_vesting_type`/`rsu_vesting_years`/
# `rsu_cliff_date`/`rsu_total_shares`/`rsu_shares_vested` are the Phase 5 equivalent for a
# `stock_position` destination - see docs/phase5-plan.md §2 and models/income.py's
# IncomeAllocation docstring for why `percentage` doesn't drive RSU vesting the way it
# drives every other destination type. `rsu_shares_vested` is a running total this app
# maintains (see services/income_posting.py's `post_income_transactions`) - a caller should never
# set it themselves; it's included here (not response-only) purely because
# IncomeAllocationResponse reuses this same base class, and always defaults to 0 on create.
class IncomeAllocationBase(BaseModel):
    destination_type: AllocationDestinationType
    destination_id: str
    percentage: Decimal = Field(..., gt=0, le=100)
    source_type: ContributionSourceType | None = None
    rsu_vesting_type: VestingType | None = None
    rsu_vesting_years: int | None = Field(None, ge=1, le=10)
    rsu_cliff_date: date | None = None
    rsu_total_shares: Decimal | None = Field(None, gt=0)
    rsu_shares_vested: Decimal = Decimal("0")

    @model_validator(mode="after")
    def _validate_source_type(self) -> "IncomeAllocationBase":
        if self.source_type is not None:
            if self.source_type != ContributionSourceType.PRE_TAX_SALARY:
                raise ValueError(
                    "An income allocation's source_type may only be pre_tax_salary - "
                    "bank_account has no source account to debit here, and track_only is "
                    "already what an unset source_type means."
                )
            if self.destination_type not in (
                AllocationDestinationType.RETIREMENT_ACCOUNT,
                AllocationDestinationType.EDUCATION_ACCOUNT,
            ):
                raise ValueError(
                    "source_type: pre_tax_salary only applies to a retirement_account or "
                    "education_account destination."
                )
        return self

    @model_validator(mode="after")
    def _validate_rsu_vesting(self) -> "IncomeAllocationBase":
        has_rsu_fields = (
            self.rsu_vesting_type is not None
            or self.rsu_vesting_years is not None
            or self.rsu_cliff_date is not None
            or self.rsu_total_shares is not None
        )
        if not has_rsu_fields:
            return self
        if self.destination_type != AllocationDestinationType.STOCK_POSITION:
            raise ValueError(
                "rsu_vesting_type/rsu_vesting_years/rsu_cliff_date only apply to a "
                "stock_position destination."
            )
        if self.rsu_vesting_type is None:
            raise ValueError("rsu_vesting_type is required when any RSU vesting field is set")
        if self.rsu_total_shares is None:
            raise ValueError("rsu_total_shares (the grant size) is required for RSU vesting")
        if self.rsu_vesting_type == VestingType.GRADED and self.rsu_vesting_years is None:
            raise ValueError("rsu_vesting_years is required for graded RSU vesting")
        if self.rsu_vesting_type == VestingType.CLIFF and self.rsu_cliff_date is None:
            raise ValueError("rsu_cliff_date is required for cliff RSU vesting")
        return self


class IncomeAllocationCreate(IncomeAllocationBase):
    pass


class IncomeAllocationResponse(IncomeAllocationBase):
    id: str

    class Config:
        from_attributes = True


# Fields shared by both the create request and the read response for an Income.
class IncomeBase(BaseModel):
    name: str = Field(..., max_length=255)
    # Always post-tax - see models/income.py's Income docstring. If entered_amount comes
    # from a UI hint like "70% of your gross salary," that math happens client-side; the
    # API only ever sees the resulting post-tax number.
    amount: Decimal = Field(..., gt=0)
    is_recurring: bool = True
    frequency: IncomeFrequency | None = None
    start_date: date | None = None
    income_date: date | None = None


# Payload for POST /income. allocations must sum to 100% across all destinations, and
# either frequency+start_date (recurring) or income_date (one-time) must be present -
# both checked here rather than left to the database, since neither is a single-column
# constraint.
class IncomeCreate(IncomeBase):
    allocations: list[IncomeAllocationCreate] = Field(..., min_length=1)

    @model_validator(mode="after")
    def _validate(self) -> "IncomeCreate":
        total = sum((a.percentage for a in self.allocations), Decimal("0"))
        if abs(total - Decimal("100")) > _ALLOCATION_SUM_TOLERANCE:
            raise ValueError(f"Allocation percentages must sum to 100, got {total}")

        if self.is_recurring:
            if self.frequency is None:
                raise ValueError("frequency is required for recurring income")
            if self.start_date is None:
                self.start_date = date.today()
        else:
            if self.income_date is None:
                raise ValueError("income_date is required for one-time income")

        return self


# Payload for PUT /income/{id}. Allocations are replaced wholesale via a separate
# endpoint (PUT /income/{id}/allocations) rather than patched here field-by-field, since a
# partial allocation edit could easily leave the set summing to something other than 100.
class IncomeUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    amount: Decimal | None = Field(None, gt=0)
    frequency: IncomeFrequency | None = None
    is_active: bool | None = None


# Payload for PUT /income/{id}/allocations - replaces every allocation on the income.
class IncomeAllocationsReplace(BaseModel):
    allocations: list[IncomeAllocationCreate] = Field(..., min_length=1)

    @model_validator(mode="after")
    def _validate_sum(self) -> "IncomeAllocationsReplace":
        total = sum((a.percentage for a in self.allocations), Decimal("0"))
        if abs(total - Decimal("100")) > _ALLOCATION_SUM_TOLERANCE:
            raise ValueError(f"Allocation percentages must sum to 100, got {total}")
        return self


# Shape returned for a single income, built from the ORM object via from_attributes.
class IncomeResponse(IncomeBase):
    id: str
    user_id: str
    is_active: bool
    allocations: list[IncomeAllocationResponse]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Payload for POST /income/{id}/log - records one real occurrence of a (usually
# recurring) income, splitting `amount` (defaults to the Income's own amount, overridable
# for e.g. a paycheck that included overtime) across its allocations and posting one
# Transaction + real balance bump per destination. `log_date` defaults to today.
class LogIncomeRequest(BaseModel):
    amount: Decimal | None = Field(None, gt=0)
    log_date: date | None = None


# Response for POST /income/{id}/log: the total amount logged plus every Transaction row
# it produced (one per allocation destination), so the frontend can show exactly where
# the money went without a second round-trip.
class LogIncomeResponse(BaseModel):
    income_id: str
    total_amount: Decimal
    log_date: date
    transactions: list[TransactionResponse]
