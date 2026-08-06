/**
 * Covers TransactionsPage's merge of real Transaction rows and read-only Expense rows
 * into one sorted log (see this page's docstring for why expenses are merged in for
 * display rather than written into the `transactions` table), the "Expenses" filter tab,
 * and that expense rows link to the Expenses page instead of offering inline edit/delete.
 */
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import TransactionsPage from './TransactionsPage'
import * as transactionsApi from '../api'
import * as expensesApi from '@/features/expenses/api'
import * as bankAccountsApi from '@/features/bank-accounts/api'
import * as retirementApi from '@/features/retirement/api'
import * as educationApi from '@/features/education/api'
import * as investmentsApi from '@/features/investments/api'
import * as schedulerApi from '@/features/scheduler/api'
import type { Transaction, Expense } from '@/types'

vi.mock('../api')
vi.mock('@/features/expenses/api')
vi.mock('@/features/bank-accounts/api')
vi.mock('@/features/retirement/api')
vi.mock('@/features/education/api')
vi.mock('@/features/investments/api')
vi.mock('@/features/scheduler/api')

const stockTransaction: Transaction = {
  id: 'txn-1',
  user_id: 'user-1',
  transaction_type: 'stock_purchase',
  amount: '1000.00',
  transaction_date: '2026-08-01',
  description: 'Bought 10 AAPL @ 100',
  account_type: 'stock_position',
  account_id: 'pos-1',
  income_id: null,
  source_type: null,
  source_bank_account_id: null,
  created_at: '2026-08-01T00:00:00Z',
  updated_at: '2026-08-01T00:00:00Z',
}

const groceryExpense: Expense = {
  id: 'exp-1',
  user_id: 'user-1',
  receipt_id: null,
  merchant_name: 'Corner Grocer',
  amount: '150.00',
  expense_date: '2026-08-04',
  category_id: null,
  bank_account_id: null,
  description: null,
  tags: null,
  is_recurring: true,
  recurrence_pattern: 'monthly',
  created_at: '2026-08-04T00:00:00Z',
  updated_at: '2026-08-04T00:00:00Z',
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <TransactionsPage />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(transactionsApi.getTransactions).mockResolvedValue([])
  vi.mocked(expensesApi.getExpenses).mockResolvedValue([])
  vi.mocked(expensesApi.getExpenseCategories).mockResolvedValue([])
  vi.mocked(bankAccountsApi.getBankAccounts).mockResolvedValue([])
  vi.mocked(retirementApi.getRetirementAccounts).mockResolvedValue([])
  vi.mocked(educationApi.getEducationAccounts).mockResolvedValue([])
  vi.mocked(investmentsApi.getStockPositions).mockResolvedValue([])
  vi.mocked(schedulerApi.runScheduler).mockResolvedValue({
    as_of: '2026-08-04',
    incomes_posted: 0,
    bank_interest_applied: 0,
    retirement_interest_applied: 0,
    education_interest_applied: 0,
    retirement_contributions_posted: 0,
    education_contributions_posted: 0,
    expenses_created: 0,
  })
})

describe('TransactionsPage', () => {
  it('merges a recurring expense into the log alongside a real transaction', async () => {
    vi.mocked(transactionsApi.getTransactions).mockResolvedValue([stockTransaction])
    vi.mocked(expensesApi.getExpenses).mockResolvedValue([groceryExpense])

    renderPage()

    expect(await screen.findByText('Corner Grocer')).toBeInTheDocument()
    expect(screen.getByText('Bought 10 AAPL @ 100')).toBeInTheDocument()
    expect(screen.getByText('Expense')).toBeInTheDocument()
  })

  it('shows an "Edit in Expenses" link instead of edit/delete icons for expense rows', async () => {
    vi.mocked(expensesApi.getExpenses).mockResolvedValue([groceryExpense])

    renderPage()

    const link = await screen.findByRole('link', { name: /edit in expenses/i })
    expect(link).toHaveAttribute('href', '/expenses')
  })

  it('the Expenses tab filters out real transactions', async () => {
    const user = userEvent.setup()
    vi.mocked(transactionsApi.getTransactions).mockResolvedValue([stockTransaction])
    vi.mocked(expensesApi.getExpenses).mockResolvedValue([groceryExpense])

    renderPage()
    await screen.findByText('Corner Grocer')

    await user.click(screen.getByRole('button', { name: 'Expenses' }))

    expect(screen.getByText('Corner Grocer')).toBeInTheDocument()
    expect(screen.queryByText('Bought 10 AAPL @ 100')).not.toBeInTheDocument()
  })

  it('shows an empty state when there are no transactions or expenses', async () => {
    renderPage()

    expect(await screen.findByText('No transactions here yet')).toBeInTheDocument()
  })

  it('clicking Sync Recurring Items triggers the scheduler and shows a summary', async () => {
    const user = userEvent.setup()
    vi.mocked(schedulerApi.runScheduler).mockResolvedValue({
      as_of: '2026-08-04',
      incomes_posted: 3,
      bank_interest_applied: 1,
      retirement_interest_applied: 0,
      education_interest_applied: 0,
      retirement_contributions_posted: 0,
      education_contributions_posted: 0,
      expenses_created: 0,
    })

    renderPage()
    await user.click(screen.getByRole('button', { name: /sync recurring items/i }))

    expect(schedulerApi.runScheduler).toHaveBeenCalledTimes(1)
    expect(
      await screen.findByText(/3 income occurrences, 1 bank interest credit/i)
    ).toBeInTheDocument()
  })

  it('shows a "nothing was due" message when the sync finds nothing to catch up', async () => {
    const user = userEvent.setup()

    renderPage()
    await user.click(screen.getByRole('button', { name: /sync recurring items/i }))

    expect(await screen.findByText(/nothing was due/i)).toBeInTheDocument()
  })
})
