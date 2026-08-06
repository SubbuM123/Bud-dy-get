/**
 * Covers StockPortfolioPage's holdings rendering and the buy-stock flow (create-then-buy
 * chaining - see BuyStockForm.tsx's docstring), following the same mocking pattern as
 * features/retirement/pages/RetirementAccountsPage.test.tsx. Moved out of
 * InvestmentsPage.test.tsx when stock positions were split onto their own page - see
 * docs/progress.md's 2026-08-04 "Phase 5 UI split" entry.
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import StockPortfolioPage from './StockPortfolioPage'
import * as investmentsApi from '../api'
import * as bankAccountsApi from '@/features/bank-accounts/api'
import type { StockPosition } from '@/types'

vi.mock('../api')
vi.mock('@/features/bank-accounts/api')

const existingPosition: StockPosition = {
  id: 'pos-1',
  user_id: 'user-1',
  ticker_symbol: 'AAPL',
  shares: '10.0000',
  average_cost_per_share: '150.0000',
  current_price: '180.00',
  last_price_update: '2026-08-01T00:00:00Z',
  market_value: '1800.00',
  unrealized_pnl: '300.00',
  funding_bank_account_id: null,
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
        <StockPortfolioPage />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(investmentsApi.getStockPositions).mockResolvedValue([])
  vi.mocked(investmentsApi.getStockPrice).mockResolvedValue({ ticker: '^GSPC', price: '5000.00' })
  vi.mocked(investmentsApi.getStockHistory).mockResolvedValue({
    ticker: '^GSPC',
    period: '3mo',
    data: [],
  })
  vi.mocked(bankAccountsApi.getBankAccounts).mockResolvedValue([])
})

describe('StockPortfolioPage', () => {
  it('renders existing stock holdings from the API', async () => {
    vi.mocked(investmentsApi.getStockPositions).mockResolvedValue([existingPosition])

    renderPage()

    expect(await screen.findByText('AAPL')).toBeInTheDocument()
  })

  it('buying a stock creates the position then records the buy', async () => {
    const user = userEvent.setup()
    const newPosition: StockPosition = { ...existingPosition, id: 'pos-new', ticker_symbol: 'MSFT' }
    vi.mocked(investmentsApi.createStockPosition).mockResolvedValue(newPosition)
    vi.mocked(investmentsApi.buyStock).mockResolvedValue({
      id: 'txn-1',
      stock_position_id: 'pos-new',
      transaction_type: 'buy',
      shares: '5',
      price_per_share: '100.00',
      transaction_date: '2026-08-01',
      realized_pnl: null,
      source_bank_account_id: null,
      notes: null,
      created_at: '2026-08-01T00:00:00Z',
    })

    renderPage()
    await screen.findByText('No stock holdings yet - buy your first above.')

    await user.type(screen.getByLabelText('Ticker Symbol'), 'MSFT')
    await user.type(screen.getByLabelText('Shares'), '5')
    await user.type(screen.getByLabelText('Cost per Share ($)'), '100')
    await user.click(screen.getByRole('button', { name: /^buy stock$/i }))

    await waitFor(() => expect(investmentsApi.createStockPosition).toHaveBeenCalled())
    expect(vi.mocked(investmentsApi.createStockPosition).mock.calls[0][0]).toBe('MSFT')
    expect(vi.mocked(investmentsApi.buyStock).mock.calls[0][0]).toBe('pos-new')
    expect(vi.mocked(investmentsApi.buyStock).mock.calls[0][1]).toEqual(
      expect.objectContaining({ shares: 5, price_per_share: 100 })
    )
  })
})
