/**
 * Covers ExpenseForm's validation (merchant name and date required) and the string->number
 * amount coercion its Zod schema is responsible for. ExpenseForm fetches categories and
 * bank accounts itself (via useExpenseCategories/useBankAccounts) rather than taking them
 * as props, so every test needs a QueryClientProvider and mocked api modules - the same
 * setup EducationAccountsPage.test.tsx uses for its own hook-fetching component.
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ExpenseForm from './ExpenseForm'
import * as expensesApi from '../api'
import * as bankAccountsApi from '@/features/bank-accounts/api'

vi.mock('../api')
vi.mock('@/features/bank-accounts/api')

function renderForm(props: Partial<React.ComponentProps<typeof ExpenseForm>> = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <ExpenseForm onSubmit={vi.fn()} {...props} />
    </QueryClientProvider>
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(expensesApi.getExpenseCategories).mockResolvedValue([
    {
      id: 'cat-1',
      user_id: 'user-1',
      name: 'Groceries',
      color: '#2a78d6',
      icon: 'shopping-cart',
      monthly_budget: null,
      is_system: true,
      created_at: '2026-01-01T00:00:00Z',
    },
  ])
  vi.mocked(bankAccountsApi.getBankAccounts).mockResolvedValue([])
})

describe('ExpenseForm', () => {
  it('rejects submission when the merchant name is missing', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    renderForm({ onSubmit })

    await user.clear(screen.getByLabelText('Merchant'))
    await user.type(screen.getByLabelText('Amount ($)'), '10')
    await user.click(screen.getByRole('button', { name: /add expense/i }))

    expect(await screen.findByText('Merchant name is required')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('submits amount as a parsed number', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    renderForm({ onSubmit })

    await user.type(screen.getByLabelText('Merchant'), 'Corner Store')
    await user.type(screen.getByLabelText('Amount ($)'), '12.50')
    await user.click(screen.getByRole('button', { name: /add expense/i }))

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1))
    const submitted = onSubmit.mock.calls[0][0]
    expect(submitted.merchant_name).toBe('Corner Store')
    expect(submitted.amount).toBe(12.5)
  })

  it('shows categories fetched from the API in the category picker', async () => {
    renderForm()

    expect(await screen.findByText('Groceries')).toBeInTheDocument()
  })

  it('submits bank_account_id as undefined, not an empty string, when left unlinked', async () => {
    // Regression test: leaving "Not linked to an account" selected used to submit '' -
    // the <select>'s sentinel value for that option - rather than omitting the field,
    // which the backend previously tried to insert into a UUID column and 500'd on.
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    renderForm({ onSubmit })

    await user.type(screen.getByLabelText('Merchant'), 'Corner Store')
    await user.type(screen.getByLabelText('Amount ($)'), '10')
    await user.click(screen.getByRole('button', { name: /add expense/i }))

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1))
    expect(onSubmit.mock.calls[0][0].bank_account_id).toBeUndefined()
  })

  it('calls onCancel when Cancel is clicked', async () => {
    const user = userEvent.setup()
    const onCancel = vi.fn()
    renderForm({ onCancel })

    await user.click(screen.getByRole('button', { name: /cancel/i }))

    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('pre-fills fields in edit mode', () => {
    renderForm({
      expense: {
        id: 'exp-1',
        user_id: 'user-1',
        receipt_id: null,
        merchant_name: 'Existing Store',
        amount: '42.00',
        expense_date: '2026-03-01',
        category_id: null,
        bank_account_id: null,
        description: null,
        tags: null,
        is_recurring: false,
        recurrence_pattern: null,
        created_at: '2026-03-01T00:00:00Z',
        updated_at: '2026-03-01T00:00:00Z',
      },
    })

    expect(screen.getByDisplayValue('Existing Store')).toBeInTheDocument()
    expect(screen.getByDisplayValue('42.00')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /save changes/i })).toBeInTheDocument()
  })
})
