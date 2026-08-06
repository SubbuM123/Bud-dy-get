"""Pydantic request/response schemas for the Transactions API.

These classes define the exact shape of JSON accepted and returned by the /transactions
endpoints in api/v1/transactions.py, independent of the SQLAlchemy model in
models/transactions.py - the same separation used by every other module's schemas. Unlike
most modules, there's no TransactionCreate here: every Transaction row is created as a
side effect of another endpoint (POST /income/{id}/log, or the retirement/education
`/contribute` endpoints), never directly - see models/transactions.py's docstring for why.
"""

from pydantic import BaseModel, Field
from datetime import datetime, date
from decimal import Decimal

from app.models.enums import TransactionType, AllocationDestinationType, ContributionSourceType


# Shape returned for a single transaction, built from the ORM object via from_attributes.
class TransactionResponse(BaseModel):
    id: str
    user_id: str
    transaction_type: TransactionType
    amount: Decimal
    transaction_date: date
    description: str | None
    account_type: AllocationDestinationType | None
    account_id: str | None
    income_id: str | None
    source_type: ContributionSourceType | None
    source_bank_account_id: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Payload for PUT /transactions/{id} - correcting a mis-entered amount/date/description
# after the fact. account_type/account_id/income_id/source_* are deliberately not
# editable here: retargeting which account(s) a posted transaction affects would require
# reversing the *old* target and applying to a *new* one in the same request, which is a
# lot of risk for a rare need - deleting the wrong-target transaction and logging/
# recording a new one covers that case instead. See api/v1/transactions.py's
# `update_transaction` for how an amount change is applied as a delta to the affected
# account(s), not a full re-apply.
class TransactionUpdate(BaseModel):
    amount: Decimal | None = Field(None, gt=0)
    transaction_date: date | None = None
    description: str | None = None
