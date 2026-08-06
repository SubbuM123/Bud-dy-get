"""API-level coverage for bond holdings and property investments: creation (optionally
funded from a bank account), selling with realized P/L, ownership scoping, and the bond
amortization schedule endpoint. Runs against SQLite (see conftest.py).
"""

BANK_PAYLOAD = {
    "account_name": "Checking",
    "account_type": "checking",
    "principal": "20000.00",
    "interest_rate": "0.01",
    "compounding_frequency": "monthly",
}

BOND_PAYLOAD = {
    "name": "US Treasury 2028",
    "purchase_price": "9500.00",
    "face_value": "10000.00",
    "coupon_rate": "0.05",
    "payment_frequency": "semi_annually",
    "purchase_date": "2026-01-01",
    "maturity_date": "2028-01-01",
}

PROPERTY_PAYLOAD = {
    "name": "Rental Duplex",
    "cost": "250000.00",
    "expected_return_rate": "0.06",
    "purchase_date": "2026-01-01",
}


async def _create_bank_account(client, headers):
    response = await client.post("/api/v1/bank-accounts", json=BANK_PAYLOAD, headers=headers)
    return response.json()["id"]


async def test_create_bond_requires_authentication(client):
    response = await client.post("/api/v1/investments/bonds", json=BOND_PAYLOAD)

    assert response.status_code == 401


async def test_create_bond_rejects_maturity_before_purchase(client, auth_headers):
    bad_payload = {**BOND_PAYLOAD, "maturity_date": "2025-01-01"}

    response = await client.post("/api/v1/investments/bonds", json=bad_payload, headers=auth_headers)

    assert response.status_code == 422


async def test_create_bond_with_bank_source_debits_bank(client, auth_headers):
    bank_id = await _create_bank_account(client, auth_headers)

    response = await client.post(
        "/api/v1/investments/bonds",
        json={**BOND_PAYLOAD, "source_bank_account_id": bank_id},
        headers=auth_headers,
    )
    assert response.status_code == 201

    bank_response = await client.get(f"/api/v1/bank-accounts/{bank_id}", headers=auth_headers)
    assert float(bank_response.json()["current_balance"]) == 10500.00  # 20000 - 9500


async def test_sell_bond_calculates_realized_pnl(client, auth_headers):
    create_response = await client.post(
        "/api/v1/investments/bonds", json=BOND_PAYLOAD, headers=auth_headers
    )
    bond_id = create_response.json()["id"]

    response = await client.post(
        f"/api/v1/investments/bonds/{bond_id}/sell",
        json={"sale_price": "9800.00"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["is_active"] is False
    assert float(body["realized_pnl"]) == 300.00  # 9800 - 9500


async def test_sell_bond_twice_returns_400(client, auth_headers):
    create_response = await client.post(
        "/api/v1/investments/bonds", json=BOND_PAYLOAD, headers=auth_headers
    )
    bond_id = create_response.json()["id"]

    await client.post(
        f"/api/v1/investments/bonds/{bond_id}/sell",
        json={"sale_price": "9800.00"},
        headers=auth_headers,
    )
    response = await client.post(
        f"/api/v1/investments/bonds/{bond_id}/sell",
        json={"sale_price": "9800.00"},
        headers=auth_headers,
    )

    assert response.status_code == 400


async def test_bonds_are_scoped_to_owner(client, auth_headers):
    await client.post("/api/v1/investments/bonds", json=BOND_PAYLOAD, headers=auth_headers)

    await client.post("/api/v1/auth/register", json={"email": "other@example.com", "password": "pw123456"})
    other_login = await client.post(
        "/api/v1/auth/login", json={"email": "other@example.com", "password": "pw123456"}
    )
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

    response = await client.get("/api/v1/investments/bonds", headers=other_headers)

    assert response.status_code == 200
    assert response.json() == []


async def test_bond_amortization_schedule_sums_to_face_value_minus_purchase_price(
    client, auth_headers
):
    create_response = await client.post(
        "/api/v1/investments/bonds", json=BOND_PAYLOAD, headers=auth_headers
    )
    bond_id = create_response.json()["id"]

    response = await client.get(
        f"/api/v1/investments/bonds/{bond_id}/amortization", headers=auth_headers
    )

    assert response.status_code == 200
    schedule = response.json()["schedule"]
    total_amortization = sum(float(p["amortization_amount"]) for p in schedule)
    assert abs(total_amortization - 500.00) < 0.01  # face_value - purchase_price
    assert float(schedule[-1]["book_value"]) == 10000.00


async def test_current_book_value_is_between_purchase_price_and_face_value(client, auth_headers):
    create_response = await client.post(
        "/api/v1/investments/bonds", json=BOND_PAYLOAD, headers=auth_headers
    )
    bond_id = create_response.json()["id"]

    response = await client.get(f"/api/v1/investments/bonds/{bond_id}", headers=auth_headers)
    body = response.json()

    assert 9500.00 <= float(body["current_book_value"]) <= 10000.00


async def test_create_property_investment_requires_authentication(client):
    response = await client.post("/api/v1/investments/property", json=PROPERTY_PAYLOAD)

    assert response.status_code == 401


async def test_create_property_with_bank_source_debits_bank(client, auth_headers):
    bank_id = await _create_bank_account(client, auth_headers)

    response = await client.post(
        "/api/v1/investments/property",
        json={**PROPERTY_PAYLOAD, "source_bank_account_id": bank_id},
        headers=auth_headers,
    )
    assert response.status_code == 201

    bank_response = await client.get(f"/api/v1/bank-accounts/{bank_id}", headers=auth_headers)
    assert float(bank_response.json()["current_balance"]) == -230000.00  # 20000 - 250000


async def test_sell_property_calculates_realized_pnl(client, auth_headers):
    create_response = await client.post(
        "/api/v1/investments/property", json=PROPERTY_PAYLOAD, headers=auth_headers
    )
    property_id = create_response.json()["id"]

    response = await client.post(
        f"/api/v1/investments/property/{property_id}/sell",
        json={"sale_price": "300000.00"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["is_active"] is False
    assert float(body["realized_pnl"]) == 50000.00


async def test_property_investments_are_scoped_to_owner(client, auth_headers):
    await client.post("/api/v1/investments/property", json=PROPERTY_PAYLOAD, headers=auth_headers)

    await client.post("/api/v1/auth/register", json={"email": "other@example.com", "password": "pw123456"})
    other_login = await client.post(
        "/api/v1/auth/login", json={"email": "other@example.com", "password": "pw123456"}
    )
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

    response = await client.get("/api/v1/investments/property", headers=other_headers)

    assert response.status_code == 200
    assert response.json() == []


async def test_investment_summary_includes_stocks_bonds_and_property(client, auth_headers):
    await client.post("/api/v1/investments/bonds", json=BOND_PAYLOAD, headers=auth_headers)
    await client.post("/api/v1/investments/property", json=PROPERTY_PAYLOAD, headers=auth_headers)

    response = await client.get("/api/v1/investments/summary", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert float(body["total_bonds_value"]) > 0
    assert float(body["total_property_value"]) > 0
    assert float(body["total_value"]) == float(body["total_stocks_value"]) + float(
        body["total_bonds_value"]
    ) + float(body["total_property_value"])
