/**
 * Summary card for a single bank account, shown in the grid on BankAccountsPage. Displays
 * balance, principal, and interest rate at a glance, and links through to
 * AccountDetailPage for the full growth simulation and recurring-action management.
 */
import { Link } from 'react-router-dom'
import { Landmark, TrendingUp, Trash2, Pencil } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { formatCurrency, formatPercent } from '@/lib/utils'
import type { BankAccount } from '@/types'

interface AccountCardProps {
  account: BankAccount
  onDelete?: (id: string) => void
  onEdit?: (account: BankAccount) => void
}

// Human-readable labels for the account_type enum values.
const accountTypeLabels = {
  savings: 'Savings',
  checking: 'Checking',
  cd: 'Certificate of Deposit',
}

export default function AccountCard({ account, onDelete, onEdit }: AccountCardProps) {
  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardHeader className="flex flex-row items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-full bg-primary-100 p-2">
            <Landmark className="h-5 w-5 text-primary-600" />
          </div>
          <div>
            <CardTitle className="text-base">{account.account_name}</CardTitle>
            <p className="text-sm text-slate-500">
              {accountTypeLabels[account.account_type]}
            </p>
          </div>
        </div>

        {account.is_simulation && (
          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
            Simulation
          </span>
        )}
      </CardHeader>

      <CardContent>
        <div className="space-y-3">
          <div>
            <p className="text-sm text-slate-500">Current Balance</p>
            <p className="text-2xl font-bold text-slate-900">
              {formatCurrency(account.current_balance)}
            </p>
          </div>

          <div className="flex gap-6 text-sm">
            <div>
              <p className="text-slate-500">Principal</p>
              <p className="font-medium">{formatCurrency(account.principal)}</p>
            </div>
            {account.interest_rate && (
              <div>
                <p className="text-slate-500">Interest Rate</p>
                <p className="font-medium text-success-600">
                  {formatPercent(account.interest_rate)}
                </p>
              </div>
            )}
          </div>

          <div className="flex items-center justify-between pt-3 border-t">
            <Link to={`/bank-accounts/${account.id}`}>
              <Button variant="outline" size="sm">
                <TrendingUp className="h-4 w-4 mr-2" />
                View & Simulate
              </Button>
            </Link>

            <div className="flex items-center">
              {onEdit && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="text-slate-400 hover:text-primary-600"
                  onClick={() => onEdit(account)}
                >
                  <Pencil className="h-4 w-4" />
                </Button>
              )}
              {onDelete && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="text-slate-400 hover:text-danger-500"
                  onClick={() => onDelete(account.id)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              )}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
