"""Entry point for the daily scheduler, run directly by Render's Cron Job service.

Replaces the old Celery Beat task: instead of enqueueing a job onto a broker for a
separate worker process to pick up, the Cron Job runs this script in its own one-off
container (same image as the web service) with a direct DB connection - no broker,
no HTTP round-trip, no secret token to manage.

Invoked as: python -m app.cron.run_scheduler
"""

import asyncio
from datetime import date

from app.database import async_session_maker
from app.services.scheduler import run_scheduled_tasks


async def main() -> None:
    async with async_session_maker() as db:
        result = await run_scheduled_tasks(db, as_of=date.today())
    print(f"Scheduler run complete: {result}")


if __name__ == "__main__":
    asyncio.run(main())
