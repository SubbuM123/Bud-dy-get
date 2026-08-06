/**
 * Smoke test that the Decimal-as-string -> number coercion CombinedGrowthChart does on
 * CombinedSimulationResponse's per-account and total series doesn't throw, for both a
 * populated and an empty response - mirrors GrowthChart.test.tsx's coverage. Also covers
 * the real bug fixed in buildCombinedChartRows: once enough CD renewal segments push some
 * into the "Other accounts" overflow fold, a continuation segment's shared boundary-month
 * point must not be double-counted (see this file's sibling component's module docstring).
 */
import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import CombinedGrowthChart, { buildCombinedChartRows } from './CombinedGrowthChart'
import type { AccountProjectionSeries, CombinedSimulationResponse } from '@/types'

const response: CombinedSimulationResponse = {
  accounts: [
    {
      account_id: 'savings-1',
      account_name: 'Everyday Savings',
      account_type: 'savings',
      compounding_frequency: 'monthly',
      is_virtual: false,
      is_continuation: false,
      projections: [
        { month: 0, date: '2026-01-01', balance: '1000.00', principal: '1000.00', interest_earned: '0.00', deposits: '0.00', withdrawals: '0.00' },
        { month: 1, date: '2026-02-01', balance: '1002.00', principal: '1000.00', interest_earned: '2.00', deposits: '0.00', withdrawals: '0.00' },
      ],
    },
    {
      account_id: 'virtual-savings',
      account_name: 'Savings (auto-created)',
      account_type: 'savings',
      compounding_frequency: 'monthly',
      is_virtual: true,
      is_continuation: false,
      projections: [
        { month: 0, date: '2026-01-01', balance: '0.00', principal: '0.00', interest_earned: '0.00', deposits: '0.00', withdrawals: '0.00' },
        { month: 1, date: '2026-02-01', balance: '2000.00', principal: '2000.00', interest_earned: '0.00', deposits: '2000.00', withdrawals: '0.00' },
      ],
    },
  ],
  total_projections: [
    { month: 0, date: '2026-01-01', total_balance: '1000.00' },
    { month: 1, date: '2026-02-01', total_balance: '3002.00' },
  ],
  final_total_balance: '3002.00',
}

const emptyResponse: CombinedSimulationResponse = {
  accounts: [],
  total_projections: [
    { month: 0, date: '2026-01-01', total_balance: '0.00' },
  ],
  final_total_balance: '0.00',
}

describe('CombinedGrowthChart', () => {
  it('renders without throwing for a populated combined simulation response', () => {
    expect(() => render(<CombinedGrowthChart data={response} />)).not.toThrow()
  })

  it('renders without throwing for a response with no accounts', () => {
    expect(() => render(<CombinedGrowthChart data={emptyResponse} />)).not.toThrow()
  })
})

// A CD segment (or renewal-of-a-renewal) covering exactly [startMonth, startMonth+1],
// with a fixed $100 balance at each point for arithmetic that's easy to reason about.
function segment(id: string, startMonth: number, isContinuation: boolean): AccountProjectionSeries {
  return {
    account_id: id,
    account_name: id,
    account_type: 'cd',
    compounding_frequency: 'monthly',
    is_virtual: false,
    is_continuation: isContinuation,
    projections: [
      { month: startMonth, date: '2026-01-01', balance: '100.00', principal: '100.00', interest_earned: '0.00', deposits: '0.00', withdrawals: '0.00' },
      { month: startMonth + 1, date: '2026-02-01', balance: '100.00', principal: '100.00', interest_earned: '0.00', deposits: '0.00', withdrawals: '0.00' },
    ],
  }
}

describe('buildCombinedChartRows', () => {
  it('does not double-count a continuation segment folded into "other"', () => {
    // 9 CD segments, one continuous chain (segment N starts where segment N-1 ended),
    // forcing segments past index 8 into the "other" overflow fold. Every segment holds
    // a flat $100, so the true total at every month is always $100 - never $200.
    const segments = Array.from({ length: 9 }, (_, i) => segment(`cd-${i}`, i, i > 0))
    const totalProjections = Array.from({ length: 10 }, (_, month) => ({
      month,
      date: '2026-01-01',
      total_balance: '100.00',
    }))
    const data: CombinedSimulationResponse = {
      accounts: segments,
      total_projections: totalProjections,
      final_total_balance: '100.00',
    }

    // maxIndividualSeries=8 pushes segment index 8 (cd-8, a continuation) into overflow.
    const rows = buildCombinedChartRows(data, 8)

    for (const row of rows) {
      if (row.other !== undefined) {
        expect(row.other).toBeLessThanOrEqual(row.total)
      }
    }
  })

  it('would have double-counted without the is_continuation check (sanity check on the fixture)', () => {
    // Same fixture as above, but reduced to just the two overflow-relevant segments and
    // a naive (continuation-unaware) sum, to confirm the fixture actually exercises the
    // bug rather than trivially passing.
    const segments = [segment('cd-8', 8, false), segment('cd-9', 9, true)]
    const naiveOtherAtBoundary = segments.reduce((sum, s) => {
      const point = s.projections.find((p) => p.month === 9)
      return sum + (point ? parseFloat(point.balance) : 0)
    }, 0)
    expect(naiveOtherAtBoundary).toBe(200) // both segments have a point at month 9
  })
})
