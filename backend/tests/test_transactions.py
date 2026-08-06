"""API-level coverage for the unified Transaction log: ownership scoping, filtering by
type, editing a bank-sourced contribution's amount (applying just the delta to both the
destination and source accounts), fully reversing one on delete, and confirming an
employer-match contribution's edit/delete only ever moves the employee's own share - the
documented intentional simplification in services/transaction_effects.py. Runs against
SQLite (see conftest.py).
"""

BANK_PAYLOAD = {
    "account_name": "Checking",
    "account_type": "checking",
    "principal": "10000.00",
    "interest_rate": "0.01",
    "compounding_frequency": "monthly",
}

IRA_PAYLOAD = {
    "account_name": "Roth IRA",
    "account_type": "roth_ira",
    "balance": "0.00",
    "expected_return_rate": "0.07",
}

FOUR_OH_ONE_K_PAYLOAD = {
    "account_name": "Acme Corp 401k",
    "account_type": "traditional_401k",
    "balance": "0.00",
    "employer_name": "Acme Corp",
    "annual_salary": "120000.00",
    "employer_match_percent": "0.5",
    "employer_match_limit_percent": "0.06",
    "expected_return_rate": "0.07",
}


async def _create_bank_account(client, headers):
    response = await client.post("/api/v1/bank-accounts", json=BANK_PAYLOAD, headers=headers)
    return response.json()["id"]


async def _create_ira(client, headers):
    response = await client.post("/api/v1/retirement-accounts", json=IRA_PAYLOAD, headers=headers)
    return response.json()["id"]


async def _create_401k(client, headers):
    response = await client.post(
        "/api/v1/retirement-accounts", json=FOUR_OH_ONE_K_PAYLOAD, headers=headers
    )
    return response.json()["id"]


async def test_transactions_are_scoped_to_owner(client, auth_headers):
    retirement_id = await _create_ira(client, auth_headers)
    await client.post(
        f"/api/v1/retirement-accounts/{retirement_id}/contribute",
        json={"amount": "1000"},
        headers=auth_headers,
    )

    await client.post("/api/v1/auth/register", json={"email": "other@example.com", "password": "pw123456"})
    other_login = await client.post(
        "/api/v1/auth/login", json={"email": "other@example.com", "password": "pw123456"}
    )
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

    response = await client.get("/api/v1/transactions", headers=other_headers)

    assert response.status_code == 200
    assert response.json() == []


async def test_list_transactions_filters_by_type(client, auth_headers):
    retirement_id = await _create_ira(client, auth_headers)
    await client.post(
        f"/api/v1/retirement-accounts/{retirement_id}/contribute",
        json={"amount": "1000"},
        headers=auth_headers,
    )

    education_payload = {
        "account_name": "Jordan's 529",
        "account_type": "529_plan",
        "beneficiary_name": "Jordan",
        "plan_provider": "NY 529 College Savings Program",
        "balance": "0.00",
        "expected_return_rate": "0.07",
    }
    education_response = await client.post(
        "/api/v1/education-accounts", json=education_payload, headers=auth_headers
    )
    education_id = education_response.json()["id"]
    await client.post(
        f"/api/v1/education-accounts/{education_id}/contribute",
        json={"amount": "500"},
        headers=auth_headers,
    )

    response = await client.get(
        "/api/v1/transactions",
        params={"transaction_type": "retirement_contribution"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    transactions = response.json()
    assert len(transactions) == 1
    assert transactions[0]["transaction_type"] == "retirement_contribution"


async def test_update_amount_adjusts_bank_sourced_contribution(client, auth_headers):
    bank_id = await _create_bank_account(client, auth_headers)
    retirement_id = await _create_ira(client, auth_headers)

    contribute_response = await client.post(
        f"/api/v1/retirement-accounts/{retirement_id}/contribute",
        json={"amount": "1000", "source_type": "bank_account", "source_bank_account_id": bank_id},
        headers=auth_headers,
    )
    transaction_id = contribute_response.json()["transaction_id"]

    response = await client.put(
        f"/api/v1/transactions/{transaction_id}",
        json={"amount": "1500"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert float(response.json()["amount"]) == 1500.00

    retirement_response = await client.get(
        f"/api/v1/retirement-accounts/{retirement_id}", headers=auth_headers
    )
    retirement_body = retirement_response.json()
    assert float(retirement_body["balance"]) == 1500.00
    assert float(retirement_body["contribution_ytd"]) == 1500.00

    bank_response = await client.get(f"/api/v1/bank-accounts/{bank_id}", headers=auth_headers)
    # 10000 starting - 1000 initial contribution - 500 additional delta = 8500.
    assert float(bank_response.json()["current_balance"]) == 8500.00


async def test_delete_transaction_fully_reverses_bank_sourced_contribution(client, auth_headers):
    bank_id = await _create_bank_account(client, auth_headers)
    retirement_id = await _create_ira(client, auth_headers)

    contribute_response = await client.post(
        f"/api/v1/retirement-accounts/{retirement_id}/contribute",
        json={"amount": "1000", "source_type": "bank_account", "source_bank_account_id": bank_id},
        headers=auth_headers,
    )
    transaction_id = contribute_response.json()["transaction_id"]

    delete_response = await client.delete(
        f"/api/v1/transactions/{transaction_id}", headers=auth_headers
    )
    assert delete_response.status_code == 204

    retirement_response = await client.get(
        f"/api/v1/retirement-accounts/{retirement_id}", headers=auth_headers
    )
    retirement_body = retirement_response.json()
    assert float(retirement_body["balance"]) == 0.00
    assert float(retirement_body["contribution_ytd"]) == 0.00

    bank_response = await client.get(f"/api/v1/bank-accounts/{bank_id}", headers=auth_headers)
    assert float(bank_response.json()["current_balance"]) == 10000.00


async def test_update_and_delete_leave_employer_match_untouched(client, auth_headers):
    account_id = await _create_401k(client, auth_headers)

    contribute_response = await client.post(
        f"/api/v1/retirement-accounts/{account_id}/contribute",
        json={"amount": "1000"},
        headers=auth_headers,
    )
    transaction_id = contribute_response.json()["transaction_id"]
    employer_match = float(contribute_response.json()["employer_match_this_contribution"])
    assert employer_match > 0  # sanity check the match actually applied

    balance_after_contribution = float(
        (await client.get(f"/api/v1/retirement-accounts/{account_id}", headers=auth_headers)).json()[
            "balance"
        ]
    )
    assert balance_after_contribution == 1000.00 + employer_match

    update_response = await client.put(
        f"/api/v1/transactions/{transaction_id}",
        json={"amount": "1500"},
        headers=auth_headers,
    )
    assert update_response.status_code == 200

    balance_after_update = float(
        (await client.get(f"/api/v1/retirement-accounts/{account_id}", headers=auth_headers)).json()[
            "balance"
        ]
    )
    # Only the employee's own contribution delta (500) moves - the match stays exactly
    # what it was when first recorded, not recomputed against the new $1500 total.
    assert balance_after_update == balance_after_contribution + 500.00

    await client.delete(f"/api/v1/transactions/{transaction_id}", headers=auth_headers)

    balance_after_delete = float(
        (await client.get(f"/api/v1/retirement-accounts/{account_id}", headers=auth_headers)).json()[
            "balance"
        ]
    )
    # Deleting reverses the full (edited) employee amount, 1500 - but the original match
    # is still never touched, so this lands at employer_match, not 0.
    assert balance_after_delete == employer_match
