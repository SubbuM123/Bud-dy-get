/**
 * Dedicated net worth view: total net worth, a ranked bar chart breaking it down by
 * category (NetWorthByCategoryChart), a "simulate N months out" section, and a set of
 * "explore" tabs beneath it that let a user drill into whichever category they're curious
 * about without leaving the page. Bank Accounts/Retirement/Education each list their real
 * accounts (same balance fields DashboardPage already aggregates); Investments has no
 * single list of its own - it's already split across two pages (bonds/property at
 * /investments, stocks at /stocks, see Sidebar.tsx's docstring) - so that tab instead
 * breaks down useInvestmentSummary's three components and links out to both.
 */
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Landmark, PiggyBank, GraduationCap, TrendingUp, ArrowRight, Sparkles } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn, formatCurrency, getApiErrorMessage } from '@/lib/utils'
import { useBankAccounts } from '@/features/bank-accounts/hooks/useBankAccounts'
import { useRetirementAccounts } from '@/features/retirement/hooks/useRetirementAccounts'
import { useEducationAccounts } from '@/features/education/hooks/useEducationAccounts'
import { useInvestmentSummary } from '@/features/investments/hooks/useInvestments'
import { useSimulateNetWorth } from '../hooks/useNetWorthSimulation'
import NetWorthByCategoryChart from '../components/NetWorthByCategoryChart'

type TabKey = 'bank-accounts' | 'retirement' | 'education' | 'investments'

const TABS: { key: TabKey; label: string; icon: typeof Landmark }[] = [
  { key: 'bank-accounts', label: 'Bank Accounts', icon: Landmark },
  { key: 'retirement', label: 'Retirement', icon: PiggyBank },
  { key: 'education', label: 'Education', icon: GraduationCap },
  { key: 'investments', label: 'Investments', icon: TrendingUp },
]

// One "name + balance, links to its detail page" row - shared shape for the three
// account-list tabs.
function AccountRow({ name, balance, href }: { name: string; balance: number; href: string }) {
  return (
    <Link
      to={href}
      className="flex items-center justify-between rounded-md px-3 py-2.5 text-sm hover:bg-slate-50"
    >
      <span className="text-slate-700">{name}</span>
      <span className="font-medium text-slate-900">{formatCurrency(balance)}</span>
    </Link>
  )
}

export default function NetWorthPage() {
  const [activeTab, setActiveTab] = useState<TabKey>('bank-accounts')
  const [simulateMonths, setSimulateMonths] = useState('12')

  const { data: bankAccounts } = useBankAccounts()
  const { data: retirementAccounts } = useRetirementAccounts()
  const { data: educationAccounts } = useEducationAccounts()
  const { data: investmentSummary } = useInvestmentSummary()
  const simulateNetWorth = useSimulateNetWorth()

  const totalBankBalance =
    bankAccounts?.reduce((sum, acc) => sum + parseFloat(acc.current_balance), 0) || 0
  const totalRetirementBalance =
    retirementAccounts?.reduce((sum, acc) => sum + parseFloat(acc.balance), 0) || 0
  const totalEducationBalance =
    educationAccounts?.reduce((sum, acc) => sum + parseFloat(acc.balance), 0) || 0
  const totalInvestmentValue = investmentSummary ? parseFloat(investmentSummary.total_value) : 0
  const netWorth = totalBankBalance + totalRetirementBalance + totalEducationBalance + totalInvestmentValue

  const chartData = [
    { name: 'Bank Accounts', amount: totalBankBalance },
    { name: 'Retirement', amount: totalRetirementBalance },
    { name: 'Education', amount: totalEducationBalance },
    { name: 'Investments', amount: totalInvestmentValue },
  ]

  function handleSimulate() {
    const months = parseInt(simulateMonths, 10)
    if (!months || months < 1 || months > 600) return
    simulateNetWorth.mutate({
      months,
      hasBankAccounts: (bankAccounts?.length ?? 0) > 0,
      retirementAccountIds: retirementAccounts?.map((acc) => acc.id) ?? [],
      educationAccountIds: educationAccounts?.map((acc) => acc.id) ?? [],
      currentInvestmentValue: totalInvestmentValue,
    })
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Net Worth</h1>
        <p className="text-slate-500">Everything you own, all in one number</p>
      </div>

      <Card>
        <CardContent className="pt-6">
          <p className="text-sm text-slate-500">Total Net Worth</p>
          <p className="text-4xl font-bold text-slate-900">{formatCurrency(netWorth)}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Breakdown by category</CardTitle>
          <CardDescription>Where your net worth currently comes from</CardDescription>
        </CardHeader>
        <CardContent>
          <NetWorthByCategoryChart data={chartData} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Simulate</CardTitle>
          <CardDescription>
            Project your net worth forward using each account's current growth rate and recurring
            contributions
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-end gap-3">
            <Input
              label="Months from now"
              type="number"
              min={1}
              max={600}
              value={simulateMonths}
              onChange={(e) => setSimulateMonths(e.target.value)}
              className="max-w-[140px]"
            />
            <Button onClick={handleSimulate} disabled={simulateNetWorth.isPending}>
              <Sparkles className="mr-2 h-4 w-4" />
              {simulateNetWorth.isPending ? 'Simulating...' : 'Simulate'}
            </Button>
          </div>

          {simulateNetWorth.isError && (
            <p className="mt-4 text-sm text-danger-500">
              {getApiErrorMessage(simulateNetWorth.error, 'Failed to run the simulation.')}
            </p>
          )}

          {simulateNetWorth.isSuccess && (
            <div className="mt-6 space-y-4">
              <div>
                <p className="text-sm text-slate-500">
                  Projected net worth in {simulateNetWorth.data.months} month
                  {simulateNetWorth.data.months === 1 ? '' : 's'}
                </p>
                <p className="text-3xl font-bold text-slate-900">
                  {formatCurrency(simulateNetWorth.data.netWorth)}
                </p>
                <p
                  className={cn(
                    'text-sm',
                    simulateNetWorth.data.netWorth >= netWorth ? 'text-success-600' : 'text-danger-500'
                  )}
                >
                  {simulateNetWorth.data.netWorth >= netWorth ? '+' : ''}
                  {formatCurrency(simulateNetWorth.data.netWorth - netWorth)} from today
                </p>
              </div>
              <NetWorthByCategoryChart
                data={[
                  { name: 'Bank Accounts', amount: simulateNetWorth.data.bankTotal },
                  { name: 'Retirement', amount: simulateNetWorth.data.retirementTotal },
                  { name: 'Education', amount: simulateNetWorth.data.educationTotal },
                  { name: 'Investments', amount: simulateNetWorth.data.investmentTotal },
                ]}
              />
              <p className="text-xs text-slate-400">
                Investments are held flat at today's value - there's no expected-return rate to
                project them from.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Explore</CardTitle>
          <CardDescription>Drill into a category to see the accounts behind it</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="mb-4 flex flex-wrap gap-2 border-b pb-4">
            {TABS.map((tab) => (
              <Button
                key={tab.key}
                variant={activeTab === tab.key ? 'default' : 'outline'}
                size="sm"
                onClick={() => setActiveTab(tab.key)}
                className={cn(activeTab === tab.key ? '' : 'text-slate-600')}
              >
                <tab.icon className="mr-2 h-4 w-4" />
                {tab.label}
              </Button>
            ))}
          </div>

          {activeTab === 'bank-accounts' && (
            <div className="space-y-1">
              {bankAccounts && bankAccounts.length > 0 ? (
                bankAccounts.map((acc) => (
                  <AccountRow
                    key={acc.id}
                    name={acc.account_name}
                    balance={parseFloat(acc.current_balance)}
                    href={`/bank-accounts/${acc.id}`}
                  />
                ))
              ) : (
                <p className="py-6 text-center text-sm text-slate-500">No bank accounts yet</p>
              )}
            </div>
          )}

          {activeTab === 'retirement' && (
            <div className="space-y-1">
              {retirementAccounts && retirementAccounts.length > 0 ? (
                retirementAccounts.map((acc) => (
                  <AccountRow
                    key={acc.id}
                    name={acc.account_name}
                    balance={parseFloat(acc.balance)}
                    href={`/retirement/${acc.id}`}
                  />
                ))
              ) : (
                <p className="py-6 text-center text-sm text-slate-500">No retirement accounts yet</p>
              )}
            </div>
          )}

          {activeTab === 'education' && (
            <div className="space-y-1">
              {educationAccounts && educationAccounts.length > 0 ? (
                educationAccounts.map((acc) => (
                  <AccountRow
                    key={acc.id}
                    name={acc.account_name}
                    balance={parseFloat(acc.balance)}
                    href={`/education/${acc.id}`}
                  />
                ))
              ) : (
                <p className="py-6 text-center text-sm text-slate-500">No education accounts yet</p>
              )}
            </div>
          )}

          {activeTab === 'investments' && (
            <div className="space-y-1">
              <div className="flex items-center justify-between px-3 py-2.5 text-sm">
                <span className="text-slate-700">Stocks</span>
                <span className="font-medium text-slate-900">
                  {formatCurrency(investmentSummary ? parseFloat(investmentSummary.total_stocks_value) : 0)}
                </span>
              </div>
              <div className="flex items-center justify-between px-3 py-2.5 text-sm">
                <span className="text-slate-700">Bonds</span>
                <span className="font-medium text-slate-900">
                  {formatCurrency(investmentSummary ? parseFloat(investmentSummary.total_bonds_value) : 0)}
                </span>
              </div>
              <div className="flex items-center justify-between px-3 py-2.5 text-sm">
                <span className="text-slate-700">Property</span>
                <span className="font-medium text-slate-900">
                  {formatCurrency(investmentSummary ? parseFloat(investmentSummary.total_property_value) : 0)}
                </span>
              </div>
              <div className="flex gap-3 pt-3">
                <Link to="/stocks">
                  <Button variant="outline" size="sm">
                    View Stocks <ArrowRight className="ml-2 h-4 w-4" />
                  </Button>
                </Link>
                <Link to="/investments">
                  <Button variant="outline" size="sm">
                    View Bonds & Property <ArrowRight className="ml-2 h-4 w-4" />
                  </Button>
                </Link>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
