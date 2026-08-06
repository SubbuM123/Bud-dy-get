"""API-level coverage for the Bank Account Simulator endpoints: create/list an account,
run a growth simulation, and confirm a recurring action feeds into that simulation. Runs
against SQLite (see conftest.py) so it can't catch the Postgres enum-label mismatch fixed
in the same session - that's covered separately in test_bank_account_enums.py.
"""

ACCOUNT_PAYLOAD = {
    "account_name": "Emergency Fund",
    "account_type": "savings",
    "principal": "10000.00",
    "interest_rate": "0.04",
    "compounding_frequency": "monthly",
}


async def test_create_account_requires_authentication(client):
    response = await client.post("/api/v1/bank-accounts", json=ACCOUNT_PAYLOAD)

    assert response.status_code == 401


async def test_create_account_seeds_current_balance_from_principal(client, auth_headers):
    response = await client.post(
        "/api/v1/bank-accounts", json=ACCOUNT_PAYLOAD, headers=auth_headers
    )

    assert response.status_code == 201
    body = response.json()
    assert body["account_type"] == "savings"
    assert body["compounding_frequency"] == "monthly"
    assert float(body["current_balance"]) == float(body["principal"]) == 10000.00


async def test_list_accounts_returns_the_created_account(client, auth_headers):
    await client.post("/api/v1/bank-accounts", json=ACCOUNT_PAYLOAD, headers=auth_headers)

    response = await client.get("/api/v1/bank-accounts", headers=auth_headers)

    assert response.status_code == 200
    accounts = response.json()
    assert len(accounts) == 1
    assert accounts[0]["account_name"] == "Emergency Fund"


async def test_accounts_are_scoped_to_their_owner(client):
    await client.post("/api/v1/auth/register", json={"email": "a@example.com", "password": "pw123456"})
    a_login = await client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "pw123456"})
    a_headers = {"Authorization": f"Bearer {a_login.json()['access_token']}"}

    await client.post("/api/v1/auth/register", json={"email": "b@example.com", "password": "pw123456"})
    b_login = await client.post("/api/v1/auth/login", json={"email": "b@example.com", "password": "pw123456"})
    b_headers = {"Authorization": f"Bearer {b_login.json()['access_token']}"}

    await client.post("/api/v1/bank-accounts", json=ACCOUNT_PAYLOAD, headers=a_headers)

    response = await client.get("/api/v1/bank-accounts", headers=b_headers)

    assert response.status_code == 200
    assert response.json() == []


async def test_simulate_growth_returns_a_projection_for_every_month(client, auth_headers):
    create_response = await client.post(
        "/api/v1/bank-accounts", json=ACCOUNT_PAYLOAD, headers=auth_headers
    )
    account_id = create_response.json()["id"]

    response = await client.post(
        f"/api/v1/bank-accounts/{account_id}/simulate",
        json={"months": 12, "include_recurring": True},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    # Month 0 (starting snapshot) plus one point per simulated month.
    assert len(body["projections"]) == 13
    assert float(body["final_balance"]) > float(ACCOUNT_PAYLOAD["principal"])


async def test_recurring_deposit_increases_the_simulated_final_balance(client, auth_headers):
    create_response = await client.post(
        "/api/v1/bank-accounts", json=ACCOUNT_PAYLOAD, headers=auth_headers
    )
    account_id = create_response.json()["id"]

    baseline = await client.post(
        f"/api/v1/bank-accounts/{account_id}/simulate",
        json={"months": 6, "include_recurring": True},
        headers=auth_headers,
    )

    action_response = await client.post(
        f"/api/v1/bank-accounts/{account_id}/recurring-actions",
        json={
            "action_type": "deposit",
            "amount": "500.00",
            "frequency_value": 1,
            "frequency_unit": "months",
            "start_date": "2026-01-01",
        },
        headers=auth_headers,
    )
    assert action_response.status_code == 201

    with_deposit = await client.post(
        f"/api/v1/bank-accounts/{account_id}/simulate",
        json={"months": 6, "include_recurring": True},
        headers=auth_headers,
    )

    assert float(with_deposit.json()["final_balance"]) > float(
        baseline.json()["final_balance"]
    )


async def test_update_bank_account_patches_only_the_given_fields(client, auth_headers):
    create_response = await client.post(
        "/api/v1/bank-accounts", json=ACCOUNT_PAYLOAD, headers=auth_headers
    )
    account_id = create_response.json()["id"]

    response = await client.put(
        f"/api/v1/bank-accounts/{account_id}",
        json={"account_name": "Renamed Fund", "interest_rate": "0.05"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["account_name"] == "Renamed Fund"
    assert float(body["interest_rate"]) == 0.05
    # Untouched fields are unchanged.
    assert body["account_type"] == "savings"
    assert float(body["principal"]) == 10000.00


async def test_update_bank_account_can_set_cd_auto_renew(client, auth_headers):
    cd_payload = {
        "account_name": "3yr CD",
        "account_type": "cd",
        "principal": "5000.00",
        "interest_rate": "0.03",
        "compounding_frequency": "monthly",
        "cd_start_date": "2026-01-01",
        "cd_term_months": 36,
    }
    create_response = await client.post(
        "/api/v1/bank-accounts", json=cd_payload, headers=auth_headers
    )
    account_id = create_response.json()["id"]
    assert create_response.json()["cd_auto_renew"] is False

    response = await client.put(
        f"/api/v1/bank-accounts/{account_id}",
        json={"cd_auto_renew": True},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["cd_auto_renew"] is True


async def test_simulate_growth_includes_recurring_income_allocation(client, auth_headers):
    create_response = await client.post(
        "/api/v1/bank-accounts", json=ACCOUNT_PAYLOAD, headers=auth_headers
    )
    account_id = create_response.json()["id"]

    await client.post(
        "/api/v1/income",
        json={
            "name": "Paycheck",
            "amount": "1000.00",
            "is_recurring": True,
            "frequency": "biweekly",
            "start_date": "2026-01-01",
            "allocations": [
                {"destination_type": "bank_account", "destination_id": account_id, "percentage": "100"}
            ],
        },
        headers=auth_headers,
    )

    with_income = await client.post(
        f"/api/v1/bank-accounts/{account_id}/simulate",
        json={"months": 1, "include_recurring": True},
        headers=auth_headers,
    )
    assert with_income.status_code == 200
    # biweekly $1000 folds to a monthly-equivalent of 1000 * 26/12 = 2166.67 - see
    # services/income_allocator.py's _OCCURRENCES_PER_MONTH.
    assert float(with_income.json()["projections"][-1]["deposits"]) == 2166.67

    without_income = await client.post(
        f"/api/v1/bank-accounts/{account_id}/simulate",
        json={"months": 1, "include_recurring": False},
        headers=auth_headers,
    )
    assert float(without_income.json()["projections"][-1]["deposits"]) == 0.00


async def test_simulate_growth_includes_recurring_expense_withdrawal(client, auth_headers):
    create_response = await client.post(
        "/api/v1/bank-accounts", json=ACCOUNT_PAYLOAD, headers=auth_headers
    )
    account_id = create_response.json()["id"]

    await client.post(
        "/api/v1/expenses",
        json={
            "merchant_name": "Landlord",
            "amount": "1500.00",
            "expense_date": "2026-01-01",
            "bank_account_id": account_id,
            "is_recurring": True,
            "recurrence_pattern": "monthly",
        },
        headers=auth_headers,
    )

    response = await client.post(
        f"/api/v1/bank-accounts/{account_id}/simulate",
        json={"months": 1, "include_recurring": True},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert float(response.json()["projections"][-1]["withdrawals"]) == 1500.00


async def test_update_recurring_action_can_change_category_amount_and_end_date(
    client, auth_headers
):
    create_response = await client.post(
        "/api/v1/bank-accounts", json=ACCOUNT_PAYLOAD, headers=auth_headers
    )
    account_id = create_response.json()["id"]

    action_response = await client.post(
        f"/api/v1/bank-accounts/{account_id}/recurring-actions",
        json={
            "action_type": "deposit",
            "amount": "500.00",
            "frequency_value": 1,
            "frequency_unit": "months",
            "start_date": "2026-01-01",
        },
        headers=auth_headers,
    )
    action_id = action_response.json()["id"]
    assert action_response.json()["category"] is None
    assert action_response.json()["end_date"] is None

    response = await client.put(
        f"/api/v1/bank-accounts/recurring-actions/{action_id}",
        json={"category": "salary", "amount": "600.00", "end_date": "2027-01-01"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["category"] == "salary"
    assert float(body["amount"]) == 600.00
    assert body["end_date"] == "2027-01-01"
    # start_date is intentionally not editable - unchanged.
    assert body["start_date"] == "2026-01-01"
