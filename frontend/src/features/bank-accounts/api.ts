/**
 * Thin wrappers around the /bank-accounts backend endpoints (accounts, recurring actions,
 * and the growth simulation). These are plain async functions with no React dependency;
 * hooks/useBankAccounts.ts wraps each one in a React Query hook for caching/invalidation.
 */
import apiClient from '@/lib/api-client'
import type {
  BankAccount,
  RecurringAction,
  SimulationResponse,
  CombinedSimulationResponse,
  ActionCategory,
} from '@/types'

// Fetch every bank account belonging to the current user.
export async function getBankAccounts(): Promise<BankAccount[]> {
  const response = await apiClient.get<BankAccount[]>('/bank-accounts')
  return response.data
}

// Fetch a single bank account by id.
export async function getBankAccount(id: string): Promise<BankAccount> {
  const response = await apiClient.get<BankAccount>(`/bank-accounts/${id}`)
  return response.data
}

// Create a new bank account.
export async function createBankAccount(data: {
  account_name: string
  account_type: 'savings' | 'checking' | 'cd'
  principal: number
  interest_rate?: number
  compounding_frequency?: string
  cd_start_date?: string
  cd_term_months?: number
  cd_auto_renew?: boolean
  is_simulation?: boolean
}): Promise<BankAccount> {
  const response = await apiClient.post<BankAccount>('/bank-accounts', data)
  return response.data
}

// Patch a bank account with whichever fields are provided.
export async function updateBankAccount(
  id: string,
  data: Partial<{
    account_name: string
    principal: number
    interest_rate: number
    compounding_frequency: string
    cd_start_date: string
    cd_term_months: number
    cd_auto_renew: boolean
  }>
): Promise<BankAccount> {
  const response = await apiClient.put<BankAccount>(`/bank-accounts/${id}`, data)
  return response.data
}

// Delete a bank account and its associated recurring actions/transactions.
export async function deleteBankAccount(id: string): Promise<void> {
  await apiClient.delete(`/bank-accounts/${id}`)
}

// Run a growth projection for an account over the given number of months.
export async function simulateGrowth(
  accountId: string,
  months: number,
  includeRecurring: boolean = true
): Promise<SimulationResponse> {
  const response = await apiClient.post<SimulationResponse>(
    `/bank-accounts/${accountId}/simulate`,
    { months, include_recurring: includeRecurring }
  )
  return response.data
}

// Fetch the recurring deposit/withdrawal rules attached to an account.
export async function getRecurringActions(accountId: string): Promise<RecurringAction[]> {
  const response = await apiClient.get<RecurringAction[]>(
    `/bank-accounts/${accountId}/recurring-actions`
  )
  return response.data
}

// Add a new recurring deposit/withdrawal rule to an account.
export async function createRecurringAction(
  accountId: string,
  data: {
    action_type: 'deposit' | 'withdrawal'
    amount: number
    description?: string
    category?: ActionCategory
    frequency_value: number
    frequency_unit: 'days' | 'weeks' | 'months'
    start_date: string
    end_date?: string
  }
): Promise<RecurringAction> {
  const response = await apiClient.post<RecurringAction>(
    `/bank-accounts/${accountId}/recurring-actions`,
    data
  )
  return response.data
}

// Patch a recurring action with whichever fields are provided (start_date and
// action_type are intentionally not patchable - immutable once created).
export async function updateRecurringAction(
  actionId: string,
  data: Partial<{
    amount: number
    description: string
    category: ActionCategory
    frequency_value: number
    frequency_unit: 'days' | 'weeks' | 'months'
    end_date: string | null
    is_active: boolean
  }>
): Promise<RecurringAction> {
  const response = await apiClient.put<RecurringAction>(
    `/bank-accounts/recurring-actions/${actionId}`,
    data
  )
  return response.data
}

// Delete a recurring action.
export async function deleteRecurringAction(actionId: string): Promise<void> {
  await apiClient.delete(`/bank-accounts/recurring-actions/${actionId}`)
}

// Run a combined growth projection across the given accounts (or every account the user
// owns, when accountIds is omitted), applying CD maturity rules (roll into a new term,
// or deposit into a savings account). Drives the Bank Accounts page's combined
// simulation section, including its per-account include/exclude checkboxes.
export async function simulateCombinedGrowth(
  months: number,
  includeRecurring: boolean = true,
  accountIds?: string[]
): Promise<CombinedSimulationResponse> {
  const response = await apiClient.post<CombinedSimulationResponse>(
    '/bank-accounts/simulate-combined',
    { months, include_recurring: includeRecurring, account_ids: accountIds ?? null }
  )
  return response.data
}
