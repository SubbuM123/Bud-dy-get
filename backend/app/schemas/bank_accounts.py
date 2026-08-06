"""Pydantic request/response schemas for the Bank Account Simulator API.

These classes define the exact shape of JSON accepted and returned by the
/bank-accounts endpoints in api/v1/bank_accounts.py, independent of the
SQLAlchemy models in models/bank_accounts.py. Keeping schemas separate from
ORM models lets us validate incoming data (e.g. reject a negative principal)
and shape outgoing data (e.g. hide internal fields) without touching the
database layer. The account_type/compounding_frequency/etc. enums are
imported from models.enums rather than redefined here, so the API layer and
the database layer can never drift out of sync on allowed values.
"""

from pydantic import BaseModel, Field
from datetime import datetime, date
from decimal import Decimal

from app.models.enums import (
    AccountType,
    CompoundingFrequency,
    ActionType,
    FrequencyUnit,
    ActionCategory,
)


# Fields shared by both the create request and the read response for an account.
class BankAccountBase(BaseModel):
    account_name: str = Field(..., max_length=255)
    account_type: AccountType
    principal: Decimal = Field(..., ge=0)
    interest_rate: Decimal | None = Field(None, ge=0, le=1)
    compounding_frequency: CompoundingFrequency = CompoundingFrequency.MONTHLY
    # Only meaningful for account_type == cd: when the CD's current term began and how
    # long it runs, in months - an explicit pair rather than a maturity date so the
    # renewal term used by services/combined_simulator.py is never re-derived from
    # unrelated data (see models/bank_accounts.py's BankAccount docstring comment).
    cd_start_date: date | None = None
    cd_term_months: int | None = Field(None, ge=1, le=600)
    # Only meaningful for account_type == cd: roll into a new CD term at maturity
    # instead of depositing into savings. See services/combined_simulator.py.
    cd_auto_renew: bool = False
    is_simulation: bool = True


# Payload for POST /bank-accounts.
class BankAccountCreate(BankAccountBase):
    pass


# Payload for PUT /bank-accounts/{id}; every field is optional so callers can patch a subset.
class BankAccountUpdate(BaseModel):
    account_name: str | None = Field(None, max_length=255)
    principal: Decimal | None = Field(None, ge=0)
    interest_rate: Decimal | None = Field(None, ge=0, le=1)
    compounding_frequency: CompoundingFrequency | None = None
    cd_start_date: date | None = None
    cd_term_months: int | None = Field(None, ge=1, le=600)
    cd_auto_renew: bool | None = None


# Shape returned for a single bank account, built from the ORM object via from_attributes.
class BankAccountResponse(BankAccountBase):
    id: str
    user_id: str
    current_balance: Decimal
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Fields shared by the create request and read response for a recurring action.
class RecurringActionBase(BaseModel):
    action_type: ActionType
    amount: Decimal = Field(..., gt=0)
    description: str | None = Field(None, max_length=255)
    category: ActionCategory | None = None
    frequency_value: int = Field(..., ge=1)
    frequency_unit: FrequencyUnit
    start_date: date
    end_date: date | None = None


# Payload for POST /bank-accounts/{id}/recurring-actions.
class RecurringActionCreate(RecurringActionBase):
    pass


# Payload for PUT on a recurring action; all fields optional for partial updates.
class RecurringActionUpdate(BaseModel):
    amount: Decimal | None = Field(None, gt=0)
    description: str | None = Field(None, max_length=255)
    category: ActionCategory | None = None
    frequency_value: int | None = Field(None, ge=1)
    frequency_unit: FrequencyUnit | None = None
    end_date: date | None = None
    is_active: bool | None = None


# Shape returned for a single recurring action.
class RecurringActionResponse(RecurringActionBase):
    id: str
    bank_account_id: str
    next_execution_date: date
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Request body for POST /bank-accounts/{id}/simulate and POST /bank-accounts/simulate-combined.
# account_ids is only consulted by the combined endpoint - None means "every account the
# user owns"; an explicit (possibly empty) list restricts the combined simulation to just
# those accounts, letting the frontend re-run it with some accounts checked out.
class SimulationRequest(BaseModel):
    months: int = Field(..., ge=1, le=600)
    include_recurring: bool = True
    account_ids: list[str] | None = None


# One row of a growth simulation: the account's projected state at a given month.
class ProjectionPoint(BaseModel):
    month: int
    date: date
    balance: Decimal
    principal: Decimal
    interest_earned: Decimal
    deposits: Decimal
    withdrawals: Decimal


# Full response for a simulation run: the month-by-month series plus running totals.
class SimulationResponse(BaseModel):
    account_id: str
    projections: list[ProjectionPoint]
    final_balance: Decimal
    total_interest: Decimal
    total_deposits: Decimal
    total_withdrawals: Decimal


# One account's (or CD renewal segment's, or the synthesized savings bucket's) series
# within a combined simulation. See services/combined_simulator.py for how segments and
# the virtual bucket are produced. is_continuation is true for every CD renewal segment
# after the first - its first projection point duplicates the prior segment's last point
# (the same money, carried over at the moment of rollover), so any client that sums
# multiple series together (e.g. a "fold remaining accounts into one line" chart) must
# skip that duplicated first point per series, exactly like this module's own
# `_sum_series` does for the `total_projections` series below - a client that read
# `projections` directly without checking this flag would double-count that one month.
class AccountProjectionSeries(BaseModel):
    account_id: str
    account_name: str
    account_type: AccountType
    compounding_frequency: CompoundingFrequency
    is_virtual: bool = False
    is_continuation: bool = False
    projections: list[ProjectionPoint]


# One row of the combined (summed-across-accounts) balance series.
class CombinedTotalPoint(BaseModel):
    month: int
    date: date
    total_balance: Decimal


# Full response for POST /bank-accounts/simulate-combined.
class CombinedSimulationResponse(BaseModel):
    accounts: list[AccountProjectionSeries]
    total_projections: list[CombinedTotalPoint]
    final_total_balance: Decimal
