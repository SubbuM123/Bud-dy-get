/**
 * Thin wrappers around the /education-accounts backend endpoints. These are plain async
 * functions with no React dependency; hooks/useEducationAccounts.ts wraps each one in a
 * React Query hook for caching/invalidation - the same split used by
 * retirement/api.ts and hooks/useRetirementAccounts.ts.
 */
import apiClient from '@/lib/api-client'
import type {
  EducationAccount,
  EducationAccountType,
  EducationSimulationResponse,
  GiftTaxInfo,
  EducationRecurringContribution,
  ContributionFrequency,
  ContributionSourceType,
} from '@/types'

// Fetch every education account belonging to the current user.
export async function getEducationAccounts(): Promise<EducationAccount[]> {
  const response = await apiClient.get<EducationAccount[]>('/education-accounts')
  return response.data
}

// Fetch a single education account by id.
export async function getEducationAccount(id: string): Promise<EducationAccount> {
  const response = await apiClient.get<EducationAccount>(`/education-accounts/${id}`)
  return response.data
}

export interface EducationAccountPayload {
  account_name: string
  account_type: EducationAccountType
  beneficiary_name: string
  beneficiary_birth_date?: string
  plan_provider?: string
  balance: number
  expected_return_rate?: number
  is_simulation?: boolean
}

// Create a new education account.
export async function createEducationAccount(
  data: EducationAccountPayload
): Promise<EducationAccount> {
  const response = await apiClient.post<EducationAccount>('/education-accounts', data)
  return response.data
}

// Patch an education account with whichever fields are provided.
export async function updateEducationAccount(
  id: string,
  data: Partial<EducationAccountPayload>
): Promise<EducationAccount> {
  const response = await apiClient.put<EducationAccount>(`/education-accounts/${id}`, data)
  return response.data
}

// Delete an education account.
export async function deleteEducationAccount(id: string): Promise<void> {
  await apiClient.delete(`/education-accounts/${id}`)
}

// Run a growth projection for an account. extraMonthlyContribution is a hypothetical
// amount on top of whatever the account's own active recurring contributions already add
// each month (includeRecurring=true, the default) - no employer match, unlike retirement.
export async function simulateEducationGrowth(
  accountId: string,
  months: number,
  extraMonthlyContribution: number = 0,
  includeRecurring: boolean = true
): Promise<EducationSimulationResponse> {
  const response = await apiClient.post<EducationSimulationResponse>(
    `/education-accounts/${accountId}/simulate`,
    {
      months,
      monthly_contribution: extraMonthlyContribution,
      include_recurring: includeRecurring,
    }
  )
  return response.data
}

// Fetch 2026 gift-tax guidance for a beneficiary - purely informational, never blocking.
// contributionAmount is optional: when given, the note reflects what would happen if that
// amount were contributed on top of the beneficiary's YTD total.
export async function getGiftTaxInfo(
  beneficiaryName: string,
  contributionAmount?: number
): Promise<GiftTaxInfo> {
  const response = await apiClient.get<GiftTaxInfo>('/education-accounts/gift-tax-info', {
    params: { beneficiary_name: beneficiaryName, contribution_amount: contributionAmount },
  })
  return response.data
}

// Record a real contribution to an account; always succeeds (never rejected), unlike
// retirement's recordContribution - a 529 has no IRS contribution cap to enforce. Returns
// updated gift-tax guidance for the beneficiary. sourceType/sourceBankAccountId mirror
// retirement's recordContribution - see that function's comment.
export async function recordContribution(
  accountId: string,
  amount: number,
  sourceType: ContributionSourceType = 'track_only',
  sourceBankAccountId?: string
): Promise<GiftTaxInfo> {
  const response = await apiClient.post<GiftTaxInfo>(
    `/education-accounts/${accountId}/contribute`,
    { amount, source_type: sourceType, source_bank_account_id: sourceBankAccountId }
  )
  return response.data
}

// Fetch the recurring contributions scheduled against an account.
export async function getRecurringContributions(
  accountId: string
): Promise<EducationRecurringContribution[]> {
  const response = await apiClient.get<EducationRecurringContribution[]>(
    `/education-accounts/${accountId}/recurring-contributions`
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
): Promise<EducationRecurringContribution> {
  const response = await apiClient.post<EducationRecurringContribution>(
    `/education-accounts/${accountId}/recurring-contributions`,
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
): Promise<EducationRecurringContribution> {
  const response = await apiClient.put<EducationRecurringContribution>(
    `/education-accounts/recurring-contributions/${contributionId}`,
    data
  )
  return response.data
}

// Delete a recurring contribution.
export async function deleteRecurringContribution(contributionId: string): Promise<void> {
  await apiClient.delete(`/education-accounts/recurring-contributions/${contributionId}`)
}
