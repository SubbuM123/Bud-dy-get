"""User profile endpoints.

Exposes read and update endpoints for the authenticated caller's own
profile. Registration and login live in auth.py instead, since they don't
require an existing authenticated session; this router is for actions a
user takes on their own account after logging in. The PUT endpoint was
added in Phase 4 so a user can set the birth_date/filing_status/
annual_income/has_employer_retirement_plan fields that
services/retirement_rules.py needs to compute contribution limits.
"""

from fastapi import APIRouter

from app.core.dependencies import CurrentUser, DBSession
from app.schemas.user import UserResponse, UserUpdate

router = APIRouter()


# Return the profile of whichever user the bearer token belongs to.
@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: CurrentUser):
    return current_user


# Patch the current user's profile with whichever fields were supplied.
@router.put("/me", response_model=UserResponse)
async def update_current_user_info(
    user_data: UserUpdate,
    current_user: CurrentUser,
    db: DBSession,
):
    update_data = user_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)

    await db.commit()
    await db.refresh(current_user)
    return current_user
