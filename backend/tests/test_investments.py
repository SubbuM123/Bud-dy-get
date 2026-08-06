"""API-level coverage for stock positions: creation (get-or-create by ticker), buying
(with and without a bank-funded source), selling (profit/loss P/L, over-selling rejected),
ownership scoping, and market-value/unrealized-P/L computed fields. Runs against SQLite
(see conftest.py). `services.stock_price.get_current_price` is monkeypatched wherever a
test needs a deterministic cached price - no real network calls, matching
tests/test_receipts.py's approach to external services.
"""

from decimal import Decimal

from app.services import stock_price

BANK_PAYLOAD = {
    "account_name": "Checking",
    "account_type": "checking",
    "principal": "10000.00",
    "interest_rate": "0.01",
    "compounding_frequency": "monthly",
}


async def _create_bank_account(client, headers):
    response = await client.post("/api/v1/bank-accounts", json=BANK_PAYLOAD, headers=headers)
    return response.json()["id"]


async def _create_position(client, headers, ticker="ACME"):
    response = await client.post(
        "/api/v1/investments/stocks", json={"ticker_symbol": ticker}, headers=headers
    )
    return response.json()["id"]


async def test_create_stock_position_requires_authentication(client):
    response = await client.post("/api/v1/investments/stocks", json={"ticker_symbol": "ACME"})

    assert response.status_code == 401


async def test_create_stock_position_reuses_existing_ticker(client, auth_headers):
    first = await client.post(
        "/api/v1/investments/stocks", json={"ticker_symbol": "acme"}, headers=auth_headers
    )
    second = await client.post(
        "/api/v1/investments/stocks", json={"ticker_symbol": "ACME"}, headers=auth_headers
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]

    list_response = await client.get("/api/v1/investments/stocks", headers=auth_headers)
    assert len(list_response.json()) == 1


async def test_buy_stock_updates_shares_and_avg_cost(client, auth_headers):
    position_id = await _create_position(client, auth_headers)

    response = await client.post(
        f"/api/v1/investments/stocks/{position_id}/buy",
        json={"shares": "10", "price_per_share": "100.00"},
        headers=auth_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["transaction_type"] == "buy"
    assert float(body["shares"]) == 10.0

    position_response = await client.get(
        f"/api/v1/investments/stocks/{position_id}", headers=auth_headers
    )
    position = position_response.json()
    assert float(position["shares"]) == 10.0
    assert float(position["average_cost_per_share"]) == 100.00


async def test_buy_stock_averages_cost_across_two_buys(client, auth_headers):
    position_id = await _create_position(client, auth_headers)

    await client.post(
        f"/api/v1/investments/stocks/{position_id}/buy",
        json={"shares": "10", "price_per_share": "100.00"},
        headers=auth_headers,
    )
    await client.post(
        f"/api/v1/investments/stocks/{position_id}/buy",
        json={"shares": "10", "price_per_share": "200.00"},
        headers=auth_headers,
    )

    position_response = await client.get(
        f"/api/v1/investments/stocks/{position_id}", headers=auth_headers
    )
    position = position_response.json()
    assert float(position["shares"]) == 20.0
    assert float(position["average_cost_per_share"]) == 150.00


async def test_buy_stock_with_bank_source_debits_bank_and_posts_transaction(client, auth_headers):
    bank_id = await _create_bank_account(client, auth_headers)
    position_id = await _create_position(client, auth_headers)

    response = await client.post(
        f"/api/v1/investments/stocks/{position_id}/buy",
        json={
            "shares": "10",
            "price_per_share": "100.00",
            "source_bank_account_id": bank_id,
        },
        headers=auth_headers,
    )
    assert response.status_code == 201

    bank_response = await client.get(f"/api/v1/bank-accounts/{bank_id}", headers=auth_headers)
    assert float(bank_response.json()["current_balance"]) == 9000.00  # 10000 - (10 * 100)

    transactions_response = await client.get(
        "/api/v1/transactions", params={"transaction_type": "stock_purchase"}, headers=auth_headers
    )
    transactions = transactions_response.json()
    assert len(transactions) == 1
    assert float(transactions[0]["amount"]) == 1000.00


async def test_buy_stock_with_bank_not_owned_by_caller_returns_404(client, auth_headers):
    await client.post("/api/v1/auth/register", json={"email": "other@example.com", "password": "pw123456"})
    other_login = await client.post(
        "/api/v1/auth/login", json={"email": "other@example.com", "password": "pw123456"}
    )
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}
    other_bank_id = await _create_bank_account(client, other_headers)

    position_id = await _create_position(client, auth_headers)

    response = await client.post(
        f"/api/v1/investments/stocks/{position_id}/buy",
        json={
            "shares": "10",
            "price_per_share": "100.00",
            "source_bank_account_id": other_bank_id,
        },
        headers=auth_headers,
    )

    assert response.status_code == 404


async def test_sell_stock_calculates_realized_pnl_profit(client, auth_headers):
    position_id = await _create_position(client, auth_headers)
    await client.post(
        f"/api/v1/investments/stocks/{position_id}/buy",
        json={"shares": "10", "price_per_share": "100.00"},
        headers=auth_headers,
    )

    response = await client.post(
        f"/api/v1/investments/stocks/{position_id}/sell",
        json={"shares": "10", "price_per_share": "150.00"},
        headers=auth_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["transaction_type"] == "sell"
    assert float(body["realized_pnl"]) == 500.00

    position_response = await client.get(
        f"/api/v1/investments/stocks/{position_id}", headers=auth_headers
    )
    assert float(position_response.json()["shares"]) == 0.0


async def test_sell_stock_calculates_realized_pnl_loss(client, auth_headers):
    position_id = await _create_position(client, auth_headers)
    await client.post(
        f"/api/v1/investments/stocks/{position_id}/buy",
        json={"shares": "10", "price_per_share": "100.00"},
        headers=auth_headers,
    )

    response = await client.post(
        f"/api/v1/investments/stocks/{position_id}/sell",
        json={"shares": "10", "price_per_share": "80.00"},
        headers=auth_headers,
    )

    assert response.status_code == 201
    assert float(response.json()["realized_pnl"]) == -200.00


async def test_sell_stock_credits_proceeds_back_to_funding_bank_account(client, auth_headers):
    bank_id = await _create_bank_account(client, auth_headers)
    position_id = await _create_position(client, auth_headers)

    await client.post(
        f"/api/v1/investments/stocks/{position_id}/buy",
        json={
            "shares": "10",
            "price_per_share": "100.00",
            "source_bank_account_id": bank_id,
        },
        headers=auth_headers,
    )
    bank_after_buy = await client.get(f"/api/v1/bank-accounts/{bank_id}", headers=auth_headers)
    assert float(bank_after_buy.json()["current_balance"]) == 9000.00  # 10000 - 1000

    sell_response = await client.post(
        f"/api/v1/investments/stocks/{position_id}/sell",
        json={"shares": "10", "price_per_share": "150.00"},
        headers=auth_headers,
    )
    assert sell_response.status_code == 201
    assert sell_response.json()["source_bank_account_id"] == bank_id

    bank_after_sell = await client.get(f"/api/v1/bank-accounts/{bank_id}", headers=auth_headers)
    assert float(bank_after_sell.json()["current_balance"]) == 10500.00  # 9000 + (10 * 150)


async def test_sell_stock_without_a_funding_account_does_not_touch_any_bank_balance(
    client, auth_headers
):
    bank_id = await _create_bank_account(client, auth_headers)
    position_id = await _create_position(client, auth_headers)

    # Bought with no source_bank_account_id - nothing to credit back on sell.
    await client.post(
        f"/api/v1/investments/stocks/{position_id}/buy",
        json={"shares": "10", "price_per_share": "100.00"},
        headers=auth_headers,
    )

    sell_response = await client.post(
        f"/api/v1/investments/stocks/{position_id}/sell",
        json={"shares": "10", "price_per_share": "150.00"},
        headers=auth_headers,
    )
    assert sell_response.status_code == 201
    assert sell_response.json()["source_bank_account_id"] is None

    bank_response = await client.get(f"/api/v1/bank-accounts/{bank_id}", headers=auth_headers)
    assert float(bank_response.json()["current_balance"]) == 10000.00  # untouched


async def test_sell_more_shares_than_held_returns_400(client, auth_headers):
    position_id = await _create_position(client, auth_headers)
    await client.post(
        f"/api/v1/investments/stocks/{position_id}/buy",
        json={"shares": "5", "price_per_share": "100.00"},
        headers=auth_headers,
    )

    response = await client.post(
        f"/api/v1/investments/stocks/{position_id}/sell",
        json={"shares": "10", "price_per_share": "100.00"},
        headers=auth_headers,
    )

    assert response.status_code == 400


async def test_positions_are_scoped_to_owner(client, auth_headers):
    await _create_position(client, auth_headers)

    await client.post("/api/v1/auth/register", json={"email": "other@example.com", "password": "pw123456"})
    other_login = await client.post(
        "/api/v1/auth/login", json={"email": "other@example.com", "password": "pw123456"}
    )
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

    response = await client.get("/api/v1/investments/stocks", headers=other_headers)

    assert response.status_code == 200
    assert response.json() == []


async def test_delete_position_requires_zero_shares(client, auth_headers):
    position_id = await _create_position(client, auth_headers)
    await client.post(
        f"/api/v1/investments/stocks/{position_id}/buy",
        json={"shares": "5", "price_per_share": "100.00"},
        headers=auth_headers,
    )

    response = await client.delete(f"/api/v1/investments/stocks/{position_id}", headers=auth_headers)
    assert response.status_code == 400

    await client.post(
        f"/api/v1/investments/stocks/{position_id}/sell",
        json={"shares": "5", "price_per_share": "100.00"},
        headers=auth_headers,
    )
    response = await client.delete(f"/api/v1/investments/stocks/{position_id}", headers=auth_headers)
    assert response.status_code == 204


async def test_market_value_and_unrealized_pnl_computed_from_cached_price(
    client, auth_headers, monkeypatch
):
    monkeypatch.setattr(stock_price, "get_current_price", lambda ticker: Decimal("150.00"))

    position_id = await _create_position(client, auth_headers)
    await client.post(
        f"/api/v1/investments/stocks/{position_id}/buy",
        json={"shares": "10", "price_per_share": "100.00"},
        headers=auth_headers,
    )

    response = await client.get(f"/api/v1/investments/stocks/{position_id}", headers=auth_headers)
    body = response.json()

    assert float(body["current_price"]) == 150.00
    assert float(body["market_value"]) == 1500.00
    assert float(body["unrealized_pnl"]) == 500.00


async def test_market_value_is_null_when_price_lookup_fails(client, auth_headers, monkeypatch):
    monkeypatch.setattr(stock_price, "get_current_price", lambda ticker: None)

    position_id = await _create_position(client, auth_headers)
    await client.post(
        f"/api/v1/investments/stocks/{position_id}/buy",
        json={"shares": "10", "price_per_share": "100.00"},
        headers=auth_headers,
    )

    response = await client.get(f"/api/v1/investments/stocks/{position_id}", headers=auth_headers)
    body = response.json()

    assert body["current_price"] is None
    assert body["market_value"] is None
    assert body["unrealized_pnl"] is None


async def test_stock_transactions_are_edited_and_deleted_only_via_investments_endpoints(
    client, auth_headers
):
    position_id = await _create_position(client, auth_headers)
    await client.post(
        f"/api/v1/investments/stocks/{position_id}/buy",
        json={"shares": "10", "price_per_share": "100.00"},
        headers=auth_headers,
    )

    transactions_response = await client.get(
        "/api/v1/transactions", params={"transaction_type": "stock_purchase"}, headers=auth_headers
    )
    transaction_id = transactions_response.json()[0]["id"]

    update_response = await client.put(
        f"/api/v1/transactions/{transaction_id}", json={"amount": "500"}, headers=auth_headers
    )
    assert update_response.status_code == 400

    delete_response = await client.delete(f"/api/v1/transactions/{transaction_id}", headers=auth_headers)
    assert delete_response.status_code == 400
