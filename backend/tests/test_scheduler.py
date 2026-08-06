"""Coverage for the V2 background scheduler (services/scheduler.py) - see
docs/future-plan.md's "Automatic Balance Updates" section for the design this
implements. Every test below `run_scheduled_tasks` directly creates its data through the
normal HTTP API (via `client`/`auth_headers`, same as every other test file) and then
drives the scheduler directly against the same database via the `db_session` fixture
(conftest.py), since most of services/scheduler.py's functions have no HTTP endpoint of
their own - the daily Celery Beat task (app/workers/recurring_actions.py) is the real
entry point. `POST /scheduler/run` (api/v1/scheduler.py) is the one exception - a manual
trigger for the same run_scheduled_tasks, covered by its own tests at the bottom of this
file.

The catch-up cases below (multi-period backfill, not just "is the very next occurrence
posted") are a direct regression test for a real bug: an earlier version of
post_due_income/apply_bank_interest/etc. posted exactly one occurrence per call and then
stamped the tracking field to `as_of` (today) rather than to the occurrence it just
posted - so a recurring Income with a `start_date` a year in the past only ever posted
one paycheck, silently dropping the other 11 months. See docs/progress.md's `functional`
bug-fix entry for the reported symptom.
"""

from datetime import date, datetime

from app.models.bank_accounts import BankAccount
from app.models.education_accounts import EducationAccount
from app.models.retirement_accounts import RetirementAccount
from app.services import scheduler

BANK_PAYLOAD = {
    "account_name": "Checking",
    "account_type": "checking",
    "principal": "1000.00",
    "interest_rate": "0.12",  # 12%/yr = 1%/mo flat, easy to hand-verify
    "compounding_frequency": "monthly",
}

IRA_PAYLOAD = {
    "account_name": "Roth IRA",
    "account_type": "roth_ira",
    "balance": "1000.00",
    "expected_return_rate": "0.12",
}

FOUR_OH_ONE_K_PAYLOAD = {
    "account_name": "Acme Corp 401k",
    "account_type": "traditional_401k",
    "balance": "10000.00",
    "employer_name": "Acme Corp",
    "annual_salary": "120000.00",
    "employer_match_percent": "0.5",
    "employer_match_limit_percent": "0.06",
    "expected_return_rate": "0.07",
}

FIVE_TWENTY_NINE_PAYLOAD = {
    "account_name": "Jordan's 529",
    "account_type": "529_plan",
    "beneficiary_name": "Jordan",
    "balance": "1000.00",
    "expected_return_rate": "0.12",
}


async def _create_bank_account(client, headers, payload=None):
    response = await client.post("/api/v1/bank-accounts", json=payload or BANK_PAYLOAD, headers=headers)
    return response.json()["id"]


async def _create_retirement_account(client, headers, payload=None):
    response = await client.post(
        "/api/v1/retirement-accounts", json=payload or IRA_PAYLOAD, headers=headers
    )
    return response.json()["id"]


async def _create_education_account(client, headers):
    response = await client.post(
        "/api/v1/education-accounts", json=FIVE_TWENTY_NINE_PAYLOAD, headers=headers
    )
    return response.json()["id"]


# The scheduler anchors an account's first interest/expected-return date on its own
# `created_at` (see scheduler.py's get_due_bank_interest docstring) - which is real
# wall-clock time at the moment the test creates the account via HTTP, not a fixed 2026
# test date. Tests that need deterministic control over how many interest periods are
# "due" as of a fixed `as_of` backdate `created_at` directly, via `db_session` rather
# than the HTTP API (which has no way to set it).
async def _backdate_created_at(db_session, model, account_id, created_at):
    account = await db_session.get(model, account_id)
    account.created_at = created_at
    await db_session.commit()


# --- calculate_next_occurrence (pure function, no DB) ---------------------------------


def test_calculate_next_occurrence_first_run_is_the_start_date():
    result = scheduler.calculate_next_occurrence(date(2026, 1, 15), "monthly", None)
    assert result == date(2026, 1, 15)


def test_calculate_next_occurrence_steps_forward_by_cadence():
    assert scheduler.calculate_next_occurrence(
        date(2026, 1, 1), "monthly", date(2026, 1, 1)
    ) == date(2026, 2, 1)
    assert scheduler.calculate_next_occurrence(
        date(2026, 1, 1), "weekly", date(2026, 1, 1)
    ) == date(2026, 1, 8)
    assert scheduler.calculate_next_occurrence(
        date(2026, 1, 1), "biweekly", date(2026, 1, 1)
    ) == date(2026, 1, 15)
    assert scheduler.calculate_next_occurrence(
        date(2026, 1, 1), "yearly", date(2026, 1, 1)
    ) == date(2027, 1, 1)


def test_calculate_next_occurrence_unrecognized_cadence_defaults_to_monthly():
    result = scheduler.calculate_next_occurrence(date(2026, 1, 1), "bogus", date(2026, 1, 1))
    assert result == date(2026, 2, 1)


# --- Recurring income -------------------------------------------------------------------


async def test_due_recurring_income_is_auto_posted(client, auth_headers, db_session):
    bank_id = await _create_bank_account(client, auth_headers)
    await client.post(
        "/api/v1/income",
        json={
            "name": "Paycheck",
            "amount": "2000.00",
            "is_recurring": True,
            "frequency": "monthly",
            "start_date": "2026-01-01",
            "allocations": [
                {"destination_type": "bank_account", "destination_id": bank_id, "percentage": "100"}
            ],
        },
        headers=auth_headers,
    )

    counts = await scheduler.run_scheduled_tasks(db_session, as_of=date(2026, 1, 1))
    assert counts["incomes_posted"] == 1

    account_response = await client.get(f"/api/v1/bank-accounts/{bank_id}", headers=auth_headers)
    assert float(account_response.json()["current_balance"]) == 3000.00  # 1000 + 2000

    transactions_response = await client.get(
        "/api/v1/transactions", params={"transaction_type": "income"}, headers=auth_headers
    )
    assert len(transactions_response.json()) == 1


async def test_recurring_income_is_not_re_posted_same_day(client, auth_headers, db_session):
    bank_id = await _create_bank_account(client, auth_headers)
    await client.post(
        "/api/v1/income",
        json={
            "name": "Paycheck",
            "amount": "2000.00",
            "is_recurring": True,
            "frequency": "monthly",
            "start_date": "2026-01-01",
            "allocations": [
                {"destination_type": "bank_account", "destination_id": bank_id, "percentage": "100"}
            ],
        },
        headers=auth_headers,
    )

    await scheduler.run_scheduled_tasks(db_session, as_of=date(2026, 1, 1))
    counts = await scheduler.run_scheduled_tasks(db_session, as_of=date(2026, 1, 1))

    assert counts["incomes_posted"] == 0
    account_response = await client.get(f"/api/v1/bank-accounts/{bank_id}", headers=auth_headers)
    assert float(account_response.json()["current_balance"]) == 3000.00


async def test_recurring_income_posts_again_next_month(client, auth_headers, db_session):
    bank_id = await _create_bank_account(client, auth_headers)
    await client.post(
        "/api/v1/income",
        json={
            "name": "Paycheck",
            "amount": "2000.00",
            "is_recurring": True,
            "frequency": "monthly",
            "start_date": "2026-01-01",
            "allocations": [
                {"destination_type": "bank_account", "destination_id": bank_id, "percentage": "100"}
            ],
        },
        headers=auth_headers,
    )

    await scheduler.run_scheduled_tasks(db_session, as_of=date(2026, 1, 1))
    counts = await scheduler.run_scheduled_tasks(db_session, as_of=date(2026, 2, 1))

    assert counts["incomes_posted"] == 1
    account_response = await client.get(f"/api/v1/bank-accounts/{bank_id}", headers=auth_headers)
    assert float(account_response.json()["current_balance"]) == 5000.00  # 1000 + 2000 + 2000


async def test_one_time_income_is_never_picked_up_by_the_scheduler(client, auth_headers, db_session):
    bank_id = await _create_bank_account(client, auth_headers)
    await client.post(
        "/api/v1/income",
        json={
            "name": "Bonus",
            "amount": "500.00",
            "is_recurring": False,
            "income_date": "2026-01-01",
            "allocations": [
                {"destination_type": "bank_account", "destination_id": bank_id, "percentage": "100"}
            ],
        },
        headers=auth_headers,
    )

    counts = await scheduler.run_scheduled_tasks(db_session, as_of=date(2026, 2, 1))
    assert counts["incomes_posted"] == 0


async def test_income_a_year_overdue_catches_up_every_missed_month_in_one_run(
    client, auth_headers, db_session
):
    """The user's exact reported scenario: start_date a year in the past, scheduler run
    once as of a year later - every missed month must be posted, not just one."""
    bank_id = await _create_bank_account(client, auth_headers)
    await client.post(
        "/api/v1/income",
        json={
            "name": "Paycheck",
            "amount": "2000.00",
            "is_recurring": True,
            "frequency": "monthly",
            "start_date": "2025-08-01",
            "allocations": [
                {"destination_type": "bank_account", "destination_id": bank_id, "percentage": "100"}
            ],
        },
        headers=auth_headers,
    )

    counts = await scheduler.run_scheduled_tasks(db_session, as_of=date(2026, 8, 1))

    # Aug 2025 through Aug 2026 inclusive, monthly = 13 occurrences.
    assert counts["incomes_posted"] == 13

    account_response = await client.get(f"/api/v1/bank-accounts/{bank_id}", headers=auth_headers)
    assert float(account_response.json()["current_balance"]) == 27000.00  # 1000 + 2000*13

    transactions_response = await client.get(
        "/api/v1/transactions", params={"transaction_type": "income"}, headers=auth_headers
    )
    transactions = transactions_response.json()
    assert len(transactions) == 13
    dates = {t["transaction_date"] for t in transactions}
    assert "2025-08-01" in dates
    assert "2026-08-01" in dates


# --- Bank interest -----------------------------------------------------------------------


async def test_bank_interest_is_applied_once_per_month(client, auth_headers, db_session):
    bank_id = await _create_bank_account(client, auth_headers)
    await _backdate_created_at(db_session, BankAccount, bank_id, datetime(2025, 12, 1))

    counts = await scheduler.run_scheduled_tasks(db_session, as_of=date(2026, 1, 5))
    assert counts["bank_interest_applied"] == 1

    account_response = await client.get(f"/api/v1/bank-accounts/{bank_id}", headers=auth_headers)
    # 1000 * (0.12/12) = 10.00 monthly interest
    assert float(account_response.json()["current_balance"]) == 1010.00

    transactions_response = await client.get(
        "/api/v1/transactions", params={"transaction_type": "interest"}, headers=auth_headers
    )
    assert len(transactions_response.json()) == 1


async def test_bank_interest_does_not_reapply_within_the_same_month(client, auth_headers, db_session):
    bank_id = await _create_bank_account(client, auth_headers)
    await _backdate_created_at(db_session, BankAccount, bank_id, datetime(2025, 12, 1))

    await scheduler.run_scheduled_tasks(db_session, as_of=date(2026, 1, 5))
    counts = await scheduler.run_scheduled_tasks(db_session, as_of=date(2026, 1, 20))

    assert counts["bank_interest_applied"] == 0
    account_response = await client.get(f"/api/v1/bank-accounts/{bank_id}", headers=auth_headers)
    assert float(account_response.json()["current_balance"]) == 1010.00


async def test_bank_account_with_no_interest_rate_is_never_due(client, auth_headers, db_session):
    await _create_bank_account(
        client,
        auth_headers,
        payload={
            "account_name": "No-interest checking",
            "account_type": "checking",
            "principal": "500.00",
        },
    )

    counts = await scheduler.run_scheduled_tasks(db_session, as_of=date(2026, 1, 5))
    assert counts["bank_interest_applied"] == 0


async def test_bank_interest_catches_up_multiple_months_with_sequential_compounding(
    client, auth_headers, db_session
):
    bank_id = await _create_bank_account(client, auth_headers)
    await _backdate_created_at(db_session, BankAccount, bank_id, datetime(2025, 11, 1))

    # First due date is 2025-11-01 + 1mo = 2025-12-01; as_of 2026-02-01 covers Dec, Jan,
    # Feb - 3 months, each compounding on the previous month's already-credited interest,
    # not 3 independent 1% bumps on the original 1000.00.
    counts = await scheduler.run_scheduled_tasks(db_session, as_of=date(2026, 2, 1))
    assert counts["bank_interest_applied"] == 3

    account_response = await client.get(f"/api/v1/bank-accounts/{bank_id}", headers=auth_headers)
    # 1000.00 -> 1010.00 (+10.00) -> 1020.10 (+10.10) -> 1030.30 (+10.20, rounded)
    assert float(account_response.json()["current_balance"]) == 1030.30

    transactions_response = await client.get(
        "/api/v1/transactions", params={"transaction_type": "interest"}, headers=auth_headers
    )
    transactions = sorted(transactions_response.json(), key=lambda t: t["transaction_date"])
    assert [t["transaction_date"] for t in transactions] == ["2025-12-01", "2026-01-01", "2026-02-01"]
    assert [float(t["amount"]) for t in transactions] == [10.00, 10.10, 10.20]


# --- Retirement/education expected return -------------------------------------------------


async def test_retirement_expected_return_is_applied_monthly(client, auth_headers, db_session):
    retirement_id = await _create_retirement_account(client, auth_headers)
    await _backdate_created_at(db_session, RetirementAccount, retirement_id, datetime(2025, 12, 1))

    counts = await scheduler.run_scheduled_tasks(db_session, as_of=date(2026, 1, 5))
    assert counts["retirement_interest_applied"] == 1

    account_response = await client.get(
        f"/api/v1/retirement-accounts/{retirement_id}", headers=auth_headers
    )
    # 1000 * (0.12/12) = 10.00
    assert float(account_response.json()["balance"]) == 1010.00


async def test_education_expected_return_is_applied_monthly(client, auth_headers, db_session):
    education_id = await _create_education_account(client, auth_headers)
    await _backdate_created_at(db_session, EducationAccount, education_id, datetime(2025, 12, 1))

    counts = await scheduler.run_scheduled_tasks(db_session, as_of=date(2026, 1, 5))
    assert counts["education_interest_applied"] == 1

    account_response = await client.get(f"/api/v1/education-accounts/{education_id}", headers=auth_headers)
    assert float(account_response.json()["balance"]) == 1010.00


# --- Recurring retirement/education contributions -----------------------------------------


async def test_due_recurring_retirement_contribution_is_auto_posted_with_employer_match(
    client, auth_headers, db_session
):
    retirement_id = await _create_retirement_account(client, auth_headers, payload=FOUR_OH_ONE_K_PAYLOAD)
    await client.post(
        f"/api/v1/retirement-accounts/{retirement_id}/recurring-contributions",
        json={"amount": "500.00", "frequency": "monthly", "start_date": "2026-01-01"},
        headers=auth_headers,
    )

    counts = await scheduler.run_scheduled_tasks(db_session, as_of=date(2026, 1, 1))
    assert counts["retirement_contributions_posted"] == 1

    account_response = await client.get(
        f"/api/v1/retirement-accounts/{retirement_id}", headers=auth_headers
    )
    body = account_response.json()
    # 500 employee + 50% match on the matchable 6% of 120k salary = min(500, 7200)*0.5 = 250
    assert float(body["balance"]) == 10750.00
    assert float(body["contribution_ytd"]) == 500.00


async def test_recurring_retirement_contribution_not_re_posted_same_day(client, auth_headers, db_session):
    retirement_id = await _create_retirement_account(client, auth_headers)
    await client.post(
        f"/api/v1/retirement-accounts/{retirement_id}/recurring-contributions",
        json={"amount": "300.00", "frequency": "monthly", "start_date": "2026-01-01"},
        headers=auth_headers,
    )

    await scheduler.run_scheduled_tasks(db_session, as_of=date(2026, 1, 1))
    counts = await scheduler.run_scheduled_tasks(db_session, as_of=date(2026, 1, 1))

    assert counts["retirement_contributions_posted"] == 0


async def test_retirement_contribution_catches_up_multiple_missed_months(client, auth_headers, db_session):
    retirement_id = await _create_retirement_account(client, auth_headers, payload=FOUR_OH_ONE_K_PAYLOAD)
    await client.post(
        f"/api/v1/retirement-accounts/{retirement_id}/recurring-contributions",
        json={"amount": "500.00", "frequency": "monthly", "start_date": "2026-01-01"},
        headers=auth_headers,
    )

    counts = await scheduler.run_scheduled_tasks(db_session, as_of=date(2026, 4, 1))

    # Jan, Feb, Mar, Apr = 4 occurrences.
    assert counts["retirement_contributions_posted"] == 4
    account_response = await client.get(
        f"/api/v1/retirement-accounts/{retirement_id}", headers=auth_headers
    )
    assert float(account_response.json()["contribution_ytd"]) == 2000.00  # 500 * 4


async def test_due_recurring_education_contribution_is_auto_posted(client, auth_headers, db_session):
    education_id = await _create_education_account(client, auth_headers)
    await client.post(
        f"/api/v1/education-accounts/{education_id}/recurring-contributions",
        json={"amount": "200.00", "frequency": "monthly", "start_date": "2026-01-01"},
        headers=auth_headers,
    )

    counts = await scheduler.run_scheduled_tasks(db_session, as_of=date(2026, 1, 1))
    assert counts["education_contributions_posted"] == 1

    account_response = await client.get(f"/api/v1/education-accounts/{education_id}", headers=auth_headers)
    body = account_response.json()
    assert float(body["balance"]) == 1200.00
    assert float(body["contribution_ytd"]) == 200.00


# --- Recurring expenses --------------------------------------------------------------------


async def test_recurring_expense_creation_day_is_not_double_counted(client, auth_headers, db_session):
    bank_id = await _create_bank_account(client, auth_headers)
    await client.post(
        "/api/v1/expenses",
        json={
            "merchant_name": "Corner Grocer",
            "amount": "150.00",
            "expense_date": "2026-01-01",
            "is_recurring": True,
            "recurrence_pattern": "monthly",
            "bank_account_id": bank_id,
        },
        headers=auth_headers,
    )

    counts = await scheduler.run_scheduled_tasks(db_session, as_of=date(2026, 1, 1))
    assert counts["expenses_created"] == 0

    expenses_response = await client.get("/api/v1/expenses", headers=auth_headers)
    assert len(expenses_response.json()) == 1


async def test_recurring_expense_auto_creates_next_occurrence_and_debits_linked_account(
    client, auth_headers, db_session
):
    bank_id = await _create_bank_account(client, auth_headers)
    await client.post(
        "/api/v1/expenses",
        json={
            "merchant_name": "Corner Grocer",
            "amount": "150.00",
            "expense_date": "2026-01-01",
            "is_recurring": True,
            "recurrence_pattern": "monthly",
            "bank_account_id": bank_id,
        },
        headers=auth_headers,
    )

    counts = await scheduler.run_scheduled_tasks(db_session, as_of=date(2026, 2, 1))
    assert counts["expenses_created"] == 1

    expenses_response = await client.get("/api/v1/expenses", headers=auth_headers)
    expenses = expenses_response.json()
    assert len(expenses) == 2
    new_occurrence = next(e for e in expenses if e["expense_date"] == "2026-02-01")
    assert new_occurrence["is_recurring"] is False
    assert float(new_occurrence["amount"]) == 150.00

    account_response = await client.get(f"/api/v1/bank-accounts/{bank_id}", headers=auth_headers)
    assert float(account_response.json()["current_balance"]) == 850.00  # 1000 - 150


async def test_recurring_expense_catches_up_multiple_missed_months(client, auth_headers, db_session):
    bank_id = await _create_bank_account(client, auth_headers)
    await client.post(
        "/api/v1/expenses",
        json={
            "merchant_name": "Corner Grocer",
            "amount": "150.00",
            "expense_date": "2026-01-01",
            "is_recurring": True,
            "recurrence_pattern": "monthly",
            "bank_account_id": bank_id,
        },
        headers=auth_headers,
    )

    counts = await scheduler.run_scheduled_tasks(db_session, as_of=date(2026, 4, 1))

    # First due occurrence is 2026-02-01 (the rule row itself already counts as the
    # January occurrence) - Feb, Mar, Apr = 3 occurrences.
    assert counts["expenses_created"] == 3

    expenses_response = await client.get("/api/v1/expenses", headers=auth_headers)
    assert len(expenses_response.json()) == 4  # 1 rule row + 3 auto-created occurrences

    account_response = await client.get(f"/api/v1/bank-accounts/{bank_id}", headers=auth_headers)
    assert float(account_response.json()["current_balance"]) == 550.00  # 1000 - 150*3


async def test_recurring_expense_with_no_bank_account_does_not_touch_any_balance(
    client, auth_headers, db_session
):
    bank_id = await _create_bank_account(client, auth_headers)
    await client.post(
        "/api/v1/expenses",
        json={
            "merchant_name": "Streaming Service",
            "amount": "15.00",
            "expense_date": "2026-01-01",
            "is_recurring": True,
            "recurrence_pattern": "monthly",
        },
        headers=auth_headers,
    )

    await scheduler.run_scheduled_tasks(db_session, as_of=date(2026, 2, 1))

    account_response = await client.get(f"/api/v1/bank-accounts/{bank_id}", headers=auth_headers)
    assert float(account_response.json()["current_balance"]) == 1000.00


async def test_one_time_expense_is_never_picked_up_by_the_scheduler(client, auth_headers, db_session):
    await client.post(
        "/api/v1/expenses",
        json={"merchant_name": "One-off purchase", "amount": "40.00", "expense_date": "2026-01-01"},
        headers=auth_headers,
    )

    counts = await scheduler.run_scheduled_tasks(db_session, as_of=date(2026, 3, 1))
    assert counts["expenses_created"] == 0


# --- POST /scheduler/run (manual trigger) ------------------------------------------------


async def test_run_scheduler_requires_authentication(client):
    response = await client.post("/api/v1/scheduler/run")

    assert response.status_code == 401


async def test_run_scheduler_endpoint_catches_up_a_due_income(client, auth_headers):
    bank_id = await _create_bank_account(client, auth_headers)
    await client.post(
        "/api/v1/income",
        json={
            "name": "Paycheck",
            "amount": "2000.00",
            "is_recurring": True,
            "frequency": "monthly",
            "start_date": "2026-01-01",
            "allocations": [
                {"destination_type": "bank_account", "destination_id": bank_id, "percentage": "100"}
            ],
        },
        headers=auth_headers,
    )

    response = await client.post("/api/v1/scheduler/run", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    # start_date=2026-01-01 is always due by the time this test runs (real wall-clock
    # "today" is well past that fixed date), so this doesn't need to backdate anything.
    assert body["incomes_posted"] >= 1

    account_response = await client.get(f"/api/v1/bank-accounts/{bank_id}", headers=auth_headers)
    assert float(account_response.json()["current_balance"]) > 1000.00
