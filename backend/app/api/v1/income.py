"""CRUD and logging endpoints for the Income module.

Income is always entered as a post-tax amount - this app doesn't model tax withholding
(no filing-status-aware paycheck calculator, no per-state rules), so asking for gross pay
and trying to compute what actually lands in the bank would just be a second source of
error on top of the first. The frontend's income form instead shows a hint: if you don't
know your post-tax number offhand, enter roughly 70% of your gross salary as a starting
estimate. `annual_income` on User (used elsewhere for retirement contribution-limit rules)
is a separate, unrelated field - this module doesn't read or write it.

Every Income is a *rule* (recurring or one-time) with a set of percentage allocations
across bank/retirement/education accounts, mirroring RecurringAction/
RetirementRecurringContribution/EducationRecurringContribution: creating one does not by
itself move any money on its own. Money actually moves - real Transaction rows posted,
real account balances bumped - in three cases: immediately, for a one-time income
(there's only ever going to be one occurrence, so there's no reason to make the user
separately "log" it); via POST /income/{id}/log, callable any time a user wants to log a
paycheck manually; or automatically, via the V2 background scheduler
(services/scheduler.py, see docs/future-plan.md) posting a recurring income's next due
occurrence on its own schedule. All three paths funnel through the same
services/income_posting.py:post_income_transactions so they can never drift apart on how
a paycheck is split into postings.

An allocation whose destination is a retirement/education account can also carry
`source_type: pre_tax_salary` (see models/income.py:IncomeAllocation and
docs/phase4.6-money-flow-plan.md's "Next Steps" §8, "Option A") - logging that occurrence
then posts a RETIREMENT_CONTRIBUTION/EDUCATION_CONTRIBUTION transaction for that
allocation's share instead of a plain INCOME one, so a payroll 401(k) deduction is
captured in the same `/log` call rather than needing a second manual `/contribute`.
Deliberately unlike a direct `/contribute` call: this path does **not** check the
destination's IRS contribution limit or compute an employer match - see
services/income_posting.py's `post_income_transactions` - keeping the "smallest change"
scope Option A was chosen for; a paycheck-driven contribution that would blow through a
limit is still recorded, just as recording it manually with `source_type: pre_tax_salary`
already was.

An allocation whose destination is a `stock_position` can carry `rsu_vesting_type` (plus
`rsu_vesting_years`/`rsu_cliff_date` as that schedule requires - see
models/income.py:IncomeAllocation and docs/phase5-plan.md §5) for an employer stock grant
(RSU): logging an occurrence calculates newly-vested shares as of that occurrence's date
and adds them to the StockPosition at that day's market price, posting an RSU_VEST
transaction instead of INCOME - the Phase 5 analog of the pre-tax-retirement case above.
"""

from datetime import date

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.dependencies import DBSession, CurrentUser
from app.models.income import Income, IncomeAllocation
from app.models.bank_accounts import BankAccount
from app.models.retirement_accounts import RetirementAccount
from app.models.education_accounts import EducationAccount
from app.models.investments import StockPosition
from app.models.enums import AllocationDestinationType
from app.schemas.income import (
    IncomeCreate,
    IncomeUpdate,
    IncomeResponse,
    IncomeAllocationsReplace,
    LogIncomeRequest,
    LogIncomeResponse,
)
from app.schemas.transactions import TransactionResponse
from app.services.income_posting import post_income_transactions

router = APIRouter()

_DESTINATION_MODELS = {
    AllocationDestinationType.BANK_ACCOUNT: BankAccount,
    AllocationDestinationType.RETIREMENT_ACCOUNT: RetirementAccount,
    AllocationDestinationType.EDUCATION_ACCOUNT: EducationAccount,
    AllocationDestinationType.STOCK_POSITION: StockPosition,
}


async def _get_owned_income(db: DBSession, income_id: str, user_id: str) -> Income:
    """Fetch an income by id, scoped to `user_id`; raise 404 if missing or not owned."""
    result = await db.execute(
        select(Income).where(Income.id == income_id, Income.user_id == user_id)
    )
    income = result.scalar_one_or_none()
    if not income:
        raise HTTPException(status_code=404, detail="Income not found")
    return income


# Confirm every allocation's destination_id actually exists and is owned by `user_id` -
# destination_id isn't a real foreign key (see models/income.py's docstring), so this is
# the only place ownership of a polymorphic destination ever gets checked.
async def _validate_destinations(db: DBSession, user_id: str, allocations) -> None:
    for allocation in allocations:
        model = _DESTINATION_MODELS[allocation.destination_type]
        result = await db.execute(
            select(model).where(model.id == allocation.destination_id, model.user_id == user_id)
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{allocation.destination_type.value} {allocation.destination_id} "
                "not found or not owned by this user.",
            )


# List every income belonging to the authenticated user. Eager-loads allocations - without
# it, IncomeResponse's `allocations` field triggers a lazy load outside an awaited call
# while FastAPI serializes the response, which AsyncSession can't do (MissingGreenlet) -
# the same class of bug fixed for GET /receipts/{id} last session (see
# api/v1/receipts.py's `_get_owned_receipt` and this repo's 2026-08-04 progress.md entry).
@router.get("", response_model=list[IncomeResponse])
async def list_incomes(current_user: CurrentUser, db: DBSession):
    result = await db.execute(
        select(Income)
        .options(selectinload(Income.allocations))
        .where(Income.user_id == current_user.id)
    )
    return result.scalars().all()


# Create a new income (recurring rule or one-time payment) with its allocations. A
# one-time income is immediately logged (see this module's docstring) so the caller never
# needs a separate POST /income/{id}/log call for it.
@router.post("", response_model=IncomeResponse, status_code=status.HTTP_201_CREATED)
async def create_income(
    income_data: IncomeCreate,
    current_user: CurrentUser,
    db: DBSession,
):
    await _validate_destinations(db, current_user.id, income_data.allocations)

    income = Income(
        user_id=current_user.id,
        name=income_data.name,
        amount=income_data.amount,
        is_recurring=income_data.is_recurring,
        frequency=income_data.frequency,
        start_date=income_data.start_date,
        income_date=income_data.income_date,
    )
    db.add(income)
    await db.flush()  # assign income.id before building allocation rows

    for allocation_data in income_data.allocations:
        db.add(
            IncomeAllocation(
                income_id=income.id,
                destination_type=allocation_data.destination_type,
                destination_id=allocation_data.destination_id,
                percentage=allocation_data.percentage,
                source_type=allocation_data.source_type,
                rsu_vesting_type=allocation_data.rsu_vesting_type,
                rsu_vesting_years=allocation_data.rsu_vesting_years,
                rsu_cliff_date=allocation_data.rsu_cliff_date,
                rsu_total_shares=allocation_data.rsu_total_shares,
            )
        )
    # Flush explicitly rather than relying on autoflush before the refresh() call inside
    # post_income_transactions below - a one-time income needs every allocation row
    # actually persisted (even mid-transaction) before it can be split and posted.
    await db.flush()

    if not income.is_recurring:
        await post_income_transactions(
            db,
            income=income,
            amount=income.amount,
            log_date=income.income_date or date.today(),
        )

    await db.commit()
    await db.refresh(income, attribute_names=["allocations"])
    return income


# Fetch a single income owned by the authenticated user.
@router.get("/{income_id}", response_model=IncomeResponse)
async def get_income(income_id: str, current_user: CurrentUser, db: DBSession):
    income = await _get_owned_income(db, income_id, current_user.id)
    await db.refresh(income, attribute_names=["allocations"])
    return income


# Patch an income's own fields (not its allocations - see PUT .../allocations below).
@router.put("/{income_id}", response_model=IncomeResponse)
async def update_income(
    income_id: str,
    income_data: IncomeUpdate,
    current_user: CurrentUser,
    db: DBSession,
):
    income = await _get_owned_income(db, income_id, current_user.id)

    update_data = income_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(income, field, value)

    await db.commit()
    await db.refresh(income, attribute_names=["allocations"])
    return income


# Replace every allocation on an income wholesale - simpler and safer than patching
# individual allocation rows, which could easily leave the set summing to something
# other than 100 (see schemas/income.py:IncomeAllocationsReplace).
@router.put("/{income_id}/allocations", response_model=IncomeResponse)
async def replace_income_allocations(
    income_id: str,
    payload: IncomeAllocationsReplace,
    current_user: CurrentUser,
    db: DBSession,
):
    income = await _get_owned_income(db, income_id, current_user.id)
    await _validate_destinations(db, current_user.id, payload.allocations)

    await db.refresh(income, attribute_names=["allocations"])
    for existing in list(income.allocations):
        await db.delete(existing)
    await db.flush()

    for allocation_data in payload.allocations:
        db.add(
            IncomeAllocation(
                income_id=income.id,
                destination_type=allocation_data.destination_type,
                destination_id=allocation_data.destination_id,
                percentage=allocation_data.percentage,
                source_type=allocation_data.source_type,
                rsu_vesting_type=allocation_data.rsu_vesting_type,
                rsu_vesting_years=allocation_data.rsu_vesting_years,
                rsu_cliff_date=allocation_data.rsu_cliff_date,
                rsu_total_shares=allocation_data.rsu_total_shares,
            )
        )

    await db.commit()
    await db.refresh(income, attribute_names=["allocations"])
    return income


# Delete an income. Past Transaction rows this income already logged are kept (income_id
# is nulled via ON DELETE SET NULL - see models/transactions.py) since they're the user's
# real posted history, not a projection tied to the rule that produced them.
@router.delete("/{income_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_income(income_id: str, current_user: CurrentUser, db: DBSession):
    income = await _get_owned_income(db, income_id, current_user.id)
    await db.delete(income)
    await db.commit()


# Log one real occurrence of a (usually recurring) income: splits the given amount
# (defaults to the income's own amount) across its allocations, posting real Transaction
# rows and bumping every destination account's real balance. Call this once per paycheck
# for a recurring income if you'd rather log it manually - the V2 background scheduler
# (services/scheduler.py) can also auto-call the shared post_income_transactions() below
# for a due recurring Income, see docs/future-plan.md.
@router.post("/{income_id}/log", response_model=LogIncomeResponse, status_code=status.HTTP_201_CREATED)
async def log_income(
    income_id: str,
    payload: LogIncomeRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    income = await _get_owned_income(db, income_id, current_user.id)

    amount = payload.amount if payload.amount is not None else income.amount
    log_date = payload.log_date or date.today()

    transactions = await post_income_transactions(db, income=income, amount=amount, log_date=log_date)

    await db.commit()
    for transaction in transactions:
        await db.refresh(transaction)

    return LogIncomeResponse(
        income_id=income.id,
        total_amount=amount,
        log_date=log_date,
        transactions=[TransactionResponse.model_validate(t) for t in transactions],
    )
