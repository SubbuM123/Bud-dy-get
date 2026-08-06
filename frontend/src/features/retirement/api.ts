/**
 * Thin wrappers around the /retirement-accounts (and profile-related /users/me) backend
 * endpoints. These are plain async functions with no React dependency;
 * hooks/useRetirementAccounts.ts wraps each one in a React Query hook for caching/invalidation.
 */
import apiClient from '@/lib/api-client'
import type {
  RetirementAccount,
  RetirementAccountType,
  VestingType,
  RetirementSimulationResponse,
  ContributionLimitInfo,
  UserProfile,
  FilingStatus,
  RetirementRecurringContribution,
  ContributionFrequency,
  ContributionSourceType,
} from '@/types'

// Fetch every retirement account belonging to the current user.
export async function getRetirementAccounts(): Promise<RetirementAccount[]> {
  const response = await apiClient.get<RetirementAccount[]>('/retirement-accounts')
  return response.data
}

// Fetch a single retirement account by id.
export async function getRetirementAccount(id: string): Promise<RetirementAccount> {
  const response = await apiClient.get<RetirementAccount>(`/retirement-accounts/${id}`)
  return response.data
}

export interface RetirementAccountPayload {
  account_name: string
  account_type: RetirementAccountType
  balance: number
  employer_name?: string
  annual_salary?: number
  employer_match_percent?: number
  employer_match_limit_percent?: number
  vesting_type?: VestingType
  vesting_years?: number
  expected_return_rate?: number
  is_simulation?: boolean
}

// Create a new retirement account.
export async function createRetirementAccount(
  data: RetirementAccountPayload
): Promise<RetirementAccount> {
  const response = await apiClient.post<RetirementAccount>('/retirement-accounts', data)
  return response.data
}

// Patch a retirement account with whichever fields are provided.
export async function updateRetirementAccount(
  id: string,
  data: Partial<RetirementAccountPayload>
): Promise<RetirementAccount> {
  const response = await apiClient.put<RetirementAccount>(`/retirement-accounts/${id}`, data)
  return response.data
}

// Delete a retirement account.
export async function deleteRetirementAccount(id: string): Promise<void> {
  await apiClient.delete(`/retirement-accounts/${id}`)
}

// Run a growth projection for an account. monthlyEmployeeContribution is an extra
// hypothetical amount on top of whatever the account's own active recurring
// contributions already add each month (includeRecurring=true, the default) - 401(k)/
// Roth 401(k) accounts also earn the account's own employer match on the combined total.
export async function simulateRetirementGrowth(
  accountId: string,
  months: number,
  monthlyEmployeeContribution: number = 0,
  includeRecurring: boolean = true
): Promise<RetirementSimulationResponse> {
  const response = await apiClient.post<RetirementSimulationResponse>(
    `/retirement-accounts/${accountId}/simulate`,
    {
      months,
      monthly_employee_contribution: monthlyEmployeeContribution,
      include_recurring: includeRecurring,
    }
  )
  return response.data
}

// Fetch the recurring contributions scheduled against an account.
export async function getRecurringContributions(
  accountId: string
): Promise<RetirementRecurringContribution[]> {
  const response = await apiClient.get<RetirementRecurringContribution[]>(
    `/retirement-accounts/${accountId}/recurring-contributions`
  )
  return response.data
}

// Add a new monthly/yearly recurring contribution to an account. This only feeds growth
// simulations - it does not itself post real contributions over time; use
// recordContribution for that.
export async function createRecurringContribution(
  accountId: string,
  data: {
    amount: number
    frequency: ContributionFrequency
    start_date: string
    end_date?: string
  }
): Promise<RetirementRecurringContribution> {
  const response = await apiClient.post<RetirementRecurringContribution>(
    `/retirement-accounts/${accountId}/recurring-contributions`,
    data
  )
  return response.data
}

// Patch a recurring contribution with whichever fields are provided.
export async function updateRecurringContribution(
  contributionId: string,
  data: Partial<{
    amount: number
    frequency: ContributionFrequency
    end_date: string | null
    is_active: boolean
  }>
): Promise<RetirementRecurringContribution> {
  const response = await apiClient.put<RetirementRecurringContribution>(
    `/retirement-accounts/recurring-contributions/${contributionId}`,
    data
  )
  return response.data
}

// Delete a recurring contribution.
export async function deleteRecurringContribution(contributionId: string): Promise<void> {
  await apiClient.delete(`/retirement-accounts/recurring-contributions/${contributionId}`)
}

// Fetch the current user's 2026 contribution limit (and, for Roth/Traditional IRA,
// income-based eligibility) for a given account type.
export async function getContributionLimits(
  accountType: RetirementAccountType
): Promise<ContributionLimitInfo> {
  const response = await apiClient.get<ContributionLimitInfo>('/retirement-accounts/limits', {
    params: { account_type: accountType },
  })
  return response.data
}

// Record a real contribution to an account; rejected (400) if it would exceed the
// caller's remaining limit for that account's contribution family. sourceType says where
// the money actually came from (defaults to 'track_only' - just record the number, don't
// touch any other account); sourceBankAccountId is required when sourceType is
// 'bank_account' and debits that account's real balance.
export async function recordContribution(
  accountId: string,
  amount: number,
  sourceType: ContributionSourceType = 'track_only',
  sourceBankAccountId?: string
): Promise<ContributionLimitInfo> {
  const response = await apiClient.post<ContributionLimitInfo>(
    `/retirement-accounts/${accountId}/contribute`,
    { amount, source_type: sourceType, source_bank_account_id: sourceBankAccountId }
  )
  return response.data
}

// Fetch the current user's own profile, including the Phase 4 fields used for
// contribution-limit calculations.
export async function getMyProfile(): Promise<UserProfile> {
  const response = await apiClient.get<UserProfile>('/users/me')
  return response.data
}

// Patch the current user's profile (birth_date, filing_status, annual_income,
// has_employer_retirement_plan) - the fields services/retirement_rules.py reads.
export async function updateMyProfile(data: {
  birth_date?: string
  filing_status?: FilingStatus
  annual_income?: number
  has_employer_retirement_plan?: boolean
}): Promise<UserProfile> {
  const response = await apiClient.put<UserProfile>('/users/me', data)
  return response.data
}
