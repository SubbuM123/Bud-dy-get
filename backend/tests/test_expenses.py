"""API-level coverage for the Expenses endpoints: manual create/list/update/delete,
ownership scoping, and the /summary aggregation endpoint's category breakdown and
default-to-current-month date range.
"""

from datetime import date

BANK_PAYLOAD = {
    "account_name": "Checking",
    "account_type": "checking",
    "principal": "1000.00",
    "interest_rate": "0.01",
    "compounding_frequency": "monthly",
}


async def _create_bank_account(client, headers):
    response = await client.post("/api/v1/bank-accounts", json=BANK_PAYLOAD, headers=headers)
    return response.json()["id"]


async def test_create_expense_requires_authentication(client):
    response = await client.post(
        "/api/v1/expenses",
        json={"merchant_name": "Corner Store", "amount": "5.00", "expense_date": "2026-03-01"},
    )

    assert response.status_code == 401


async def test_create_and_list_manual_expense(client, auth_headers):
    response = await client.post(
        "/api/v1/expenses",
        json={"merchant_name": "Corner Store", "amount": "5.00", "expense_date": "2026-03-01"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["merchant_name"] == "Corner Store"
    assert body["receipt_id"] is None

    list_response = await client.get("/api/v1/expenses", headers=auth_headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


async def test_expenses_are_scoped_to_their_owner(client):
    await client.post("/api/v1/auth/register", json={"email": "a@example.com", "password": "pw123456"})
    a_login = await client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "pw123456"})
    a_headers = {"Authorization": f"Bearer {a_login.json()['access_token']}"}

    await client.post("/api/v1/auth/register", json={"email": "b@example.com", "password": "pw123456"})
    b_login = await client.post("/api/v1/auth/login", json={"email": "b@example.com", "password": "pw123456"})
    b_headers = {"Authorization": f"Bearer {b_login.json()['access_token']}"}

    await client.post(
        "/api/v1/expenses",
        json={"merchant_name": "Corner Store", "amount": "5.00", "expense_date": "2026-03-01"},
        headers=a_headers,
    )

    response = await client.get("/api/v1/expenses", headers=b_headers)

    assert response.status_code == 200
    assert response.json() == []


async def test_update_expense_category_and_amount(client, auth_headers):
    categories = await client.get("/api/v1/expense-categories", headers=auth_headers)
    category_id = categories.json()[0]["id"]

    create_response = await client.post(
        "/api/v1/expenses",
        json={"merchant_name": "Corner Store", "amount": "5.00", "expense_date": "2026-03-01"},
        headers=auth_headers,
    )
    expense_id = create_response.json()["id"]

    response = await client.put(
        f"/api/v1/expenses/{expense_id}",
        json={"amount": "7.50", "category_id": category_id},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert float(body["amount"]) == 7.50
    assert body["category_id"] == category_id


async def test_create_expense_with_empty_string_bank_account_id_is_treated_as_not_linked(
    client, auth_headers
):
    # Regression test: the frontend's "Not linked to an account" <select> option submits
    # '' rather than omitting the field - this used to reach the DB layer as a literal
    # empty string for a UUID foreign-key column and 500 instead of creating the expense.
    response = await client.post(
        "/api/v1/expenses",
        json={
            "merchant_name": "Corner Store",
            "amount": "5.00",
            "expense_date": "2026-03-01",
            "bank_account_id": "",
            "category_id": "",
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["bank_account_id"] is None
    assert body["category_id"] is None


async def test_create_expense_links_to_an_owned_bank_account(client, auth_headers):
    bank_id = await _create_bank_account(client, auth_headers)

    response = await client.post(
        "/api/v1/expenses",
        json={
            "merchant_name": "Corner Store",
            "amount": "5.00",
            "expense_date": "2026-03-01",
            "bank_account_id": bank_id,
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    assert response.json()["bank_account_id"] == bank_id


async def test_create_expense_with_bank_account_not_owned_by_caller_returns_404(
    client, auth_headers
):
    await client.post("/api/v1/auth/register", json={"email": "other@example.com", "password": "pw123456"})
    other_login = await client.post(
        "/api/v1/auth/login", json={"email": "other@example.com", "password": "pw123456"}
    )
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}
    other_bank_id = await _create_bank_account(client, other_headers)

    response = await client.post(
        "/api/v1/expenses",
        json={
            "merchant_name": "Corner Store",
            "amount": "5.00",
            "expense_date": "2026-03-01",
            "bank_account_id": other_bank_id,
        },
        headers=auth_headers,
    )

    assert response.status_code == 404


async def test_create_expense_with_nonexistent_category_id_returns_404(client, auth_headers):
    response = await client.post(
        "/api/v1/expenses",
        json={
            "merchant_name": "Corner Store",
            "amount": "5.00",
            "expense_date": "2026-03-01",
            "category_id": "00000000-0000-0000-0000-000000000000",
        },
        headers=auth_headers,
    )

    assert response.status_code == 404


async def test_update_expense_with_empty_string_bank_account_id_clears_the_link(
    client, auth_headers
):
    bank_id = await _create_bank_account(client, auth_headers)
    create_response = await client.post(
        "/api/v1/expenses",
        json={
            "merchant_name": "Corner Store",
            "amount": "5.00",
            "expense_date": "2026-03-01",
            "bank_account_id": bank_id,
        },
        headers=auth_headers,
    )
    expense_id = create_response.json()["id"]

    response = await client.put(
        f"/api/v1/expenses/{expense_id}",
        json={"bank_account_id": ""},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["bank_account_id"] is None


async def test_delete_expense(client, auth_headers):
    create_response = await client.post(
        "/api/v1/expenses",
        json={"merchant_name": "Corner Store", "amount": "5.00", "expense_date": "2026-03-01"},
        headers=auth_headers,
    )
    expense_id = create_response.json()["id"]

    delete_response = await client.delete(f"/api/v1/expenses/{expense_id}", headers=auth_headers)
    assert delete_response.status_code == 204

    get_response = await client.get(f"/api/v1/expenses/{expense_id}", headers=auth_headers)
    assert get_response.status_code == 404


async def test_summary_defaults_to_the_current_calendar_month(client, auth_headers):
    today = date.today()
    this_month = today.replace(day=15).isoformat()
    # Roughly a year ago - safely outside the current month regardless of what day
    # `today` happens to be, without touching month/day-of-month edge cases.
    last_year = today.replace(year=today.year - 1).isoformat()

    await client.post(
        "/api/v1/expenses",
        json={"merchant_name": "This Month", "amount": "10.00", "expense_date": this_month},
        headers=auth_headers,
    )
    await client.post(
        "/api/v1/expenses",
        json={"merchant_name": "Last Year", "amount": "999.00", "expense_date": last_year},
        headers=auth_headers,
    )

    response = await client.get("/api/v1/expenses/summary", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["expense_count"] == 1
    assert float(body["total_amount"]) == 10.00


async def test_summary_groups_by_category_including_uncategorized(client, auth_headers):
    categories = await client.get("/api/v1/expense-categories", headers=auth_headers)
    category_id = categories.json()[0]["id"]
    today_iso = date.today().replace(day=10).isoformat()

    await client.post(
        "/api/v1/expenses",
        json={
            "merchant_name": "Categorized",
            "amount": "20.00",
            "expense_date": today_iso,
            "category_id": category_id,
        },
        headers=auth_headers,
    )
    await client.post(
        "/api/v1/expenses",
        json={"merchant_name": "Uncategorized", "amount": "8.00", "expense_date": today_iso},
        headers=auth_headers,
    )

    response = await client.get("/api/v1/expenses/summary", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert float(body["total_amount"]) == 28.00
    assert len(body["by_category"]) == 2
    uncategorized = next(c for c in body["by_category"] if c["category_id"] is None)
    assert uncategorized["category_name"] == "Uncategorized"
    assert float(uncategorized["total_amount"]) == 8.00


async def test_summary_respects_explicit_date_range(client, auth_headers):
    await client.post(
        "/api/v1/expenses",
        json={"merchant_name": "In Range", "amount": "15.00", "expense_date": "2026-01-15"},
        headers=auth_headers,
    )
    await client.post(
        "/api/v1/expenses",
        json={"merchant_name": "Out Of Range", "amount": "50.00", "expense_date": "2026-06-01"},
        headers=auth_headers,
    )

    response = await client.get(
        "/api/v1/expenses/summary",
        params={"start_date": "2026-01-01", "end_date": "2026-02-01"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["expense_count"] == 1
    assert float(body["total_amount"]) == 15.00
