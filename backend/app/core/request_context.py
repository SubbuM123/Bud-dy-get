"""Per-request identity used to drive Postgres row-level security.

`current_user_id` is set once per request (in `core.auth.get_current_user`, right after
the bearer token resolves to a User row) and read by `app.database`'s SQLAlchemy `begin`
event listener, which re-issues it to Postgres as a transaction-local `app.current_user_id`
setting at the start of every transaction - see that module's docstring for why it has to
be re-issued per-transaction rather than set once per session.

`rls_bypass` exists for exactly one caller: `api/v1/scheduler.py`'s `run_scheduler_now`,
which intentionally runs a system-wide job across every user's data (see that module's
docstring) and would otherwise be silently clipped to the triggering user's own rows once
RLS policies are in place. `system_context()` is the only supported way to set it.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

current_user_id: ContextVar[str | None] = ContextVar("current_user_id", default=None)
rls_bypass: ContextVar[bool] = ContextVar("rls_bypass", default=False)


@contextmanager
def system_context() -> Iterator[None]:
    """Mark the current request as a trusted system job that bypasses row-level security.

    Only for jobs that are legitimately system-wide by design (currently just the V2
    scheduler's manual-run trigger) - never for handling a single user's own request, even
    an administrative one.
    """
    token = rls_bypass.set(True)
    try:
        yield
    finally:
        rls_bypass.reset(token)
