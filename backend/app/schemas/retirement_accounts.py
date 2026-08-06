"""Pydantic request/response schemas for the Retirement Accounts API.

These classes define the exact shape of JSON accepted and returned by the
/retirement-accounts endpoints in api/v1/retirement_accounts.py, independent
of the SQLAlchemy model in models/retirement_accounts.py - the same
separation used by schemas/bank_accounts.py. The account_type/vesting_type
enums are imported from models.enums rather than redefined here, so the API
layer and the database layer can never drift out of sync on allowed values.
"""

from pydantic import BaseModel, Field, model_validator
from datetime import datetime, date
from decimal import Decimal

from app.models.enums import (
    RetirementAccountType,
    VestingType,
    ContributionFrequency,
    ContributionSourceType,
)


# Fields shared by both the create request and the read response for a retirement account.
class RetirementAccountBase(BaseModel):
    account_name: str = Field(..., max_length=255)
    account_type: RetirementAccountType
    balance: Decimal = Field(..., ge=0)
    employer_name: str | None = Field(None, max_length=255)
    annual_salary: Decimal | None = Field(None, ge=0)
    employer_match_percent: Decimal | None = Field(None, ge=0, le=1)
    employer_match_limit_percent: Decimal | None = Field(None, ge=0, le=1)
    vesting_type: VestingType | None = None
    vesting_years: int | None = Field(None, ge=0, le=10)
    expected_return_rate: Decimal = Field(Decimal("0.07"), ge=0, le=1)
    is_simulation: bool = True


# Payload for POST /retirement-accounts.
class RetirementAccountCreate(RetirementAccountBase):
    pass


# Payload for PUT /retirement-accounts/{id}; every field is optional so callers can patch a subset.
class RetirementAccountUpdate(BaseModel):
    account_name: str | None = Field(None, max_length=255)
    balance: Decimal | None = Field(None, ge=0)
    employer_name: str | None = Field(None, max_length=255)
    annual_salary: Decimal | None = Field(None, ge=0)
    employer_match_percent: Decimal | None = Field(None, ge=0, le=1)
    employer_match_limit_percent: Decimal | None = Field(None, ge=0, le=1)
    vesting_type: VestingType | None = None
    vesting_years: int | None = Field(None, ge=0, le=10)
    expected_return_rate: Decimal | None = Field(None, ge=0, le=1)


# Shape returned for a single retirement account, built from the ORM object via from_attributes.
class RetirementAccountResponse(RetirementAccountBase):
    id: str
    user_id: str
    contribution_ytd: Decimal
    vested_percent: Decimal
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Payload for POST /retirement-accounts/{id}/contribute. source_type says where the money
# actually came from - see models/enums.py:ContributionSourceType - and, matching real
# 401(k)/IRA funding patterns, determines what else this contribution affects:
# BANK_ACCOUNT debits source_bank_account_id's real balance (required in that case);
# PRE_TAX_SALARY and TRACK_ONLY touch no other account. Every contribution - regardless of
# source_type - still posts a Transaction row (see api/v1/retirement_accounts.py) so it
# shows up in the unified transaction log and can be corrected later.
class ContributionCreate(BaseModel):
    amount: Decimal = Field(..., gt=0)
    source_type: ContributionSourceType = ContributionSourceType.TRACK_ONLY
    source_bank_account_id: str | None = None

    @model_validator(mode="after")
    def _require_source_account(self) -> "ContributionCreate":
        if self.source_type == ContributionSourceType.BANK_ACCOUNT and not self.source_bank_account_id:
            raise ValueError("source_bank_account_id is required when source_type is bank_account")
        return self


# Response for both POST /retirement-accounts/{id}/contribute and
# GET /retirement-accounts/limits: the account's contribution limits given the owning
# user's age/income/filing status, how much of that limit has already been used this
# year, and (for employer-sponsored accounts) the resulting employer match.
class ContributionLimitInfo(BaseModel):
    account_id: str | None = None
    account_type: RetirementAccountType
    employee_limit: Decimal
    total_limit: Decimal | None = None
    catch_up_eligible: bool
    catch_up_amount: Decimal
    contribution_ytd: Decimal
    remaining_contribution: Decimal
    employer_match_this_contribution: Decimal | None = None
    # Populated only for Roth IRA / Traditional IRA, where the plan's own income/coverage
    # rules can zero out or shrink the otherwise-applicable limit.
    eligible: bool = True
    eligibility_note: str | None = None
    # The Transaction row this contribution posted (see models/transactions.py) - null only
    # when this response is returned from GET /retirement-accounts/limits, which doesn't
    # post anything.
    transaction_id: str | None = None


# One row of a retirement account's growth simulation.
class RetirementProjectionPoint(BaseModel):
    month: int
    date: date
    balance: Decimal
    employee_contributions: Decimal
    employer_contributions: Decimal
    growth: Decimal


# Full response for POST /retirement-accounts/{id}/simulate.
class RetirementSimulationResponse(BaseModel):
    account_id: str
    projections: list[RetirementProjectionPoint]
    final_balance: Decimal
    total_employee_contributions: Decimal
    total_employer_contributions: Decimal
    total_growth: Decimal


# Request body for POST /retirement-accounts/{id}/simulate. monthly_employee_contribution
# is an extra hypothetical monthly amount on top of whatever the account's own active
# recurring contributions already add (include_recurring=True, the default) - useful for
# "what if I contributed $200/month more than my scheduled amount" without having to edit
# or create a recurring contribution just to test the scenario.
class RetirementSimulationRequest(BaseModel):
    months: int = Field(..., ge=1, le=600)
    monthly_employee_contribution: Decimal = Field(Decimal("0"), ge=0)
    include_recurring: bool = True


# Fields shared by both the create request and the read response for a recurring
# contribution.
class RecurringContributionBase(BaseModel):
    amount: Decimal = Field(..., gt=0)
    frequency: ContributionFrequency
    start_date: date
    end_date: date | None = None


# Payload for POST /retirement-accounts/{id}/recurring-contributions.
class RecurringContributionCreate(RecurringContributionBase):
    pass


# Payload for PUT on a recurring contribution; all fields optional for partial updates.
class RecurringContributionUpdate(BaseModel):
    amount: Decimal | None = Field(None, gt=0)
    frequency: ContributionFrequency | None = None
    end_date: date | None = None
    is_active: bool | None = None


# Shape returned for a single recurring contribution.
class RecurringContributionResponse(RecurringContributionBase):
    id: str
    retirement_account_id: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
