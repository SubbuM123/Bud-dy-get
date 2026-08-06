"""Core logic for the V2 background scheduler (docs/future-plan.md's "Automatic Balance
Updates" section) - the daily Celery Beat task (app/workers/recurring_actions.py) that
auto-executes every recurring rule in the app on its own cadence, closing the gap where
V1 required a manual action (POST /income/{id}/log, a `/contribute` call, or hand-entering
each recurring bill) to ever move real money or post a real Transaction.

Every "get_due_*" function below returns the rows across *all* users that are due as of a
given date - this runs as one system-wide daily task, not a per-request/per-user call, so
there's no `current_user` to scope against the way every api/v1 router does. Each rule
type tracks its own idempotency independently via a `last_executed_date`/
`last_interest_applied_date` column (added by migration 012).

Every "post_due_*"/"apply_due_*" function **catches up fully**, not just once: if a rule
has been due for several periods (a `start_date` set months in the past before the
scheduler first ran, or the scheduler being down for a while), it loops - posting one
correctly-dated Transaction/Expense per missed period, advancing the tracking field to
that period's own date each time - rather than posting a single occurrence and jumping
the tracking field straight to `as_of`, which would silently discard every period in
between. (An earlier version of this module did exactly that; see docs/progress.md's
"functional" bug-fix entry for the symptom that surfaced it - a year-old recurring Income
that had only ever posted one paycheck.) A generous `_MAX_CATCHUP_PERIODS` iteration cap
guards each loop against a runaway loop from a malformed date, not a real user-facing
limit.

Posting logic is deliberately reused, not reimplemented, wherever a manual equivalent
already exists: recurring Income occurrences go through
services/income_posting.post_income_transactions (the exact function
POST /income/{id}/log already calls), and every balance bump goes through
services/transaction_effects.apply_effect (the exact function every other posting path in
this app already uses). Recurring retirement/education contributions and interest/
expected-return postings have no pre-existing manual-endpoint function to reuse instead of
duplicate (the manual `/contribute` endpoints take a `source_type`/possible
`source_bank_account_id` a recurring rule row doesn't carry, and there is no
"apply expected return" endpoint at all) - those are implemented directly in this module,
following the same IRS-limit/employer-match pattern api/v1/income.py's Option A path
already established: a scheduler-driven posting does **not** enforce the IRS contribution
limit or, for education, gift-tax considerations - same "smallest change, still recorded"
tradeoff, not an oversight.
"""

from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.calculations.compound_interest import calculate_monthly_interest
from app.models.bank_accounts import BankAccount
from app.models.education_accounts import EducationAccount, EducationRecurringContribution
from app.models.expenses import Expense
from app.models.income import Income
from app.models.retirement_accounts import RetirementAccount, RetirementRecurringContribution
from app.models.transactions import Transaction
from app.models.enums import (
    AllocationDestinationType,
    CompoundingFrequency,
    ContributionSourceType,
    RetirementAccountType,
    TransactionType,
)
from app.services.income_posting import post_income_transactions
from app.services.retirement_rules import calculate_employer_match
from app.services.transaction_effects import apply_effect

_401K_TYPES = {RetirementAccountType.TRADITIONAL_401K, RetirementAccountType.ROTH_401K}

# Defensive cap on how many periods a single post_due_*/apply_due_* call will catch up in
# one go - 1200 months (100 years) or 1200 weeks (~23 years), comfortably beyond any real
# usage of this app. Exists only to turn a malformed date (e.g. a start_date typo'd into
# the distant past) into a bounded, resumable catch-up rather than a runaway loop -
# whatever wasn't caught up this run picks up again next run, since the tracking field is
# still advanced to wherever the loop stopped.
_MAX_CATCHUP_PERIODS = 1200

# How far to advance a rule's "next due" date for each cadence keyword, shared by Income's
# `frequency` (IncomeFrequency values), retirement/education recurring contributions'
# `frequency` (ContributionFrequency values: "monthly"/"yearly"), and Expense's
# `recurrence_pattern` (free text, same "weekly"/"biweekly"/"monthly"/"yearly" vocabulary
# api/v1/bank_accounts.py's `_RECURRENCE_PATTERN_TO_FREQUENCY` already uses for
# projections). Semi-monthly (the 1st/15th, or similar) is approximated as a flat 15-day
# step rather than modeled as two distinct calendar anchors - the same "don't teach every
# consumer a real semi-monthly calendar" simplification services/income_allocator.py
# already documents for *projecting* a semi-monthly income's monthly-equivalent amount,
# applied here to *scheduling* its actual occurrence dates instead.
_CADENCE_STEPS = {
    "weekly": relativedelta(weeks=1),
    "biweekly": relativedelta(weeks=2),
    "semi_monthly": relativedelta(days=15),
    "monthly": relativedelta(months=1),
    "yearly": relativedelta(years=1),
}


def calculate_next_occurrence(start_date: date, cadence: str, last_executed: date | None) -> date:
    """The next date a recurring rule is due, given when it started, its cadence keyword
    (a key of `_CADENCE_STEPS`; unrecognized values fall back to monthly, same default
    `_RECURRENCE_PATTERN_TO_FREQUENCY` uses), and the date it last actually executed (None
    if never). The rule's very first occurrence is `start_date` itself, not `start_date` +
    one cadence step - the same "the rule started, so the first payment is due starting
    then" semantics `start_date` already carries for every simulator/projection in this
    app. Callers that need a *different* first-occurrence date (interest, which accrues
    starting one period *after* an anchor rather than on it; recurring Expenses, whose own
    row already counts as occurrence #1) get that by passing a non-None `last_executed`
    even on their conceptual "first" call - see get_due_recurring_expenses and
    apply_due_bank_interest's docstrings for the two concrete examples.
    """
    if last_executed is None:
        return start_date
    step = _CADENCE_STEPS.get(cadence, _CADENCE_STEPS["monthly"])
    return last_executed + step


def _is_due(start_date: date, cadence: str, last_executed: date | None, as_of: date) -> bool:
    return calculate_next_occurrence(start_date, cadence, last_executed) <= as_of


# --- Income ------------------------------------------------------------------


async def get_due_incomes(db: AsyncSession, as_of: date) -> list[Income]:
    """Every active recurring Income with at least one occurrence due on or before
    `as_of` - a pre-filter for `post_due_income`, which catches up every due occurrence,
    not just the first."""
    result = await db.execute(
        select(Income).where(
            Income.is_active == True,  # noqa: E712
            Income.is_recurring == True,  # noqa: E712
        )
    )
    return [
        income
        for income in result.scalars().all()
        if income.frequency is not None
        and income.start_date is not None
        and _is_due(income.start_date, income.frequency.value, income.last_executed_date, as_of)
    ]


async def post_due_income(db: AsyncSession, income: Income, as_of: date) -> list[Transaction]:
    """Auto-post every occurrence of a recurring Income due on or before `as_of`, via the
    same post_income_transactions manual logging already uses - one Transaction set per
    missed period, each dated its own occurrence date (not `as_of`), advancing
    `last_executed_date` after each so a later call resumes from wherever this one
    stopped."""
    transactions: list[Transaction] = []
    periods = 0
    next_date = calculate_next_occurrence(income.start_date, income.frequency.value, income.last_executed_date)
    while next_date <= as_of and periods < _MAX_CATCHUP_PERIODS:
        transactions.extend(
            await post_income_transactions(db, income=income, amount=income.amount, log_date=next_date)
        )
        income.last_executed_date = next_date
        next_date = calculate_next_occurrence(income.start_date, income.frequency.value, income.last_executed_date)
        periods += 1
    return transactions


# --- Interest / expected return (bank, retirement, education) ------------------


# Shared catch-up loop for the three interest-bearing account types below - each calls
# this with its own balance-read/balance-write closures and Transaction shape, so the
# "loop until caught up, compound sequentially, respect the catch-up cap" logic lives in
# exactly one place. `anchor` is the date interest starts accruing from (an account's own
# `created_at`, since an account has implicitly been earning since it existed, even if
# the scheduler never got around to posting it) - the *first* due date is one cadence step
# *after* `anchor`, not on it (no growth has happened yet at the moment of creation), which
# is why `last_applied or anchor` is passed as `last_executed` even on the conceptual
# first call, the same "pass a non-None last_executed to shift the first-occurrence date"
# technique get_due_recurring_expenses relies on for its own different reason.
async def _catch_up_interest(
    *,
    anchor: date,
    last_applied: date | None,
    as_of: date,
    compute_interest,
    apply_amount,
    make_transaction,
    advance_last_applied,
) -> list[Transaction]:
    transactions: list[Transaction] = []
    periods = 0
    next_date = calculate_next_occurrence(anchor, "monthly", last_applied or anchor)
    while next_date <= as_of and periods < _MAX_CATCHUP_PERIODS:
        interest = compute_interest()
        advance_last_applied(next_date)
        if interest > 0:
            transaction = make_transaction(interest, next_date)
            await apply_amount(interest)
            transactions.append(transaction)
        next_date = calculate_next_occurrence(anchor, "monthly", next_date)
        periods += 1
    return transactions


async def get_due_bank_interest(db: AsyncSession, as_of: date) -> list[BankAccount]:
    """Every bank account with a positive interest rate that has at least one month of
    interest due on or before `as_of`."""
    result = await db.execute(select(BankAccount).where(BankAccount.interest_rate.isnot(None)))
    return [
        account
        for account in result.scalars().all()
        if account.interest_rate
        and account.interest_rate > 0
        and _is_due(
            account.created_at.date(),
            "monthly",
            account.last_interest_applied_date or account.created_at.date(),
            as_of,
        )
    ]


async def apply_due_bank_interest(db: AsyncSession, account: BankAccount, as_of: date) -> list[Transaction]:
    """Catch up every month of interest `account` has earned but not yet had posted,
    using the exact same compounding math the growth-projection chart already uses
    (services/bank_simulator.py) - each month's interest compounds on the balance the
    *previous* catch-up month already credited, matching how compounding actually works,
    not a naive "multiply one month's rate by however many months were missed."""

    def make_transaction(interest: Decimal, as_of_month: date) -> Transaction:
        transaction = Transaction(
            user_id=account.user_id,
            transaction_type=TransactionType.INTEREST,
            amount=interest,
            transaction_date=as_of_month,
            description=f"Interest: {account.account_name}",
            account_type=AllocationDestinationType.BANK_ACCOUNT,
            account_id=account.id,
        )
        db.add(transaction)
        return transaction

    async def apply_amount(interest: Decimal) -> None:
        await apply_effect(
            db,
            account_type=AllocationDestinationType.BANK_ACCOUNT,
            account_id=account.id,
            transaction_type=TransactionType.INTEREST,
            source_bank_account_id=None,
            amount=interest,
        )

    return await _catch_up_interest(
        anchor=account.created_at.date(),
        last_applied=account.last_interest_applied_date,
        as_of=as_of,
        compute_interest=lambda: calculate_monthly_interest(
            account.current_balance, account.interest_rate, account.compounding_frequency
        ),
        apply_amount=apply_amount,
        make_transaction=make_transaction,
        advance_last_applied=lambda d: setattr(account, "last_interest_applied_date", d),
    )


async def get_due_retirement_interest(db: AsyncSession, as_of: date) -> list[RetirementAccount]:
    """Every retirement account with a positive expected return rate that has at least
    one month of growth due on or before `as_of`."""
    result = await db.execute(select(RetirementAccount))
    return [
        account
        for account in result.scalars().all()
        if account.expected_return_rate
        and account.expected_return_rate > 0
        and _is_due(
            account.created_at.date(),
            "monthly",
            account.last_interest_applied_date or account.created_at.date(),
            as_of,
        )
    ]


async def apply_due_retirement_interest(
    db: AsyncSession, account: RetirementAccount, as_of: date
) -> list[Transaction]:
    """Catch up every month of expected-return growth `account` has accrued but not yet
    had posted - see `apply_due_bank_interest`'s docstring for the sequential-compounding
    reasoning, applied here against `account.balance` with `expected_return_rate` instead
    of `interest_rate`/`compounding_frequency`."""

    def make_transaction(growth: Decimal, as_of_month: date) -> Transaction:
        transaction = Transaction(
            user_id=account.user_id,
            transaction_type=TransactionType.INTEREST,
            amount=growth,
            transaction_date=as_of_month,
            description=f"Expected return: {account.account_name}",
            account_type=AllocationDestinationType.RETIREMENT_ACCOUNT,
            account_id=account.id,
        )
        db.add(transaction)
        return transaction

    async def apply_amount(growth: Decimal) -> None:
        await apply_effect(
            db,
            account_type=AllocationDestinationType.RETIREMENT_ACCOUNT,
            account_id=account.id,
            transaction_type=TransactionType.INTEREST,
            source_bank_account_id=None,
            amount=growth,
        )

    return await _catch_up_interest(
        anchor=account.created_at.date(),
        last_applied=account.last_interest_applied_date,
        as_of=as_of,
        compute_interest=lambda: calculate_monthly_interest(
            account.balance, account.expected_return_rate, CompoundingFrequency.MONTHLY
        ),
        apply_amount=apply_amount,
        make_transaction=make_transaction,
        advance_last_applied=lambda d: setattr(account, "last_interest_applied_date", d),
    )


async def get_due_education_interest(db: AsyncSession, as_of: date) -> list[EducationAccount]:
    """Every education account with a positive expected return rate that has at least
    one month of growth due on or before `as_of`."""
    result = await db.execute(select(EducationAccount))
    return [
        account
        for account in result.scalars().all()
        if account.expected_return_rate
        and account.expected_return_rate > 0
        and _is_due(
            account.created_at.date(),
            "monthly",
            account.last_interest_applied_date or account.created_at.date(),
            as_of,
        )
    ]


async def apply_due_education_interest(
    db: AsyncSession, account: EducationAccount, as_of: date
) -> list[Transaction]:
    """Same as `apply_due_retirement_interest`, for an education account's `balance`."""

    def make_transaction(growth: Decimal, as_of_month: date) -> Transaction:
        transaction = Transaction(
            user_id=account.user_id,
            transaction_type=TransactionType.INTEREST,
            amount=growth,
            transaction_date=as_of_month,
            description=f"Expected return: {account.account_name}",
            account_type=AllocationDestinationType.EDUCATION_ACCOUNT,
            account_id=account.id,
        )
        db.add(transaction)
        return transaction

    async def apply_amount(growth: Decimal) -> None:
        await apply_effect(
            db,
            account_type=AllocationDestinationType.EDUCATION_ACCOUNT,
            account_id=account.id,
            transaction_type=TransactionType.INTEREST,
            source_bank_account_id=None,
            amount=growth,
        )

    return await _catch_up_interest(
        anchor=account.created_at.date(),
        last_applied=account.last_interest_applied_date,
        as_of=as_of,
        compute_interest=lambda: calculate_monthly_interest(
            account.balance, account.expected_return_rate, CompoundingFrequency.MONTHLY
        ),
        apply_amount=apply_amount,
        make_transaction=make_transaction,
        advance_last_applied=lambda d: setattr(account, "last_interest_applied_date", d),
    )


# --- Retirement recurring contributions ------------------------------------------


async def get_due_retirement_contributions(
    db: AsyncSession, as_of: date
) -> list[RetirementRecurringContribution]:
    result = await db.execute(
        select(RetirementRecurringContribution).where(
            RetirementRecurringContribution.is_active == True  # noqa: E712
        )
    )
    return [
        contribution
        for contribution in result.scalars().all()
        if (contribution.end_date is None or as_of <= contribution.end_date)
        and _is_due(
            contribution.start_date,
            contribution.frequency.value,
            contribution.last_executed_date,
            as_of,
        )
    ]


async def post_due_retirement_contribution(
    db: AsyncSession, contribution: RetirementRecurringContribution, as_of: date
) -> list[Transaction]:
    """Catch up every occurrence of a recurring retirement contribution due on or before
    `as_of` (and on or before the rule's own `end_date`, if set), each posted as
    TRACK_ONLY (a recurring rule carries no funding bank account the way a manual
    `/contribute` call can - see models/enums.py:ContributionSourceType), including
    employer match for a 401(k)/Roth 401(k) - the same delta-of-cumulative-match
    calculation api/v1/retirement_accounts.py's `record_contribution` uses, recomputed
    fresh each occurrence off `account.contribution_ytd` so multiple catch-up occurrences
    in one call still match correctly. Does NOT check the IRS contribution limit - see
    this module's docstring for why that's a deliberate, documented simplification rather
    than an oversight.
    """
    account = await db.get(RetirementAccount, contribution.retirement_account_id)

    transactions: list[Transaction] = []
    periods = 0
    next_date = calculate_next_occurrence(
        contribution.start_date, contribution.frequency.value, contribution.last_executed_date
    )
    while (
        next_date <= as_of
        and (contribution.end_date is None or next_date <= contribution.end_date)
        and periods < _MAX_CATCHUP_PERIODS
    ):
        employer_match = Decimal("0")
        if (
            account.account_type in _401K_TYPES
            and account.annual_salary
            and account.employer_match_percent
            and account.employer_match_limit_percent
        ):
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

        transaction = Transaction(
            user_id=account.user_id,
            transaction_type=TransactionType.RETIREMENT_CONTRIBUTION,
            amount=contribution.amount,
            transaction_date=next_date,
            description=f"Auto-posted recurring contribution: {account.account_name}",
            account_type=AllocationDestinationType.RETIREMENT_ACCOUNT,
            account_id=account.id,
            source_type=ContributionSourceType.TRACK_ONLY,
        )
        db.add(transaction)
        transactions.append(transaction)

        contribution.last_executed_date = next_date
        next_date = calculate_next_occurrence(
            contribution.start_date, contribution.frequency.value, contribution.last_executed_date
        )
        periods += 1

    return transactions


# --- Education recurring contributions ------------------------------------------


async def get_due_education_contributions(
    db: AsyncSession, as_of: date
) -> list[EducationRecurringContribution]:
    result = await db.execute(
        select(EducationRecurringContribution).where(
            EducationRecurringContribution.is_active == True  # noqa: E712
        )
    )
    return [
        contribution
        for contribution in result.scalars().all()
        if (contribution.end_date is None or as_of <= contribution.end_date)
        and _is_due(
            contribution.start_date,
            contribution.frequency.value,
            contribution.last_executed_date,
            as_of,
        )
    ]


async def post_due_education_contribution(
    db: AsyncSession, contribution: EducationRecurringContribution, as_of: date
) -> list[Transaction]:
    """Catch up every occurrence of a recurring education contribution due on or before
    `as_of` (and the rule's own `end_date`, if set) - see
    `post_due_retirement_contribution`'s docstring for why each is posted as TRACK_ONLY
    (no funding account on the rule, no gift-tax enforcement, same deliberate
    simplification)."""
    account = await db.get(EducationAccount, contribution.education_account_id)

    transactions: list[Transaction] = []
    periods = 0
    next_date = calculate_next_occurrence(
        contribution.start_date, contribution.frequency.value, contribution.last_executed_date
    )
    while (
        next_date <= as_of
        and (contribution.end_date is None or next_date <= contribution.end_date)
        and periods < _MAX_CATCHUP_PERIODS
    ):
        account.contribution_ytd += contribution.amount
        account.balance += contribution.amount

        transaction = Transaction(
            user_id=account.user_id,
            transaction_type=TransactionType.EDUCATION_CONTRIBUTION,
            amount=contribution.amount,
            transaction_date=next_date,
            description=f"Auto-posted recurring contribution: {account.account_name}",
            account_type=AllocationDestinationType.EDUCATION_ACCOUNT,
            account_id=account.id,
            source_type=ContributionSourceType.TRACK_ONLY,
        )
        db.add(transaction)
        transactions.append(transaction)

        contribution.last_executed_date = next_date
        next_date = calculate_next_occurrence(
            contribution.start_date, contribution.frequency.value, contribution.last_executed_date
        )
        periods += 1

    return transactions


# --- Recurring expenses ---------------------------------------------------------


async def get_due_recurring_expenses(db: AsyncSession, as_of: date) -> list[Expense]:
    """Every recurring Expense "rule" row with at least one occurrence due on or before
    `as_of`. Only the original recurring row is ever due again - the occurrences this
    task creates (see `post_due_recurring_expense`) are plain is_recurring=False rows, so
    they're never matched by this query themselves.

    Unlike Income (where the rule itself never posts anything until logged), a recurring
    Expense's own row already **is** a real, already-counted occurrence the moment it's
    created (see models/expenses.py's last_executed_date docstring) - so the first
    auto-created occurrence must be one cadence step *after* `expense_date`, not on
    `expense_date` itself, or the day the rule was created would get double-counted. This
    is done by always treating `last_executed_date or expense_date` as the "last
    executed" anchor for `calculate_next_occurrence`, never leaving it None the way
    Income/contribution rules legitimately can on their first run.
    """
    result = await db.execute(
        select(Expense).where(Expense.is_recurring == True)  # noqa: E712
    )
    return [
        expense
        for expense in result.scalars().all()
        if _is_due(
            expense.expense_date,
            (expense.recurrence_pattern or "monthly").lower(),
            expense.last_executed_date or expense.expense_date,
            as_of,
        )
    ]


async def post_due_recurring_expense(db: AsyncSession, expense: Expense, as_of: date) -> list[Expense]:
    """Catch up every missed occurrence of a recurring expense "rule" on or before
    `as_of` - one plain one-time Expense row per occurrence, cloned from the rule's own
    merchant/amount/category/bank_account_id and dated that occurrence's own date. If a
    bank account is linked, each occurrence debits it for real via apply_effect (see
    models/expenses.py's bank_account_id docstring for how this differs from a manually-
    entered expense's bank_account_id, which is tag-only). Advances the *rule* row's
    `last_executed_date` after each occurrence so a later call resumes correctly; the new
    occurrence rows themselves are is_recurring=False and never become due on their own.
    """
    cadence = (expense.recurrence_pattern or "monthly").lower()
    occurrences: list[Expense] = []
    periods = 0
    next_date = calculate_next_occurrence(
        expense.expense_date, cadence, expense.last_executed_date or expense.expense_date
    )
    while next_date <= as_of and periods < _MAX_CATCHUP_PERIODS:
        occurrence = Expense(
            user_id=expense.user_id,
            merchant_name=expense.merchant_name,
            amount=expense.amount,
            expense_date=next_date,
            category_id=expense.category_id,
            bank_account_id=expense.bank_account_id,
            description=expense.description,
            tags=expense.tags,
            is_recurring=False,
        )
        db.add(occurrence)
        occurrences.append(occurrence)

        if expense.bank_account_id is not None:
            # Positive amount = debit the source account (money leaving), matching
            # api/v1/investments.py's buy_stock's identical account_type=None,
            # source_bank_account_id=... call shape - a negative amount there means
            # credit instead (see sell_stock), so this must stay positive.
            await apply_effect(
                db,
                account_type=None,
                account_id=None,
                transaction_type=TransactionType.INCOME,  # unused when account_type is None
                source_bank_account_id=expense.bank_account_id,
                amount=expense.amount,
            )

        expense.last_executed_date = next_date
        next_date = calculate_next_occurrence(expense.expense_date, cadence, expense.last_executed_date)
        periods += 1

    return occurrences


# --- Orchestrator ----------------------------------------------------------------


async def run_scheduled_tasks(db: AsyncSession, as_of: date | None = None) -> dict[str, int]:
    """Run every due recurring rule across all users as of `as_of` (defaults to today),
    catching each fully up to `as_of` (not just one occurrence - see this module's
    docstring), committing once at the end. Called by the daily Celery task
    (app/workers/recurring_actions.py). Returns a count of how many *occurrences* of each
    kind were auto-posted (a single Income catching up 12 months contributes 12 to
    `incomes_posted`, not 1), for the task's return value/logs.
    """
    as_of = as_of or date.today()
    counts = {
        "incomes_posted": 0,
        "bank_interest_applied": 0,
        "retirement_interest_applied": 0,
        "education_interest_applied": 0,
        "retirement_contributions_posted": 0,
        "education_contributions_posted": 0,
        "expenses_created": 0,
    }

    for income in await get_due_incomes(db, as_of):
        counts["incomes_posted"] += len(await post_due_income(db, income, as_of))

    for account in await get_due_bank_interest(db, as_of):
        counts["bank_interest_applied"] += len(await apply_due_bank_interest(db, account, as_of))

    for account in await get_due_retirement_interest(db, as_of):
        counts["retirement_interest_applied"] += len(await apply_due_retirement_interest(db, account, as_of))

    for account in await get_due_education_interest(db, as_of):
        counts["education_interest_applied"] += len(await apply_due_education_interest(db, account, as_of))

    for contribution in await get_due_retirement_contributions(db, as_of):
        counts["retirement_contributions_posted"] += len(
            await post_due_retirement_contribution(db, contribution, as_of)
        )

    for contribution in await get_due_education_contributions(db, as_of):
        counts["education_contributions_posted"] += len(
            await post_due_education_contribution(db, contribution, as_of)
        )

    for expense in await get_due_recurring_expenses(db, as_of):
        counts["expenses_created"] += len(await post_due_recurring_expense(db, expense, as_of))

    await db.commit()
    return counts
