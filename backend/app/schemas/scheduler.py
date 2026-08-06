"""Pydantic response schema for the scheduler-trigger endpoints.

Mirrors services/scheduler.run_scheduled_tasks's return shape. Shared by both the
JWT-authenticated manual trigger (api/v1/scheduler.py) and the secret-authenticated
daily cron trigger (api/cron.py).
"""

from pydantic import BaseModel
from datetime import date


class SchedulerRunResponse(BaseModel):
    as_of: date
    incomes_posted: int
    bank_interest_applied: int
    retirement_interest_applied: int
    education_interest_applied: int
    retirement_contributions_posted: int
    education_contributions_posted: int
    expenses_created: int
