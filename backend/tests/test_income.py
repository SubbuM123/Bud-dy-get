"""API-level coverage for the Income module: creating recurring/one-time income with
percentage allocations, auto-posting a Transaction for a one-time income at creation time,
logging a real occurrence of a recurring income (splitting across destinations, with and
without an amount/date override), destination-ownership validation, replacing an income's
allocations wholesale, and confirming a deleted Income keeps its already-posted
Transaction history. Runs against SQLite (see conftest.py). The RSU vesting cases at the
bottom monkeypatch services.stock_price.get_current_price for a deterministic vest price -
no real network calls, matching tests/test_investments.py's approach.
"""

from decimal import Decimal

from app.services import stock_price

BANK_PAYLOAD = {
    "account_name": "Checking",
    "account_type": "checking",
    "principal": "1000.00",
    "interest_rate": "0.01",
    "compounding_frequency": "monthly",
}

IRA_PAYLOAD = {
    "account_name": "Roth IRA",
    "account_type": "roth_ira",
    "balance": "0.00",
    "expected_return_rate": "0.07",
}


async def _create_bank_account(client, headers, payload=None):
    response = await client.post(
        "/api/v1/bank-accounts", json=payload or BANK_PAYLOAD, headers=headers
    )
    return response.json()["id"]


async def _create_retirement_account(client, headers):
    response = await client.post(
        "/api/v1/retirement-accounts", json=IRA_PAYLOAD, headers=headers
    )
    return response.json()["id"]


async def _create_stock_position(client, headers, ticker="ACME"):
    response = await client.post(
        "/api/v1/investments/stocks", json={"ticker_symbol": ticker}, headers=headers
    )
    return response.json()["id"]


async def test_create_income_requires_authentication(client):
    response = await client.post(
        "/api/v1/income",
        json={
            "name": "Salary",
            "amount": "1000",
            "is_recurring": False,
            "income_date": "2026-03-01",
            "allocations": [
                {"destination_type": "bank_account", "destination_id": "does-not-matter", "percentage": "100"}
            ],
        },
    )

    assert response.status_code == 401


async def test_allocation_percentages_must_sum_to_100(client, auth_headers):
    bank_id = await _create_bank_account(client, auth_headers)

    response = await client.post(
        "/api/v1/income",
        json={
            "name": "Salary",
            "amount": "1000",
            "is_recurring": False,
            "income_date": "2026-03-01",
            "allocations": [
                {"destination_type": "bank_account", "destination_id": bank_id, "percentage": "60"},
                {"destination_type": "bank_account", "destination_id": bank_id, "percentage": "30"},
            ],
        },
        headers=auth_headers,
    )

    assert response.status_code == 422


async def test_create_one_time_income_auto_logs_and_posts_transaction(client, auth_headers):
    bank_id = await _create_bank_account(client, auth_headers)

    response = await client.post(
        "/api/v1/income",
        json={
            "name": "Tax Refund",
            "amount": "500.00",
            "is_recurring": False,
            "income_date": "2026-03-01",
            "allocations": [
                {"destination_type": "bank_account", "destination_id": bank_id, "percentage": "100"}
            ],
        },
        headers=auth_headers,
    )
    assert response.status_code == 201

    transactions_response = await client.get(
        "/api/v1/transactions", params={"transaction_type": "income"}, headers=auth_headers
    )
    transactions = transactions_response.json()
    assert len(transactions) == 1
    assert float(transactions[0]["amount"]) == 500.00

    account_response = await client.get(f"/api/v1/bank-accounts/{bank_id}", headers=auth_headers)
    assert float(account_response.json()["current_balance"]) == 1500.00  # 1000 starting + 500


async def test_create_recurring_income_does_not_auto_post(client, auth_headers):
    bank_id = await _create_bank_account(client, auth_headers)

    response = await client.post(
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
    assert response.status_code == 201

    transactions_response = await client.get("/api/v1/transactions", headers=auth_headers)
    assert transactions_response.json() == []

    account_response = await client.get(f"/api/v1/bank-accounts/{bank_id}", headers=auth_headers)
    assert float(account_response.json()["current_balance"]) == 1000.00  # unchanged


async def test_log_income_splits_across_two_destinations(client, auth_headers):
    bank_id = await _create_bank_account(client, auth_headers)
    retirement_id = await _create_retirement_account(client, auth_headers)

    create_response = await client.post(
        "/api/v1/income",
        json={
            "name": "Paycheck",
            "amount": "2000.00",
            "is_recurring": True,
            "frequency": "monthly",
            "start_date": "2026-01-01",
            "allocations": [
                {"destination_type": "bank_account", "destination_id": bank_id, "percentage": "60"},
                {"destination_type": "retirement_account", "destination_id": retirement_id, "percentage": "40"},
            ],
        },
        headers=auth_headers,
    )
    income_id = create_response.json()["id"]

    log_response = await client.post(
        f"/api/v1/income/{income_id}/log", json={}, headers=auth_headers
    )

    assert log_response.status_code == 201
    body = log_response.json()
    assert len(body["transactions"]) == 2
    total_posted = sum(float(t["amount"]) for t in body["transactions"])
    assert total_posted == 2000.00

    bank_response = await client.get(f"/api/v1/bank-accounts/{bank_id}", headers=auth_headers)
    assert float(bank_response.json()["current_balance"]) == 1000.00 + 1200.00  # 60% of 2000

    retirement_response = await client.get(
        f"/api/v1/retirement-accounts/{retirement_id}", headers=auth_headers
    )
    assert float(retirement_response.json()["balance"]) == 0.00 + 800.00  # 40% of 2000


async def test_log_income_with_amount_and_date_override(client, auth_headers):
    bank_id = await _create_bank_account(client, auth_headers)

    create_response = await client.post(
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
    income_id = create_response.json()["id"]

    log_response = await client.post(
        f"/api/v1/income/{income_id}/log",
        json={"amount": "3000.00", "log_date": "2026-05-15"},
        headers=auth_headers,
    )

    assert log_response.status_code == 201
    body = log_response.json()
    assert float(body["total_amount"]) == 3000.00
    assert body["log_date"] == "2026-05-15"
    assert len(body["transactions"]) == 1
    assert float(body["transactions"][0]["amount"]) == 3000.00
    assert body["transactions"][0]["transaction_date"] == "2026-05-15"


async def test_destination_ownership_is_validated(client, auth_headers):
    await client.post("/api/v1/auth/register", json={"email": "other@example.com", "password": "pw123456"})
    other_login = await client.post(
        "/api/v1/auth/login", json={"email": "other@example.com", "password": "pw123456"}
    )
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}
    other_bank_id = await _create_bank_account(client, other_headers)

    response = await client.post(
        "/api/v1/income",
        json={
            "name": "Paycheck",
            "amount": "2000.00",
            "is_recurring": True,
            "frequency": "monthly",
            "start_date": "2026-01-01",
            "allocations": [
                {"destination_type": "bank_account", "destination_id": other_bank_id, "percentage": "100"}
            ],
        },
        headers=auth_headers,
    )

    assert response.status_code == 400


async def test_replace_income_allocations(client, auth_headers):
    bank_id = await _create_bank_account(client, auth_headers)
    retirement_id = await _create_retirement_account(client, auth_headers)

    create_response = await client.post(
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
    income_id = create_response.json()["id"]

    response = await client.put(
        f"/api/v1/income/{income_id}/allocations",
        json={
            "allocations": [
                {"destination_type": "bank_account", "destination_id": bank_id, "percentage": "50"},
                {"destination_type": "retirement_account", "destination_id": retirement_id, "percentage": "50"},
            ]
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    allocations = response.json()["allocations"]
    assert len(allocations) == 2
    assert {float(a["percentage"]) for a in allocations} == {50.0}


async def test_log_income_with_pre_tax_allocation_posts_retirement_contribution(client, auth_headers):
    """Phase 4.6 "Option A" (see docs/phase4.6-money-flow-plan.md's Next Steps §8): an
    allocation into a retirement account marked source_type: pre_tax_salary should post a
    RETIREMENT_CONTRIBUTION (which also bumps contribution_ytd), not a plain INCOME
    transaction - closing the gap where recording a payroll 401(k) deduction used to need
    a second, separate manual /contribute call."""
    bank_id = await _create_bank_account(client, auth_headers)
    retirement_id = await _create_retirement_account(client, auth_headers)

    create_response = await client.post(
        "/api/v1/income",
        json={
            "name": "Paycheck",
            "amount": "2000.00",
            "is_recurring": True,
            "frequency": "monthly",
            "start_date": "2026-01-01",
            "allocations": [
                {"destination_type": "bank_account", "destination_id": bank_id, "percentage": "80"},
                {
                    "destination_type": "retirement_account",
                    "destination_id": retirement_id,
                    "percentage": "20",
                    "source_type": "pre_tax_salary",
                },
            ],
        },
        headers=auth_headers,
    )
    income_id = create_response.json()["id"]

    log_response = await client.post(
        f"/api/v1/income/{income_id}/log", json={}, headers=auth_headers
    )
    assert log_response.status_code == 201

    transactions = log_response.json()["transactions"]
    retirement_transaction = next(t for t in transactions if t["account_type"] == "retirement_account")
    assert retirement_transaction["transaction_type"] == "retirement_contribution"
    assert retirement_transaction["source_type"] == "pre_tax_salary"
    assert float(retirement_transaction["amount"]) == 400.00  # 20% of 2000

    bank_transaction = next(t for t in transactions if t["account_type"] == "bank_account")
    assert bank_transaction["transaction_type"] == "income"

    retirement_response = await client.get(
        f"/api/v1/retirement-accounts/{retirement_id}", headers=auth_headers
    )
    retirement_body = retirement_response.json()
    assert float(retirement_body["balance"]) == 400.00
    assert float(retirement_body["contribution_ytd"]) == 400.00  # counts against IRS limits


async def test_income_allocation_pre_tax_salary_rejected_for_bank_destination(client, auth_headers):
    bank_id = await _create_bank_account(client, auth_headers)

    response = await client.post(
        "/api/v1/income",
        json={
            "name": "Paycheck",
            "amount": "2000.00",
            "is_recurring": True,
            "frequency": "monthly",
            "start_date": "2026-01-01",
            "allocations": [
                {
                    "destination_type": "bank_account",
                    "destination_id": bank_id,
                    "percentage": "100",
                    "source_type": "pre_tax_salary",
                }
            ],
        },
        headers=auth_headers,
    )

    assert response.status_code == 422


async def test_delete_income_keeps_past_transactions(client, auth_headers):
    bank_id = await _create_bank_account(client, auth_headers)

    create_response = await client.post(
        "/api/v1/income",
        json={
            "name": "Tax Refund",
            "amount": "500.00",
            "is_recurring": False,
            "income_date": "2026-03-01",
            "allocations": [
                {"destination_type": "bank_account", "destination_id": bank_id, "percentage": "100"}
            ],
        },
        headers=auth_headers,
    )
    income_id = create_response.json()["id"]

    delete_response = await client.delete(f"/api/v1/income/{income_id}", headers=auth_headers)
    assert delete_response.status_code == 204

    transactions_response = await client.get("/api/v1/transactions", headers=auth_headers)
    transactions = transactions_response.json()
    assert len(transactions) == 1
    assert transactions[0]["income_id"] is None


async def test_log_income_with_stock_allocation_vests_shares_immediately(
    client, auth_headers, monkeypatch
):
    monkeypatch.setattr(stock_price, "get_current_price", lambda ticker: Decimal("50.00"))
    position_id = await _create_stock_position(client, auth_headers)

    create_response = await client.post(
        "/api/v1/income",
        json={
            "name": "RSU Grant",
            "amount": "1.00",
            "is_recurring": True,
            "frequency": "monthly",
            "start_date": "2026-01-01",
            "allocations": [
                {
                    "destination_type": "stock_position",
                    "destination_id": position_id,
                    "percentage": "100",
                    "rsu_vesting_type": "immediate",
                    "rsu_total_shares": "100",
                }
            ],
        },
        headers=auth_headers,
    )
    assert create_response.status_code == 201
    income_id = create_response.json()["id"]

    log_response = await client.post(
        f"/api/v1/income/{income_id}/log", json={}, headers=auth_headers
    )
    assert log_response.status_code == 201
    transactions = log_response.json()["transactions"]
    assert len(transactions) == 1
    assert transactions[0]["transaction_type"] == "rsu_vest"
    assert float(transactions[0]["amount"]) == 5000.00  # 100 shares * $50

    position_response = await client.get(
        f"/api/v1/investments/stocks/{position_id}", headers=auth_headers
    )
    position = position_response.json()
    assert float(position["shares"]) == 100.0
    assert float(position["average_cost_per_share"]) == 50.00


async def test_log_income_with_stock_allocation_vests_shares_graded(
    client, auth_headers, monkeypatch
):
    monkeypatch.setattr(stock_price, "get_current_price", lambda ticker: Decimal("50.00"))
    position_id = await _create_stock_position(client, auth_headers)

    create_response = await client.post(
        "/api/v1/income",
        json={
            "name": "RSU Grant",
            "amount": "1.00",
            "is_recurring": True,
            "frequency": "monthly",
            "start_date": "2020-01-01",  # far enough in the past that a 1-year graded
            "allocations": [               # schedule is fully vested by the time this runs
                {
                    "destination_type": "stock_position",
                    "destination_id": position_id,
                    "percentage": "100",
                    "rsu_vesting_type": "graded",
                    "rsu_vesting_years": 1,
                    "rsu_total_shares": "100",
                }
            ],
        },
        headers=auth_headers,
    )
    income_id = create_response.json()["id"]

    log_response = await client.post(
        f"/api/v1/income/{income_id}/log", json={}, headers=auth_headers
    )
    assert log_response.status_code == 201
    assert len(log_response.json()["transactions"]) == 1

    position_response = await client.get(
        f"/api/v1/investments/stocks/{position_id}", headers=auth_headers
    )
    assert float(position_response.json()["shares"]) == 100.0


async def test_log_income_with_stock_allocation_vests_nothing_before_cliff(
    client, auth_headers, monkeypatch
):
    monkeypatch.setattr(stock_price, "get_current_price", lambda ticker: Decimal("50.00"))
    position_id = await _create_stock_position(client, auth_headers)

    create_response = await client.post(
        "/api/v1/income",
        json={
            "name": "RSU Grant",
            "amount": "1.00",
            "is_recurring": True,
            "frequency": "monthly",
            "start_date": "2026-01-01",
            "allocations": [
                {
                    "destination_type": "stock_position",
                    "destination_id": position_id,
                    "percentage": "100",
                    "rsu_vesting_type": "cliff",
                    "rsu_vesting_years": 1,
                    "rsu_cliff_date": "2099-01-01",  # far future - never reached in a real run
                    "rsu_total_shares": "100",
                }
            ],
        },
        headers=auth_headers,
    )
    income_id = create_response.json()["id"]

    log_response = await client.post(
        f"/api/v1/income/{income_id}/log", json={}, headers=auth_headers
    )
    assert log_response.status_code == 201
    assert log_response.json()["transactions"] == []

    position_response = await client.get(
        f"/api/v1/investments/stocks/{position_id}", headers=auth_headers
    )
    assert float(position_response.json()["shares"]) == 0.0


async def test_income_allocation_rsu_fields_require_stock_position_destination(
    client, auth_headers
):
    bank_id = await _create_bank_account(client, auth_headers)

    response = await client.post(
        "/api/v1/income",
        json={
            "name": "RSU Grant",
            "amount": "1.00",
            "is_recurring": True,
            "frequency": "monthly",
            "start_date": "2026-01-01",
            "allocations": [
                {
                    "destination_type": "bank_account",
                    "destination_id": bank_id,
                    "percentage": "100",
                    "rsu_vesting_type": "immediate",
                    "rsu_total_shares": "100",
                }
            ],
        },
        headers=auth_headers,
    )

    assert response.status_code == 422


async def test_income_allocation_rsu_vesting_requires_total_shares(client, auth_headers):
    position_id = await _create_stock_position(client, auth_headers)

    response = await client.post(
        "/api/v1/income",
        json={
            "name": "RSU Grant",
            "amount": "1.00",
            "is_recurring": True,
            "frequency": "monthly",
            "start_date": "2026-01-01",
            "allocations": [
                {
                    "destination_type": "stock_position",
                    "destination_id": position_id,
                    "percentage": "100",
                    "rsu_vesting_type": "immediate",
                }
            ],
        },
        headers=auth_headers,
    )

    assert response.status_code == 422


async def test_income_allocation_graded_rsu_requires_vesting_years(client, auth_headers):
    position_id = await _create_stock_position(client, auth_headers)

    response = await client.post(
        "/api/v1/income",
        json={
            "name": "RSU Grant",
            "amount": "1.00",
            "is_recurring": True,
            "frequency": "monthly",
            "start_date": "2026-01-01",
            "allocations": [
                {
                    "destination_type": "stock_position",
                    "destination_id": position_id,
                    "percentage": "100",
                    "rsu_vesting_type": "graded",
                    "rsu_total_shares": "100",
                }
            ],
        },
        headers=auth_headers,
    )

    assert response.status_code == 422


async def test_income_allocation_cliff_rsu_requires_cliff_date(client, auth_headers):
    position_id = await _create_stock_position(client, auth_headers)

    response = await client.post(
        "/api/v1/income",
        json={
            "name": "RSU Grant",
            "amount": "1.00",
            "is_recurring": True,
            "frequency": "monthly",
            "start_date": "2026-01-01",
            "allocations": [
                {
                    "destination_type": "stock_position",
                    "destination_id": position_id,
                    "percentage": "100",
                    "rsu_vesting_type": "cliff",
                    "rsu_total_shares": "100",
                }
            ],
        },
        headers=auth_headers,
    )

    assert response.status_code == 422
