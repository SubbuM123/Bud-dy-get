"""API-level coverage for the Retirement Accounts endpoints: create/list/scope an account,
run a growth simulation with employer match, fetch contribution limits driven by the
user's profile, and record a contribution that's rejected once it exceeds the remaining
limit. Runs against SQLite (see conftest.py) - the Postgres enum-label mismatch class of
bug is covered separately in test_retirement_account_enums.py.
"""

IRA_PAYLOAD = {
    "account_name": "Roth IRA",
    "account_type": "roth_ira",
    "balance": "5000.00",
    "expected_return_rate": "0.07",
}

FOUR_OH_ONE_K_PAYLOAD = {
    "account_name": "Acme Corp 401k",
    "account_type": "traditional_401k",
    "balance": "20000.00",
    "employer_name": "Acme Corp",
    "annual_salary": "120000.00",
    "employer_match_percent": "0.5",
    "employer_match_limit_percent": "0.06",
    "expected_return_rate": "0.07",
}


async def test_create_account_requires_authentication(client):
    response = await client.post("/api/v1/retirement-accounts", json=IRA_PAYLOAD)

    assert response.status_code == 401


async def test_create_and_list_retirement_account(client, auth_headers):
    create_response = await client.post(
        "/api/v1/retirement-accounts", json=IRA_PAYLOAD, headers=auth_headers
    )
    assert create_response.status_code == 201
    body = create_response.json()
    assert body["account_type"] == "roth_ira"
    assert float(body["balance"]) == 5000.00
    assert float(body["contribution_ytd"]) == 0.0

    list_response = await client.get("/api/v1/retirement-accounts", headers=auth_headers)
    assert list_response.status_code == 200
    accounts = list_response.json()
    assert len(accounts) == 1
    assert accounts[0]["account_name"] == "Roth IRA"


async def test_accounts_are_scoped_to_their_owner(client):
    await client.post("/api/v1/auth/register", json={"email": "a@example.com", "password": "pw123456"})
    a_login = await client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "pw123456"})
    a_headers = {"Authorization": f"Bearer {a_login.json()['access_token']}"}

    await client.post("/api/v1/auth/register", json={"email": "b@example.com", "password": "pw123456"})
    b_login = await client.post("/api/v1/auth/login", json={"email": "b@example.com", "password": "pw123456"})
    b_headers = {"Authorization": f"Bearer {b_login.json()['access_token']}"}

    await client.post("/api/v1/retirement-accounts", json=IRA_PAYLOAD, headers=a_headers)

    response = await client.get("/api/v1/retirement-accounts", headers=b_headers)

    assert response.status_code == 200
    assert response.json() == []


async def test_simulate_growth_with_employer_match(client, auth_headers):
    create_response = await client.post(
        "/api/v1/retirement-accounts", json=FOUR_OH_ONE_K_PAYLOAD, headers=auth_headers
    )
    account_id = create_response.json()["id"]

    response = await client.post(
        f"/api/v1/retirement-accounts/{account_id}/simulate",
        json={"months": 12, "monthly_employee_contribution": "1000"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["projections"]) == 13  # month 0 through month 12 inclusive
    assert float(body["total_employee_contributions"]) == 12000.00
    # 50% match up to 6% of a $120k salary ($600/mo matchable ceiling) on a $1000/mo
    # contribution matches the full $600/mo ceiling at 50% = $300/mo, 12 months = $3600.
    assert float(body["total_employer_contributions"]) == 3600.00
    assert float(body["final_balance"]) > float(FOUR_OH_ONE_K_PAYLOAD["balance"])


async def test_contribution_limits_reflect_user_profile_and_ytd(client, auth_headers):
    await client.put(
        "/api/v1/users/me",
        json={"birth_date": "1970-01-01"},  # 55+ in 2026, standard 401k catch-up eligible
        headers=auth_headers,
    )
    create_response = await client.post(
        "/api/v1/retirement-accounts", json=FOUR_OH_ONE_K_PAYLOAD, headers=auth_headers
    )
    account_id = create_response.json()["id"]

    response = await client.get(
        "/api/v1/retirement-accounts/limits",
        params={"account_type": "traditional_401k"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["catch_up_eligible"] is True
    assert float(body["employee_limit"]) == 32500.00
    assert float(body["remaining_contribution"]) == 32500.00
    assert account_id  # created successfully as part of this scenario


async def test_contribute_rejects_amount_exceeding_remaining_limit(client, auth_headers):
    create_response = await client.post(
        "/api/v1/retirement-accounts", json=IRA_PAYLOAD, headers=auth_headers
    )
    account_id = create_response.json()["id"]

    response = await client.post(
        f"/api/v1/retirement-accounts/{account_id}/contribute",
        json={"amount": "9000"},  # exceeds the $7,500 under-50 IRA limit
        headers=auth_headers,
    )

    assert response.status_code == 400


async def test_contribute_within_limit_updates_balance_and_ytd(client, auth_headers):
    create_response = await client.post(
        "/api/v1/retirement-accounts", json=IRA_PAYLOAD, headers=auth_headers
    )
    account_id = create_response.json()["id"]

    response = await client.post(
        f"/api/v1/retirement-accounts/{account_id}/contribute",
        json={"amount": "1000"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert float(response.json()["contribution_ytd"]) == 1000.00

    account_response = await client.get(
        f"/api/v1/retirement-accounts/{account_id}", headers=auth_headers
    )
    account = account_response.json()
    assert float(account["balance"]) == 6000.00  # 5000 starting + 1000 contribution
    assert float(account["contribution_ytd"]) == 1000.00


async def test_ira_contribution_limit_is_shared_across_traditional_and_roth(client, auth_headers):
    roth = await client.post("/api/v1/retirement-accounts", json=IRA_PAYLOAD, headers=auth_headers)
    traditional_payload = {**IRA_PAYLOAD, "account_name": "Traditional IRA", "account_type": "traditional_ira"}
    traditional = await client.post(
        "/api/v1/retirement-accounts", json=traditional_payload, headers=auth_headers
    )

    await client.post(
        f"/api/v1/retirement-accounts/{roth.json()['id']}/contribute",
        json={"amount": "5000"},
        headers=auth_headers,
    )

    # $5,000 already contributed to the Roth IRA this year leaves only $2,500 of the
    # shared $7,500 IRA limit available to the Traditional IRA.
    response = await client.post(
        f"/api/v1/retirement-accounts/{traditional.json()['id']}/contribute",
        json={"amount": "3000"},
        headers=auth_headers,
    )

    assert response.status_code == 400


BANK_PAYLOAD = {
    "account_name": "Checking",
    "account_type": "checking",
    "principal": "5000.00",
    "interest_rate": "0.01",
    "compounding_frequency": "monthly",
}


async def test_contribute_with_bank_account_source_debits_bank_and_posts_transaction(
    client, auth_headers
):
    bank_response = await client.post(
        "/api/v1/bank-accounts", json=BANK_PAYLOAD, headers=auth_headers
    )
    bank_id = bank_response.json()["id"]
    retirement_response = await client.post(
        "/api/v1/retirement-accounts", json=IRA_PAYLOAD, headers=auth_headers
    )
    account_id = retirement_response.json()["id"]

    response = await client.post(
        f"/api/v1/retirement-accounts/{account_id}/contribute",
        json={"amount": "1000", "source_type": "bank_account", "source_bank_account_id": bank_id},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["transaction_id"] is not None

    bank_account = await client.get(f"/api/v1/bank-accounts/{bank_id}", headers=auth_headers)
    assert float(bank_account.json()["current_balance"]) == 4000.00  # 5000 - 1000

    retirement_account = await client.get(
        f"/api/v1/retirement-accounts/{account_id}", headers=auth_headers
    )
    assert float(retirement_account.json()["balance"]) == 6000.00  # 5000 starting + 1000


async def test_contribute_with_pre_tax_salary_source_does_not_touch_any_bank_balance(
    client, auth_headers
):
    bank_response = await client.post(
        "/api/v1/bank-accounts", json=BANK_PAYLOAD, headers=auth_headers
    )
    bank_id = bank_response.json()["id"]
    retirement_response = await client.post(
        "/api/v1/retirement-accounts", json=IRA_PAYLOAD, headers=auth_headers
    )
    account_id = retirement_response.json()["id"]

    response = await client.post(
        f"/api/v1/retirement-accounts/{account_id}/contribute",
        json={"amount": "1000", "source_type": "pre_tax_salary"},
        headers=auth_headers,
    )

    assert response.status_code == 200

    bank_account = await client.get(f"/api/v1/bank-accounts/{bank_id}", headers=auth_headers)
    assert float(bank_account.json()["current_balance"]) == 5000.00  # untouched


async def test_contribute_requires_source_bank_account_id_when_source_type_is_bank_account(
    client, auth_headers
):
    retirement_response = await client.post(
        "/api/v1/retirement-accounts", json=IRA_PAYLOAD, headers=auth_headers
    )
    account_id = retirement_response.json()["id"]

    response = await client.post(
        f"/api/v1/retirement-accounts/{account_id}/contribute",
        json={"amount": "1000", "source_type": "bank_account"},
        headers=auth_headers,
    )

    assert response.status_code == 422


async def test_contribute_with_bank_account_not_owned_by_caller_returns_404(client, auth_headers):
    await client.post("/api/v1/auth/register", json={"email": "other@example.com", "password": "pw123456"})
    other_login = await client.post(
        "/api/v1/auth/login", json={"email": "other@example.com", "password": "pw123456"}
    )
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}
    other_bank_response = await client.post(
        "/api/v1/bank-accounts", json=BANK_PAYLOAD, headers=other_headers
    )
    other_bank_id = other_bank_response.json()["id"]

    retirement_response = await client.post(
        "/api/v1/retirement-accounts", json=IRA_PAYLOAD, headers=auth_headers
    )
    account_id = retirement_response.json()["id"]

    response = await client.post(
        f"/api/v1/retirement-accounts/{account_id}/contribute",
        json={
            "amount": "1000",
            "source_type": "bank_account",
            "source_bank_account_id": other_bank_id,
        },
        headers=auth_headers,
    )

    assert response.status_code == 404


async def test_simulate_growth_includes_recurring_income_allocation(client, auth_headers):
    create_response = await client.post(
        "/api/v1/retirement-accounts", json=IRA_PAYLOAD, headers=auth_headers
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
                {"destination_type": "retirement_account", "destination_id": account_id, "percentage": "100"}
            ],
        },
        headers=auth_headers,
    )

    with_income = await client.post(
        f"/api/v1/retirement-accounts/{account_id}/simulate",
        json={"months": 1, "include_recurring": True},
        headers=auth_headers,
    )
    assert with_income.status_code == 200
    # biweekly $1000 folds to a monthly-equivalent of 1000 * 26/12 = 2166.67 - see
    # services/income_allocator.py's _OCCURRENCES_PER_MONTH.
    assert float(with_income.json()["total_employee_contributions"]) == 2166.67

    without_income = await client.post(
        f"/api/v1/retirement-accounts/{account_id}/simulate",
        json={"months": 1, "include_recurring": False},
        headers=auth_headers,
    )
    assert float(without_income.json()["total_employee_contributions"]) == 0.00
