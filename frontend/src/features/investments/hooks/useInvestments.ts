/**
 * React Query hooks wrapping the investments api.ts functions (Phase 5). These give
 * components caching, loading states, and automatic cache invalidation after mutations
 * without each component managing that bookkeeping itself - the same pattern as
 * features/retirement/hooks/useRetirementAccounts.ts. Buy/sell mutations also invalidate
 * ['bank-accounts'] and ['transactions'] since they can move real money between accounts
 * and always post to the unified transaction log.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getStockPrice,
  getStockHistory,
  getStockPositions,
  getStockPosition,
  createStockPosition,
  deleteStockPosition,
  buyStock,
  sellStock,
  getStockTransactions,
  getBondHoldings,
  createBondHolding,
  sellBondHolding,
  deleteBondHolding,
  getBondAmortizationSchedule,
  getPropertyInvestments,
  createPropertyInvestment,
  sellPropertyInvestment,
  deletePropertyInvestment,
  getInvestmentSummary,
  type StockBuyPayload,
  type StockSellPayload,
  type BondCreatePayload,
  type PropertyCreatePayload,
} from '../api'

// Invalidated by every mutation that can move money between a bank account and an
// investment, or post to the unified transaction log.
function invalidateMoneyFlowQueries(queryClient: ReturnType<typeof useQueryClient>) {
  queryClient.invalidateQueries({ queryKey: ['bank-accounts'] })
  queryClient.invalidateQueries({ queryKey: ['transactions'] })
  queryClient.invalidateQueries({ queryKey: ['investment-summary'] })
}

// --- Market data --------------------------------------------------------------------

export function useStockPrice(ticker: string) {
  return useQuery({
    queryKey: ['stock-price', ticker],
    queryFn: () => getStockPrice(ticker),
    enabled: !!ticker,
    staleTime: 1000 * 60 * 5,
  })
}

export function useStockHistory(ticker: string, period: string) {
  return useQuery({
    queryKey: ['stock-history', ticker, period],
    queryFn: () => getStockHistory(ticker, period),
    enabled: !!ticker,
    staleTime: 1000 * 60 * 5,
  })
}

// --- Stock positions ------------------------------------------------------------------

export function useStockPositions() {
  return useQuery({
    queryKey: ['stock-positions'],
    queryFn: getStockPositions,
  })
}

export function useStockPosition(id: string) {
  return useQuery({
    queryKey: ['stock-positions', id],
    queryFn: () => getStockPosition(id),
    enabled: !!id,
  })
}

export function useCreateStockPosition() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: createStockPosition,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['stock-positions'] })
    },
  })
}

export function useDeleteStockPosition() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteStockPosition,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['stock-positions'] })
    },
  })
}

export function useBuyStock() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ positionId, data }: { positionId: string; data: StockBuyPayload }) =>
      buyStock(positionId, data),
    onSuccess: (_, { positionId }) => {
      queryClient.invalidateQueries({ queryKey: ['stock-positions'] })
      queryClient.invalidateQueries({ queryKey: ['stock-positions', positionId] })
      queryClient.invalidateQueries({ queryKey: ['stock-transactions', positionId] })
      invalidateMoneyFlowQueries(queryClient)
    },
  })
}

export function useSellStock() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ positionId, data }: { positionId: string; data: StockSellPayload }) =>
      sellStock(positionId, data),
    onSuccess: (_, { positionId }) => {
      queryClient.invalidateQueries({ queryKey: ['stock-positions'] })
      queryClient.invalidateQueries({ queryKey: ['stock-positions', positionId] })
      queryClient.invalidateQueries({ queryKey: ['stock-transactions', positionId] })
      invalidateMoneyFlowQueries(queryClient)
    },
  })
}

export function useStockTransactions(positionId: string) {
  return useQuery({
    queryKey: ['stock-transactions', positionId],
    queryFn: () => getStockTransactions(positionId),
    enabled: !!positionId,
  })
}

// --- Bonds -----------------------------------------------------------------------------

export function useBondHoldings() {
  return useQuery({
    queryKey: ['bond-holdings'],
    queryFn: getBondHoldings,
  })
}

export function useCreateBondHolding() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: BondCreatePayload) => createBondHolding(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bond-holdings'] })
      invalidateMoneyFlowQueries(queryClient)
    },
  })
}

export function useSellBondHolding() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: { sale_price: number; sale_date?: string } }) =>
      sellBondHolding(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bond-holdings'] })
      invalidateMoneyFlowQueries(queryClient)
    },
  })
}

export function useDeleteBondHolding() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteBondHolding,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bond-holdings'] })
    },
  })
}

export function useBondAmortizationSchedule(bondId: string, enabled: boolean) {
  return useQuery({
    queryKey: ['bond-amortization', bondId],
    queryFn: () => getBondAmortizationSchedule(bondId),
    enabled: enabled && !!bondId,
  })
}

// --- Property investments ---------------------------------------------------------------

export function usePropertyInvestments() {
  return useQuery({
    queryKey: ['property-investments'],
    queryFn: getPropertyInvestments,
  })
}

export function useCreatePropertyInvestment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: PropertyCreatePayload) => createPropertyInvestment(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['property-investments'] })
      invalidateMoneyFlowQueries(queryClient)
    },
  })
}

export function useSellPropertyInvestment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: { sale_price: number; sale_date?: string } }) =>
      sellPropertyInvestment(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['property-investments'] })
      invalidateMoneyFlowQueries(queryClient)
    },
  })
}

export function useDeletePropertyInvestment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deletePropertyInvestment,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['property-investments'] })
    },
  })
}

// --- Summary -----------------------------------------------------------------------------

export function useInvestmentSummary() {
  return useQuery({
    queryKey: ['investment-summary'],
    queryFn: getInvestmentSummary,
  })
}
