/**
 * React Query hooks wrapping the transactions api.ts functions - the same caching/
 * invalidation pattern every other feature module uses. Editing or deleting a transaction
 * changes a real balance on whatever bank/retirement/education account it affected, so
 * both mutations also invalidate those account lists, not just 'transactions'.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getTransactions,
  updateTransaction,
  deleteTransaction,
  type TransactionListFilters,
  type TransactionUpdatePayload,
} from '../api'

const BALANCE_QUERY_KEYS = ['bank-accounts', 'retirement-accounts', 'education-accounts']

export function useTransactions(filters?: TransactionListFilters) {
  return useQuery({
    queryKey: ['transactions', filters],
    queryFn: () => getTransactions(filters),
  })
}

export function useUpdateTransaction() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: TransactionUpdatePayload }) =>
      updateTransaction(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
      BALANCE_QUERY_KEYS.forEach((key) => queryClient.invalidateQueries({ queryKey: [key] }))
    },
  })
}

export function useDeleteTransaction() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: deleteTransaction,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
      BALANCE_QUERY_KEYS.forEach((key) => queryClient.invalidateQueries({ queryKey: [key] }))
    },
  })
}
