/**
 * React Query hooks wrapping the education api.ts functions. These give components
 * (EducationAccountsPage, EducationAccountDetailPage, the account/contribution forms)
 * caching, loading states, and automatic cache invalidation after mutations without each
 * component managing that bookkeeping itself - the same pattern as
 * retirement/hooks/useRetirementAccounts.ts.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getEducationAccounts,
  getEducationAccount,
  createEducationAccount,
  updateEducationAccount,
  deleteEducationAccount,
  simulateEducationGrowth,
  getGiftTaxInfo,
  recordContribution,
  getRecurringContributions,
  createRecurringContribution,
  updateRecurringContribution,
  deleteRecurringContribution,
} from '../api'
import type { ContributionSourceType } from '@/types'

// List every education account for the current user.
export function useEducationAccounts() {
  return useQuery({
    queryKey: ['education-accounts'],
    queryFn: getEducationAccounts,
  })
}

// Fetch a single education account by id; skipped until an id is available.
export function useEducationAccount(id: string) {
  return useQuery({
    queryKey: ['education-accounts', id],
    queryFn: () => getEducationAccount(id),
    enabled: !!id,
  })
}

// Create an education account and refresh the account list on success.
export function useCreateEducationAccount() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: createEducationAccount,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['education-accounts'] })
    },
  })
}

// Update an education account and refresh both the list and the single-account cache entry.
export function useUpdateEducationAccount() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string
      data: Parameters<typeof updateEducationAccount>[1]
    }) => updateEducationAccount(id, data),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['education-accounts'] })
      queryClient.invalidateQueries({ queryKey: ['education-accounts', id] })
    },
  })
}

// Delete an education account and refresh the account list on success.
export function useDeleteEducationAccount() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: deleteEducationAccount,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['education-accounts'] })
    },
  })
}

// Run a growth simulation; re-fetches automatically whenever the inputs change.
export function useEducationSimulation(
  accountId: string,
  months: number,
  extraMonthlyContribution: number = 0,
  includeRecurring: boolean = true
) {
  return useQuery({
    queryKey: [
      'education-simulation',
      accountId,
      months,
      extraMonthlyContribution,
      includeRecurring,
    ],
    queryFn: () =>
      simulateEducationGrowth(accountId, months, extraMonthlyContribution, includeRecurring),
    enabled: !!accountId && months > 0,
  })
}

// List the recurring contributions scheduled against an account.
export function useRecurringContributions(accountId: string) {
  return useQuery({
    queryKey: ['education-recurring-contributions', accountId],
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
        queryKey: ['education-recurring-contributions', accountId],
      })
      queryClient.invalidateQueries({ queryKey: ['education-simulation'] })
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
      queryClient.invalidateQueries({ queryKey: ['education-recurring-contributions'] })
      queryClient.invalidateQueries({ queryKey: ['education-simulation'] })
    },
  })
}

// Delete a recurring contribution; refreshes the contribution list and any cached simulations.
export function useDeleteRecurringContribution() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: deleteRecurringContribution,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['education-recurring-contributions'] })
      queryClient.invalidateQueries({ queryKey: ['education-simulation'] })
    },
  })
}

// Fetch 2026 gift-tax guidance for a beneficiary.
export function useGiftTaxInfo(beneficiaryName: string | undefined, contributionAmount?: number) {
  return useQuery({
    queryKey: ['gift-tax-info', beneficiaryName, contributionAmount],
    queryFn: () => getGiftTaxInfo(beneficiaryName!, contributionAmount),
    enabled: !!beneficiaryName,
  })
}

// Record a contribution; refreshes the account (balance/YTD changed) and gift-tax info,
// plus - since a bank_account-sourced contribution debits a real bank account and posts a
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
      queryClient.invalidateQueries({ queryKey: ['education-accounts'] })
      queryClient.invalidateQueries({ queryKey: ['education-accounts', accountId] })
      queryClient.invalidateQueries({ queryKey: ['gift-tax-info'] })
      queryClient.invalidateQueries({ queryKey: ['bank-accounts'] })
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
    },
  })
}
