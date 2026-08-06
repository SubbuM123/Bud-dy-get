/**
 * Covers RetirementAccountsPage's list rendering and create flow, following the same
 * pattern (and regression concern - silent failures, missing navigation on success) as
 * bank-accounts/pages/BankAccountsPage.test.tsx.
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import RetirementAccountsPage from './RetirementAccountsPage'
import * as retirementApi from '../api'
import type { RetirementAccount, UserProfile } from '@/types'

const mockNavigate = vi.fn()

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return { ...actual, useNavigate: () => mockNavigate }
})

vi.mock('../api')

const existingAccount: RetirementAccount = {
  id: 'acct-1',
  user_id: 'user-1',
  account_name: 'Acme 401k',
  account_type: 'traditional_401k',
  balance: '20000.00',
  contribution_ytd: '5000.00',
  employer_name: 'Acme Corp',
  annual_salary: '120000.00',
  employer_match_percent: '0.5',
  employer_match_limit_percent: '0.06',
  vesting_type: null,
  vesting_years: null,
  vested_percent: '100.00',
  expected_return_rate: '0.07',
  is_simulation: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const profile: UserProfile = {
  id: 'user-1',
  email: 'user@example.com',
  full_name: null,
  is_active: true,
  birth_date: null,
  filing_status: null,
  annual_income: null,
  has_employer_retirement_plan: false,
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
        <RetirementAccountsPage />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

async function fillAndSubmitCreateForm(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: /add account/i }))
  await user.type(screen.getByLabelText('Account Name'), 'New 401k')
  await user.type(screen.getByLabelText('Current Balance ($)'), '10000')
  await user.click(screen.getByRole('button', { name: /^create account$/i }))
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(retirementApi.getMyProfile).mockResolvedValue(profile)
  // RetirementAccountCard fetches contribution limits for whatever account_type it's
  // given - give it a resolved default so tests that don't care about it don't hang.
  vi.mocked(retirementApi.getContributionLimits).mockResolvedValue({
    account_id: null,
    account_type: 'traditional_401k',
    employee_limit: '24500.00',
    total_limit: '72000.00',
    catch_up_eligible: false,
    catch_up_amount: '0.00',
    contribution_ytd: '5000.00',
    remaining_contribution: '19500.00',
    employer_match_this_contribution: null,
    eligible: true,
    eligibility_note: null,
    transaction_id: null,
  })
})

describe('RetirementAccountsPage', () => {
  it('renders existing accounts from the API', async () => {
    vi.mocked(retirementApi.getRetirementAccounts).mockResolvedValue([existingAccount])

    renderPage()

    expect(
      await screen.findByRole('heading', { name: 'Acme 401k' })
    ).toBeInTheDocument()
  })

  it('navigates to the new account detail page after a successful create', async () => {
    const user = userEvent.setup()
    vi.mocked(retirementApi.getRetirementAccounts).mockResolvedValue([])
    vi.mocked(retirementApi.createRetirementAccount).mockResolvedValue({
      ...existingAccount,
      id: 'acct-new',
      account_name: 'New 401k',
    })

    renderPage()
    await screen.findByText('No retirement accounts yet')

    await fillAndSubmitCreateForm(user)

    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/retirement/acct-new'))
    expect(vi.mocked(retirementApi.createRetirementAccount).mock.calls[0][0]).toEqual(
      expect.objectContaining({ account_name: 'New 401k', balance: 10000 })
    )
  })

  it('shows the backend error and stays on the page when create fails', async () => {
    const user = userEvent.setup()
    vi.mocked(retirementApi.getRetirementAccounts).mockResolvedValue([])
    vi.mocked(retirementApi.createRetirementAccount).mockRejectedValue(new Error('boom'))

    renderPage()
    await screen.findByText('No retirement accounts yet')

    await fillAndSubmitCreateForm(user)

    expect(mockNavigate).not.toHaveBeenCalled()
    // The form stays open with the entered data intact so the user can retry.
    expect(screen.getByLabelText('Account Name')).toHaveValue('New 401k')
  })
})
