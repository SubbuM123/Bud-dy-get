"""Aggregates every feature router into a single `/api/v1` mount point.

New feature modules (investments, planning) should register their router
here as they're built, following the same
`include_router(module.router, prefix=..., tags=[...])` pattern already used
for auth, users, bank accounts, retirement accounts, education accounts,
receipts, expenses, expense categories, and dashboard. main.py mounts this
single `api_router` under the `/api/v1` prefix, so individual routers only
need to know their own sub-path.
"""

from fastapi import APIRouter

from app.api.v1 import (
    auth,
    users,
    bank_accounts,
    retirement_accounts,
    education_accounts,
    receipts,
    expenses,
    expense_categories,
    dashboard,
    income,
    transactions,
    investments,
    scheduler,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(bank_accounts.router, prefix="/bank-accounts", tags=["Bank Accounts"])
api_router.include_router(
    retirement_accounts.router, prefix="/retirement-accounts", tags=["Retirement Accounts"]
)
api_router.include_router(
    education_accounts.router, prefix="/education-accounts", tags=["Education Accounts"]
)
api_router.include_router(receipts.router, prefix="/receipts", tags=["Receipts"])
api_router.include_router(expenses.router, prefix="/expenses", tags=["Expenses"])
api_router.include_router(
    expense_categories.router, prefix="/expense-categories", tags=["Expense Categories"]
)
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(income.router, prefix="/income", tags=["Income"])
api_router.include_router(transactions.router, prefix="/transactions", tags=["Transactions"])
api_router.include_router(investments.router, prefix="/investments", tags=["Investments"])
api_router.include_router(scheduler.router, prefix="/scheduler", tags=["Scheduler"])
