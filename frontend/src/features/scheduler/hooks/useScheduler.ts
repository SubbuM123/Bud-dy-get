/**
 * React Query hook wrapping the scheduler api.ts function - same caching/invalidation
 * pattern every other feature module uses. Running the scheduler can touch balances and
 * post rows across every account type at once (income, bank/retirement/education
 * interest, recurring contributions, recurring expenses), so its success handler
 * invalidates every query any of that could have changed, not just 'transactions'.
 */
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { runScheduler } from '../api'

const AFFECTED_QUERY_KEYS = [
  'transactions',
  'expenses',
  'bank-accounts',
  'retirement-accounts',
  'education-accounts',
  'retirement-recurring-contributions',
  'education-recurring-contributions',
  'contribution-limits',
]

export function useRunScheduler() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: runScheduler,
    onSuccess: () => {
      AFFECTED_QUERY_KEYS.forEach((key) => queryClient.invalidateQueries({ queryKey: [key] }))
    },
  })
}
