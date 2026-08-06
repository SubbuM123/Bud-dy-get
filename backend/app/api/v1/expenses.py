"""CRUD and summary endpoints for the Expenses resource (Expense Tracker module).

Every route scopes its query to the authenticated user via `_get_owned_expense`, matching
every other module's ownership-scoping pattern in this app. `/expenses/summary` is
registered before `/{expense_id}` so the literal path segment "summary" is never captured
as a path parameter - the same static-route-before-dynamic-route ordering
api/v1/retirement_accounts.py's `/limits` and api/v1/education_accounts.py's
`/gift-tax-info` already need.
"""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.core.dependencies import DBSession, CurrentUser
from app.models.bank_accounts import BankAccount
from app.models.expenses import Expense
from app.models.expense_categories import ExpenseCategory
from app.schemas.expenses import (
    ExpenseCreate,
    ExpenseUpdate,
    ExpenseResponse,
    ExpenseSummaryResponse,
    ExpenseCategorySummary,
)

router = APIRouter()


async def _get_owned_expense(db: DBSession, expense_id: str, user_id: str) -> Expense:
    """Fetch an expense by id, scoped to `user_id`; raise 404 if missing or not owned."""
    result = await db.execute(
        select(Expense).where(Expense.id == expense_id, Expense.user_id == user_id)
    )
    expense = result.scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    return expense


# Confirm an optional category_id/bank_account_id actually exists and is owned by
# `user_id` before it's written onto an Expense row - without this, a bad or foreign id
# would only surface as a raw foreign-key-violation 500 at commit time (neither column has
# application-level ownership scoping the way _get_owned_expense gives the row itself).
# Both are no-ops when `value` is None, matching schemas/expenses.py's
# _normalize_empty_ids which already turns a stray '' into None before this ever runs.
async def _validate_category_id(db: DBSession, category_id: str | None, user_id: str) -> None:
    if category_id is None:
        return
    result = await db.execute(
        select(ExpenseCategory).where(
            ExpenseCategory.id == category_id, ExpenseCategory.user_id == user_id
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Category not found")


async def _validate_bank_account_id(db: DBSession, bank_account_id: str | None, user_id: str) -> None:
    if bank_account_id is None:
        return
    result = await db.execute(
        select(BankAccount).where(BankAccount.id == bank_account_id, BankAccount.user_id == user_id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Bank account not found")


# Default a summary/list query with no explicit range to the current calendar month, the
# same "if you don't say otherwise, assume this month" default most personal finance
# tools use for their headline spending figure.
def _default_month_range(today: date | None = None) -> tuple[date, date]:
    today = today or date.today()
    start = today.replace(day=1)
    if today.month == 12:
        end = today.replace(year=today.year + 1, month=1, day=1)
    else:
        end = today.replace(month=today.month + 1, day=1)
    return start, end


# List the authenticated user's expenses, optionally filtered by category and/or date
# range - powers ExpensesPage's filterable list. Paginated since this list only grows over
# the account's lifetime (every logged expense adds a row), unlike the small, roughly-
# static category list.
@router.get("", response_model=list[ExpenseResponse])
async def list_expenses(
    current_user: CurrentUser,
    db: DBSession,
    category_id: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    query = select(Expense).where(Expense.user_id == current_user.id)
    if category_id is not None:
        query = query.where(Expense.category_id == category_id)
    if start_date is not None:
        query = query.where(Expense.expense_date >= start_date)
    if end_date is not None:
        query = query.where(Expense.expense_date <= end_date)
    query = query.order_by(Expense.expense_date.desc()).limit(limit).offset(offset)

    result = await db.execute(query)
    return result.scalars().all()


# Create a manual expense (no receipt behind it). Creating one *from* a receipt instead
# goes through POST /receipts/{id}/create-expense - see api/v1/receipts.py.
@router.post("", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
async def create_expense(expense_data: ExpenseCreate, current_user: CurrentUser, db: DBSession):
    await _validate_category_id(db, expense_data.category_id, current_user.id)
    await _validate_bank_account_id(db, expense_data.bank_account_id, current_user.id)

    expense = Expense(user_id=current_user.id, **expense_data.model_dump())
    db.add(expense)
    await db.commit()
    await db.refresh(expense)
    return expense


# Spending summary for a date range (defaults to the current calendar month), broken down
# by category - powers SpendingPieChart and the expenses list's header stat.
@router.get("/summary", response_model=ExpenseSummaryResponse)
async def get_expense_summary(
    current_user: CurrentUser,
    db: DBSession,
    start_date: date | None = None,
    end_date: date | None = None,
):
    if start_date is None or end_date is None:
        default_start, default_end = _default_month_range()
        start_date = start_date or default_start
        end_date = end_date or default_end

    result = await db.execute(
        select(Expense).where(
            Expense.user_id == current_user.id,
            Expense.expense_date >= start_date,
            Expense.expense_date < end_date,
        )
    )
    expenses = result.scalars().all()

    category_ids = {e.category_id for e in expenses if e.category_id is not None}
    categories_by_id: dict[str, ExpenseCategory] = {}
    if category_ids:
        categories_result = await db.execute(
            select(ExpenseCategory).where(ExpenseCategory.id.in_(category_ids))
        )
        categories_by_id = {c.id: c for c in categories_result.scalars().all()}

    # Aggregate in Python (matches api/v1/dashboard.py's approach) rather than a SQL GROUP
    # BY - simpler to reason about here since it also needs the "no category assigned"
    # bucket, which isn't a real row to LEFT JOIN against.
    totals_by_category: dict[str | None, Decimal] = {}
    counts_by_category: dict[str | None, int] = {}
    for expense in expenses:
        totals_by_category[expense.category_id] = (
            totals_by_category.get(expense.category_id, Decimal("0")) + expense.amount
        )
        counts_by_category[expense.category_id] = counts_by_category.get(expense.category_id, 0) + 1

    by_category = []
    for cat_id, total in sorted(totals_by_category.items(), key=lambda kv: kv[1], reverse=True):
        category = categories_by_id.get(cat_id) if cat_id else None
        by_category.append(
            ExpenseCategorySummary(
                category_id=cat_id,
                category_name=category.name if category else "Uncategorized",
                category_color=category.color if category else None,
                total_amount=total,
                expense_count=counts_by_category[cat_id],
            )
        )

    return ExpenseSummaryResponse(
        start_date=start_date,
        end_date=end_date,
        total_amount=sum((e.amount for e in expenses), Decimal("0")),
        expense_count=len(expenses),
        by_category=by_category,
    )


# Fetch a single expense.
@router.get("/{expense_id}", response_model=ExpenseResponse)
async def get_expense(expense_id: str, current_user: CurrentUser, db: DBSession):
    return await _get_owned_expense(db, expense_id, current_user.id)


# Patch an expense with whichever fields were supplied.
@router.put("/{expense_id}", response_model=ExpenseResponse)
async def update_expense(
    expense_id: str, expense_data: ExpenseUpdate, current_user: CurrentUser, db: DBSession
):
    expense = await _get_owned_expense(db, expense_id, current_user.id)

    update_data = expense_data.model_dump(exclude_unset=True)
    if "category_id" in update_data:
        await _validate_category_id(db, update_data["category_id"], current_user.id)
    if "bank_account_id" in update_data:
        await _validate_bank_account_id(db, update_data["bank_account_id"], current_user.id)
    for field, value in update_data.items():
        setattr(expense, field, value)

    await db.commit()
    await db.refresh(expense)
    return expense


# Delete an expense. If it was created from a receipt, the receipt itself is untouched.
@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(expense_id: str, current_user: CurrentUser, db: DBSession):
    expense = await _get_owned_expense(db, expense_id, current_user.id)
    await db.delete(expense)
    await db.commit()
