"""API-level coverage for the Expense Categories endpoints: the default starter set seeded
at registration, custom category CRUD, duplicate-name rejection, and that deleting a
category doesn't take its expenses down with it.
"""

from app.models.expense_categories import DEFAULT_CATEGORIES


async def test_registration_seeds_the_default_category_set(client):
    await client.post("/api/v1/auth/register", json={"email": "new@example.com", "password": "pw123456"})
    login = await client.post("/api/v1/auth/login", json={"email": "new@example.com", "password": "pw123456"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = await client.get("/api/v1/expense-categories", headers=headers)

    assert response.status_code == 200
    categories = response.json()
    assert len(categories) == len(DEFAULT_CATEGORIES)
    names = {c["name"] for c in categories}
    assert names == {name for name, _, _ in DEFAULT_CATEGORIES}
    assert all(c["is_system"] for c in categories)


async def test_create_custom_category(client, auth_headers):
    response = await client.post(
        "/api/v1/expense-categories",
        json={"name": "Pet Supplies", "color": "#00ff00", "icon": "paw-print"},
        headers=auth_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Pet Supplies"
    assert body["is_system"] is False


async def test_duplicate_category_name_for_same_user_is_rejected(client, auth_headers):
    payload = {"name": "Pet Supplies", "color": "#00ff00", "icon": "paw-print"}
    await client.post("/api/v1/expense-categories", json=payload, headers=auth_headers)

    response = await client.post("/api/v1/expense-categories", json=payload, headers=auth_headers)

    assert response.status_code == 400


async def test_categories_are_scoped_to_their_owner(client):
    await client.post("/api/v1/auth/register", json={"email": "a@example.com", "password": "pw123456"})
    a_login = await client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "pw123456"})
    a_headers = {"Authorization": f"Bearer {a_login.json()['access_token']}"}

    await client.post("/api/v1/auth/register", json={"email": "b@example.com", "password": "pw123456"})
    b_login = await client.post("/api/v1/auth/login", json={"email": "b@example.com", "password": "pw123456"})
    b_headers = {"Authorization": f"Bearer {b_login.json()['access_token']}"}

    a_categories = await client.get("/api/v1/expense-categories", headers=a_headers)
    a_category_id = a_categories.json()[0]["id"]

    response = await client.put(
        f"/api/v1/expense-categories/{a_category_id}",
        json={"name": "Hijacked"},
        headers=b_headers,
    )

    assert response.status_code == 404


async def test_update_category_budget(client, auth_headers):
    categories = await client.get("/api/v1/expense-categories", headers=auth_headers)
    category_id = categories.json()[0]["id"]

    response = await client.put(
        f"/api/v1/expense-categories/{category_id}",
        json={"monthly_budget": "500.00"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert float(response.json()["monthly_budget"]) == 500.00


async def test_deleting_a_category_nulls_it_out_on_existing_expenses_rather_than_deleting_them(
    client, auth_headers
):
    categories = await client.get("/api/v1/expense-categories", headers=auth_headers)
    category_id = categories.json()[0]["id"]

    expense_response = await client.post(
        "/api/v1/expenses",
        json={
            "merchant_name": "Test Store",
            "amount": "25.00",
            "expense_date": "2026-03-01",
            "category_id": category_id,
        },
        headers=auth_headers,
    )
    expense_id = expense_response.json()["id"]

    delete_response = await client.delete(
        f"/api/v1/expense-categories/{category_id}", headers=auth_headers
    )
    assert delete_response.status_code == 204

    expense_response = await client.get(f"/api/v1/expenses/{expense_id}", headers=auth_headers)
    assert expense_response.status_code == 200
    assert expense_response.json()["category_id"] is None
