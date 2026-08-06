/**
 * React Query hooks wrapping the income api.ts functions - the same caching/invalidation
 * pattern every other feature module uses (see e.g.
 * education/hooks/useEducationAccounts.ts). Logging an income (or creating a one-time
 * one, which auto-logs) posts real Transaction rows and bumps a real balance on whichever
 * bank/retirement/education account(s) it's allocated to, so those mutations also
 * invalidate 'bank-accounts', 'retirement-accounts', 'education-accounts', and
 * 'transactions' - not just 'income' - so every page showing one of those balances
 * reflects the change without a manual refresh.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getIncomes,
  getIncome,
  createIncome,
  updateIncome,
  replaceIncomeAllocations,
  deleteIncome,
  logIncome,
  type IncomePayload,
  type IncomeAllocationPayload,
} from '../api'

const BALANCE_QUERY_KEYS = ['bank-accounts', 'retirement-accounts', 'education-accounts', 'transactions']

export function useIncomes() {
  return useQuery({
    queryKey: ['income'],
    queryFn: getIncomes,
  })
}

export function useIncome(id: string) {
  return useQuery({
    queryKey: ['income', id],
    queryFn: () => getIncome(id),
    enabled: !!id,
  })
}

// Create an income; a one-time income auto-logs server-side, so this also invalidates
// every balance-bearing query, not just the income list.
export function useCreateIncome() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: IncomePayload) => createIncome(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['income'] })
      BALANCE_QUERY_KEYS.forEach((key) => queryClient.invalidateQueries({ queryKey: [key] }))
    },
  })
}

export function useUpdateIncome() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Parameters<typeof updateIncome>[1] }) =>
      updateIncome(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['income'] })
    },
  })
}

export function useReplaceIncomeAllocations() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, allocations }: { id: string; allocations: IncomeAllocationPayload[] }) =>
      replaceIncomeAllocations(id, allocations),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['income'] })
    },
  })
}

export function useDeleteIncome() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: deleteIncome,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['income'] })
    },
  })
}

// Log one real occurrence of a recurring income - posts real Transaction rows and bumps
// real balances, so every balance-bearing query gets invalidated alongside 'income'.
export function useLogIncome() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data?: Parameters<typeof logIncome>[1] }) =>
      logIncome(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['income'] })
      BALANCE_QUERY_KEYS.forEach((key) => queryClient.invalidateQueries({ queryKey: [key] }))
    },
  })
}
