"""Async SQLAlchemy engine, session factory, and declarative base.

Every ORM model in the app (see app/models) inherits from the `Base` class
defined here, and every database-touching request obtains its session
through the `get_db` FastAPI dependency, which guarantees the session is
closed after the request completes even if a handler raises. The engine URL
and echo/debug flag are pulled from the centralized Settings object in
config.py so behavior can be tuned per-environment without code changes.
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

_engine_kwargs = {
    "echo": settings.debug,
    "future": True,
}

if settings.database_url.startswith("postgresql"):
    # statement_cache_size=0 alone stops asyncpg from *caching* prepared statements, but
    # it still auto-names each one (__asyncpg_stmt_N__) - since PgBouncer's transaction
    # pooling can hand two different pooled connections the same backend session, that
    # name can collide server-side (DuplicatePreparedStatementError). Forcing every
    # prepared statement to use PostgreSQL's anonymous/unnamed slot instead of a named one
    # sidesteps the collision entirely.
    _engine_kwargs["connect_args"] = {
        "ssl": "require",
        "statement_cache_size": 0,
        "prepared_statement_name_func": lambda: "",
    }
    _engine_kwargs["pool_size"] = 5
    _engine_kwargs["max_overflow"] = 5

engine = create_async_engine(settings.database_url, **_engine_kwargs)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Declarative base class that all ORM models inherit from."""

    pass


# FastAPI dependency that yields a request-scoped async session and always closes it.
async def get_db() -> AsyncSession:
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
