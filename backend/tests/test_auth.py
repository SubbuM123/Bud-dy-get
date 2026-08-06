"""Regression coverage for the register -> login -> /users/me flow that broke twice in
practice: once because no migration had run against a fresh database, and once because
passlib/bcrypt version drift made every password hash raise "password cannot be longer
than 72 bytes" regardless of actual length.
"""

CREDENTIALS = {"email": "jd@example.com", "password": "a-real-pw", "full_name": "JD"}


async def test_register_creates_user(client):
    response = await client.post("/api/v1/auth/register", json=CREDENTIALS)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == CREDENTIALS["email"]
    assert "password_hash" not in body
    assert "password" not in body


async def test_register_rejects_duplicate_email(client):
    await client.post("/api/v1/auth/register", json=CREDENTIALS)
    response = await client.post("/api/v1/auth/register", json=CREDENTIALS)

    assert response.status_code == 400


async def test_register_accepts_a_short_normal_password(client):
    """Guards against the passlib/bcrypt 72-byte regression: an ordinary 8-character
    password must hash successfully, not raise ValueError."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "short@example.com", "password": "eight111"},
    )

    assert response.status_code == 201


async def test_login_succeeds_with_correct_credentials(client):
    await client.post("/api/v1/auth/register", json=CREDENTIALS)

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": CREDENTIALS["email"], "password": CREDENTIALS["password"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


async def test_login_rejects_wrong_password(client):
    await client.post("/api/v1/auth/register", json=CREDENTIALS)

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": CREDENTIALS["email"], "password": "not-the-password"},
    )

    assert response.status_code == 401


async def test_login_rejects_unknown_email(client):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "whatever123"},
    )

    assert response.status_code == 401


async def test_access_token_from_login_authenticates_me_endpoint(client):
    await client.post("/api/v1/auth/register", json=CREDENTIALS)
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": CREDENTIALS["email"], "password": CREDENTIALS["password"]},
    )
    access_token = login_response.json()["access_token"]

    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == CREDENTIALS["email"]


async def test_me_endpoint_rejects_missing_token(client):
    response = await client.get("/api/v1/users/me")

    assert response.status_code == 401


async def test_refresh_issues_new_access_token(client):
    await client.post("/api/v1/auth/register", json=CREDENTIALS)
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": CREDENTIALS["email"], "password": CREDENTIALS["password"]},
    )
    # Passed explicitly rather than relying on the client's cookie jar to resend it:
    # the cookie is set with Secure=True, and httpx's jar (correctly) won't attach a
    # Secure cookie to a follow-up request over the test transport's http:// scheme.
    refresh_cookie = login_response.cookies["refresh_token"]

    response = await client.post(
        "/api/v1/auth/refresh", cookies={"refresh_token": refresh_cookie}
    )

    assert response.status_code == 200
    assert response.json()["access_token"]


async def test_refresh_without_cookie_is_rejected(client):
    response = await client.post("/api/v1/auth/refresh")

    assert response.status_code == 401


async def test_refresh_rejects_an_access_token_used_as_a_refresh_token(client):
    await client.post("/api/v1/auth/register", json=CREDENTIALS)
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": CREDENTIALS["email"], "password": CREDENTIALS["password"]},
    )
    access_token = login_response.json()["access_token"]

    response = await client.post(
        "/api/v1/auth/refresh", cookies={"refresh_token": access_token}
    )

    assert response.status_code == 401
