/**
 * React Query hooks wrapping the retirement api.ts functions. These give components
 * (RetirementAccountsPage, RetirementAccountDetailPage, the account/contribution forms)
 * caching, loading states, and automatic cache invalidation after mutations without each
 * component managing that bookkeeping itself - the same pattern as
 * bank-accounts/hooks/useBankAccounts.ts.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getRetirementAccounts,
  getRetirementAccount,
  createRetirementAccount,
  updateRetirementAccount,
  deleteRetirementAccount,
  simulateRetirementGrowth,
  getContributionLimits,
  recordContribution,
  getMyProfile,
  updateMyProfile,
  getRecurringContributions,
  createRecurringContribution,
  updateRecurringContribution,
  deleteRecurringContribution,
} from '../api'
import type { RetirementAccountType, ContributionSourceType } from '@/types'

// List every retirement account for the current user.
export function useRetirementAccounts() {
  return useQuery({
    queryKey: ['retirement-accounts'],
    queryFn: getRetirementAccounts,
  })
}

// Fetch a single retirement account by id; skipped until an id is available.
export function useRetirementAccount(id: string) {
  return useQuery({
    queryKey: ['retirement-accounts', id],
    queryFn: () => getRetirementAccount(id),
    enabled: !!id,
  })
}

// Create a retirement account and refresh the account list on success.
export function useCreateRetirementAccount() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: createRetirementAccount,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['retirement-accounts'] })
    },
  })
}

// Update a retirement account and refresh both the list and the single-account cache entry.
export function useUpdateRetirementAccount() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string
      data: Parameters<typeof updateRetirementAccount>[1]
    }) => updateRetirementAccount(id, data),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['retirement-accounts'] })
      queryClient.invalidateQueries({ queryKey: ['retirement-accounts', id] })
    },
  })
}

// Delete a retirement account and refresh the account list on success.
export function useDeleteRetirementAccount() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: deleteRetirementAccount,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['retirement-accounts'] })
    },
  })
}

// Run a growth simulation; re-fetches automatically whenever the inputs change.
export function useRetirementSimulation(
  accountId: string,
  months: number,
  monthlyEmployeeContribution: number = 0,
  includeRecurring: boolean = true
) {
  return useQuery({
    queryKey: [
      'retirement-simulation',
      accountId,
      months,
      monthlyEmployeeContribution,
      includeRecurring,
    ],
    queryFn: () =>
      simulateRetirementGrowth(accountId, months, monthlyEmployeeContribution, includeRecurring),
    enabled: !!accountId && months > 0,
  })
}

// List the recurring contributions scheduled against an account.
export function useRecurringContributions(accountId: string) {
  return useQuery({
    queryKey: ['retirement-recurring-contributions', accountId],
    queryFn: () => getRecurringContributions(accountId),
    enabled: !!accountId,
  })
}

// Create a recurring contribution; refreshes the contribution list and any cached
// simulations, since adding one changes projected growth.
export function useCreateRecurringContribution() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      accountId,
      data,
    }: {
      accountId: string
      data: Parameters<typeof createRecurringContribution>[1]
    }) => createRecurringContribution(accountId, data),
    onSuccess: (_, { accountId }) => {
      queryClient.invalidateQueries({
        queryKey: ['retirement-recurring-contributions', accountId],
      })
      queryClient.invalidateQueries({ queryKey: ['retirement-simulation'] })
    },
  })
}

// Update a recurring contribution; refreshes the contribution list and any cached simulations.
export function useUpdateRecurringContribution() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      contributionId,
      data,
    }: {
      contributionId: string
      data: Parameters<typeof updateRecurringContribution>[1]
    }) => updateRecurringContribution(contributionId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['retirement-recurring-contributions'] })
      queryClient.invalidateQueries({ queryKey: ['retirement-simulation'] })
    },
  })
}

// Delete a recurring contribution; refreshes the contribution list and any cached simulations.
export function useDeleteRecurringContribution() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: deleteRecurringContribution,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['retirement-recurring-contributions'] })
      queryClient.invalidateQueries({ queryKey: ['retirement-simulation'] })
    },
  })
}

// Fetch the current user's contribution limits for a given account type.
export function useContributionLimits(accountType: RetirementAccountType | undefined) {
  return useQuery({
    queryKey: ['contribution-limits', accountType],
    queryFn: () => getContributionLimits(accountType!),
    enabled: !!accountType,
  })
}

// Record a contribution; refreshes the account (balance/YTD changed), the limits query,
// and - since a bank_account-sourced contribution debits a real bank account and posts a
// Transaction - the bank accounts and transactions caches too.
export function useRecordContribution() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      accountId,
      amount,
      sourceType,
      sourceBankAccountId,
    }: {
      accountId: string
      amount: number
      sourceType?: ContributionSourceType
      sourceBankAccountId?: string
    }) => recordContribution(accountId, amount, sourceType, sourceBankAccountId),
    onSuccess: (_, { accountId }) => {
      queryClient.invalidateQueries({ queryKey: ['retirement-accounts'] })
      queryClient.invalidateQueries({ queryKey: ['retirement-accounts', accountId] })
      queryClient.invalidateQueries({ queryKey: ['contribution-limits'] })
      queryClient.invalidateQueries({ queryKey: ['bank-accounts'] })
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
    },
  })
}

// Fetch the current user's own profile.
export function useMyProfile() {
  return useQuery({
    queryKey: ['my-profile'],
    queryFn: getMyProfile,
  })
}

// Update the current user's profile and refresh anything limit-related that depends on it.
export function useUpdateMyProfile() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: updateMyProfile,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['my-profile'] })
      queryClient.invalidateQueries({ queryKey: ['contribution-limits'] })
    },
  })
}
