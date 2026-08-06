"""Cross-module summary endpoints for the top-level dashboard page.

This router aggregates data across a user's accounts rather than exposing
CRUD for a single resource. As of Phase 3 it folds bank, retirement, and
education account balances into a single "net worth" total, plus this
calendar month's total spending from the Expense Tracker module (spending
isn't a balance, so it's kept out of net worth itself, just surfaced
alongside it - see docs/phase3-plan.md); investment and planning modules
should add their totals here too as those phases are built, so the frontend
dashboard doesn't need to call every feature API separately.
"""

from datetime import date

from fastapi import APIRouter
from sqlalchemy import select

from app.core.dependencies import DBSession, CurrentUser
from app.models.bank_accounts import BankAccount
from app.models.retirement_accounts import RetirementAccount
from app.models.education_accounts import EducationAccount
from app.models.expenses import Expense

router = APIRouter()


# Roll up the current user's bank, retirement, and education accounts into headline
# dashboard figures, plus this calendar month's total spending.
@router.get("/summary")
async def get_dashboard_summary(current_user: CurrentUser, db: DBSession):
    bank_result = await db.execute(
        select(BankAccount).where(BankAccount.user_id == current_user.id)
    )
    bank_accounts = bank_result.scalars().all()

    retirement_result = await db.execute(
        select(RetirementAccount).where(RetirementAccount.user_id == current_user.id)
    )
    retirement_accounts = retirement_result.scalars().all()

    education_result = await db.execute(
        select(EducationAccount).where(EducationAccount.user_id == current_user.id)
    )
    education_accounts = education_result.scalars().all()

    today = date.today()
    month_start = today.replace(day=1)
    expense_result = await db.execute(
        select(Expense).where(
            Expense.user_id == current_user.id, Expense.expense_date >= month_start
        )
    )
    expenses_this_month = expense_result.scalars().all()

    total_bank_balance = sum(acc.current_balance for acc in bank_accounts)
    total_retirement_balance = sum(acc.balance for acc in retirement_accounts)
    total_education_balance = sum(acc.balance for acc in education_accounts)
    total_expenses_this_month = sum(e.amount for e in expenses_this_month)

    return {
        "total_bank_balance": total_bank_balance,
        "total_retirement_balance": total_retirement_balance,
        "total_education_balance": total_education_balance,
        "net_worth": total_bank_balance + total_retirement_balance + total_education_balance,
        "total_expenses_this_month": total_expenses_this_month,
        "accounts_count": len(bank_accounts),
        "accounts_by_type": {
            "savings": sum(1 for acc in bank_accounts if acc.account_type.value == "savings"),
            "checking": sum(1 for acc in bank_accounts if acc.account_type.value == "checking"),
            "cd": sum(1 for acc in bank_accounts if acc.account_type.value == "cd"),
        },
        "retirement_accounts_count": len(retirement_accounts),
        "education_accounts_count": len(education_accounts),
    }
