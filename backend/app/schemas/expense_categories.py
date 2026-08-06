"""Pydantic request/response schemas for the Expense Categories API.

These classes define the exact shape of JSON accepted and returned by the
/expense-categories endpoints in api/v1/expense_categories.py, independent of
the SQLAlchemy model in models/expense_categories.py - the same separation
used by every other module's schemas.
"""

from pydantic import BaseModel, Field
from datetime import datetime
from decimal import Decimal


# Fields shared by both the create request and the read response for a category.
class ExpenseCategoryBase(BaseModel):
    name: str = Field(..., max_length=100)
    color: str | None = Field(None, max_length=7)
    icon: str | None = Field(None, max_length=50)
    monthly_budget: Decimal | None = Field(None, ge=0)


# Payload for POST /expense-categories.
class ExpenseCategoryCreate(ExpenseCategoryBase):
    pass


# Payload for PUT /expense-categories/{id}; every field is optional so callers can patch a subset.
class ExpenseCategoryUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    color: str | None = Field(None, max_length=7)
    icon: str | None = Field(None, max_length=50)
    monthly_budget: Decimal | None = Field(None, ge=0)


# Shape returned for a single category, built from the ORM object via from_attributes.
class ExpenseCategoryResponse(ExpenseCategoryBase):
    id: str
    user_id: str
    is_system: bool
    created_at: datetime

    class Config:
        from_attributes = True
