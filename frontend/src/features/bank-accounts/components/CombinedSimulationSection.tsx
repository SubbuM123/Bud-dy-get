/**
 * Combined growth simulation across a user-chosen subset of their bank accounts
 * (including CD maturity/rollover rules - see the backend's combined_simulator.py),
 * rendered on BankAccountsPage below the account cards. Each real account gets a
 * checkbox; unchecking one re-runs the simulation excluding it (the request goes back to
 * the backend rather than just hiding a line client-side, since which accounts are
 * present can change CD-maturity behavior - e.g. whether a matured CD has a real savings
 * account to land in). Renders CombinedGrowthChart plus a per-account side panel with
 * each series' ending balance and average interest earned per that account's own
 * compounding period (a monthly account shows "$X / month", a quarterly one "$X / quarter").
 */
import { useEffect, useState } from 'react'
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import CombinedGrowthChart from '@/components/charts/CombinedGrowthChart'
import { useBankAccounts, useCombinedSimulation } from '../hooks/useBankAccounts'
import {
  formatCurrency,
  compoundingPeriodsElapsed,
  compoundingPeriodLabel,
} from '@/lib/utils'

export default function CombinedSimulationSection() {
  const [months, setMonths] = useState(12)
  const [includeRecurring, setIncludeRecurring] = useState(true)
  const [selectedAccountIds, setSelectedAccountIds] = useState<string[] | null>(null)

  const { data: accounts } = useBankAccounts()

  // Seed the selection with every account the first time the list loads, then keep it in
  // sync as accounts are created/deleted - newly created accounts default to included,
  // deleted ones are dropped, and the user's existing checked/unchecked choices for
  // accounts that still exist are left alone (a background refetch shouldn't silently
  // reset what they picked).
  useEffect(() => {
    if (!accounts) return
    setSelectedAccountIds((prev) => {
      if (prev === null) return accounts.map((a) => a.id)
      const currentIds = new Set(accounts.map((a) => a.id))
      const kept = prev.filter((id) => currentIds.has(id))
      const added = accounts.map((a) => a.id).filter((id) => !prev.includes(id))
      return [...kept, ...added]
    })
  }, [accounts])

  const { data: simulation, isLoading } = useCombinedSimulation(
    months,
    includeRecurring,
    selectedAccountIds
  )

  const toggleAccount = (id: string) => {
    setSelectedAccountIds((prev) => {
      const current = prev ?? []
      return current.includes(id) ? current.filter((x) => x !== id) : [...current, id]
    })
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <CardTitle>Combined Account Growth Simulation</CardTitle>
            <CardDescription>
              Every account's projected balance, and the total across all of them
            </CardDescription>
          </div>
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={includeRecurring}
                onChange={(e) => setIncludeRecurring(e.target.checked)}
                className="rounded border-slate-300"
              />
              <span className="text-sm">Include recurring actions</span>
            </label>
            <div className="flex items-center gap-2">
              <Input
                type="number"
                min={1}
                max={600}
                value={months}
                onChange={(e) => setMonths(parseInt(e.target.value) || 12)}
                className="w-20"
              />
              <span className="text-sm text-slate-500">months</span>
            </div>
          </div>
        </div>

        {accounts && accounts.length > 0 && (
          <div className="flex flex-wrap gap-x-4 gap-y-2 pt-4 border-t mt-4">
            <span className="text-sm text-slate-500">Include:</span>
            {accounts.map((account) => (
              <label key={account.id} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={selectedAccountIds?.includes(account.id) ?? true}
                  onChange={() => toggleAccount(account.id)}
                  className="rounded border-slate-300"
                />
                <span className="text-sm">{account.account_name}</span>
              </label>
            ))}
          </div>
        )}
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="flex items-center justify-center h-96">
            <p className="text-slate-500">Calculating combined projection...</p>
          </div>
        ) : simulation && simulation.accounts.length > 0 ? (
          <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
            <CombinedGrowthChart data={simulation} />

            <div className="space-y-3">
              <div className="rounded-lg bg-slate-50 p-4">
                <p className="text-sm text-slate-500">Total Balance</p>
                <p className="text-2xl font-bold">
                  {formatCurrency(simulation.final_total_balance)}
                </p>
              </div>
              {simulation.accounts.map((series) => {
                const first = series.projections[0]
                const last = series.projections[series.projections.length - 1]
                const periods = compoundingPeriodsElapsed(
                  series.compounding_frequency,
                  last.month - first.month
                )
                const avgInterest =
                  periods > 0
                    ? (parseFloat(last.interest_earned) - parseFloat(first.interest_earned)) /
                      periods
                    : 0

                return (
                  <div key={series.account_id} className="rounded-lg border border-slate-200 p-4">
                    <p className="font-medium">
                      {series.account_name}
                      {series.is_virtual && (
                        <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
                          Auto-created
                        </span>
                      )}
                    </p>
                    <p className="text-sm text-slate-500 capitalize">{series.account_type}</p>
                    <p className="mt-2 text-xl font-bold">{formatCurrency(last.balance)}</p>
                    {periods > 0 && (
                      <p className="text-sm text-success-600">
                        ≈ {formatCurrency(avgInterest)} /{' '}
                        {compoundingPeriodLabel(series.compounding_frequency)}
                      </p>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        ) : (
          <p className="text-slate-500 text-center py-12">
            {accounts && accounts.length > 0
              ? 'No accounts selected - check at least one above to see the combined simulation'
              : 'Create a bank account to see the combined simulation'}
          </p>
        )}
      </CardContent>
    </Card>
  )
}
