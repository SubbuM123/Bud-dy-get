/**
 * Covers buildMonthlyTotals - the actual logic in SpendingTrendChart.tsx, bucketing a flat
 * expense list into calendar months (including zero-spend months) - the same
 * export-the-logic-for-direct-testing pattern CombinedGrowthChart.tsx's
 * buildCombinedChartRows uses.
 */
import { describe, expect, it } from 'vitest'
import { buildMonthlyTotals } from './SpendingTrendChart'
import type { Expense } from '@/types'

function makeExpense(amount: string, expense_date: string): Expense {
  return {
    id: crypto.randomUUID(),
    user_id: 'user-1',
    receipt_id: null,
    merchant_name: 'Test Merchant',
    amount,
    expense_date,
    category_id: null,
    bank_account_id: null,
    description: null,
    tags: null,
    is_recurring: false,
    recurrence_pattern: null,
    created_at: `${expense_date}T00:00:00Z`,
    updated_at: `${expense_date}T00:00:00Z`,
  }
}

describe('buildMonthlyTotals', () => {
  it('returns the requested number of months, oldest first', () => {
    const today = new Date(2026, 2, 15) // March 15, 2026 (month is 0-indexed)
    const result = buildMonthlyTotals([], 3, today)

    expect(result).toHaveLength(3)
    expect(result.map((m) => m.monthKey)).toEqual(['2026-01', '2026-02', '2026-03'])
    expect(result.map((m) => m.label)).toEqual(['Jan 2026', 'Feb 2026', 'Mar 2026'])
  })

  it('sums expenses into their calendar month', () => {
    const today = new Date(2026, 2, 15)
    const expenses = [
      makeExpense('10.00', '2026-03-01'),
      makeExpense('5.50', '2026-03-20'),
      makeExpense('100.00', '2026-02-10'),
    ]

    const result = buildMonthlyTotals(expenses, 3, today)

    const march = result.find((m) => m.monthKey === '2026-03')!
    const february = result.find((m) => m.monthKey === '2026-02')!
    const january = result.find((m) => m.monthKey === '2026-01')!
    expect(march.total).toBeCloseTo(15.5)
    expect(february.total).toBeCloseTo(100.0)
    expect(january.total).toBe(0)
  })

  it('ignores expenses outside the requested window', () => {
    const today = new Date(2026, 2, 15)
    const expenses = [makeExpense('999.00', '2025-01-01')]

    const result = buildMonthlyTotals(expenses, 3, today)

    expect(result.reduce((sum, m) => sum + m.total, 0)).toBe(0)
  })

  it('handles a year boundary correctly', () => {
    const today = new Date(2026, 0, 15) // January 15, 2026
    const result = buildMonthlyTotals([], 3, today)

    expect(result.map((m) => m.monthKey)).toEqual(['2025-11', '2025-12', '2026-01'])
  })
})
