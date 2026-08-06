/**
 * Thin wrapper around POST /scheduler/run - manually triggers the V2 background
 * scheduler instead of waiting for its daily Celery Beat tick (see
 * backend/app/api/v1/scheduler.py's docstring for why this endpoint exists). No React
 * dependency; hooks/useScheduler.ts wraps it in a React Query mutation.
 */
import apiClient from '@/lib/api-client'
import type { SchedulerRunResult } from '@/types'

export async function runScheduler(): Promise<SchedulerRunResult> {
  const response = await apiClient.post<SchedulerRunResult>('/scheduler/run')
  return response.data
}
