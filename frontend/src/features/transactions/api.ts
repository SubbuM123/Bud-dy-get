/**
 * Thin wrappers around the /transactions backend endpoints. These are plain async
 * functions with no React dependency; hooks/useTransactions.ts wraps each one in a React
 * Query hook for caching/invalidation - the same split every other feature module uses.
 * There is no createTransaction here: every Transaction row is created as a side effect
 * of another endpoint (income logging, retirement/education contributions) - see
 * backend/app/models/transactions.py's docstring.
 */
import apiClient from '@/lib/api-client'
import type { Transaction, TransactionType, AllocationDestinationType } from '@/types'

export interface TransactionListFilters {
  transaction_type?: TransactionType
  account_type?: AllocationDestinationType
  account_id?: string
  start_date?: string
  end_date?: string
}

// List the current user's transactions, optionally filtered.
export async function getTransactions(filters?: TransactionListFilters): Promise<Transaction[]> {
  const response = await apiClient.get<Transaction[]>('/transactions', { params: filters })
  return response.data
}

export interface TransactionUpdatePayload {
  amount?: number
  transaction_date?: string
  description?: string
}

// Correct a transaction's amount/date/description - an amount change is applied as a
// delta to whatever account(s) it originally affected (see api/v1/transactions.py).
export async function updateTransaction(
  id: string,
  data: TransactionUpdatePayload
): Promise<Transaction> {
  const response = await apiClient.put<Transaction>(`/transactions/${id}`, data)
  return response.data
}

// Delete a transaction, fully reversing its effect on whatever account(s) it affected.
export async function deleteTransaction(id: string): Promise<void> {
  await apiClient.delete(`/transactions/${id}`)
}
