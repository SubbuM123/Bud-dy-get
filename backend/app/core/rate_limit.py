"""Shared slowapi rate limiter instance.

A single Limiter is created here and imported by both main.py (to register it on the
app and handle 429s) and any router that needs to decorate an individual endpoint
(e.g. api/v1/auth.py's login/register, api/v1/scheduler.py's manual run trigger) -
slowapi requires the same Limiter instance be used for `app.state.limiter` and every
`@limiter.limit(...)` decorator for its exception handler to fire correctly.

Keyed by remote address (IP) rather than by user, since the endpoints this protects
either run before authentication (login/register) or should be throttled regardless of
which authenticated user is calling (scheduler run).

`rate_limit()` below - not `limiter.limit()` directly - is what every router should
import and decorate with. In DEBUG mode (the test suite's default - see
tests/conftest.py) it's a no-op: the limiter's in-memory counters are process-wide and
never reset between tests, and dozens of tests across the suite hit /auth/register or
/auth/login via the shared `auth_headers` fixture, so a real per-minute limit would
eventually 429 an unrelated test purely from cumulative test-suite traffic. Skipping
slowapi's own enable/disable switch in favor of this wrapper keeps the test bypass fully
inside this codebase rather than depending on an unverified library internal.
"""

from typing import Callable

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings

limiter = Limiter(key_func=get_remote_address)


def rate_limit(limit_string: str) -> Callable:
    settings = get_settings()
    if settings.debug:
        return lambda func: func
    return limiter.limit(limit_string)
