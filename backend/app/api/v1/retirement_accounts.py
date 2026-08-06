"""CRUD, simulation, and contribution endpoints for the Retirement Accounts module.

Follows the same shape as api/v1/bank_accounts.py: every route scopes its
query to the authenticated user via `_get_owned_account`, and the growth
simulation endpoint mirrors `/bank-accounts/{id}/simulate`. Two things are
specific to retirement accounts: `/retirement-accounts/limits`, which
surfaces the 2026 IRS contribution limit (and, for Roth/Traditional IRA,
income-based eligibility) computed by services/retirement_rules.py from the
caller's own profile fields on User; and `/retirement-accounts/{id}/contribute`,
which records a contribution and rejects it if it would exceed that limit.
Declared before `/{account_id}` so the literal path segment "limits" is
never captured as a path parameter.
"""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.dependencies import DBSession, CurrentUser
from app.models.retirement_accounts import RetirementAccount, RetirementRecurringContribution
from app.models.bank_accounts import BankAccount
from app.models.transactions import Transaction
from app.models.income import Income
from app.models.enums import RetirementAccountType, ContributionSourceType, TransactionType, AllocationDestinationType
from app.models.user import User
from app.services.income_allocator import build_allocation_stubs
from app.schemas.retirement_accounts import (
    RetirementAccountCreate,
    RetirementAccountUpdate,
    RetirementAccountResponse,
    ContributionCreate,
    ContributionLimitInfo,
    RetirementSimulationRequest,
    RetirementSimulationResponse,
    RetirementProjectionPoint,
    RecurringContributionCreate,
    RecurringContributionUpdate,
    RecurringContributionResponse,
)
from app.services.retirement_simulator import RetirementSimulatorService
from app.services.retirement_rules import get_contribution_limit_info, calculate_employer_match

router = APIRouter()

_401K_TYPES = {RetirementAccountType.TRADITIONAL_401K, RetirementAccountType.ROTH_401K}
_IRA_TYPES = {RetirementAccountType.TRADITIONAL_IRA, RetirementAccountType.ROTH_IRA}


async def _get_owned_account(db: DBSession, account_id: str, user_id: str) -> RetirementAccount:
    """Fetch a retirement account by id, scoped to `user_id`; raise 404 if missing or not owned."""
    result = await db.execute(
        select(RetirementAccount).where(
            RetirementAccount.id == account_id,
            RetirementAccount.user_id == user_id,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Retirement account not found")
    return account


async def _get_owned_recurring_contribution(
    db: DBSession, contribution_id: str, user_id: str
) -> RetirementRecurringContribution:
    """Fetch a recurring contribution by id, scoped to `user_id` via its parent account's owner."""
    result = await db.execute(
        select(RetirementRecurringContribution)
        .join(RetirementAccount)
        .where(
            RetirementRecurringContribution.id == contribution_id,
            RetirementAccount.user_id == user_id,
        )
    )
    contribution = result.scalar_one_or_none()
    if not contribution:
        raise HTTPException(status_code=404, detail="Recurring contribution not found")
    return contribution


# Every active recurring income's retirement-account-destination allocations, as
# monthly-equivalent contribution stubs keyed by retirement_account_id - see
# bank_accounts.py's identical `_bank_allocation_stubs` and services/income_allocator.py.
async def _retirement_allocation_stubs(db: DBSession, user_id: str) -> dict[str, list]:
    result = await db.execute(
        select(Income)
        .options(selectinload(Income.allocations))
        .where(Income.user_id == user_id, Income.is_active == True, Income.is_recurring == True)
    )
    stubs_by_destination = build_allocation_stubs(result.scalars().all())
    return {
        destination_id: stubs
        for (destination_type, destination_id), stubs in stubs_by_destination.items()
        if destination_type == AllocationDestinationType.RETIREMENT_ACCOUNT
    }


def _age_from_birth_date(birth_date: date | None) -> int:
    """Age in whole years as of today; defaults to 30 when the user hasn't set a birth_date,
    since contribution limits still need *some* age to compute against, and 30 falls well
    below every catch-up threshold so it never silently grants a catch-up a user hasn't
    confirmed they're eligible for."""
    if birth_date is None:
        return 30
    today = date.today()
    years = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        years -= 1
    return years


async def _ytd_contribution_for_family(db: DBSession, user_id: str, account_type: RetirementAccountType) -> Decimal:
    """Sum contribution_ytd across every account sharing a contribution limit with
    `account_type` - 401(k)/Roth 401(k) share the employee elective-deferral limit, and
    Traditional/Roth IRA share the combined IRA limit, both per real IRS rules."""
    family = _401K_TYPES if account_type in _401K_TYPES else _IRA_TYPES if account_type in _IRA_TYPES else {account_type}
    result = await db.execute(
        select(RetirementAccount).where(
            RetirementAccount.user_id == user_id,
            RetirementAccount.account_type.in_(family),
        )
    )
    accounts = result.scalars().all()
    return sum((a.contribution_ytd for a in accounts), Decimal("0"))


def _limit_info_for_user(
    account_type: RetirementAccountType, current_user: User, contribution_ytd: Decimal
) -> dict:
    age = _age_from_birth_date(current_user.birth_date)
    return get_contribution_limit_info(
        account_type=account_type,
        age=age,
        contribution_ytd=contribution_ytd,
        magi=current_user.annual_income,
        filing_status=current_user.filing_status,
        has_employer_plan=current_user.has_employer_retirement_plan,
    )


# List every retirement account belonging to the authenticated user.
@router.get("", response_model=list[RetirementAccountResponse])
async def list_retirement_accounts(current_user: CurrentUser, db: DBSession):
    result = await db.execute(
        select(RetirementAccount).where(RetirementAccount.user_id == current_user.id)
    )
    return result.scalars().all()


# Create a new retirement account.
@router.post("", response_model=RetirementAccountResponse, status_code=status.HTTP_201_CREATED)
async def create_retirement_account(
    account_data: RetirementAccountCreate,
    current_user: CurrentUser,
    db: DBSession,
):
    account = RetirementAccount(
        user_id=current_user.id,
        account_name=account_data.account_name,
        account_type=account_data.account_type,
        balance=account_data.balance,
        employer_name=account_data.employer_name,
        annual_salary=account_data.annual_salary,
        employer_match_percent=account_data.employer_match_percent,
        employer_match_limit_percent=account_data.employer_match_limit_percent,
        vesting_type=account_data.vesting_type,
        vesting_years=account_data.vesting_years,
        expected_return_rate=account_data.expected_return_rate,
        is_simulation=account_data.is_simulation,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


# Get the authenticated user's contribution limits for a given account type, based on
# their profile (birth_date, filing_status, annual_income, has_employer_retirement_plan)
# and their existing accounts' YTD contributions.
@router.get("/limits", response_model=ContributionLimitInfo)
async def get_contribution_limits(
    account_type: RetirementAccountType,
    current_user: CurrentUser,
    db: DBSession,
):
    contribution_ytd = await _ytd_contribution_for_family(db, current_user.id, account_type)
    info = _limit_info_for_user(account_type, current_user, contribution_ytd)
    return ContributionLimitInfo(**info)


# Fetch a single retirement account owned by the authenticated user.
@router.get("/{account_id}", response_model=RetirementAccountResponse)
async def get_retirement_account(
    account_id: str,
    current_user: CurrentUser,
    db: DBSession,
):
    return await _get_owned_account(db, account_id, current_user.id)


# Patch a retirement account with whichever fields were supplied.
@router.put("/{account_id}", response_model=RetirementAccountResponse)
async def update_retirement_account(
    account_id: str,
    account_data: RetirementAccountUpdate,
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


# Delete a retirement account.
@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_retirement_account(
    account_id: str,
    current_user: CurrentUser,
    db: DBSession,
):
    account = await _get_owned_account(db, account_id, current_user.id)

    await db.delete(account)
    await db.commit()


# Run a growth projection for an account over N months, given a hypothetical flat monthly
# employee contribution (401(k)/Roth 401(k) accounts also earn the account's own employer
# match on that contribution - see services/retirement_simulator.py).
@router.post("/{account_id}/simulate", response_model=RetirementSimulationResponse)
async def simulate_growth(
    account_id: str,
    simulation: RetirementSimulationRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    account = await _get_owned_account(db, account_id, current_user.id)

    recurring_contributions = []
    if simulation.include_recurring:
        contributions_result = await db.execute(
            select(RetirementRecurringContribution).where(
                RetirementRecurringContribution.retirement_account_id == account_id,
                RetirementRecurringContribution.is_active == True,
            )
        )
        recurring_contributions = list(contributions_result.scalars().all())

        allocation_stubs = await _retirement_allocation_stubs(db, current_user.id)
        recurring_contributions.extend(allocation_stubs.get(account_id, []))

    simulator = RetirementSimulatorService()
    projections = simulator.generate_projection(
        account=account,
        months=simulation.months,
        monthly_employee_contribution=simulation.monthly_employee_contribution,
        recurring_contributions=recurring_contributions,
    )

    final = projections[-1] if projections else None

    return RetirementSimulationResponse(
        account_id=account_id,
        projections=[
            RetirementProjectionPoint(
                month=p.month,
                date=p.date,
                balance=p.balance,
                employee_contributions=p.employee_contributions,
                employer_contributions=p.employer_contributions,
                growth=p.growth,
            )
            for p in projections
        ],
        final_balance=final.balance if final else account.balance,
        total_employee_contributions=final.employee_contributions if final else Decimal("0"),
        total_employer_contributions=final.employer_contributions if final else Decimal("0"),
        total_growth=final.growth if final else Decimal("0"),
    )


# List the recurring contributions scheduled against an account.
@router.get(
    "/{account_id}/recurring-contributions", response_model=list[RecurringContributionResponse]
)
async def list_recurring_contributions(
    account_id: str,
    current_user: CurrentUser,
    db: DBSession,
):
    await _get_owned_account(db, account_id, current_user.id)

    result = await db.execute(
        select(RetirementRecurringContribution).where(
            RetirementRecurringContribution.retirement_account_id == account_id
        )
    )
    return result.scalars().all()


# Add a new monthly/yearly recurring contribution to an account. This only feeds
# simulations (see services/retirement_simulator.py) - it does not itself post real
# contributions over time; use POST /{account_id}/contribute for that.
@router.post(
    "/{account_id}/recurring-contributions",
    response_model=RecurringContributionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_recurring_contribution(
    account_id: str,
    contribution_data: RecurringContributionCreate,
    current_user: CurrentUser,
    db: DBSession,
):
    await _get_owned_account(db, account_id, current_user.id)

    contribution = RetirementRecurringContribution(
        retirement_account_id=account_id,
        amount=contribution_data.amount,
        frequency=contribution_data.frequency,
        start_date=contribution_data.start_date,
        end_date=contribution_data.end_date,
    )
    db.add(contribution)
    await db.commit()
    await db.refresh(contribution)
    return contribution


# Patch a recurring contribution with whichever fields were supplied.
@router.put(
    "/recurring-contributions/{contribution_id}", response_model=RecurringContributionResponse
)
async def update_recurring_contribution(
    contribution_id: str,
    contribution_data: RecurringContributionUpdate,
    current_user: CurrentUser,
    db: DBSession,
):
    contribution = await _get_owned_recurring_contribution(db, contribution_id, current_user.id)

    update_data = contribution_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(contribution, field, value)

    await db.commit()
    await db.refresh(contribution)
    return contribution


# Delete a recurring contribution; the account itself and its history are unaffected.
@router.delete("/recurring-contributions/{contribution_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recurring_contribution(
    contribution_id: str,
    current_user: CurrentUser,
    db: DBSession,
):
    contribution = await _get_owned_recurring_contribution(db, contribution_id, current_user.id)

    await db.delete(contribution)
    await db.commit()


# Record a real contribution to an account: validates it against the user's remaining
# limit for that account's contribution family, then bumps both contribution_ytd and
# balance (plus the resulting employer match, for a 401(k)/Roth 401(k) account with match
# fields configured), debits the source bank account for real if source_type is
# bank_account, and posts a Transaction row so the contribution shows up in the unified
# transaction log and can be corrected later (see api/v1/transactions.py). Returns the
# account's updated limit picture plus the posted transaction's id.
@router.post("/{account_id}/contribute", response_model=ContributionLimitInfo)
async def record_contribution(
    account_id: str,
    contribution: ContributionCreate,
    current_user: CurrentUser,
    db: DBSession,
):
    account = await _get_owned_account(db, account_id, current_user.id)

    if contribution.source_type == ContributionSourceType.BANK_ACCOUNT:
        source_result = await db.execute(
            select(BankAccount).where(
                BankAccount.id == contribution.source_bank_account_id,
                BankAccount.user_id == current_user.id,
            )
        )
        if source_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="Source bank account not found")

    existing_ytd = await _ytd_contribution_for_family(db, current_user.id, account.account_type)
    info = _limit_info_for_user(account.account_type, current_user, existing_ytd)

    limit_enforced = account.account_type in (_401K_TYPES | _IRA_TYPES)

    if limit_enforced and not info["eligible"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=info["eligibility_note"] or "Not eligible to contribute to this account type.",
        )
    if limit_enforced and contribution.amount > info["remaining_contribution"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Contribution of {contribution.amount} exceeds the remaining "
                f"{info['remaining_contribution']} available under the 2026 contribution limit."
            ),
        )

    employer_match = Decimal("0")
    if account.account_type in _401K_TYPES and account.annual_salary and account.employer_match_percent and account.employer_match_limit_percent:
        employer_match = calculate_employer_match(
            salary=account.annual_salary,
            employee_contribution=account.contribution_ytd + contribution.amount,
            match_percent=account.employer_match_percent,
            match_limit_percent=account.employer_match_limit_percent,
        ) - calculate_employer_match(
            salary=account.annual_salary,
            employee_contribution=account.contribution_ytd,
            match_percent=account.employer_match_percent,
            match_limit_percent=account.employer_match_limit_percent,
        )

    account.contribution_ytd += contribution.amount
    account.balance += contribution.amount + employer_match

    # Only the employee's own contribution is reversible via the transaction log - see
    # services/transaction_effects.py's docstring for why employer match is excluded.
    transaction = Transaction(
        user_id=current_user.id,
        transaction_type=TransactionType.RETIREMENT_CONTRIBUTION,
        amount=contribution.amount,
        transaction_date=date.today(),
        account_type=AllocationDestinationType.RETIREMENT_ACCOUNT,
        account_id=account.id,
        source_type=contribution.source_type,
        source_bank_account_id=contribution.source_bank_account_id,
    )
    db.add(transaction)

    if contribution.source_type == ContributionSourceType.BANK_ACCOUNT:
        source_account = await db.get(BankAccount, contribution.source_bank_account_id)
        source_account.current_balance -= contribution.amount

    await db.commit()
    await db.refresh(account)
    await db.refresh(transaction)

    new_ytd = await _ytd_contribution_for_family(db, current_user.id, account.account_type)
    updated_info = _limit_info_for_user(account.account_type, current_user, new_ytd)
    return ContributionLimitInfo(
        account_id=account.id,
        employer_match_this_contribution=employer_match,
        transaction_id=transaction.id,
        **updated_info,
    )
