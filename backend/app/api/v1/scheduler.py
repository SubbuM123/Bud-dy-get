"""Trigger for the V2 background scheduler (services/scheduler.py).

This is the *only* trigger for the scheduler - there is no server-side cron/timer. This
app is used infrequently enough (personal use, opened every few months rather than daily)
that a fixed daily tick would mostly run against nothing due; instead, the frontend calls
this once per login (see frontend/src/features/scheduler), right after auth resolves, so
catch-up happens the moment someone opens the app rather than waiting on a schedule or a
manual button. Calling it runs services/scheduler.run_scheduled_tasks synchronously, for
every user's data (not just the caller's) - the scheduler has always been a system-wide
job, not a per-user one, so "run it now" naturally means "run the whole thing now."

Rate-limited (not just authenticated) because "system-wide job, triggerable by any single
authenticated user" is otherwise a cheap DoS lever - repeated calls are safe from a
correctness standpoint (last_executed_date/last_interest_applied_date make every posting
idempotent - see scheduler.py), but each call still does a full table scan across every
recurring rule and interest-bearing account for every user.
"""

from datetime import date

from fastapi import APIRouter, Request

from app.core.dependencies import DBSession, CurrentUser
from app.core.rate_limit import rate_limit
from app.core.request_context import system_context
from app.schemas.scheduler import SchedulerRunResponse
from app.services.scheduler import run_scheduled_tasks

router = APIRouter()


# Requires authentication (like every other route) purely to keep this off the open
# internet, not to scope its effect to the caller - see this module's docstring.
@router.post("/run", response_model=SchedulerRunResponse)
@rate_limit("2/minute")
async def run_scheduler_now(request: Request, current_user: CurrentUser, db: DBSession):
    as_of = date.today()
    # Row-level-security policies (migration 015) would otherwise clip this intentionally
    # system-wide job down to just current_user's own rows - see request_context.py's
    # system_context docstring.
    with system_context():
        counts = await run_scheduled_tasks(db, as_of=as_of)
    return SchedulerRunResponse(as_of=as_of, **counts)
