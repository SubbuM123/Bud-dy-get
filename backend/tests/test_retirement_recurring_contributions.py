"""API-level coverage for retirement recurring contributions: CRUD, ownership scoping,
and that an active recurring contribution (monthly or yearly) is automatically folded
into a growth simulation - the retirement-module equivalent of
test_bank_accounts.py's recurring-action coverage.
"""

IRA_PAYLOAD = {
    "account_name": "Roth IRA",
    "account_type": "roth_ira",
    "balance": "5000.00",
    "expected_return_rate": "0.07",
}


async def _create_account(client, auth_headers, payload=IRA_PAYLOAD):
    response = await client.post("/api/v1/retirement-accounts", json=payload, headers=auth_headers)
    return response.json()["id"]


async def test_create_recurring_contribution_requires_authentication(client, auth_headers):
    account_id = await _create_account(client, auth_headers)

    response = await client.post(
        f"/api/v1/retirement-accounts/{account_id}/recurring-contributions",
        json={"amount": "500", "frequency": "monthly", "start_date": "2026-01-01"},
    )

    assert response.status_code == 401


async def test_create_and_list_recurring_contribution(client, auth_headers):
    account_id = await _create_account(client, auth_headers)

    create_response = await client.post(
        f"/api/v1/retirement-accounts/{account_id}/recurring-contributions",
        json={"amount": "500", "frequency": "monthly", "start_date": "2026-01-01"},
        headers=auth_headers,
    )
    assert create_response.status_code == 201
    body = create_response.json()
    assert body["frequency"] == "monthly"
    assert body["is_active"] is True

    list_response = await client.get(
        f"/api/v1/retirement-accounts/{account_id}/recurring-contributions", headers=auth_headers
    )
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


async def test_update_and_delete_recurring_contribution(client, auth_headers):
    account_id = await _create_account(client, auth_headers)
    create_response = await client.post(
        f"/api/v1/retirement-accounts/{account_id}/recurring-contributions",
        json={"amount": "500", "frequency": "monthly", "start_date": "2026-01-01"},
        headers=auth_headers,
    )
    contribution_id = create_response.json()["id"]

    update_response = await client.put(
        f"/api/v1/retirement-accounts/recurring-contributions/{contribution_id}",
        json={"amount": "600", "is_active": False},
        headers=auth_headers,
    )
    assert update_response.status_code == 200
    assert float(update_response.json()["amount"]) == 600.00
    assert update_response.json()["is_active"] is False

    delete_response = await client.delete(
        f"/api/v1/retirement-accounts/recurring-contributions/{contribution_id}",
        headers=auth_headers,
    )
    assert delete_response.status_code == 204

    list_response = await client.get(
        f"/api/v1/retirement-accounts/{account_id}/recurring-contributions", headers=auth_headers
    )
    assert list_response.json() == []


async def test_recurring_contributions_are_scoped_to_their_owner(client):
    await client.post("/api/v1/auth/register", json={"email": "a@example.com", "password": "pw123456"})
    a_login = await client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "pw123456"})
    a_headers = {"Authorization": f"Bearer {a_login.json()['access_token']}"}

    await client.post("/api/v1/auth/register", json={"email": "b@example.com", "password": "pw123456"})
    b_login = await client.post("/api/v1/auth/login", json={"email": "b@example.com", "password": "pw123456"})
    b_headers = {"Authorization": f"Bearer {b_login.json()['access_token']}"}

    account_id = await _create_account(client, a_headers)
    create_response = await client.post(
        f"/api/v1/retirement-accounts/{account_id}/recurring-contributions",
        json={"amount": "500", "frequency": "monthly", "start_date": "2026-01-01"},
        headers=a_headers,
    )
    contribution_id = create_response.json()["id"]

    # B can't see A's account's recurring contributions, nor act on them directly by id.
    list_response = await client.get(
        f"/api/v1/retirement-accounts/{account_id}/recurring-contributions", headers=b_headers
    )
    assert list_response.status_code == 404  # B doesn't own the account either

    update_response = await client.put(
        f"/api/v1/retirement-accounts/recurring-contributions/{contribution_id}",
        json={"amount": "1"},
        headers=b_headers,
    )
    assert update_response.status_code == 404


async def test_simulation_includes_monthly_recurring_contribution_by_default(client, auth_headers):
    account_id = await _create_account(client, auth_headers)
    await client.post(
        f"/api/v1/retirement-accounts/{account_id}/recurring-contributions",
        json={"amount": "500", "frequency": "monthly", "start_date": "2026-01-01"},
        headers=auth_headers,
    )

    response = await client.post(
        f"/api/v1/retirement-accounts/{account_id}/simulate",
        json={"months": 12},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert float(response.json()["total_employee_contributions"]) == 6000.00  # 500 * 12


async def test_simulation_folds_yearly_contribution_into_monthly_equivalent(client, auth_headers):
    account_id = await _create_account(client, auth_headers)
    await client.post(
        f"/api/v1/retirement-accounts/{account_id}/recurring-contributions",
        json={"amount": "1200", "frequency": "yearly", "start_date": "2026-01-01"},
        headers=auth_headers,
    )

    response = await client.post(
        f"/api/v1/retirement-accounts/{account_id}/simulate",
        json={"months": 12},
        headers=auth_headers,
    )

    assert response.status_code == 200
    # $1200/year -> $100/month equivalent, applied for 12 months = $1200.
    assert float(response.json()["total_employee_contributions"]) == 1200.00


async def test_simulation_excludes_recurring_when_include_recurring_is_false(client, auth_headers):
    account_id = await _create_account(client, auth_headers)
    await client.post(
        f"/api/v1/retirement-accounts/{account_id}/recurring-contributions",
        json={"amount": "500", "frequency": "monthly", "start_date": "2026-01-01"},
        headers=auth_headers,
    )

    response = await client.post(
        f"/api/v1/retirement-accounts/{account_id}/simulate",
        json={"months": 12, "include_recurring": False},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert float(response.json()["total_employee_contributions"]) == 0.0


async def test_inactive_recurring_contribution_is_excluded_from_simulation(client, auth_headers):
    account_id = await _create_account(client, auth_headers)
    create_response = await client.post(
        f"/api/v1/retirement-accounts/{account_id}/recurring-contributions",
        json={"amount": "500", "frequency": "monthly", "start_date": "2026-01-01"},
        headers=auth_headers,
    )
    contribution_id = create_response.json()["id"]
    await client.put(
        f"/api/v1/retirement-accounts/recurring-contributions/{contribution_id}",
        json={"is_active": False},
        headers=auth_headers,
    )

    response = await client.post(
        f"/api/v1/retirement-accounts/{account_id}/simulate",
        json={"months": 12},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert float(response.json()["total_employee_contributions"]) == 0.0
