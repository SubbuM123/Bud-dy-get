"""Centralized application configuration, loaded from environment variables.

This module defines the single Settings object that every other module in
the backend reads from (database URL, JWT secret, CORS origins, etc.) rather
than reading environment variables directly. Values default to sensible
local-development values but are expected to be overridden via a .env file
or real environment variables in staging/production. `get_settings()` is
cached so the environment is only parsed once per process.
"""

from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode
from functools import lru_cache

# Shared between Settings.secret_key's default and main.py's startup check - if this
# literal is still in effect once DEBUG=false, every JWT is signed with a key anyone can
# read straight out of this file, so main.py refuses to start rather than silently
# accepting it.
INSECURE_DEFAULT_SECRET_KEY = "your-secret-key-change-in-production"


class Settings(BaseSettings):
    app_name: str = "Personal Finance Dashboard"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/finance_db"

    # JWT
    secret_key: str = INSECURE_DEFAULT_SECRET_KEY
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # CORS
    #
    # pydantic-settings JSON-decodes list-typed env vars by default (e.g. requires
    # CORS_ORIGINS='["https://a.com","https://b.com"]'), which isn't what anyone types
    # into a Render dashboard field - it raises a SettingsError before the app even
    # starts. NoDecode turns that automatic JSON parsing off for this field, and the
    # validator below splits a plain comma-separated string ("https://a.com,https://b.com")
    # into a list instead. A value that's already a list (e.g. from a .env file written
    # as JSON) passes through unchanged.
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]
    cors_origin_regex: str | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    class Config:
        env_file = ".env"


# Cached accessor so Settings() is only constructed once per process.
@lru_cache
def get_settings() -> Settings:
    return Settings()
