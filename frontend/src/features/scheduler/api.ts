/**
 * Thin wrapper around POST /scheduler/run - triggers the V2 background scheduler's
 * catch-up (see backend/app/api/v1/scheduler.py's docstring). Called automatically once
 * per session by MainLayout, and also available via the manual "Sync Recurring Items"
 * button (features/transactions) as a fallback. No React dependency; hooks/useScheduler.ts
 * wraps it in a React Query mutation.
 */
import apiClient from '@/lib/api-client'
import type { SchedulerRunResult } from '@/types'

export async function runScheduler(): Promise<SchedulerRunResult> {
  const response = await apiClient.post<SchedulerRunResult>('/scheduler/run')
  return response.data
}
