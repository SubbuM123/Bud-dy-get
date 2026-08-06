/**
 * Summary card for a single retirement account, shown in the grid on
 * RetirementAccountsPage. Displays balance, account type, a YTD-contributions-vs-limit
 * progress bar, employer match info (401(k)/Roth 401(k) only), and a vesting progress bar
 * when a vesting schedule is configured. Links through to RetirementAccountDetailPage for
 * the full growth simulation and contribution history.
 */
import { Link } from 'react-router-dom'
import { PiggyBank, TrendingUp, Trash2, Pencil } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { InfoTooltip } from '@/components/ui/info-tooltip'
import { formatCurrency, formatPercent } from '@/lib/utils'
import { useContributionLimits } from '../hooks/useRetirementAccounts'
import { RETIREMENT_GLOSSARY } from '../glossary'
import type { RetirementAccount } from '@/types'

interface RetirementAccountCardProps {
  account: RetirementAccount
  onDelete?: (id: string) => void
  onEdit?: (account: RetirementAccount) => void
}

// Human-readable labels for the account_type enum values.
const accountTypeLabels: Record<RetirementAccount['account_type'], string> = {
  traditional_401k: 'Traditional 401(k)',
  roth_401k: 'Roth 401(k)',
  traditional_ira: 'Traditional IRA',
  roth_ira: 'Roth IRA',
  sep_ira: 'SEP IRA',
  simple_ira: 'SIMPLE IRA',
  hsa: 'HSA',
}

const FOUR_OH_ONE_K_TYPES: RetirementAccount['account_type'][] = ['traditional_401k', 'roth_401k']

export default function RetirementAccountCard({
  account,
  onDelete,
  onEdit,
}: RetirementAccountCardProps) {
  const { data: limits } = useContributionLimits(account.account_type)
  const isEmployerSponsored = FOUR_OH_ONE_K_TYPES.includes(account.account_type)
  const ytd = parseFloat(account.contribution_ytd)
  const employeeLimit = limits ? parseFloat(limits.employee_limit) : null
  const contributionProgress =
    employeeLimit && employeeLimit > 0 ? Math.min((ytd / employeeLimit) * 100, 100) : 0
  const vestedPercent = parseFloat(account.vested_percent)

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardHeader className="flex flex-row items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-full bg-purple-100 p-2">
            <PiggyBank className="h-5 w-5 text-purple-600" />
          </div>
          <div>
            <CardTitle className="text-base">{account.account_name}</CardTitle>
            <div className="flex items-center gap-1">
              <p className="text-sm text-slate-500">{accountTypeLabels[account.account_type]}</p>
              <InfoTooltip {...RETIREMENT_GLOSSARY[account.account_type]} />
            </div>
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
            <p className="text-2xl font-bold text-slate-900">{formatCurrency(account.balance)}</p>
          </div>

          {isEmployerSponsored && account.employer_name && (
            <div className="text-sm">
              <p className="text-slate-500">Employer</p>
              <p className="font-medium">{account.employer_name}</p>
              {account.employer_match_percent && account.employer_match_limit_percent && (
                <p className="flex items-center gap-1 text-success-600">
                  {formatPercent(account.employer_match_percent)} match up to{' '}
                  {formatPercent(account.employer_match_limit_percent)} of salary
                  <InfoTooltip {...RETIREMENT_GLOSSARY.employer_match} />
                </p>
              )}
            </div>
          )}

          {employeeLimit !== null && (
            <div>
              <div className="flex items-center justify-between text-xs text-slate-500">
                <span className="flex items-center gap-1">
                  YTD Contributions
                  <InfoTooltip {...RETIREMENT_GLOSSARY.ytd_contributions} />
                </span>
                <span>
                  {formatCurrency(ytd)} / {formatCurrency(employeeLimit)}
                </span>
              </div>
              <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-slate-100">
                <div
                  className="h-full rounded-full bg-primary-600"
                  style={{ width: `${contributionProgress}%` }}
                />
              </div>
            </div>
          )}

          {account.vesting_type && (
            <div>
              <div className="flex items-center justify-between text-xs text-slate-500">
                <span className="flex items-center gap-1">
                  Vested
                  <InfoTooltip {...RETIREMENT_GLOSSARY.vesting} />
                </span>
                <span>{vestedPercent.toFixed(0)}%</span>
              </div>
              <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-slate-100">
                <div
                  className="h-full rounded-full bg-success-500"
                  style={{ width: `${vestedPercent}%` }}
                />
              </div>
            </div>
          )}

          <div className="flex items-center justify-between pt-3 border-t">
            <Link to={`/retirement/${account.id}`}>
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
