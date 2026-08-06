/**
 * React Query hooks wrapping the bank-accounts api.ts functions. These give components
 * (BankAccountsPage, AccountDetailPage, the account/action forms) caching, loading states,
 * and automatic cache invalidation after mutations without each component managing that
 * bookkeeping itself.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getBankAccounts,
  getBankAccount,
  createBankAccount,
  updateBankAccount,
  deleteBankAccount,
  simulateGrowth,
  getRecurringActions,
  createRecurringAction,
  updateRecurringAction,
  deleteRecurringAction,
  simulateCombinedGrowth,
} from '../api'

// List every bank account for the current user.
export function useBankAccounts() {
  return useQuery({
    queryKey: ['bank-accounts'],
    queryFn: getBankAccounts,
  })
}

// Fetch a single bank account by id; skipped until an id is available.
export function useBankAccount(id: string) {
  return useQuery({
    queryKey: ['bank-accounts', id],
    queryFn: () => getBankAccount(id),
    enabled: !!id,
  })
}

// Create a bank account and refresh the account list on success.
export function useCreateBankAccount() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: createBankAccount,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bank-accounts'] })
      queryClient.invalidateQueries({ queryKey: ['combined-simulation'] })
    },
  })
}

// Update a bank account and refresh both the list and the single-account cache entry.
export function useUpdateBankAccount() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Parameters<typeof updateBankAccount>[1] }) =>
      updateBankAccount(id, data),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['bank-accounts'] })
      queryClient.invalidateQueries({ queryKey: ['bank-accounts', id] })
      queryClient.invalidateQueries({ queryKey: ['combined-simulation'] })
    },
  })
}

// Delete a bank account and refresh the account list on success.
export function useDeleteBankAccount() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: deleteBankAccount,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bank-accounts'] })
      queryClient.invalidateQueries({ queryKey: ['combined-simulation'] })
    },
  })
}

// Run a growth simulation; re-fetches automatically whenever account/months/includeRecurring change.
export function useSimulation(accountId: string, months: number, includeRecurring: boolean = true) {
  return useQuery({
    queryKey: ['simulation', accountId, months, includeRecurring],
    queryFn: () => simulateGrowth(accountId, months, includeRecurring),
    enabled: !!accountId && months > 0,
  })
}

// List the recurring actions attached to an account.
export function useRecurringActions(accountId: string) {
  return useQuery({
    queryKey: ['recurring-actions', accountId],
    queryFn: () => getRecurringActions(accountId),
    enabled: !!accountId,
  })
}

// Create a recurring action; refreshes the action list and any cached simulations, since
// adding a recurring action changes projected growth.
export function useCreateRecurringAction() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      accountId,
      data,
    }: {
      accountId: string
      data: Parameters<typeof createRecurringAction>[1]
    }) => createRecurringAction(accountId, data),
    onSuccess: (_, { accountId }) => {
      queryClient.invalidateQueries({ queryKey: ['recurring-actions', accountId] })
      queryClient.invalidateQueries({ queryKey: ['simulation'] })
      queryClient.invalidateQueries({ queryKey: ['combined-simulation'] })
    },
  })
}

// Update a recurring action; refreshes the action list and any cached simulations,
// since editing amount/frequency/end date changes projected growth.
export function useUpdateRecurringAction() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      actionId,
      data,
    }: {
      actionId: string
      data: Parameters<typeof updateRecurringAction>[1]
    }) => updateRecurringAction(actionId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recurring-actions'] })
      queryClient.invalidateQueries({ queryKey: ['simulation'] })
      queryClient.invalidateQueries({ queryKey: ['combined-simulation'] })
    },
  })
}

// Delete a recurring action; refreshes the action list and any cached simulations.
export function useDeleteRecurringAction() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: deleteRecurringAction,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recurring-actions'] })
      queryClient.invalidateQueries({ queryKey: ['simulation'] })
      queryClient.invalidateQueries({ queryKey: ['combined-simulation'] })
    },
  })
}

// Run a combined growth simulation across the given accounts; re-fetches automatically
// whenever months/includeRecurring/accountIds change. accountIds is `null` while the
// caller hasn't yet decided which accounts to include (e.g. still loading the account
// list to seed its checkboxes) - the query stays disabled until then.
export function useCombinedSimulation(
  months: number,
  includeRecurring: boolean = true,
  accountIds: string[] | null = null
) {
  return useQuery({
    queryKey: ['combined-simulation', months, includeRecurring, accountIds],
    queryFn: () => simulateCombinedGrowth(months, includeRecurring, accountIds ?? undefined),
    enabled: months > 0 && accountIds !== null,
  })
}
