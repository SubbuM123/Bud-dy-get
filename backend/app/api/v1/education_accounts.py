"""CRUD, simulation, and contribution endpoints for the Education Savings module.

Follows the same shape as api/v1/retirement_accounts.py: every route scopes
its query to the authenticated user via `_get_owned_account`, and the growth
simulation endpoint mirrors `/retirement-accounts/{id}/simulate`. The key
difference from retirement accounts: `/education-accounts/gift-tax-info`
surfaces 2026 gift-tax guidance grouped by *beneficiary* rather than by
account type (see `_ytd_contribution_for_beneficiary` below - a 529 has no
IRS contribution cap shared across "family" account types the way 401(k)/IRA
limits do, only a gift-tax reporting threshold per beneficiary), and
`/education-accounts/{id}/contribute` never rejects a contribution (200
always) since there's nothing to enforce, only to inform. Declared before
`/{account_id}` so the literal path segment "gift-tax-info" is never
captured as a path parameter.
"""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.dependencies import DBSession, CurrentUser
from app.models.education_accounts import EducationAccount, EducationRecurringContribution
from app.models.bank_accounts import BankAccount
from app.models.transactions import Transaction
from app.models.income import Income
from app.models.enums import ContributionSourceType, TransactionType, AllocationDestinationType
from app.services.income_allocator import build_allocation_stubs
from app.schemas.education_accounts import (
    EducationAccountCreate,
    EducationAccountUpdate,
    EducationAccountResponse,
    ContributionCreate,
    GiftTaxInfo,
    EducationSimulationRequest,
    EducationSimulationResponse,
    EducationProjectionPoint,
    RecurringContributionCreate,
    RecurringContributionUpdate,
    RecurringContributionResponse,
)
from app.services.education_simulator import EducationSimulatorService
from app.services.education_rules import get_gift_tax_info

router = APIRouter()


async def _get_owned_account(db: DBSession, account_id: str, user_id: str) -> EducationAccount:
    """Fetch an education account by id, scoped to `user_id`; raise 404 if missing or not owned."""
    result = await db.execute(
        select(EducationAccount).where(
            EducationAccount.id == account_id,
            EducationAccount.user_id == user_id,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Education account not found")
    return account


async def _get_owned_recurring_contribution(
    db: DBSession, contribution_id: str, user_id: str
) -> EducationRecurringContribution:
    """Fetch a recurring contribution by id, scoped to `user_id` via its parent account's owner."""
    result = await db.execute(
        select(EducationRecurringContribution)
        .join(EducationAccount)
        .where(
            EducationRecurringContribution.id == contribution_id,
            EducationAccount.user_id == user_id,
        )
    )
    contribution = result.scalar_one_or_none()
    if not contribution:
        raise HTTPException(status_code=404, detail="Recurring contribution not found")
    return contribution


# Every active recurring income's education-account-destination allocations, as
# monthly-equivalent contribution stubs keyed by education_account_id - see
# bank_accounts.py's identical `_bank_allocation_stubs` and services/income_allocator.py.
async def _education_allocation_stubs(db: DBSession, user_id: str) -> dict[str, list]:
    result = await db.execute(
        select(Income)
        .options(selectinload(Income.allocations))
        .where(Income.user_id == user_id, Income.is_active == True, Income.is_recurring == True)
    )
    stubs_by_destination = build_allocation_stubs(result.scalars().all())
    return {
        destination_id: stubs
        for (destination_type, destination_id), stubs in stubs_by_destination.items()
        if destination_type == AllocationDestinationType.EDUCATION_ACCOUNT
    }


async def _ytd_contribution_for_beneficiary(
    db: DBSession, user_id: str, beneficiary_name: str
) -> Decimal:
    """Sum contribution_ytd across every education account the user owns for this same
    beneficiary - the annual gift-tax exclusion is per (giver, beneficiary), not per
    account, so a user with two kids and two 529s must see two independent exclusions."""
    result = await db.execute(
        select(EducationAccount).where(
            EducationAccount.user_id == user_id,
            EducationAccount.beneficiary_name == beneficiary_name,
        )
    )
    accounts = result.scalars().all()
    return sum((a.contribution_ytd for a in accounts), Decimal("0"))


# List every education account belonging to the authenticated user.
@router.get("", response_model=list[EducationAccountResponse])
async def list_education_accounts(current_user: CurrentUser, db: DBSession):
    result = await db.execute(
        select(EducationAccount).where(EducationAccount.user_id == current_user.id)
    )
    return result.scalars().all()


# Create a new education account.
@router.post("", response_model=EducationAccountResponse, status_code=status.HTTP_201_CREATED)
async def create_education_account(
    account_data: EducationAccountCreate,
    current_user: CurrentUser,
    db: DBSession,
):
    account = EducationAccount(
        user_id=current_user.id,
        account_name=account_data.account_name,
        account_type=account_data.account_type,
        beneficiary_name=account_data.beneficiary_name,
        beneficiary_birth_date=account_data.beneficiary_birth_date,
        plan_provider=account_data.plan_provider,
        balance=account_data.balance,
        expected_return_rate=account_data.expected_return_rate,
        is_simulation=account_data.is_simulation,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


# Get 2026 gift-tax guidance for a beneficiary - purely informational, never blocking.
# contribution_amount is optional: when given, the note reflects what would happen if that
# amount were contributed on top of the beneficiary's YTD total.
@router.get("/gift-tax-info", response_model=GiftTaxInfo)
async def get_gift_tax_information(
    beneficiary_name: str,
    current_user: CurrentUser,
    db: DBSession,
    contribution_amount: Decimal | None = None,
):
    contribution_ytd = await _ytd_contribution_for_beneficiary(db, current_user.id, beneficiary_name)
    info = get_gift_tax_info(
        beneficiary_name=beneficiary_name,
        beneficiary_contribution_ytd=contribution_ytd,
        new_contribution_amount=contribution_amount,
    )
    return GiftTaxInfo(**info)


# Fetch a single education account owned by the authenticated user.
@router.get("/{account_id}", response_model=EducationAccountResponse)
async def get_education_account(
    account_id: str,
    current_user: CurrentUser,
    db: DBSession,
):
    return await _get_owned_account(db, account_id, current_user.id)


# Patch an education account with whichever fields were supplied.
@router.put("/{account_id}", response_model=EducationAccountResponse)
async def update_education_account(
    account_id: str,
    account_data: EducationAccountUpdate,
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


# Delete an education account.
@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_education_account(
    account_id: str,
    current_user: CurrentUser,
    db: DBSession,
):
    account = await _get_owned_account(db, account_id, current_user.id)

    await db.delete(account)
    await db.commit()


# Run a growth projection for an account over N months, given a hypothetical flat monthly
# contribution on top of whatever the account's own active recurring contributions add.
@router.post("/{account_id}/simulate", response_model=EducationSimulationResponse)
async def simulate_growth(
    account_id: str,
    simulation: EducationSimulationRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    account = await _get_owned_account(db, account_id, current_user.id)

    recurring_contributions = []
    if simulation.include_recurring:
        contributions_result = await db.execute(
            select(EducationRecurringContribution).where(
                EducationRecurringContribution.education_account_id == account_id,
                EducationRecurringContribution.is_active == True,
            )
        )
        recurring_contributions = list(contributions_result.scalars().all())

        allocation_stubs = await _education_allocation_stubs(db, current_user.id)
        recurring_contributions.extend(allocation_stubs.get(account_id, []))

    simulator = EducationSimulatorService()
    projections = simulator.generate_projection(
        account=account,
        months=simulation.months,
        monthly_contribution=simulation.monthly_contribution,
        recurring_contributions=recurring_contributions,
    )

    final = projections[-1] if projections else None

    return EducationSimulationResponse(
        account_id=account_id,
        projections=[
            EducationProjectionPoint(
                month=p.month,
                date=p.date,
                balance=p.balance,
                contributions=p.contributions,
                growth=p.growth,
            )
            for p in projections
        ],
        final_balance=final.balance if final else account.balance,
        total_contributions=final.contributions if final else Decimal("0"),
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
        select(EducationRecurringContribution).where(
            EducationRecurringContribution.education_account_id == account_id
        )
    )
    return result.scalars().all()


# Add a new monthly/yearly recurring contribution to an account. This only feeds
# simulations (see services/education_simulator.py) - it does not itself post real
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

    contribution = EducationRecurringContribution(
        education_account_id=account_id,
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


# Record a real contribution to an account: always succeeds (200) and bumps both
# contribution_ytd and balance - unlike retirement's /contribute, this never rejects the
# request, since a 529 has no IRS contribution cap to enforce. Debits the source bank
# account for real if source_type is bank_account, and posts a Transaction row so the
# contribution shows up in the unified transaction log and can be corrected later (see
# api/v1/transactions.py). Returns updated gift-tax guidance for the beneficiary plus the
# posted transaction's id.
@router.post("/{account_id}/contribute", response_model=GiftTaxInfo)
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

    account.contribution_ytd += contribution.amount
    account.balance += contribution.amount

    transaction = Transaction(
        user_id=current_user.id,
        transaction_type=TransactionType.EDUCATION_CONTRIBUTION,
        amount=contribution.amount,
        transaction_date=date.today(),
        account_type=AllocationDestinationType.EDUCATION_ACCOUNT,
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

    new_ytd = await _ytd_contribution_for_beneficiary(db, current_user.id, account.beneficiary_name)
    info = get_gift_tax_info(
        beneficiary_name=account.beneficiary_name,
        beneficiary_contribution_ytd=new_ytd,
    )
    return GiftTaxInfo(account_id=account.id, transaction_id=transaction.id, **info)
