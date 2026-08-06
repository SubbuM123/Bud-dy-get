"""FastAPI application entry point.

This module builds and configures the single FastAPI `app` instance that
Uvicorn serves (see backend/Dockerfile.prod's CMD). It wires up CORS so the
frontend can call the API, mounts every versioned route under /api/v1 via
the aggregated router in api/v1/router.py, and exposes a simple health-check
endpoint used by Render's health check and load balancers to verify the
service is up. The daily scheduler is triggered over HTTP by a GitHub Actions
scheduled workflow calling the secret-authenticated /cron/run-scheduler route
(api/cron.py) - Render's Cron Job resource has no free tier, so it isn't used.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy.exc import DBAPIError

from app.config import get_settings, INSECURE_DEFAULT_SECRET_KEY
from app.api.v1.router import api_router
from app.api.cron import router as cron_router
from app.core.rate_limit import limiter

logger = logging.getLogger(__name__)

settings = get_settings()

# Refuse to boot with the checked-in placeholder secret once DEBUG=false - every access/
# refresh JWT is signed with this key, so leaving the default in effect in production
# means anyone who has read this file can forge a token for any user.
if not settings.debug and settings.secret_key == INSECURE_DEFAULT_SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY is still set to its insecure default. Set a real SECRET_KEY "
        "environment variable before running with DEBUG=false."
    )

app = FastAPI(
    title=settings.app_name,
    description="A comprehensive personal finance management dashboard",
    version="1.0.0",
    # OpenAPI docs reveal every route's request/response shape; harmless on their own
    # (every route still enforces its own auth), but there's no reason to expose them
    # once this is a real deployment rather than a local dev instance.
    docs_url="/api/docs" if settings.debug else None,
    redoc_url="/api/redoc" if settings.debug else None,
    openapi_url="/api/openapi.json" if settings.debug else None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_origin_regex=settings.cors_origin_regex,
)


# Catches driver-level DB errors that reach here unhandled - most commonly a malformed
# UUID passed as a path parameter (id fields are typed `str`, not `UUID`, across every
# router; Postgres raises on a non-UUID string compared against a UUID column). Without
# this, such a request 500s with the raw driver exception message exposed to the client.
# The exception is logged server-side (with the DB's actual detail) and a generic 400
# returned to the client instead.
@app.exception_handler(DBAPIError)
async def db_error_handler(request: Request, exc: DBAPIError) -> JSONResponse:
    logger.error("Unhandled database error on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": "Invalid request"},
    )


app.include_router(api_router, prefix="/api/v1")
app.include_router(cron_router, prefix="/cron", tags=["cron"])


# Liveness probe used by Render's health check; not part of the versioned API.
@app.get("/health")
async def health_check():
    return {"status": "healthy"}
