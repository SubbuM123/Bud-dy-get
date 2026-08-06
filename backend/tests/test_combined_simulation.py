"""Coverage for POST /bank-accounts/simulate-combined and the CD maturity rules it
applies (services/combined_simulator.py): a matured CD either rolls into a new CD term
(cd_auto_renew=True) or deposits into a savings account - the user's own if one exists,
otherwise a synthesized "virtual-savings" bucket. Runs against SQLite like the rest of
the suite (see conftest.py).
"""
from datetime import date

SAVINGS_PAYLOAD = {
    "account_name": "Everyday Savings",
    "account_type": "savings",
    "principal": "1000.00",
    "interest_rate": "0.02",
    "compounding_frequency": "monthly",
}


def _cd_payload(auto_renew: bool, term_months: int = 3, principal: str = "2000.00"):
    return {
        "account_name": "Short CD",
        "account_type": "cd",
        "principal": principal,
        "interest_rate": "0.12",
        "compounding_frequency": "monthly",
        "cd_start_date": date.today().isoformat(),
        "cd_term_months": term_months,
        "cd_auto_renew": auto_renew,
    }


async def test_combined_total_equals_sum_of_plain_accounts_every_month(client, auth_headers):
    await client.post("/api/v1/bank-accounts", json=SAVINGS_PAYLOAD, headers=auth_headers)
    await client.post(
        "/api/v1/bank-accounts",
        json={**SAVINGS_PAYLOAD, "account_name": "Second Savings", "principal": "500.00"},
        headers=auth_headers,
    )

    response = await client.post(
        "/api/v1/bank-accounts/simulate-combined",
        json={"months": 6, "include_recurring": True},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["accounts"]) == 2

    for month in range(7):
        expected = sum(
            float(series["projections"][month]["balance"]) for series in body["accounts"]
        )
        actual = float(body["total_projections"][month]["total_balance"])
        assert actual == round(expected, 2)

    assert float(body["final_total_balance"]) == float(
        body["total_projections"][-1]["total_balance"]
    )


async def test_cd_maturity_without_auto_renew_deposits_into_existing_savings(
    client, auth_headers
):
    await client.post("/api/v1/bank-accounts", json=SAVINGS_PAYLOAD, headers=auth_headers)
    await client.post(
        "/api/v1/bank-accounts", json=_cd_payload(auto_renew=False), headers=auth_headers
    )

    response = await client.post(
        "/api/v1/bank-accounts/simulate-combined",
        json={"months": 10, "include_recurring": True},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()

    account_ids = [a["account_id"] for a in body["accounts"]]
    assert "virtual-savings" not in account_ids

    cd_series = next(a for a in body["accounts"] if a["account_type"] == "cd")
    savings_series = next(a for a in body["accounts"] if a["account_type"] == "savings")

    # The CD's own series stops at maturity rather than covering the full window.
    assert cd_series["projections"][-1]["month"] < 10

    # The real savings account ends up with more than it would have on its own
    # (principal 1000 @ 2% for 10 months), because the matured CD's ~2000 landed in it.
    assert float(savings_series["projections"][-1]["balance"]) > 2500


async def test_cd_maturity_without_auto_renew_and_no_savings_creates_virtual_bucket(
    client, auth_headers
):
    await client.post(
        "/api/v1/bank-accounts", json=_cd_payload(auto_renew=False), headers=auth_headers
    )

    response = await client.post(
        "/api/v1/bank-accounts/simulate-combined",
        json={"months": 10, "include_recurring": True},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()

    virtual = next(
        (a for a in body["accounts"] if a["account_id"] == "virtual-savings"), None
    )
    assert virtual is not None
    assert virtual["is_virtual"] is True
    assert virtual["account_type"] == "savings"
    # The matured ~2000 CD balance should show up in the virtual bucket by the end.
    assert float(virtual["projections"][-1]["balance"]) > 1900


async def test_cd_auto_renew_keeps_compounding_past_maturity(client, auth_headers):
    await client.post(
        "/api/v1/bank-accounts", json=_cd_payload(auto_renew=True), headers=auth_headers
    )

    response = await client.post(
        "/api/v1/bank-accounts/simulate-combined",
        json={"months": 10, "include_recurring": True},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()

    account_ids = [a["account_id"] for a in body["accounts"]]
    assert any(aid.endswith("-renewal-1") for aid in account_ids)


async def test_auto_renewing_cd_out_earns_a_non_renewing_cd_with_no_savings_account(
    client, auth_headers
):
    # Two otherwise-identical users, one auto-renews the CD, one lets it fall into a
    # 0%-rate virtual savings bucket - the renewer should end up with more money.
    await client.post(
        "/api/v1/auth/register", json={"email": "renew@example.com", "password": "a-real-pw"}
    )
    renew_login = await client.post(
        "/api/v1/auth/login", json={"email": "renew@example.com", "password": "a-real-pw"}
    )
    renew_headers = {"Authorization": f"Bearer {renew_login.json()['access_token']}"}

    await client.post(
        "/api/v1/auth/register", json={"email": "norenew@example.com", "password": "a-real-pw"}
    )
    norenew_login = await client.post(
        "/api/v1/auth/login", json={"email": "norenew@example.com", "password": "a-real-pw"}
    )
    norenew_headers = {"Authorization": f"Bearer {norenew_login.json()['access_token']}"}

    await client.post(
        "/api/v1/bank-accounts", json=_cd_payload(auto_renew=True), headers=renew_headers
    )
    await client.post(
        "/api/v1/bank-accounts", json=_cd_payload(auto_renew=False), headers=norenew_headers
    )

    renew_response = await client.post(
        "/api/v1/bank-accounts/simulate-combined",
        json={"months": 10, "include_recurring": True},
        headers=renew_headers,
    )
    norenew_response = await client.post(
        "/api/v1/bank-accounts/simulate-combined",
        json={"months": 10, "include_recurring": True},
        headers=norenew_headers,
    )

    assert float(renew_response.json()["final_total_balance"]) > float(
        norenew_response.json()["final_total_balance"]
    )


async def test_combined_simulation_account_ids_restricts_which_accounts_are_included(
    client, auth_headers
):
    savings_response = await client.post(
        "/api/v1/bank-accounts", json=SAVINGS_PAYLOAD, headers=auth_headers
    )
    savings_id = savings_response.json()["id"]
    await client.post(
        "/api/v1/bank-accounts",
        json={**SAVINGS_PAYLOAD, "account_name": "Second Savings", "principal": "500.00"},
        headers=auth_headers,
    )

    response = await client.post(
        "/api/v1/bank-accounts/simulate-combined",
        json={"months": 6, "include_recurring": True, "account_ids": [savings_id]},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["accounts"]) == 1
    assert body["accounts"][0]["account_id"] == savings_id
    assert float(body["final_total_balance"]) < 1500


async def test_renewal_segments_are_flagged_as_continuations_to_prevent_double_counting(
    client, auth_headers
):
    """Regression test for a real bug: a CD that renews enough times to push a segment
    past a frontend chart's "fold the rest into one line" cutoff was summing each
    renewal segment's shared boundary-month point twice, since the frontend didn't know
    which segments were continuations of the same CD. is_continuation - true for every
    renewal segment after the first - is what a client needs to skip that duplicated
    point, exactly like this endpoint's own total_projections already does internally.
    """
    await client.post(
        "/api/v1/bank-accounts",
        json=_cd_payload(auto_renew=True, term_months=1),
        headers=auth_headers,
    )

    response = await client.post(
        "/api/v1/bank-accounts/simulate-combined",
        json={"months": 6, "include_recurring": True},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    segments = body["accounts"]
    # A 1-month term over a 6-month window renews multiple times.
    assert len(segments) > 1

    first_segment = segments[0]
    later_segments = segments[1:]
    assert first_segment["is_continuation"] is False
    assert all(seg["is_continuation"] is True for seg in later_segments)

    # Summing every segment's own balance at each month, skipping a continuation
    # segment's first (duplicate-boundary) point, must reproduce the backend's own total -
    # proving is_continuation carries enough information for a client to do this correctly.
    totals_by_month = {p["month"]: float(p["total_balance"]) for p in body["total_projections"]}
    reconstructed = {m: 0.0 for m in totals_by_month}
    naive = {m: 0.0 for m in totals_by_month}
    for seg in segments:
        points = seg["projections"]
        start_idx = 1 if seg["is_continuation"] and points else 0
        for point in points[start_idx:]:
            reconstructed[point["month"]] += float(point["balance"])
        for point in points:
            naive[point["month"]] += float(point["balance"])

    for month, total in totals_by_month.items():
        assert round(reconstructed[month], 2) == round(total, 2)

    # The naive (continuation-unaware) sum used to match a shared boundary month like the
    # frontend bug did - demonstrating that skipping is_continuation would have been wrong.
    boundary_months = [
        p["month"] for p in segments[1]["projections"] if p["month"] == segments[0]["projections"][-1]["month"]
    ]
    assert boundary_months, "expected a shared boundary month between segments 0 and 1"
    boundary_month = boundary_months[0]
    assert naive[boundary_month] > totals_by_month[boundary_month]


async def test_combined_simulation_with_no_accounts_returns_empty_series(client, auth_headers):
    response = await client.post(
        "/api/v1/bank-accounts/simulate-combined",
        json={"months": 6, "include_recurring": True},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["accounts"] == []
    assert float(body["final_total_balance"]) == 0
    assert len(body["total_projections"]) == 7
