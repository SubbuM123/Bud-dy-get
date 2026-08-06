/**
 * Thin wrappers around the /income backend endpoints. These are plain async functions
 * with no React dependency; hooks/useIncome.ts wraps each one in a React Query hook for
 * caching/invalidation - the same split every other feature module uses.
 */
import apiClient from '@/lib/api-client'
import type {
  Income,
  IncomeFrequency,
  AllocationDestinationType,
  ContributionSourceType,
  LogIncomeResponse,
} from '@/types'

// Fetch every income belonging to the current user.
export async function getIncomes(): Promise<Income[]> {
  const response = await apiClient.get<Income[]>('/income')
  return response.data
}

// Fetch a single income by id.
export async function getIncome(id: string): Promise<Income> {
  const response = await apiClient.get<Income>(`/income/${id}`)
  return response.data
}

export interface IncomeAllocationPayload {
  destination_type: AllocationDestinationType
  destination_id: string
  percentage: number
  // 'pre_tax_salary' only - see types/index.ts:IncomeAllocation. Omit/undefined for an
  // ordinary allocation.
  source_type?: ContributionSourceType
}

export interface IncomePayload {
  name: string
  amount: number
  is_recurring: boolean
  frequency?: IncomeFrequency
  start_date?: string
  income_date?: string
  allocations: IncomeAllocationPayload[]
}

// Create a new income (recurring rule or one-time payment). A one-time income is
// immediately logged server-side - real Transaction rows posted, real balances bumped -
// so no separate logIncome call is needed for it.
export async function createIncome(data: IncomePayload): Promise<Income> {
  const response = await apiClient.post<Income>('/income', data)
  return response.data
}

// Patch an income's own fields (name/amount/frequency/is_active) - not its allocations,
// see replaceIncomeAllocations for that.
export async function updateIncome(
  id: string,
  data: Partial<Pick<IncomePayload, 'name' | 'amount' | 'frequency'>> & { is_active?: boolean }
): Promise<Income> {
  const response = await apiClient.put<Income>(`/income/${id}`, data)
  return response.data
}

// Replace every allocation on an income wholesale.
export async function replaceIncomeAllocations(
  id: string,
  allocations: IncomeAllocationPayload[]
): Promise<Income> {
  const response = await apiClient.put<Income>(`/income/${id}/allocations`, { allocations })
  return response.data
}

// Delete an income. Past logged transactions are kept.
export async function deleteIncome(id: string): Promise<void> {
  await apiClient.delete(`/income/${id}`)
}

// Log one real occurrence of a (usually recurring) income: splits the given amount
// (defaults to the income's own amount) across its allocations, posting real Transaction
// rows and bumping every destination account's real balance.
export async function logIncome(
  id: string,
  data?: { amount?: number; log_date?: string }
): Promise<LogIncomeResponse> {
  const response = await apiClient.post<LogIncomeResponse>(`/income/${id}/log`, data ?? {})
  return response.data
}
