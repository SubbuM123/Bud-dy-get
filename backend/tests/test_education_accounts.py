"""API-level coverage for the Education Savings endpoints: create/list/scope an account,
run a growth simulation, fetch gift-tax guidance driven by a beneficiary's YTD
contributions, and confirm a contribution never returns 400 (unlike retirement's
/contribute) even when it exceeds the annual gift-tax exclusion. Runs against SQLite
(see conftest.py) - the Postgres enum-label mismatch class of bug is covered separately
in test_education_account_enums.py.
"""

FIVE_TWENTY_NINE_PAYLOAD = {
    "account_name": "Jordan's 529",
    "account_type": "529_plan",
    "beneficiary_name": "Jordan",
    "plan_provider": "NY 529 College Savings Program",
    "balance": "5000.00",
    "expected_return_rate": "0.07",
}


async def test_create_account_requires_authentication(client):
    response = await client.post("/api/v1/education-accounts", json=FIVE_TWENTY_NINE_PAYLOAD)

    assert response.status_code == 401


async def test_create_and_list_education_account(client, auth_headers):
    create_response = await client.post(
        "/api/v1/education-accounts", json=FIVE_TWENTY_NINE_PAYLOAD, headers=auth_headers
    )
    assert create_response.status_code == 201
    body = create_response.json()
    assert body["account_type"] == "529_plan"
    assert body["beneficiary_name"] == "Jordan"
    assert float(body["balance"]) == 5000.00
    assert float(body["contribution_ytd"]) == 0.0

    list_response = await client.get("/api/v1/education-accounts", headers=auth_headers)
    assert list_response.status_code == 200
    accounts = list_response.json()
    assert len(accounts) == 1
    assert accounts[0]["account_name"] == "Jordan's 529"


async def test_accounts_are_scoped_to_their_owner(client):
    await client.post("/api/v1/auth/register", json={"email": "a@example.com", "password": "pw123456"})
    a_login = await client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "pw123456"})
    a_headers = {"Authorization": f"Bearer {a_login.json()['access_token']}"}

    await client.post("/api/v1/auth/register", json={"email": "b@example.com", "password": "pw123456"})
    b_login = await client.post("/api/v1/auth/login", json={"email": "b@example.com", "password": "pw123456"})
    b_headers = {"Authorization": f"Bearer {b_login.json()['access_token']}"}

    await client.post("/api/v1/education-accounts", json=FIVE_TWENTY_NINE_PAYLOAD, headers=a_headers)

    response = await client.get("/api/v1/education-accounts", headers=b_headers)

    assert response.status_code == 200
    assert response.json() == []


async def test_simulate_growth(client, auth_headers):
    create_response = await client.post(
        "/api/v1/education-accounts", json=FIVE_TWENTY_NINE_PAYLOAD, headers=auth_headers
    )
    account_id = create_response.json()["id"]

    response = await client.post(
        f"/api/v1/education-accounts/{account_id}/simulate",
        json={"months": 12, "monthly_contribution": "500"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["projections"]) == 13  # month 0 through month 12 inclusive
    assert float(body["total_contributions"]) == 6000.00  # 500 * 12
    assert float(body["final_balance"]) > float(FIVE_TWENTY_NINE_PAYLOAD["balance"])


async def test_gift_tax_info_reflects_beneficiary_ytd(client, auth_headers):
    create_response = await client.post(
        "/api/v1/education-accounts", json=FIVE_TWENTY_NINE_PAYLOAD, headers=auth_headers
    )
    account_id = create_response.json()["id"]
    await client.post(
        f"/api/v1/education-accounts/{account_id}/contribute",
        json={"amount": "10000"},
        headers=auth_headers,
    )

    response = await client.get(
        "/api/v1/education-accounts/gift-tax-info",
        params={"beneficiary_name": "Jordan"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert float(body["beneficiary_contribution_ytd"]) == 10000.00
    assert float(body["remaining_before_exclusion"]) == 9000.00  # 19000 - 10000
    assert body["would_exceed_exclusion"] is False


async def test_contribute_never_returns_400_even_over_the_gift_tax_exclusion(client, auth_headers):
    create_response = await client.post(
        "/api/v1/education-accounts", json=FIVE_TWENTY_NINE_PAYLOAD, headers=auth_headers
    )
    account_id = create_response.json()["id"]

    response = await client.post(
        f"/api/v1/education-accounts/{account_id}/contribute",
        json={"amount": "50000"},  # well over the $19,000 annual gift-tax exclusion
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["would_exceed_exclusion"] is True
    assert float(body["beneficiary_contribution_ytd"]) == 50000.00

    account_response = await client.get(
        f"/api/v1/education-accounts/{account_id}", headers=auth_headers
    )
    account = account_response.json()
    assert float(account["balance"]) == 55000.00  # 5000 starting + 50000 contribution
    assert float(account["contribution_ytd"]) == 50000.00


async def test_gift_tax_exclusion_is_tracked_per_beneficiary_not_globally(client, auth_headers):
    jordan_response = await client.post(
        "/api/v1/education-accounts", json=FIVE_TWENTY_NINE_PAYLOAD, headers=auth_headers
    )
    taylor_payload = {**FIVE_TWENTY_NINE_PAYLOAD, "account_name": "Taylor's 529", "beneficiary_name": "Taylor"}
    taylor_response = await client.post(
        "/api/v1/education-accounts", json=taylor_payload, headers=auth_headers
    )

    await client.post(
        f"/api/v1/education-accounts/{jordan_response.json()['id']}/contribute",
        json={"amount": "19000"},
        headers=auth_headers,
    )

    # Taylor's own exclusion is untouched by Jordan's contributions - two separate kids,
    # two separate $19,000 exclusions.
    response = await client.get(
        "/api/v1/education-accounts/gift-tax-info",
        params={"beneficiary_name": "Taylor"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert float(body["beneficiary_contribution_ytd"]) == 0.0
    assert float(body["remaining_before_exclusion"]) == 19000.00


async def test_two_accounts_same_beneficiary_share_one_exclusion(client, auth_headers):
    account_1 = await client.post(
        "/api/v1/education-accounts", json=FIVE_TWENTY_NINE_PAYLOAD, headers=auth_headers
    )
    second_payload = {**FIVE_TWENTY_NINE_PAYLOAD, "account_name": "Jordan's Second 529"}
    account_2 = await client.post(
        "/api/v1/education-accounts", json=second_payload, headers=auth_headers
    )

    await client.post(
        f"/api/v1/education-accounts/{account_1.json()['id']}/contribute",
        json={"amount": "12000"},
        headers=auth_headers,
    )
    await client.post(
        f"/api/v1/education-accounts/{account_2.json()['id']}/contribute",
        json={"amount": "12000"},
        headers=auth_headers,
    )

    response = await client.get(
        "/api/v1/education-accounts/gift-tax-info",
        params={"beneficiary_name": "Jordan"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert float(body["beneficiary_contribution_ytd"]) == 24000.00  # summed across both accounts
    assert body["would_exceed_exclusion"] is True


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
    education_response = await client.post(
        "/api/v1/education-accounts", json=FIVE_TWENTY_NINE_PAYLOAD, headers=auth_headers
    )
    account_id = education_response.json()["id"]

    response = await client.post(
        f"/api/v1/education-accounts/{account_id}/contribute",
        json={"amount": "1000", "source_type": "bank_account", "source_bank_account_id": bank_id},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["transaction_id"] is not None

    bank_account = await client.get(f"/api/v1/bank-accounts/{bank_id}", headers=auth_headers)
    assert float(bank_account.json()["current_balance"]) == 4000.00  # 5000 - 1000

    education_account = await client.get(
        f"/api/v1/education-accounts/{account_id}", headers=auth_headers
    )
    assert float(education_account.json()["balance"]) == 6000.00  # 5000 starting + 1000


async def test_contribute_with_pre_tax_salary_source_does_not_touch_any_bank_balance(
    client, auth_headers
):
    bank_response = await client.post(
        "/api/v1/bank-accounts", json=BANK_PAYLOAD, headers=auth_headers
    )
    bank_id = bank_response.json()["id"]
    education_response = await client.post(
        "/api/v1/education-accounts", json=FIVE_TWENTY_NINE_PAYLOAD, headers=auth_headers
    )
    account_id = education_response.json()["id"]

    response = await client.post(
        f"/api/v1/education-accounts/{account_id}/contribute",
        json={"amount": "1000", "source_type": "pre_tax_salary"},
        headers=auth_headers,
    )

    assert response.status_code == 200

    bank_account = await client.get(f"/api/v1/bank-accounts/{bank_id}", headers=auth_headers)
    assert float(bank_account.json()["current_balance"]) == 5000.00  # untouched


async def test_contribute_requires_source_bank_account_id_when_source_type_is_bank_account(
    client, auth_headers
):
    education_response = await client.post(
        "/api/v1/education-accounts", json=FIVE_TWENTY_NINE_PAYLOAD, headers=auth_headers
    )
    account_id = education_response.json()["id"]

    response = await client.post(
        f"/api/v1/education-accounts/{account_id}/contribute",
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

    education_response = await client.post(
        "/api/v1/education-accounts", json=FIVE_TWENTY_NINE_PAYLOAD, headers=auth_headers
    )
    account_id = education_response.json()["id"]

    response = await client.post(
        f"/api/v1/education-accounts/{account_id}/contribute",
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
        "/api/v1/education-accounts", json=FIVE_TWENTY_NINE_PAYLOAD, headers=auth_headers
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
                {"destination_type": "education_account", "destination_id": account_id, "percentage": "100"}
            ],
        },
        headers=auth_headers,
    )

    with_income = await client.post(
        f"/api/v1/education-accounts/{account_id}/simulate",
        json={"months": 1, "include_recurring": True},
        headers=auth_headers,
    )
    assert with_income.status_code == 200
    # biweekly $1000 folds to a monthly-equivalent of 1000 * 26/12 = 2166.67 - see
    # services/income_allocator.py's _OCCURRENCES_PER_MONTH.
    assert float(with_income.json()["total_contributions"]) == 2166.67

    without_income = await client.post(
        f"/api/v1/education-accounts/{account_id}/simulate",
        json={"months": 1, "include_recurring": False},
        headers=auth_headers,
    )
    assert float(without_income.json()["total_contributions"]) == 0.00
