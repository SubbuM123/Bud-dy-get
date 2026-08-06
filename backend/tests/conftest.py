"""Shared test fixtures.

Runs the FastAPI app against an in-memory SQLite database instead of the real Postgres
instance, so the suite has no external dependencies. StaticPool is required here because
SQLite's `:memory:` database is otherwise per-connection - without it, the engine's
connection pool would hand different tests (or even the app and the test client within the
same test) separate, empty databases.

SQLite ignores foreign key constraints (including `ondelete="SET NULL"`/`"CASCADE"`)
unless `PRAGMA foreign_keys=ON` is set on every connection - unlike Postgres, which always
enforces them. Without the "connect" listener below, a test relying on an FK's `ondelete`
behavior (e.g. `transactions.income_id`'s `SET NULL` when its `Income` is deleted - see
models/transactions.py) would silently see the pre-delete value instead, passing or
failing based on an SQLite quirk that has nothing to do with the application's own logic.
"""

import os

# Must run before any `app.*` import: app.main refuses to boot with the insecure default
# SECRET_KEY once DEBUG isn't explicitly true (see main.py's startup check) - tests run
# with neither a .env file nor real deployment env vars, so both are set here to keep
# that check from firing during collection. setdefault so a real CI-provided value (if
# ever set) still wins.
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-use")
os.environ.setdefault("DEBUG", "true")

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


@pytest_asyncio.fixture
async def db_engine():
    """The in-memory SQLite engine underlying both `client` and `db_session` below - split
    out so a single test can request both and have them share one database, rather than
    each fixture spinning up its own empty engine. Function-scoped (the default), so
    within one test `db_engine` resolves to the same instance for every fixture that
    depends on it - pytest caches a fixture's result per test by name."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_engine):
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def db_session(db_engine):
    """A raw AsyncSession against the same database `client` talks to over HTTP - for
    tests that need to call a service function directly rather than through an API route
    (e.g. tests/test_scheduler.py calling services/scheduler.py's functions, which have no
    HTTP endpoint of their own - they're only ever invoked by the Celery Beat task)."""
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_maker() as session:
        yield session


@pytest_asyncio.fixture
async def auth_headers(client):
    """Register and log in a throwaway user, returning an Authorization header dict for
    tests that need to hit authenticated bank-account endpoints."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": "owner@example.com", "password": "a-real-pw"},
    )
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "a-real-pw"},
    )
    access_token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {access_token}"}
