/**
 * Thin wrappers around the /investments backend endpoints (Phase 5). These are plain
 * async functions with no React dependency; hooks/useInvestments.ts wraps each one in a
 * React Query hook for caching/invalidation - the same split every other feature module
 * uses (see features/income/api.ts).
 */
import apiClient from '@/lib/api-client'
import type {
  StockPosition,
  StockTransaction,
  StockHistoryResponse,
  BondHolding,
  BondAmortizationSchedule,
  PropertyInvestment,
  InvestmentSummary,
  BondPaymentFrequency,
} from '@/types'

// --- Market data --------------------------------------------------------------------

export async function getStockPrice(ticker: string): Promise<{ ticker: string; price: string | null }> {
  const response = await apiClient.get(`/investments/market/${ticker}/price`)
  return response.data
}

export async function getStockHistory(ticker: string, period: string): Promise<StockHistoryResponse> {
  const response = await apiClient.get<StockHistoryResponse>(
    `/investments/market/${ticker}/history`,
    { params: { period } }
  )
  return response.data
}

// --- Stock positions ------------------------------------------------------------------

export async function getStockPositions(): Promise<StockPosition[]> {
  const response = await apiClient.get<StockPosition[]>('/investments/stocks')
  return response.data
}

export async function getStockPosition(id: string): Promise<StockPosition> {
  const response = await apiClient.get<StockPosition>(`/investments/stocks/${id}`)
  return response.data
}

// Get-or-create by ticker - see api/v1/investments.py's create_stock_position.
export async function createStockPosition(tickerSymbol: string): Promise<StockPosition> {
  const response = await apiClient.post<StockPosition>('/investments/stocks', {
    ticker_symbol: tickerSymbol,
  })
  return response.data
}

export async function deleteStockPosition(id: string): Promise<void> {
  await apiClient.delete(`/investments/stocks/${id}`)
}

export interface StockBuyPayload {
  shares: number
  price_per_share: number
  transaction_date?: string
  source_bank_account_id?: string
  notes?: string
}

export async function buyStock(positionId: string, data: StockBuyPayload): Promise<StockTransaction> {
  const response = await apiClient.post<StockTransaction>(
    `/investments/stocks/${positionId}/buy`,
    data
  )
  return response.data
}

export interface StockSellPayload {
  shares: number
  price_per_share: number
  transaction_date?: string
  notes?: string
}

export async function sellStock(positionId: string, data: StockSellPayload): Promise<StockTransaction> {
  const response = await apiClient.post<StockTransaction>(
    `/investments/stocks/${positionId}/sell`,
    data
  )
  return response.data
}

export async function getStockTransactions(positionId: string): Promise<StockTransaction[]> {
  const response = await apiClient.get<StockTransaction[]>(
    `/investments/stocks/${positionId}/transactions`
  )
  return response.data
}

// --- Bonds -----------------------------------------------------------------------------

export async function getBondHoldings(): Promise<BondHolding[]> {
  const response = await apiClient.get<BondHolding[]>('/investments/bonds')
  return response.data
}

export interface BondCreatePayload {
  name: string
  purchase_price: number
  face_value: number
  coupon_rate: number
  payment_frequency: BondPaymentFrequency
  purchase_date: string
  maturity_date: string
  source_bank_account_id?: string
}

export async function createBondHolding(data: BondCreatePayload): Promise<BondHolding> {
  const response = await apiClient.post<BondHolding>('/investments/bonds', data)
  return response.data
}

export async function sellBondHolding(
  id: string,
  data: { sale_price: number; sale_date?: string }
): Promise<BondHolding> {
  const response = await apiClient.post<BondHolding>(`/investments/bonds/${id}/sell`, data)
  return response.data
}

export async function deleteBondHolding(id: string): Promise<void> {
  await apiClient.delete(`/investments/bonds/${id}`)
}

export async function getBondAmortizationSchedule(id: string): Promise<BondAmortizationSchedule> {
  const response = await apiClient.get<BondAmortizationSchedule>(
    `/investments/bonds/${id}/amortization`
  )
  return response.data
}

// --- Property investments ---------------------------------------------------------------

export interface PropertyCreatePayload {
  name: string
  cost: number
  expected_return_rate: number
  purchase_date: string
  source_bank_account_id?: string
}

export async function getPropertyInvestments(): Promise<PropertyInvestment[]> {
  const response = await apiClient.get<PropertyInvestment[]>('/investments/property')
  return response.data
}

export async function createPropertyInvestment(data: PropertyCreatePayload): Promise<PropertyInvestment> {
  const response = await apiClient.post<PropertyInvestment>('/investments/property', data)
  return response.data
}

export async function sellPropertyInvestment(
  id: string,
  data: { sale_price: number; sale_date?: string }
): Promise<PropertyInvestment> {
  const response = await apiClient.post<PropertyInvestment>(`/investments/property/${id}/sell`, data)
  return response.data
}

export async function deletePropertyInvestment(id: string): Promise<void> {
  await apiClient.delete(`/investments/property/${id}`)
}

// --- Summary -----------------------------------------------------------------------------

export async function getInvestmentSummary(): Promise<InvestmentSummary> {
  const response = await apiClient.get<InvestmentSummary>('/investments/summary')
  return response.data
}
