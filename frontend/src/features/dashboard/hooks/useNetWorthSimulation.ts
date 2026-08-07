/**
 * On-demand ("Simulate" button, not an auto-firing query) projection of total net worth N
 * months out. There's no single backend endpoint for this - bank accounts have their own
 * /bank-accounts/simulate-combined (every bank account in one call), but retirement and
 * education each only expose a per-account /simulate, so this fans out one call per
 * retirement/education account and sums the results client-side. Investments (stocks,
 * bonds, property) have no expected-return concept anywhere in this app the way
 * interest-bearing accounts do - no rate to project from - so they're carried forward at
 * today's value rather than guessing one.
 */
import { useMutation } from '@tanstack/react-query'
import { simulateCombinedGrowth } from '@/features/bank-accounts/api'
import { simulateRetirementGrowth } from '@/features/retirement/api'
import { simulateEducationGrowth } from '@/features/education/api'

export interface NetWorthSimulationResult {
  months: number
  bankTotal: number
  retirementTotal: number
  educationTotal: number
  investmentTotal: number
  netWorth: number
}

interface SimulateNetWorthArgs {
  months: number
  hasBankAccounts: boolean
  retirementAccountIds: string[]
  educationAccountIds: string[]
  currentInvestmentValue: number
}

async function simulateNetWorth({
  months,
  hasBankAccounts,
  retirementAccountIds,
  educationAccountIds,
  currentInvestmentValue,
}: SimulateNetWorthArgs): Promise<NetWorthSimulationResult> {
  const [bankResult, retirementResults, educationResults] = await Promise.all([
    hasBankAccounts ? simulateCombinedGrowth(months, true) : Promise.resolve(null),
    Promise.all(retirementAccountIds.map((id) => simulateRetirementGrowth(id, months, 0, true))),
    Promise.all(educationAccountIds.map((id) => simulateEducationGrowth(id, months, 0, true))),
  ])

  const bankTotal = bankResult ? parseFloat(bankResult.final_total_balance) : 0
  const retirementTotal = retirementResults.reduce((sum, r) => sum + parseFloat(r.final_balance), 0)
  const educationTotal = educationResults.reduce((sum, r) => sum + parseFloat(r.final_balance), 0)
  const investmentTotal = currentInvestmentValue

  return {
    months,
    bankTotal,
    retirementTotal,
    educationTotal,
    investmentTotal,
    netWorth: bankTotal + retirementTotal + educationTotal + investmentTotal,
  }
}

export function useSimulateNetWorth() {
  return useMutation({ mutationFn: simulateNetWorth })
}
