/**
 * React Query hooks wrapping the expenses/receipts/categories api.ts functions. These give
 * components caching, loading states, and automatic cache invalidation after mutations
 * without each component managing that bookkeeping itself - the same pattern every other
 * feature module uses (see e.g. features/retirement/hooks/useRetirementAccounts.ts).
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  uploadReceipts,
  getReceipts,
  getReceipt,
  updateReceipt,
  deleteReceipt,
  reprocessReceipt,
  createExpenseFromReceipt,
  getExpenseCategories,
  createExpenseCategory,
  updateExpenseCategory,
  deleteExpenseCategory,
  getExpenses,
  getExpense,
  createExpense,
  updateExpense,
  deleteExpense,
  getExpenseSummary,
  type ExpenseListFilters,
} from '../api'
import type { ReceiptProcessingStatus } from '@/types'

// --- Receipts ---------------------------------------------------------------

// Upload one or more receipt files; refreshes the receipt list on success so newly
// queued receipts show up immediately (still 'pending'/'processing' until Celery finishes).
export function useUploadReceipts() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: uploadReceipts,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['receipts'] })
    },
  })
}

// List receipts, optionally filtered by processing status. Polls every 3s on its own
// whenever the current result includes a still-pending/processing receipt, and stops
// polling once nothing is in flight - so ReceiptsPage sees a batch upload's status move
// from queued -> processing -> ready for review without a manual refresh or its own
// polling loop, and without polling forever once everything's settled.
export function useReceipts(processingStatus?: ReceiptProcessingStatus) {
  return useQuery({
    queryKey: ['receipts', processingStatus],
    queryFn: () => getReceipts(processingStatus),
    refetchInterval: (query) => {
      const receipts = query.state.data
      const anyInFlight = receipts?.some(
        (r) => r.processing_status === 'pending' || r.processing_status === 'processing'
      )
      return anyInFlight ? 3000 : false
    },
  })
}

export function useReceipt(id: string) {
  return useQuery({
    queryKey: ['receipts', 'detail', id],
    queryFn: () => getReceipt(id),
    enabled: !!id,
  })
}

// Correct extracted fields (or mark verified); refreshes the list and this receipt's
// own cache entry.
export function useUpdateReceipt() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Parameters<typeof updateReceipt>[1] }) =>
      updateReceipt(id, data),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['receipts'] })
      queryClient.invalidateQueries({ queryKey: ['receipts', 'detail', id] })
    },
  })
}

export function useDeleteReceipt() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: deleteReceipt,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['receipts'] })
    },
  })
}

// Re-run extraction; refreshes the list and this receipt's own cache entry so its status
// flips back to 'pending'/'processing' in the UI right away.
export function useReprocessReceipt() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: reprocessReceipt,
    onSuccess: (receipt) => {
      queryClient.invalidateQueries({ queryKey: ['receipts'] })
      queryClient.invalidateQueries({ queryKey: ['receipts', 'detail', receipt.id] })
    },
  })
}

// Turn a receipt into an Expense; refreshes receipts (in case future UI marks the source
// receipt) and the expense list/summary, since a new expense just appeared.
export function useCreateExpenseFromReceipt() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      receiptId,
      data,
    }: {
      receiptId: string
      data: Parameters<typeof createExpenseFromReceipt>[1]
    }) => createExpenseFromReceipt(receiptId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['receipts'] })
      queryClient.invalidateQueries({ queryKey: ['expenses'] })
    },
  })
}

// --- Expense Categories ------------------------------------------------------

export function useExpenseCategories() {
  return useQuery({
    queryKey: ['expense-categories'],
    queryFn: getExpenseCategories,
  })
}

export function useCreateExpenseCategory() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: createExpenseCategory,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expense-categories'] })
    },
  })
}

export function useUpdateExpenseCategory() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string
      data: Parameters<typeof updateExpenseCategory>[1]
    }) => updateExpenseCategory(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expense-categories'] })
    },
  })
}

// Deleting a category doesn't delete its expenses (the backend nulls category_id instead),
// so the expense list/summary need refreshing too, not just the category list.
export function useDeleteExpenseCategory() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: deleteExpenseCategory,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expense-categories'] })
      queryClient.invalidateQueries({ queryKey: ['expenses'] })
    },
  })
}

// --- Expenses -----------------------------------------------------------------

export function useExpenseList(filters?: ExpenseListFilters) {
  return useQuery({
    queryKey: ['expenses', 'list', filters],
    queryFn: () => getExpenses(filters),
  })
}

export function useExpense(id: string) {
  return useQuery({
    queryKey: ['expenses', 'detail', id],
    queryFn: () => getExpense(id),
    enabled: !!id,
  })
}

export function useCreateExpense() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: createExpense,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expenses'] })
    },
  })
}

export function useUpdateExpense() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Parameters<typeof updateExpense>[1] }) =>
      updateExpense(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expenses'] })
    },
  })
}

export function useDeleteExpense() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: deleteExpense,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expenses'] })
    },
  })
}

// Spending summary for a date range (undefined start/end means "current calendar month,"
// resolved server-side).
export function useExpenseSummary(startDate?: string, endDate?: string) {
  return useQuery({
    queryKey: ['expenses', 'summary', startDate, endDate],
    queryFn: () => getExpenseSummary(startDate, endDate),
  })
}
