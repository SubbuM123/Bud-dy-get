"""Pydantic request/response schemas for the Education Savings API.

These classes define the exact shape of JSON accepted and returned by the
/education-accounts endpoints in api/v1/education_accounts.py, independent
of the SQLAlchemy model in models/education_accounts.py - the same
separation used by schemas/retirement_accounts.py. The account_type enum is
imported from models.enums rather than redefined here, so the API layer and
the database layer can never drift out of sync on allowed values.
"""

from pydantic import BaseModel, Field, model_validator
from datetime import datetime, date
from decimal import Decimal

from app.models.enums import EducationAccountType, ContributionFrequency, ContributionSourceType


# Fields shared by both the create request and the read response for an education account.
class EducationAccountBase(BaseModel):
    account_name: str = Field(..., max_length=255)
    account_type: EducationAccountType = EducationAccountType.FIVE_TWENTY_NINE
    beneficiary_name: str = Field(..., max_length=255)
    beneficiary_birth_date: date | None = None
    plan_provider: str | None = Field(None, max_length=255)
    balance: Decimal = Field(..., ge=0)
    expected_return_rate: Decimal = Field(Decimal("0.07"), ge=0, le=1)
    is_simulation: bool = True


# Payload for POST /education-accounts.
class EducationAccountCreate(EducationAccountBase):
    pass


# Payload for PUT /education-accounts/{id}; every field is optional so callers can patch a subset.
class EducationAccountUpdate(BaseModel):
    account_name: str | None = Field(None, max_length=255)
    beneficiary_name: str | None = Field(None, max_length=255)
    beneficiary_birth_date: date | None = None
    plan_provider: str | None = Field(None, max_length=255)
    balance: Decimal | None = Field(None, ge=0)
    expected_return_rate: Decimal | None = Field(None, ge=0, le=1)


# Shape returned for a single education account, built from the ORM object via from_attributes.
class EducationAccountResponse(EducationAccountBase):
    id: str
    user_id: str
    contribution_ytd: Decimal
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Payload for POST /education-accounts/{id}/contribute. source_type mirrors
# retirement_accounts.py:ContributionCreate - see that schema's comment and
# models/enums.py:ContributionSourceType for what each value means and does.
class ContributionCreate(BaseModel):
    amount: Decimal = Field(..., gt=0)
    source_type: ContributionSourceType = ContributionSourceType.TRACK_ONLY
    source_bank_account_id: str | None = None

    @model_validator(mode="after")
    def _require_source_account(self) -> "ContributionCreate":
        if self.source_type == ContributionSourceType.BANK_ACCOUNT and not self.source_bank_account_id:
            raise ValueError("source_bank_account_id is required when source_type is bank_account")
        return self


# Response for both GET /education-accounts/gift-tax-info and
# POST /education-accounts/{id}/contribute: purely informational gift-tax guidance for a
# beneficiary - unlike retirement's ContributionLimitInfo, there is no `eligible` field
# and nothing here ever blocks a contribution, since 529s have no IRS contribution cap,
# only a gift-tax *reporting* threshold. See services/education_rules.py.
class GiftTaxInfo(BaseModel):
    account_id: str | None = None
    beneficiary_name: str
    annual_exclusion: Decimal
    superfunding_lump_sum: Decimal
    beneficiary_contribution_ytd: Decimal
    remaining_before_exclusion: Decimal
    would_exceed_exclusion: bool
    note: str
    # The Transaction row this contribution posted (see models/transactions.py) - null
    # when this response comes from GET /education-accounts/gift-tax-info, which doesn't
    # post anything.
    transaction_id: str | None = None


# One row of an education account's growth simulation. No employee/employer split -
# 529s aren't employer-sponsored, unlike RetirementProjectionPoint.
class EducationProjectionPoint(BaseModel):
    month: int
    date: date
    balance: Decimal
    contributions: Decimal
    growth: Decimal


# Full response for POST /education-accounts/{id}/simulate.
class EducationSimulationResponse(BaseModel):
    account_id: str
    projections: list[EducationProjectionPoint]
    final_balance: Decimal
    total_contributions: Decimal
    total_growth: Decimal


# Request body for POST /education-accounts/{id}/simulate. monthly_contribution is an
# extra hypothetical monthly amount on top of whatever the account's own active recurring
# contributions already add (include_recurring=True, the default) - mirrors
# RetirementSimulationRequest's monthly_employee_contribution semantics.
class EducationSimulationRequest(BaseModel):
    months: int = Field(..., ge=1, le=600)
    monthly_contribution: Decimal = Field(Decimal("0"), ge=0)
    include_recurring: bool = True


# Fields shared by both the create request and the read response for a recurring
# contribution.
class RecurringContributionBase(BaseModel):
    amount: Decimal = Field(..., gt=0)
    frequency: ContributionFrequency
    start_date: date
    end_date: date | None = None


# Payload for POST /education-accounts/{id}/recurring-contributions.
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
    education_account_id: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
