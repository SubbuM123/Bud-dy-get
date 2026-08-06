"""Pydantic response schema for the manual scheduler-trigger endpoint.

Mirrors services/scheduler.run_scheduled_tasks's return shape - see api/v1/scheduler.py's
docstring for why this endpoint exists alongside the daily Celery Beat task.
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
