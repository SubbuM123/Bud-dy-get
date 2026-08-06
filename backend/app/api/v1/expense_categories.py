"""CRUD endpoints for user-defined expense categories (Expense Tracker module).

Every route scopes its query to the authenticated user via `_get_owned_category`, matching
every other module's ownership-scoping pattern in this app. There's no protection against
editing or deleting a `is_system` (starter) category here - see
models/expense_categories.py's docstring for why that flag is informational only, not an
immutability guard.
"""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.dependencies import DBSession, CurrentUser
from app.models.expense_categories import ExpenseCategory
from app.schemas.expense_categories import (
    ExpenseCategoryCreate,
    ExpenseCategoryUpdate,
    ExpenseCategoryResponse,
)

router = APIRouter()


async def _get_owned_category(db: DBSession, category_id: str, user_id: str) -> ExpenseCategory:
    """Fetch a category by id, scoped to `user_id`; raise 404 if missing or not owned."""
    result = await db.execute(
        select(ExpenseCategory).where(
            ExpenseCategory.id == category_id, ExpenseCategory.user_id == user_id
        )
    )
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


# List every category belonging to the authenticated user (the starter set seeded at
# registration, plus anything they've added themselves).
@router.get("", response_model=list[ExpenseCategoryResponse])
async def list_expense_categories(current_user: CurrentUser, db: DBSession):
    result = await db.execute(
        select(ExpenseCategory).where(ExpenseCategory.user_id == current_user.id)
    )
    return result.scalars().all()


# Create a custom category. Duplicate names for the same user are rejected at the database
# level (uq_expense_category_user_name) and surfaced here as a 400 rather than a raw 500.
@router.post("", response_model=ExpenseCategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_expense_category(
    category_data: ExpenseCategoryCreate, current_user: CurrentUser, db: DBSession
):
    existing = await db.execute(
        select(ExpenseCategory).where(
            ExpenseCategory.user_id == current_user.id,
            ExpenseCategory.name == category_data.name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have a category with this name",
        )

    category = ExpenseCategory(user_id=current_user.id, **category_data.model_dump())
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


# Patch a category with whichever fields were supplied.
@router.put("/{category_id}", response_model=ExpenseCategoryResponse)
async def update_expense_category(
    category_id: str,
    category_data: ExpenseCategoryUpdate,
    current_user: CurrentUser,
    db: DBSession,
):
    category = await _get_owned_category(db, category_id, current_user.id)

    update_data = category_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(category, field, value)

    await db.commit()
    await db.refresh(category)
    return category


# Delete a category. Expenses that referenced it keep existing with category_id set to
# NULL (ON DELETE SET NULL on expenses.category_id) rather than being deleted themselves -
# a user's spending history shouldn't disappear because they cleaned up their category list.
@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense_category(category_id: str, current_user: CurrentUser, db: DBSession):
    category = await _get_owned_category(db, category_id, current_user.id)
    await db.delete(category)
    await db.commit()
