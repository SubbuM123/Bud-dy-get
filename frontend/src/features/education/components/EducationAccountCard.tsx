/**
 * Summary card for a single education savings account, shown in the horizontal strip on
 * EducationAccountsPage. Displays balance, beneficiary name and derived age, plan
 * provider, and an informational YTD-contributions-vs-gift-tax-exclusion indicator - not a
 * hard-limit progress bar like RetirementAccountCard's, since exceeding the exclusion
 * never blocks anything. Links through to EducationAccountDetailPage for the full growth
 * simulation and gift-tax guidance.
 */
import { Link } from 'react-router-dom'
import { differenceInYears } from 'date-fns'
import { GraduationCap, TrendingUp, Trash2, Pencil } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { InfoTooltip } from '@/components/ui/info-tooltip'
import { formatCurrency } from '@/lib/utils'
import { useGiftTaxInfo } from '../hooks/useEducationAccounts'
import { EDUCATION_GLOSSARY } from '../glossary'
import type { EducationAccount } from '@/types'

interface EducationAccountCardProps {
  account: EducationAccount
  onDelete?: (id: string) => void
  onEdit?: (account: EducationAccount) => void
}

// Human-readable labels for the account_type enum values.
const accountTypeLabels: Record<EducationAccount['account_type'], string> = {
  '529_plan': '529 Plan',
  coverdell_esa: 'Coverdell ESA',
  custodial_utma_ugma: 'Custodial (UTMA/UGMA)',
}

export default function EducationAccountCard({
  account,
  onDelete,
  onEdit,
}: EducationAccountCardProps) {
  const { data: giftTaxInfo } = useGiftTaxInfo(account.beneficiary_name)
  const beneficiaryAge = account.beneficiary_birth_date
    ? differenceInYears(new Date(), new Date(account.beneficiary_birth_date))
    : null

  const ytd = giftTaxInfo ? parseFloat(giftTaxInfo.beneficiary_contribution_ytd) : null
  const exclusion = giftTaxInfo ? parseFloat(giftTaxInfo.annual_exclusion) : null
  const exclusionProgress = ytd !== null && exclusion ? Math.min((ytd / exclusion) * 100, 100) : 0

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardHeader className="flex flex-row items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-full bg-purple-100 p-2">
            <GraduationCap className="h-5 w-5 text-purple-600" />
          </div>
          <div>
            <CardTitle className="text-base">{account.account_name}</CardTitle>
            <div className="flex items-center gap-1">
              <p className="text-sm text-slate-500">{accountTypeLabels[account.account_type]}</p>
              <InfoTooltip {...EDUCATION_GLOSSARY[account.account_type]} />
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

          <div className="text-sm">
            <p className="flex items-center gap-1 text-slate-500">
              Beneficiary
              <InfoTooltip {...EDUCATION_GLOSSARY.beneficiary} />
            </p>
            <p className="font-medium">
              {account.beneficiary_name}
              {beneficiaryAge !== null && (
                <span className="text-slate-500 font-normal"> (age {beneficiaryAge})</span>
              )}
            </p>
            {account.plan_provider && (
              <p className="flex items-center gap-1 text-slate-500">
                {account.plan_provider}
                <InfoTooltip {...EDUCATION_GLOSSARY.plan_provider} />
              </p>
            )}
          </div>

          {ytd !== null && exclusion !== null && (
            <div>
              <div className="flex items-center justify-between text-xs text-slate-500">
                <span className="flex items-center gap-1">
                  YTD Contributions
                  <InfoTooltip {...EDUCATION_GLOSSARY.ytd_contributions} />
                </span>
                <span>
                  {formatCurrency(ytd)} / {formatCurrency(exclusion)}
                </span>
              </div>
              <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-slate-100">
                <div
                  className="h-full rounded-full bg-primary-600"
                  style={{ width: `${exclusionProgress}%` }}
                />
              </div>
              {giftTaxInfo?.would_exceed_exclusion && (
                <p className="mt-1 flex items-center gap-1 text-xs text-amber-600">
                  Over this year's gift-tax exclusion
                  <InfoTooltip {...EDUCATION_GLOSSARY.gift_tax_exclusion} />
                </p>
              )}
            </div>
          )}

          <div className="flex items-center justify-between pt-3 border-t">
            <Link to={`/education/${account.id}`}>
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
