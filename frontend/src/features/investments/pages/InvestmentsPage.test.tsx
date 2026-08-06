/**
 * Covers InvestmentsPage's bond/property holdings rendering and the buy-bond flow,
 * following the same mocking pattern as
 * features/retirement/pages/RetirementAccountsPage.test.tsx. Stock-specific cases moved
 * to StockPortfolioPage.test.tsx when stock positions were split onto their own page -
 * see docs/progress.md's 2026-08-04 "Phase 5 UI split" entry.
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import InvestmentsPage from './InvestmentsPage'
import * as investmentsApi from '../api'
import * as bankAccountsApi from '@/features/bank-accounts/api'
import type { BondHolding, PropertyInvestment } from '@/types'

vi.mock('../api')
vi.mock('@/features/bank-accounts/api')

const existingBond: BondHolding = {
  id: 'bond-1',
  user_id: 'user-1',
  name: 'US Treasury 2028',
  purchase_price: '9500.00',
  face_value: '10000.00',
  coupon_rate: '0.0500',
  payment_frequency: 'semi_annually',
  purchase_date: '2026-01-01',
  maturity_date: '2028-01-01',
  is_simulation: true,
  is_active: true,
  sale_price: null,
  sale_date: null,
  realized_pnl: null,
  current_book_value: '9700.00',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const existingProperty: PropertyInvestment = {
  id: 'prop-1',
  user_id: 'user-1',
  name: 'Rental Duplex',
  cost: '250000.00',
  expected_return_rate: '0.0600',
  purchase_date: '2026-01-01',
  is_simulation: true,
  is_active: true,
  sale_price: null,
  sale_date: null,
  realized_pnl: null,
  current_value: '255000.00',
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
        <InvestmentsPage />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(investmentsApi.getBondHoldings).mockResolvedValue([])
  vi.mocked(investmentsApi.getPropertyInvestments).mockResolvedValue([])
  vi.mocked(bankAccountsApi.getBankAccounts).mockResolvedValue([])
})

describe('InvestmentsPage', () => {
  it('renders existing bond and property holdings from the API', async () => {
    vi.mocked(investmentsApi.getBondHoldings).mockResolvedValue([existingBond])
    vi.mocked(investmentsApi.getPropertyInvestments).mockResolvedValue([existingProperty])

    renderPage()

    expect(await screen.findByText('US Treasury 2028')).toBeInTheDocument()
    expect(screen.getByText('Rental Duplex')).toBeInTheDocument()
  })

  it('renders empty states with no holdings', async () => {
    renderPage()

    expect(await screen.findByText('No bond holdings yet - buy your first above.')).toBeInTheDocument()
    expect(
      screen.getByText('No property investments yet - buy your first above.')
    ).toBeInTheDocument()
  })

  it('buying a bond submits the form with the entered fields', async () => {
    const user = userEvent.setup()
    vi.mocked(investmentsApi.createBondHolding).mockResolvedValue({
      ...existingBond,
      id: 'bond-new',
      name: 'New Bond',
    })

    renderPage()
    await screen.findByText('No bond holdings yet - buy your first above.')

    // "Name" and "Purchase Date" appear in both the bond and property forms on this page
    // - the bond form renders first.
    await user.type(screen.getAllByLabelText('Name')[0], 'New Bond')
    await user.type(screen.getByLabelText('Purchase Price ($)'), '9500')
    await user.type(screen.getByLabelText('Face Value ($)'), '10000')
    await user.type(screen.getAllByLabelText('Purchase Date')[0], '2026-01-01')
    await user.type(screen.getByLabelText('Maturity Date'), '2028-01-01')
    await user.click(screen.getByRole('button', { name: /^buy bond$/i }))

    await waitFor(() => expect(investmentsApi.createBondHolding).toHaveBeenCalled())
    expect(vi.mocked(investmentsApi.createBondHolding).mock.calls[0][0]).toEqual(
      expect.objectContaining({
        name: 'New Bond',
        purchase_price: 9500,
        face_value: 10000,
        purchase_date: '2026-01-01',
        maturity_date: '2028-01-01',
      })
    )
  })
})
