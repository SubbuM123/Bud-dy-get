"""Secret-authenticated endpoint that triggers the daily scheduler over HTTP.

Render's own Cron Job resource requires a paid/card-verified account with no free
tier, so the scheduler is instead triggered by a GitHub Actions scheduled workflow
(free) that POSTs here once a day with the CRON_SECRET header (see
.github/workflows/scheduler.yml). This is deliberately separate from
api/v1/scheduler.py's `/run` endpoint, which is JWT-authenticated and meant for a
logged-in user to trigger a catch-up run - this one has no user session at all, so
it's authenticated by a shared secret instead.
"""

import hmac
from datetime import date

from fastapi import APIRouter, Header, HTTPException, status

from app.config import get_settings
from app.core.dependencies import DBSession
from app.schemas.scheduler import SchedulerRunResponse
from app.services.scheduler import run_scheduled_tasks

router = APIRouter()


@router.post("/run-scheduler", response_model=SchedulerRunResponse)
async def run_scheduler_cron(db: DBSession, x_cron_secret: str = Header(default="")):
    settings = get_settings()
    if not settings.cron_secret or not hmac.compare_digest(x_cron_secret, settings.cron_secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid cron secret")

    as_of = date.today()
    counts = await run_scheduled_tasks(db, as_of=as_of)
    return SchedulerRunResponse(as_of=as_of, **counts)
