/**
 * Thin wrappers around the /receipts, /expenses, and /expense-categories backend
 * endpoints. These are plain async functions with no React dependency;
 * hooks/useExpenses.ts wraps each one in a React Query hook for caching/invalidation -
 * the same split every other feature module uses. uploadReceipts is the one function here
 * that isn't JSON: it posts a FormData body (one or many files, e.g. an entire folder
 * selected via ReceiptUploader's `webkitdirectory` input) and deliberately does not set a
 * Content-Type header - axios detects the FormData body and lets the browser generate the
 * correct `multipart/form-data; boundary=...` header itself, which a manually-set header
 * (even naming the right MIME type) would prevent by omitting the boundary parameter.
 */
import apiClient from '@/lib/api-client'
import type {
  Receipt,
  ReceiptDetail,
  ReceiptProcessingStatus,
  ReceiptUploadResponse,
  ExpenseCategory,
  Expense,
  ExpenseSummaryResponse,
} from '@/types'

// Upload one or more receipt files in a single batch request - a single photo, several
// files picked at once, or every file collected from a folder picker.
export async function uploadReceipts(files: File[]): Promise<ReceiptUploadResponse> {
  const formData = new FormData()
  files.forEach((file) => formData.append('files', file))
  const response = await apiClient.post<ReceiptUploadResponse>('/receipts/upload', formData)
  return response.data
}

// List the current user's receipts, optionally filtered by processing status.
export async function getReceipts(processingStatus?: ReceiptProcessingStatus): Promise<Receipt[]> {
  const response = await apiClient.get<Receipt[]>('/receipts', {
    params: processingStatus ? { processing_status: processingStatus } : undefined,
  })
  return response.data
}

// Fetch a single receipt with its line items - the review/detail view.
export async function getReceipt(id: string): Promise<ReceiptDetail> {
  const response = await apiClient.get<ReceiptDetail>(`/receipts/${id}`)
  return response.data
}

export interface ReceiptUpdatePayload {
  merchant_name?: string
  total_amount?: number
  transaction_date?: string
  tax_amount?: number
  subtotal_amount?: number
  payment_method?: string
  receipt_number?: string
  user_verified?: boolean
}

// Correct extracted fields (or mark a receipt verified) during human review.
export async function updateReceipt(id: string, data: ReceiptUpdatePayload): Promise<Receipt> {
  const response = await apiClient.put<Receipt>(`/receipts/${id}`, data)
  return response.data
}

// Delete a receipt and its underlying file. Any expense created from it is kept.
export async function deleteReceipt(id: string): Promise<void> {
  await apiClient.delete(`/receipts/${id}`)
}

// Re-run extraction against the already-uploaded file.
export async function reprocessReceipt(id: string): Promise<Receipt> {
  const response = await apiClient.post<Receipt>(`/receipts/${id}/reprocess`)
  return response.data
}

// Turn a receipt's fields into an Expense - requires merchant/total/date to already be
// present (correct them via updateReceipt first if the extraction left any blank).
export async function createExpenseFromReceipt(
  receiptId: string,
  data: { category_id?: string; bank_account_id?: string; description?: string }
): Promise<Expense> {
  const response = await apiClient.post<Expense>(`/receipts/${receiptId}/create-expense`, data)
  return response.data
}

// Fetch every category belonging to the current user (the starter set seeded at
// registration, plus anything they've added themselves).
export async function getExpenseCategories(): Promise<ExpenseCategory[]> {
  const response = await apiClient.get<ExpenseCategory[]>('/expense-categories')
  return response.data
}

export interface ExpenseCategoryPayload {
  name: string
  color?: string
  icon?: string
  monthly_budget?: number
}

export async function createExpenseCategory(data: ExpenseCategoryPayload): Promise<ExpenseCategory> {
  const response = await apiClient.post<ExpenseCategory>('/expense-categories', data)
  return response.data
}

export async function updateExpenseCategory(
  id: string,
  data: Partial<ExpenseCategoryPayload>
): Promise<ExpenseCategory> {
  const response = await apiClient.put<ExpenseCategory>(`/expense-categories/${id}`, data)
  return response.data
}

export async function deleteExpenseCategory(id: string): Promise<void> {
  await apiClient.delete(`/expense-categories/${id}`)
}

export interface ExpenseListFilters {
  category_id?: string
  start_date?: string
  end_date?: string
}

// List the current user's expenses, optionally filtered by category and/or date range.
export async function getExpenses(filters?: ExpenseListFilters): Promise<Expense[]> {
  const response = await apiClient.get<Expense[]>('/expenses', { params: filters })
  return response.data
}

export async function getExpense(id: string): Promise<Expense> {
  const response = await apiClient.get<Expense>(`/expenses/${id}`)
  return response.data
}

export interface ExpensePayload {
  merchant_name: string
  amount: number
  expense_date: string
  category_id?: string
  bank_account_id?: string
  description?: string
  tags?: string[]
  is_recurring?: boolean
  recurrence_pattern?: string
}

// Create a manual expense (no receipt behind it). Creating one from a receipt instead
// goes through createExpenseFromReceipt above.
export async function createExpense(data: ExpensePayload): Promise<Expense> {
  const response = await apiClient.post<Expense>('/expenses', data)
  return response.data
}

export async function updateExpense(id: string, data: Partial<ExpensePayload>): Promise<Expense> {
  const response = await apiClient.put<Expense>(`/expenses/${id}`, data)
  return response.data
}

export async function deleteExpense(id: string): Promise<void> {
  await apiClient.delete(`/expenses/${id}`)
}

// Spending summary for a date range (defaults to the current calendar month server-side
// when neither date is given), broken down by category.
export async function getExpenseSummary(
  startDate?: string,
  endDate?: string
): Promise<ExpenseSummaryResponse> {
  const response = await apiClient.get<ExpenseSummaryResponse>('/expenses/summary', {
    params: { start_date: startDate, end_date: endDate },
  })
  return response.data
}
