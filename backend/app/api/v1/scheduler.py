"""Manual trigger for the V2 background scheduler (services/scheduler.py).

The scheduler's primary entry point is the daily Render Cron Job (app/cron/
run_scheduler.py, invoked directly against the DB - no HTTP hop). This endpoint exists so
a user isn't stuck waiting for the next scheduled tick (up to 24 hours away) to see a
newly-created recurring rule actually catch up. Calling it runs the exact same
services/scheduler.run_scheduled_tasks the daily cron calls, synchronously, for every
user's data (not just the caller's) - the scheduler has always been a system-wide job, not
a per-user one, so "run it now" naturally means "run the whole thing now," the same as the
daily tick would.

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
from app.schemas.scheduler import SchedulerRunResponse
from app.services.scheduler import run_scheduled_tasks

router = APIRouter()


# Requires authentication (like every other route) purely to keep this off the open
# internet, not to scope its effect to the caller - see this module's docstring.
@router.post("/run", response_model=SchedulerRunResponse)
@rate_limit("2/minute")
async def run_scheduler_now(request: Request, current_user: CurrentUser, db: DBSession):
    as_of = date.today()
    counts = await run_scheduled_tasks(db, as_of=as_of)
    return SchedulerRunResponse(as_of=as_of, **counts)
