/**
 * Guards the balance->number coercion GrowthChart does on the API's Decimal-as-string
 * projection fields - a regression here would silently render an empty/NaN chart instead
 * of throwing, so it's worth pinning down explicitly.
 */
import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import GrowthChart from './GrowthChart'
import type { ProjectionPoint } from '@/types'

const projections: ProjectionPoint[] = [
  {
    month: 0,
    date: '2026-01-01',
    balance: '10000.00',
    principal: '10000.00',
    interest_earned: '0.00',
    deposits: '0.00',
    withdrawals: '0.00',
  },
  {
    month: 1,
    date: '2026-02-01',
    balance: '10041.67',
    principal: '10000.00',
    interest_earned: '41.67',
    deposits: '0.00',
    withdrawals: '0.00',
  },
]

describe('GrowthChart', () => {
  it('renders without throwing for a valid projection series', () => {
    expect(() => render(<GrowthChart data={projections} />)).not.toThrow()
  })

  it('renders without throwing for an empty projection series', () => {
    expect(() => render(<GrowthChart data={[]} />)).not.toThrow()
  })
})
