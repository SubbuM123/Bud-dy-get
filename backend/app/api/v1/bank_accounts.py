"""CRUD and simulation endpoints for the Bank Account Simulator module.

This router covers three related resources: bank accounts themselves
(savings/checking/CD), the recurring deposit/withdrawal rules attached to an
account, and the on-demand growth simulation endpoint that drives the
frontend's GrowthChart. Every route scopes its query to the authenticated
user via `_get_owned_account` / `_get_owned_recurring_action` below, which
ensures one user can never read or mutate another user's accounts even if
they guess a valid UUID.
"""

from collections import defaultdict

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from decimal import Decimal

from app.core.dependencies import DBSession, CurrentUser
from app.models.bank_accounts import BankAccount, RecurringAction, ActionType
from app.models.income import Income
from app.models.expenses import Expense
from app.models.enums import AllocationDestinationType, FrequencyUnit
from app.services.income_allocator import build_allocation_stubs, IncomeAllocationStub
from app.schemas.bank_accounts import (
    BankAccountCreate,
    BankAccountUpdate,
    BankAccountResponse,
    RecurringActionCreate,
    RecurringActionUpdate,
    RecurringActionResponse,
    SimulationRequest,
    SimulationResponse,
    ProjectionPoint,
    CombinedSimulationResponse,
    AccountProjectionSeries,
    CombinedTotalPoint,
)
from app.services.bank_simulator import BankSimulatorService
from app.services.combined_simulator import CombinedSimulatorService

router = APIRouter()


async def _get_owned_account(db: DBSession, account_id: str, user_id: str) -> BankAccount:
    """Fetch a bank account by id, scoped to `user_id`; raise 404 if missing or not owned."""
    result = await db.execute(
        select(BankAccount).where(
            BankAccount.id == account_id,
            BankAccount.user_id == user_id,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


async def _get_owned_recurring_action(
    db: DBSession, action_id: str, user_id: str
) -> RecurringAction:
    """Fetch a recurring action by id, scoped to `user_id` via its parent account's owner."""
    result = await db.execute(
        select(RecurringAction)
        .join(BankAccount)
        .where(
            RecurringAction.id == action_id,
            BankAccount.user_id == user_id,
        )
    )
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Recurring action not found")
    return action


# Every active recurring income's bank-account-destination allocations, as monthly-
# equivalent deposit stubs keyed by bank_account_id - folded into simulate_growth's and
# simulate_combined_growth's recurring lists below so a salary split (see
# models/income.py) shows up in bank projections alongside RecurringAction rows, without
# BankSimulatorService needing to know Income exists. See services/income_allocator.py.
async def _bank_allocation_stubs(db: DBSession, user_id: str) -> dict[str, list]:
    result = await db.execute(
        select(Income)
        .options(selectinload(Income.allocations))
        .where(Income.user_id == user_id, Income.is_active == True, Income.is_recurring == True)
    )
    stubs_by_destination = build_allocation_stubs(result.scalars().all())
    return {
        destination_id: stubs
        for (destination_type, destination_id), stubs in stubs_by_destination.items()
        if destination_type == AllocationDestinationType.BANK_ACCOUNT
    }


# A recurring Expense's freeform recurrence_pattern (see models/expenses.py) mapped onto
# a (frequency_value, frequency_unit) pair BankSimulatorService already knows how to fold
# into a monthly-equivalent amount - see that service's _get_monthly_recurring_amount.
# Unrecognized/missing patterns default to monthly, the most common case, rather than
# silently dropping the expense from projections entirely.
_RECURRENCE_PATTERN_TO_FREQUENCY = {
    "weekly": (1, FrequencyUnit.WEEKS),
    "biweekly": (2, FrequencyUnit.WEEKS),
    "monthly": (1, FrequencyUnit.MONTHS),
    "yearly": (12, FrequencyUnit.MONTHS),
}


# Every recurring Expense linked to one of this user's bank accounts, as a
# RecurringAction-shaped WITHDRAWAL stub keyed by bank_account_id - folds "monthly
# averages" of a user's ongoing spending (rent, subscriptions) into that account's
# projection, mirroring how a recurring income allocation folds in as a deposit (see
# `_bank_allocation_stubs` above). Expenses with no bank_account_id (the common case,
# since that link is optional - see models/expenses.py) simply aren't projectable against
# any particular account and are skipped here.
async def _bank_recurring_expense_stubs(db: DBSession, user_id: str) -> dict[str, list]:
    result = await db.execute(
        select(Expense).where(
            Expense.user_id == user_id,
            Expense.is_recurring == True,
            Expense.bank_account_id.isnot(None),
        )
    )
    stubs: dict[str, list] = defaultdict(list)
    for expense in result.scalars().all():
        frequency_value, frequency_unit = _RECURRENCE_PATTERN_TO_FREQUENCY.get(
            (expense.recurrence_pattern or "").lower(), (1, FrequencyUnit.MONTHS)
        )
        stubs[expense.bank_account_id].append(
            IncomeAllocationStub(
                amount=expense.amount,
                action_type=ActionType.WITHDRAWAL,
                frequency_value=frequency_value,
                frequency_unit=frequency_unit,
            )
        )
    return stubs


# List every bank account belonging to the authenticated user.
@router.get("", response_model=list[BankAccountResponse])
async def list_bank_accounts(current_user: CurrentUser, db: DBSession):
    result = await db.execute(
        select(BankAccount).where(BankAccount.user_id == current_user.id)
    )
    return result.scalars().all()


# Create a new bank account, seeding current_balance from the given principal.
@router.post("", response_model=BankAccountResponse, status_code=status.HTTP_201_CREATED)
async def create_bank_account(
    account_data: BankAccountCreate,
    current_user: CurrentUser,
    db: DBSession,
):
    account = BankAccount(
        user_id=current_user.id,
        account_name=account_data.account_name,
        account_type=account_data.account_type,
        principal=account_data.principal,
        current_balance=account_data.principal,
        interest_rate=account_data.interest_rate,
        compounding_frequency=account_data.compounding_frequency,
        cd_start_date=account_data.cd_start_date,
        cd_term_months=account_data.cd_term_months,
        cd_auto_renew=account_data.cd_auto_renew,
        is_simulation=account_data.is_simulation,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


# Run a combined growth projection across every account the user owns, applying CD
# maturity rules (roll into a new CD term, or deposit into a savings account - the
# user's own if they have one, otherwise one synthesized for this simulation only; see
# services/combined_simulator.py). Declared before /{account_id} so "simulate-combined"
# is never captured as a path parameter.
@router.post("/simulate-combined", response_model=CombinedSimulationResponse)
async def simulate_combined_growth(
    simulation: SimulationRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    account_filters = [BankAccount.user_id == current_user.id]
    if simulation.account_ids is not None:
        account_filters.append(BankAccount.id.in_(simulation.account_ids))

    accounts_result = await db.execute(
        select(BankAccount).where(*account_filters).order_by(BankAccount.created_at)
    )
    accounts = accounts_result.scalars().all()

    recurring_by_account_id: dict[str, list[RecurringAction]] = {a.id: [] for a in accounts}
    if simulation.include_recurring and accounts:
        actions_result = await db.execute(
            select(RecurringAction).where(
                RecurringAction.bank_account_id.in_([a.id for a in accounts]),
                RecurringAction.is_active == True,
            )
        )
        for action in actions_result.scalars().all():
            recurring_by_account_id[action.bank_account_id].append(action)

        allocation_stubs = await _bank_allocation_stubs(db, current_user.id)
        expense_stubs = await _bank_recurring_expense_stubs(db, current_user.id)
        for account in accounts:
            recurring_by_account_id[account.id].extend(allocation_stubs.get(account.id, []))
            recurring_by_account_id[account.id].extend(expense_stubs.get(account.id, []))

    simulator = CombinedSimulatorService()
    result = simulator.generate_combined_projection(
        accounts=accounts,
        recurring_by_account_id=recurring_by_account_id,
        months=simulation.months,
        include_recurring=simulation.include_recurring,
    )

    return CombinedSimulationResponse(
        accounts=[
            AccountProjectionSeries(
                account_id=series.account_id,
                account_name=series.account_name,
                account_type=series.account_type,
                compounding_frequency=series.compounding_frequency,
                is_virtual=series.is_virtual,
                is_continuation=series.is_continuation,
                projections=[
                    ProjectionPoint(
                        month=p.month,
                        date=p.date,
                        balance=p.balance,
                        principal=p.principal,
                        interest_earned=p.interest_earned,
                        deposits=p.deposits,
                        withdrawals=p.withdrawals,
                    )
                    for p in series.projections
                ],
            )
            for series in result.accounts
        ],
        total_projections=[
            CombinedTotalPoint(
                month=point["month"], date=point["date"], total_balance=point["total_balance"]
            )
            for point in result.total_projections
        ],
        final_total_balance=result.final_total_balance,
    )


# Fetch a single bank account owned by the authenticated user.
@router.get("/{account_id}", response_model=BankAccountResponse)
async def get_bank_account(
    account_id: str,
    current_user: CurrentUser,
    db: DBSession,
):
    return await _get_owned_account(db, account_id, current_user.id)


# Patch a bank account with whichever fields were supplied.
@router.put("/{account_id}", response_model=BankAccountResponse)
async def update_bank_account(
    account_id: str,
    account_data: BankAccountUpdate,
    current_user: CurrentUser,
    db: DBSession,
):
    account = await _get_owned_account(db, account_id, current_user.id)

    update_data = account_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(account, field, value)

    await db.commit()
    await db.refresh(account)
    return account


# Delete a bank account; cascades to its recurring actions and transaction history.
@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bank_account(
    account_id: str,
    current_user: CurrentUser,
    db: DBSession,
):
    account = await _get_owned_account(db, account_id, current_user.id)

    await db.delete(account)
    await db.commit()


# Run a growth projection for an account over N months, optionally applying recurring actions.
@router.post("/{account_id}/simulate", response_model=SimulationResponse)
async def simulate_growth(
    account_id: str,
    simulation: SimulationRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    account = await _get_owned_account(db, account_id, current_user.id)

    recurring_actions = []
    if simulation.include_recurring:
        actions_result = await db.execute(
            select(RecurringAction).where(
                RecurringAction.bank_account_id == account_id,
                RecurringAction.is_active == True,
            )
        )
        recurring_actions = list(actions_result.scalars().all())

        allocation_stubs = await _bank_allocation_stubs(db, current_user.id)
        expense_stubs = await _bank_recurring_expense_stubs(db, current_user.id)
        recurring_actions.extend(allocation_stubs.get(account_id, []))
        recurring_actions.extend(expense_stubs.get(account_id, []))

    simulator = BankSimulatorService()
    projections = simulator.generate_projection(
        account=account,
        months=simulation.months,
        recurring_actions=recurring_actions,
    )

    final = projections[-1] if projections else None

    return SimulationResponse(
        account_id=account_id,
        projections=[
            ProjectionPoint(
                month=p.month,
                date=p.date,
                balance=p.balance,
                principal=p.principal,
                interest_earned=p.interest_earned,
                deposits=p.deposits,
                withdrawals=p.withdrawals,
            )
            for p in projections
        ],
        final_balance=final.balance if final else account.current_balance,
        total_interest=final.interest_earned if final else Decimal("0"),
        total_deposits=final.deposits if final else Decimal("0"),
        total_withdrawals=final.withdrawals if final else Decimal("0"),
    )


# List the recurring deposit/withdrawal rules attached to an account.
@router.get("/{account_id}/recurring-actions", response_model=list[RecurringActionResponse])
async def list_recurring_actions(
    account_id: str,
    current_user: CurrentUser,
    db: DBSession,
):
    await _get_owned_account(db, account_id, current_user.id)

    result = await db.execute(
        select(RecurringAction).where(RecurringAction.bank_account_id == account_id)
    )
    return result.scalars().all()


# Add a new recurring deposit/withdrawal rule to an account.
@router.post(
    "/{account_id}/recurring-actions",
    response_model=RecurringActionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_recurring_action(
    account_id: str,
    action_data: RecurringActionCreate,
    current_user: CurrentUser,
    db: DBSession,
):
    await _get_owned_account(db, account_id, current_user.id)

    action = RecurringAction(
        bank_account_id=account_id,
        action_type=action_data.action_type,
        amount=action_data.amount,
        description=action_data.description,
        category=action_data.category,
        frequency_value=action_data.frequency_value,
        frequency_unit=action_data.frequency_unit,
        start_date=action_data.start_date,
        end_date=action_data.end_date,
        next_execution_date=action_data.start_date,
    )
    db.add(action)
    await db.commit()
    await db.refresh(action)
    return action


# Patch a recurring action with whichever fields were supplied.
@router.put("/recurring-actions/{action_id}", response_model=RecurringActionResponse)
async def update_recurring_action(
    action_id: str,
    action_data: RecurringActionUpdate,
    current_user: CurrentUser,
    db: DBSession,
):
    action = await _get_owned_recurring_action(db, action_id, current_user.id)

    update_data = action_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(action, field, value)

    await db.commit()
    await db.refresh(action)
    return action


# Delete a recurring action; the account itself and its history are unaffected.
@router.delete("/recurring-actions/{action_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recurring_action(
    action_id: str,
    current_user: CurrentUser,
    db: DBSession,
):
    action = await _get_owned_recurring_action(db, action_id, current_user.id)

    await db.delete(action)
    await db.commit()
