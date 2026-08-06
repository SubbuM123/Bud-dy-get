/**
 * Small, dependency-light helper functions used throughout the frontend: a Tailwind
 * class-merging utility for components with a `className` prop, and formatters that
 * turn the raw string values returned by the API (Decimal fields are serialized as
 * strings) into the currency/percent/date strings shown in the UI.
 */
import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
import axios from 'axios'
import type { ApiError } from '@/types'

// Merge conditional class names and resolve conflicting Tailwind utility classes.
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// Extract a user-facing message from a failed API call, preferring the backend's
// HTTPException `detail` over Axios's generic "Request failed with status code..." text.
export function getApiErrorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError<ApiError>(err)) {
    return err.response?.data?.detail ?? fallback
  }
  return err instanceof Error ? err.message : fallback
}

// Format a numeric amount (or the string form the API returns) as USD currency.
export function formatCurrency(amount: number | string): string {
  const num = typeof amount === 'string' ? parseFloat(amount) : amount
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(num)
}

// Format a decimal rate (e.g. 0.0425) as a percentage string (e.g. "4.25%").
export function formatPercent(rate: number | string): string {
  const num = typeof rate === 'string' ? parseFloat(rate) : rate
  return `${(num * 100).toFixed(2)}%`
}

// Format an ISO date string or Date object as a short human-readable date.
export function formatDate(date: string | Date): string {
  return new Date(date).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

type CompoundingFrequency = 'daily' | 'monthly' | 'quarterly' | 'annually'

// Convert a simulation length in months into a count of an account's own compounding
// periods (e.g. 12 simulated months = 12 "months" for a monthly account, but only 4
// "quarters" for a quarterly one), so "average interest per period" reads in whatever
// unit that account's compounding actually follows.
export function compoundingPeriodsElapsed(
  compounding: CompoundingFrequency,
  months: number
): number {
  switch (compounding) {
    case 'daily':
      return months * 30
    case 'quarterly':
      return months / 3
    case 'annually':
      return months / 12
    case 'monthly':
    default:
      return months
  }
}

// Singular label for one of an account's own compounding periods, e.g. "month" or "quarter".
export function compoundingPeriodLabel(compounding: CompoundingFrequency): string {
  switch (compounding) {
    case 'daily':
      return 'day'
    case 'quarterly':
      return 'quarter'
    case 'annually':
      return 'year'
    case 'monthly':
    default:
      return 'month'
  }
}
