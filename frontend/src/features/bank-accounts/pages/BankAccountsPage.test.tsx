/**
 * Covers the bug reported in practice: creating an account appeared to do nothing because
 * (a) a failed create request was never surfaced to the user, and (b) a successful create
 * left the user on the list page instead of taking them to the new account's growth chart.
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { AxiosError, AxiosHeaders } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import BankAccountsPage from './BankAccountsPage'
import * as bankAccountsApi from '../api'
import type { BankAccount } from '@/types'

const mockNavigate = vi.fn()

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return { ...actual, useNavigate: () => mockNavigate }
})

vi.mock('../api')

const existingAccount: BankAccount = {
  id: 'acct-1',
  user_id: 'user-1',
  account_name: 'Existing Savings',
  account_type: 'savings',
  principal: '5000.00',
  current_balance: '5100.00',
  interest_rate: '0.0400',
  compounding_frequency: 'monthly',
  cd_start_date: null,
  cd_term_months: null,
  cd_auto_renew: false,
  is_simulation: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <BankAccountsPage />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

async function fillAndSubmitCreateForm(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: /add account/i }))
  await user.type(screen.getByLabelText('Account Name'), 'New Savings')
  await user.type(screen.getByLabelText('Principal Amount ($)'), '10000')
  await user.click(screen.getByRole('button', { name: /^create account$/i }))
}

beforeEach(() => {
  vi.clearAllMocks()
  // The combined-simulation section (rendered on every page state) fetches on mount;
  // give its query a resolved default so tests that don't care about it don't log
  // React Query's "data cannot be undefined" warning from the bare auto-mock.
  vi.mocked(bankAccountsApi.simulateCombinedGrowth).mockResolvedValue({
    accounts: [],
    total_projections: [],
    final_total_balance: '0.00',
  })
})

describe('BankAccountsPage', () => {
  it('renders existing accounts from the API', async () => {
    vi.mocked(bankAccountsApi.getBankAccounts).mockResolvedValue([existingAccount])

    renderPage()

    // The account name also appears in the combined-simulation section's include/exclude
    // checkbox label below the cards, so scope this to the card's own heading.
    expect(
      await screen.findByRole('heading', { name: 'Existing Savings' })
    ).toBeInTheDocument()
  })

  it('navigates to the new account detail page after a successful create', async () => {
    const user = userEvent.setup()
    vi.mocked(bankAccountsApi.getBankAccounts).mockResolvedValue([])
    vi.mocked(bankAccountsApi.createBankAccount).mockResolvedValue({
      ...existingAccount,
      id: 'acct-new',
      account_name: 'New Savings',
    })

    renderPage()
    await screen.findByText('No accounts yet')

    await fillAndSubmitCreateForm(user)

    await waitFor(() =>
      expect(mockNavigate).toHaveBeenCalledWith('/bank-accounts/acct-new')
    )
    expect(vi.mocked(bankAccountsApi.createBankAccount).mock.calls[0][0]).toEqual(
      expect.objectContaining({ account_name: 'New Savings', principal: 10000 })
    )
  })

  it('shows the backend error and stays on the page when create fails', async () => {
    const user = userEvent.setup()
    vi.mocked(bankAccountsApi.getBankAccounts).mockResolvedValue([])
    const axiosError = new AxiosError(
      'Request failed with status code 401',
      '401',
      undefined,
      undefined,
      {
        status: 401,
        statusText: 'Unauthorized',
        headers: new AxiosHeaders(),
        config: { headers: new AxiosHeaders() },
        data: { detail: 'Could not validate credentials' },
      }
    )
    vi.mocked(bankAccountsApi.createBankAccount).mockRejectedValue(axiosError)

    renderPage()
    await screen.findByText('No accounts yet')

    await fillAndSubmitCreateForm(user)

    expect(await screen.findByText('Could not validate credentials')).toBeInTheDocument()
    expect(mockNavigate).not.toHaveBeenCalled()
    // The form stays open with the entered data intact so the user can retry.
    expect(screen.getByLabelText('Account Name')).toHaveValue('New Savings')
  })
})
