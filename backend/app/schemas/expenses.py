"""Pydantic request/response schemas for the Expenses API.

These classes define the exact shape of JSON accepted and returned by the
/expenses endpoints in api/v1/expenses.py, independent of the SQLAlchemy
model in models/expenses.py - the same separation used by every other
module's schemas.
"""

from pydantic import BaseModel, Field, field_validator
from datetime import datetime, date
from decimal import Decimal


# A stray '' for an optional foreign-key-ish string field (most often a frontend <select>
# whose "none selected" option uses '' as its sentinel value, rather than omitting the
# field or sending null) is normalized to None here rather than left to fail later trying
# to look up / insert a non-existent id - see api/v1/expenses.py's `_validate_category_id`/
# `_validate_bank_account_id`, which would otherwise 404 on a literal '' instead of just
# treating it as "not provided."
def _empty_str_to_none(value: str | None) -> str | None:
    return value if value else None


# Fields shared by both the create request and the read response for an expense.
class ExpenseBase(BaseModel):
    merchant_name: str = Field(..., max_length=255)
    amount: Decimal = Field(..., gt=0)
    expense_date: date
    category_id: str | None = None
    bank_account_id: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    is_recurring: bool = False
    recurrence_pattern: str | None = Field(None, max_length=50)

    @field_validator("category_id", "bank_account_id", mode="before")
    @classmethod
    def _normalize_empty_ids(cls, value: str | None) -> str | None:
        return _empty_str_to_none(value)


# Payload for POST /expenses - a manual entry with no receipt behind it. Creating an
# expense *from* a receipt instead goes through POST /receipts/{id}/create-expense (see
# schemas/receipts.py:CreateExpenseFromReceiptRequest), which pre-fills merchant_name/
# amount/expense_date from the receipt's own fields rather than requiring the caller to
# repeat them here.
class ExpenseCreate(ExpenseBase):
    pass


# Payload for PUT /expenses/{id}; every field is optional so callers can patch a subset.
class ExpenseUpdate(BaseModel):
    merchant_name: str | None = Field(None, max_length=255)
    amount: Decimal | None = Field(None, gt=0)
    expense_date: date | None = None
    category_id: str | None = None
    bank_account_id: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    is_recurring: bool | None = None
    recurrence_pattern: str | None = Field(None, max_length=50)

    @field_validator("category_id", "bank_account_id", mode="before")
    @classmethod
    def _normalize_empty_ids(cls, value: str | None) -> str | None:
        return _empty_str_to_none(value)


# Shape returned for a single expense, built from the ORM object via from_attributes.
class ExpenseResponse(ExpenseBase):
    id: str
    user_id: str
    receipt_id: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# One category's slice of a spending summary - see ExpenseSummaryResponse below.
class ExpenseCategorySummary(BaseModel):
    category_id: str | None  # None groups every expense with no category assigned
    category_name: str
    category_color: str | None
    total_amount: Decimal
    expense_count: int


# Full response for GET /expenses/summary - powers SpendingPieChart (by_category) and the
# expenses list's header stat. start_date/end_date echo back the resolved query window
# (defaults applied server-side, e.g. "this calendar month") so the frontend always knows
# exactly what range a given total covers.
class ExpenseSummaryResponse(BaseModel):
    start_date: date
    end_date: date
    total_amount: Decimal
    expense_count: int
    by_category: list[ExpenseCategorySummary]
