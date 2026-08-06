/**
 * Top-level landing page at /dashboard, giving a cross-module overview of the user's
 * finances. As of Phase 5 it aggregates bank, retirement, education, and investment
 * (stocks/bonds/property) accounts into a net worth stat tile, plus this calendar month's
 * total spending from the Expense Tracker module - spending isn't a balance, so it's shown
 * alongside net worth rather than folded into it, matching backend/app/api/v1/dashboard.py's
 * own total_expenses_this_month field (unused here - this page aggregates client-side from
 * each module's own list/summary query, the same pattern every prior phase used, rather
 * than calling that endpoint). Investments is the one exception that already calls its own
 * summary endpoint (GET /investments/summary) instead of aggregating client-side, since the
 * computed market-value/current-book-value figures live server-side - see
 * schemas/investments.py's module docstring.
 */
import { Link } from 'react-router-dom'
import {
  Landmark,
  ArrowRight,
  TrendingUp,
  Receipt,
  ScanLine,
  PiggyBank,
  GraduationCap,
  Wallet,
} from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { formatCurrency } from '@/lib/utils'
import { useBankAccounts } from '@/features/bank-accounts/hooks/useBankAccounts'
import { useRetirementAccounts } from '@/features/retirement/hooks/useRetirementAccounts'
import { useEducationAccounts } from '@/features/education/hooks/useEducationAccounts'
import { useExpenseSummary } from '@/features/expenses/hooks/useExpenses'
import { useInvestmentSummary } from '@/features/investments/hooks/useInvestments'

export default function DashboardPage() {
  const { data: bankAccounts } = useBankAccounts()
  const { data: retirementAccounts } = useRetirementAccounts()
  const { data: educationAccounts } = useEducationAccounts()
  const { data: expenseSummary } = useExpenseSummary()
  const { data: investmentSummary } = useInvestmentSummary()

  // Sum current balances across all accounts for the headline stat tiles.
  const totalBankBalance =
    bankAccounts?.reduce((sum, acc) => sum + parseFloat(acc.current_balance), 0) || 0
  const totalRetirementBalance =
    retirementAccounts?.reduce((sum, acc) => sum + parseFloat(acc.balance), 0) || 0
  const totalEducationBalance =
    educationAccounts?.reduce((sum, acc) => sum + parseFloat(acc.balance), 0) || 0
  const totalInvestmentValue = investmentSummary ? parseFloat(investmentSummary.total_value) : 0
  const netWorth =
    totalBankBalance + totalRetirementBalance + totalEducationBalance + totalInvestmentValue
  const totalExpensesThisMonth = expenseSummary ? parseFloat(expenseSummary.total_amount) : 0

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
        <p className="text-slate-500">Welcome to your financial dashboard</p>
      </div>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="rounded-full bg-primary-100 p-3">
                <Wallet className="h-6 w-6 text-primary-600" />
              </div>
              <div>
                <p className="text-sm text-slate-500">Net Worth</p>
                <p className="text-2xl font-bold">{formatCurrency(netWorth)}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="rounded-full bg-success-500/10 p-3">
                <Landmark className="h-6 w-6 text-success-600" />
              </div>
              <div>
                <p className="text-sm text-slate-500">Total Bank Balance</p>
                <p className="text-2xl font-bold">{formatCurrency(totalBankBalance)}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="rounded-full bg-purple-100 p-3">
                <PiggyBank className="h-6 w-6 text-purple-600" />
              </div>
              <div>
                <p className="text-sm text-slate-500">Total Retirement Balance</p>
                <p className="text-2xl font-bold">{formatCurrency(totalRetirementBalance)}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="rounded-full bg-purple-100 p-3">
                <GraduationCap className="h-6 w-6 text-purple-600" />
              </div>
              <div>
                <p className="text-sm text-slate-500">Total Education Balance</p>
                <p className="text-2xl font-bold">{formatCurrency(totalEducationBalance)}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="rounded-full bg-sky-100 p-3">
                <TrendingUp className="h-6 w-6 text-sky-600" />
              </div>
              <div>
                <p className="text-sm text-slate-500">Total Investments</p>
                <p className="text-2xl font-bold">{formatCurrency(totalInvestmentValue)}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="rounded-full bg-amber-100 p-3">
                <Receipt className="h-6 w-6 text-amber-600" />
              </div>
              <div>
                <p className="text-sm text-slate-500">Spending This Month</p>
                <p className="text-2xl font-bold">{formatCurrency(totalExpensesThisMonth)}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Bank Accounts</CardTitle>
                <CardDescription>Your savings and checking accounts</CardDescription>
              </div>
              <Link to="/bank-accounts">
                <Button variant="ghost" size="sm">
                  View All
                  <ArrowRight className="h-4 w-4 ml-2" />
                </Button>
              </Link>
            </div>
          </CardHeader>
          <CardContent>
            {bankAccounts?.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-slate-500 mb-4">No accounts yet</p>
                <Link to="/bank-accounts">
                  <Button>Get Started</Button>
                </Link>
              </div>
            ) : (
              <div className="space-y-3">
                {bankAccounts?.slice(0, 5).map((account) => (
                  <Link
                    key={account.id}
                    to={`/bank-accounts/${account.id}`}
                    className="flex items-center justify-between p-3 rounded-lg hover:bg-slate-50 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <div className="rounded-full bg-slate-100 p-2">
                        <Landmark className="h-4 w-4 text-slate-600" />
                      </div>
                      <div>
                        <p className="font-medium">{account.account_name}</p>
                        <p className="text-sm text-slate-500 capitalize">
                          {account.account_type}
                        </p>
                      </div>
                    </div>
                    <p className="font-semibold">
                      {formatCurrency(account.current_balance)}
                    </p>
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Retirement Accounts</CardTitle>
                <CardDescription>401(k), IRA, and HSA balances</CardDescription>
              </div>
              <Link to="/retirement">
                <Button variant="ghost" size="sm">
                  View All
                  <ArrowRight className="h-4 w-4 ml-2" />
                </Button>
              </Link>
            </div>
          </CardHeader>
          <CardContent>
            {retirementAccounts?.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-slate-500 mb-4">No retirement accounts yet</p>
                <Link to="/retirement">
                  <Button>Get Started</Button>
                </Link>
              </div>
            ) : (
              <div className="space-y-3">
                {retirementAccounts?.slice(0, 5).map((account) => (
                  <Link
                    key={account.id}
                    to={`/retirement/${account.id}`}
                    className="flex items-center justify-between p-3 rounded-lg hover:bg-slate-50 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <div className="rounded-full bg-slate-100 p-2">
                        <PiggyBank className="h-4 w-4 text-slate-600" />
                      </div>
                      <div>
                        <p className="font-medium">{account.account_name}</p>
                        <p className="text-sm text-slate-500">
                          {account.account_type.replace(/_/g, ' ')}
                        </p>
                      </div>
                    </div>
                    <p className="font-semibold">{formatCurrency(account.balance)}</p>
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Education Accounts</CardTitle>
                <CardDescription>529 college savings plans</CardDescription>
              </div>
              <Link to="/education">
                <Button variant="ghost" size="sm">
                  View All
                  <ArrowRight className="h-4 w-4 ml-2" />
                </Button>
              </Link>
            </div>
          </CardHeader>
          <CardContent>
            {educationAccounts?.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-slate-500 mb-4">No education accounts yet</p>
                <Link to="/education">
                  <Button>Get Started</Button>
                </Link>
              </div>
            ) : (
              <div className="space-y-3">
                {educationAccounts?.slice(0, 5).map((account) => (
                  <Link
                    key={account.id}
                    to={`/education/${account.id}`}
                    className="flex items-center justify-between p-3 rounded-lg hover:bg-slate-50 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <div className="rounded-full bg-slate-100 p-2">
                        <GraduationCap className="h-4 w-4 text-slate-600" />
                      </div>
                      <div>
                        <p className="font-medium">{account.account_name}</p>
                        <p className="text-sm text-slate-500">{account.beneficiary_name}</p>
                      </div>
                    </div>
                    <p className="font-semibold">{formatCurrency(account.balance)}</p>
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Quick Actions</CardTitle>
          <CardDescription>Common tasks and shortcuts</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 md:grid-cols-2">
            <Link to="/bank-accounts">
              <Button variant="outline" className="w-full justify-start">
                <Landmark className="h-4 w-4 mr-3" />
                Add Bank Account
              </Button>
            </Link>
            <Link to="/retirement">
              <Button variant="outline" className="w-full justify-start">
                <PiggyBank className="h-4 w-4 mr-3" />
                Add Retirement Account
              </Button>
            </Link>
            <Link to="/education">
              <Button variant="outline" className="w-full justify-start">
                <GraduationCap className="h-4 w-4 mr-3" />
                Add Education Account
              </Button>
            </Link>
            <Link to="/receipts">
              <Button variant="outline" className="w-full justify-start">
                <ScanLine className="h-4 w-4 mr-3" />
                Upload Receipt
              </Button>
            </Link>
            <Link to="/stocks">
              <Button variant="outline" className="w-full justify-start">
                <TrendingUp className="h-4 w-4 mr-3" />
                Buy Stock
              </Button>
            </Link>
            <Link to="/investments">
              <Button variant="outline" className="w-full justify-start">
                <TrendingUp className="h-4 w-4 mr-3" />
                Buy Bond or Property
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
