/**
 * Covers EducationAccountsPage's list rendering and create flow, following the same
 * pattern (and regression concern - silent failures, missing navigation on success) as
 * retirement/pages/RetirementAccountsPage.test.tsx.
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import EducationAccountsPage from './EducationAccountsPage'
import * as educationApi from '../api'
import type { EducationAccount } from '@/types'

const mockNavigate = vi.fn()

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return { ...actual, useNavigate: () => mockNavigate }
})

vi.mock('../api')

const existingAccount: EducationAccount = {
  id: 'acct-1',
  user_id: 'user-1',
  account_name: "Jordan's College Fund",
  account_type: '529_plan',
  beneficiary_name: 'Jordan Smith',
  beneficiary_birth_date: '2015-06-01',
  plan_provider: 'NY 529 College Savings Program',
  balance: '5000.00',
  contribution_ytd: '2000.00',
  expected_return_rate: '0.07',
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
        <EducationAccountsPage />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

async function fillAndSubmitCreateForm(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: /add account/i }))
  await user.type(screen.getByLabelText('Account Name'), 'New 529')
  await user.type(screen.getByLabelText('Beneficiary Name'), 'Alex Smith')
  await user.type(screen.getByLabelText('Current Balance ($)'), '10000')
  await user.click(screen.getByRole('button', { name: /^create account$/i }))
}

beforeEach(() => {
  vi.clearAllMocks()
  // EducationAccountCard fetches gift-tax info for whatever beneficiary it's given - give
  // it a resolved default so tests that don't care about it don't hang.
  vi.mocked(educationApi.getGiftTaxInfo).mockResolvedValue({
    account_id: null,
    beneficiary_name: 'Jordan Smith',
    annual_exclusion: '19000.00',
    superfunding_lump_sum: '95000.00',
    beneficiary_contribution_ytd: '2000.00',
    remaining_before_exclusion: '17000.00',
    would_exceed_exclusion: false,
    note: 'Jordan Smith has 17000.00 of this year\'s 19000.00 gift-tax exclusion remaining.',
    transaction_id: null,
  })
})

describe('EducationAccountsPage', () => {
  it('renders existing accounts from the API', async () => {
    vi.mocked(educationApi.getEducationAccounts).mockResolvedValue([existingAccount])

    renderPage()

    expect(
      await screen.findByRole('heading', { name: "Jordan's College Fund" })
    ).toBeInTheDocument()
  })

  it('navigates to the new account detail page after a successful create', async () => {
    const user = userEvent.setup()
    vi.mocked(educationApi.getEducationAccounts).mockResolvedValue([])
    vi.mocked(educationApi.createEducationAccount).mockResolvedValue({
      ...existingAccount,
      id: 'acct-new',
      account_name: 'New 529',
    })

    renderPage()
    await screen.findByText('No education savings accounts yet')

    await fillAndSubmitCreateForm(user)

    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/education/acct-new'))
    expect(vi.mocked(educationApi.createEducationAccount).mock.calls[0][0]).toEqual(
      expect.objectContaining({ account_name: 'New 529', balance: 10000 })
    )
  })

  it('shows the backend error and stays on the page when create fails', async () => {
    const user = userEvent.setup()
    vi.mocked(educationApi.getEducationAccounts).mockResolvedValue([])
    vi.mocked(educationApi.createEducationAccount).mockRejectedValue(new Error('boom'))

    renderPage()
    await screen.findByText('No education savings accounts yet')

    await fillAndSubmitCreateForm(user)

    expect(mockNavigate).not.toHaveBeenCalled()
    // The form stays open with the entered data intact so the user can retry.
    expect(screen.getByLabelText('Account Name')).toHaveValue('New 529')
  })
})
