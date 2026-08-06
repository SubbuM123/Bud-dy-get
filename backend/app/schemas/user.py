"""Pydantic request/response schemas for user accounts and authentication.

These models validate the payloads for registration, login, and profile
endpoints in api/v1/auth.py and api/v1/users.py, and define the JWT token
envelope returned to clients. They are intentionally separate from the User
ORM model in models/user.py so that sensitive fields like password_hash are
never accidentally serialized into an API response. The birth_date/
filing_status/annual_income/has_employer_retirement_plan fields were added
for Phase 4 - retirement_rules.py needs them to compute catch-up
eligibility, Roth IRA income phaseouts, and Traditional IRA deductibility.
"""

from pydantic import BaseModel, EmailStr, Field
from datetime import datetime, date
from decimal import Decimal

from app.models.enums import FilingStatus


# Fields common to both the registration request and the profile response.
class UserBase(BaseModel):
    email: EmailStr
    full_name: str | None = None


# Payload for POST /auth/register; includes the plaintext password to be hashed. Capped at
# 72 characters since bcrypt (core/auth.py) silently ignores bytes past its 72-byte input
# limit - rejecting an over-long password here is clearer than a password that "works" at
# registration but only its first 72 bytes are ever actually checked.
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=72)


# Payload for PUT /users/me; all fields optional so callers can patch a subset. Profile
# fields (birth_date onward) are what retirement_rules.py reads to compute contribution
# limits - password change support is left for a later phase.
class UserUpdate(BaseModel):
    full_name: str | None = None
    birth_date: date | None = None
    filing_status: FilingStatus | None = None
    annual_income: Decimal | None = Field(None, ge=0)
    has_employer_retirement_plan: bool | None = None


# Public-facing user profile, built from the ORM object via from_attributes.
class UserResponse(UserBase):
    id: str
    is_active: bool
    birth_date: date | None = None
    filing_status: FilingStatus | None = None
    annual_income: Decimal | None = None
    has_employer_retirement_plan: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# JWT bearer token envelope returned by /auth/login and /auth/register.
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# Decoded payload extracted from a JWT during request authentication.
class TokenData(BaseModel):
    user_id: str | None = None


# Payload for POST /auth/login.
class LoginRequest(BaseModel):
    email: EmailStr
    password: str
