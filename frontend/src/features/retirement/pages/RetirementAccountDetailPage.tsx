/**
 * Detail view for a single retirement account, mounted at /retirement/:accountId. Lets the
 * user pick a hypothetical monthly employee contribution and simulate growth (employer
 * match applied automatically for 401(k)/Roth 401(k) accounts with match fields set),
 * record a real contribution against their 2026 IRS limit, and edit the account's own
 * fields inline - the same three-part structure as bank-accounts' AccountDetailPage.
 */
import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Pencil, PlusCircle, Plus, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card'
import { InfoTooltip } from '@/components/ui/info-tooltip'
import RetirementGrowthChart from '@/components/charts/RetirementGrowthChart'
import RetirementAccountForm from '../components/RetirementAccountForm'
import ContributionForm from '../components/ContributionForm'
import RecurringContributionForm from '../components/RecurringContributionForm'
import { formatCurrency, formatPercent, getApiErrorMessage } from '@/lib/utils'
import {
  useRetirementAccount,
  useRetirementSimulation,
  useUpdateRetirementAccount,
  useRecordContribution,
  useRecurringContributions,
  useCreateRecurringContribution,
  useUpdateRecurringContribution,
  useDeleteRecurringContribution,
} from '../hooks/useRetirementAccounts'
import { RETIREMENT_GLOSSARY } from '../glossary'
import type { VestingType } from '@/types'

const ACCOUNT_TYPE_LABELS: Record<string, string> = {
  traditional_401k: 'Traditional 401(k)',
  roth_401k: 'Roth 401(k)',
  traditional_ira: 'Traditional IRA',
  roth_ira: 'Roth IRA',
  sep_ira: 'SEP IRA',
  simple_ira: 'SIMPLE IRA',
  hsa: 'HSA',
}

export default function RetirementAccountDetailPage() {
  const { accountId } = useParams<{ accountId: string }>()
  const [months, setMonths] = useState(120)
  const [monthlyContribution, setMonthlyContribution] = useState(0)
  const [showAccountEditForm, setShowAccountEditForm] = useState(false)
  const [showContributeForm, setShowContributeForm] = useState(false)
  const [includeRecurring, setIncludeRecurring] = useState(true)
  const [showRecurringForm, setShowRecurringForm] = useState(false)
  const [editingRecurringId, setEditingRecurringId] = useState<string | null>(null)

  const { data: account, isLoading: accountLoading } = useRetirementAccount(accountId!)
  const updateAccount = useUpdateRetirementAccount()
  const { data: simulation, isLoading: simLoading } = useRetirementSimulation(
    accountId!,
    months,
    monthlyContribution,
    includeRecurring
  )
  const recordContribution = useRecordContribution()
  const { data: recurringContributions } = useRecurringContributions(accountId!)
  const createRecurring = useCreateRecurringContribution()
  const updateRecurring = useUpdateRecurringContribution()
  const deleteRecurring = useDeleteRecurringContribution()

  const handleUpdateAccount = async (data: {
    account_name: string
    balance: number
    expected_return_rate: number
    employer_name?: string
    annual_salary?: number
    employer_match_percent?: number
    employer_match_limit_percent?: number
    vesting_type?: VestingType
    vesting_years?: number
  }) => {
    await updateAccount.mutateAsync({
      id: accountId!,
      data: {
        account_name: data.account_name,
        balance: data.balance,
        expected_return_rate: data.expected_return_rate,
        employer_name: data.employer_name,
        annual_salary: data.annual_salary,
        employer_match_percent: data.employer_match_percent,
        employer_match_limit_percent: data.employer_match_limit_percent,
        vesting_type: data.vesting_type,
        vesting_years: data.vesting_years,
      },
    })
    setShowAccountEditForm(false)
  }

  const handleContribute = async (data: {
    amount: number
    source_type: 'track_only' | 'bank_account' | 'pre_tax_salary'
    source_bank_account_id?: string
  }) => {
    try {
      await recordContribution.mutateAsync({
        accountId: accountId!,
        amount: data.amount,
        sourceType: data.source_type,
        sourceBankAccountId: data.source_bank_account_id,
      })
      setShowContributeForm(false)
    } catch {
      // handled via recordContribution.error
    }
  }

  // Submit the recurring-contribution form, then collapse it back down on success.
  const handleCreateRecurring = async (
    data: Parameters<typeof createRecurring.mutate>[0]['data']
  ) => {
    await createRecurring.mutateAsync({ accountId: accountId!, data })
    setShowRecurringForm(false)
  }

  // Submit an in-place edit - only the fields RecurringContributionUpdate actually
  // accepts are forwarded (frequency/start_date are immutable and dropped even though the
  // form still emits them for create's sake).
  const handleUpdateRecurring = async (
    contributionId: string,
    data: Parameters<typeof createRecurring.mutate>[0]['data']
  ) => {
    await updateRecurring.mutateAsync({
      contributionId,
      data: { amount: data.amount, end_date: data.end_date ?? null },
    })
    setEditingRecurringId(null)
  }

  if (accountLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-slate-500">Loading account...</p>
      </div>
    )
  }

  if (!account) {
    return (
      <div className="text-center py-12">
        <p className="text-slate-500">Account not found</p>
        <Link to="/retirement" className="text-primary-600 hover:underline">
          Back to accounts
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link to="/retirement">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-5 w-5" />
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">{account.account_name}</h1>
            <div className="flex items-center gap-1">
              <p className="text-slate-500">{ACCOUNT_TYPE_LABELS[account.account_type]}</p>
              <InfoTooltip {...RETIREMENT_GLOSSARY[account.account_type]} />
            </div>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={() => setShowAccountEditForm((v) => !v)}>
          <Pencil className="h-4 w-4 mr-2" />
          Edit Account
        </Button>
      </div>

      {showAccountEditForm && (
        <Card>
          <CardHeader>
            <CardTitle>Edit Account</CardTitle>
          </CardHeader>
          <CardContent>
            <RetirementAccountForm
              account={account}
              onSubmit={handleUpdateAccount}
              isLoading={updateAccount.isPending}
              onCancel={() => setShowAccountEditForm(false)}
            />
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 md:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-slate-500">Current Balance</p>
            <p className="text-2xl font-bold">{formatCurrency(account.balance)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="flex items-center gap-1 text-sm text-slate-500">
              YTD Contributions
              <InfoTooltip {...RETIREMENT_GLOSSARY.ytd_contributions} />
            </p>
            <p className="text-2xl font-bold">{formatCurrency(account.contribution_ytd)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="flex items-center gap-1 text-sm text-slate-500">
              Expected Return
              <InfoTooltip {...RETIREMENT_GLOSSARY.expected_return} />
            </p>
            <p className="text-2xl font-bold text-success-600">
              {formatPercent(account.expected_return_rate)}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="flex items-center gap-1 text-sm text-slate-500">
              Vested
              <InfoTooltip {...RETIREMENT_GLOSSARY.vesting} />
            </p>
            <p className="text-2xl font-bold">
              {account.vesting_type ? `${parseFloat(account.vested_percent).toFixed(0)}%` : 'N/A'}
            </p>
          </CardContent>
        </Card>
      </div>

      {account.employer_name && (
        <Card>
          <CardContent className="pt-6 flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-500">Employer</p>
              <p className="text-lg font-semibold">{account.employer_name}</p>
            </div>
            {account.employer_match_percent && account.employer_match_limit_percent && (
              <div className="text-right">
                <p className="text-sm text-slate-500">Match</p>
                <p className="text-lg font-semibold">
                  {formatPercent(account.employer_match_percent)} up to{' '}
                  {formatPercent(account.employer_match_limit_percent)} of salary
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Record a Contribution</CardTitle>
              <CardDescription>
                Add to this account's YTD contributions, validated against your 2026 limit
              </CardDescription>
            </div>
            {!showContributeForm && (
              <Button onClick={() => setShowContributeForm(true)} size="sm">
                <PlusCircle className="h-4 w-4 mr-2" />
                Contribute
              </Button>
            )}
          </div>
        </CardHeader>
        {showContributeForm && (
          <CardContent>
            {recordContribution.isError && (
              <div className="mb-4 rounded-md bg-danger-500/10 p-3 text-sm text-danger-500">
                {getApiErrorMessage(recordContribution.error, 'Failed to record contribution')}
              </div>
            )}
            <ContributionForm
              accountType={account.account_type}
              onSubmit={handleContribute}
              isLoading={recordContribution.isPending}
              onCancel={() => setShowContributeForm(false)}
            />
          </CardContent>
        )}
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Recurring Contributions</CardTitle>
              <CardDescription>
                Monthly or yearly amounts (e.g. payroll deductions) automatically included
                in the growth simulation below
              </CardDescription>
            </div>
            <Button onClick={() => setShowRecurringForm(true)} size="sm">
              <Plus className="h-4 w-4 mr-2" />
              Add Recurring Contribution
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {showRecurringForm && (
            <div className="mb-6 pb-6 border-b">
              <RecurringContributionForm
                onSubmit={handleCreateRecurring}
                isLoading={createRecurring.isPending}
                onCancel={() => setShowRecurringForm(false)}
              />
            </div>
          )}

          {recurringContributions?.length === 0 ? (
            <p className="text-slate-500 text-center py-6">
              No recurring contributions set up yet
            </p>
          ) : (
            <div className="space-y-3">
              {recurringContributions?.map((contribution) =>
                editingRecurringId === contribution.id ? (
                  <div key={contribution.id} className="p-4 rounded-lg bg-slate-50">
                    <RecurringContributionForm
                      contribution={contribution}
                      onSubmit={(data) => handleUpdateRecurring(contribution.id, data)}
                      isLoading={updateRecurring.isPending}
                      onCancel={() => setEditingRecurringId(null)}
                    />
                  </div>
                ) : (
                  <div
                    key={contribution.id}
                    className="flex items-center justify-between p-4 rounded-lg bg-slate-50"
                  >
                    <div>
                      <p className="font-medium">
                        +{formatCurrency(contribution.amount)}
                        <span className="text-sm text-slate-500 font-normal">
                          {' '}
                          / {contribution.frequency === 'monthly' ? 'month' : 'year'}
                        </span>
                      </p>
                      <p className="text-xs text-slate-400">
                        {contribution.end_date
                          ? `Ends ${contribution.end_date}`
                          : 'Never ends'}
                        {!contribution.is_active && ' - Inactive'}
                      </p>
                    </div>
                    <div className="flex items-center gap-4">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="text-slate-400 hover:text-primary-600"
                        onClick={() => setEditingRecurringId(contribution.id)}
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="text-slate-400 hover:text-danger-500"
                        onClick={() => deleteRecurring.mutate(contribution.id)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                )
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Growth Simulation</CardTitle>
              <CardDescription>Project your account balance over time</CardDescription>
            </div>
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={includeRecurring}
                  onChange={(e) => setIncludeRecurring(e.target.checked)}
                  className="rounded border-slate-300"
                />
                <span className="text-sm">Include recurring contributions</span>
              </label>
              <div className="flex items-center gap-2">
                <Input
                  type="number"
                  min={0}
                  value={monthlyContribution}
                  onChange={(e) => setMonthlyContribution(parseFloat(e.target.value) || 0)}
                  className="w-24"
                />
                <span className="text-sm text-slate-500">extra $/month</span>
              </div>
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
        </CardHeader>
        <CardContent>
          {simLoading ? (
            <div className="flex items-center justify-center h-96">
              <p className="text-slate-500">Calculating projection...</p>
            </div>
          ) : simulation ? (
            <>
              <RetirementGrowthChart data={simulation.projections} />

              <div className="grid grid-cols-2 gap-4 mt-6 pt-6 border-t md:grid-cols-4">
                <div>
                  <p className="text-sm text-slate-500">Final Balance</p>
                  <p className="text-xl font-bold">{formatCurrency(simulation.final_balance)}</p>
                </div>
                <div>
                  <p className="text-sm text-slate-500">Employee Contributions</p>
                  <p className="text-xl font-bold text-primary-600">
                    +{formatCurrency(simulation.total_employee_contributions)}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-slate-500">Employer Contributions</p>
                  <p className="text-xl font-bold text-primary-600">
                    +{formatCurrency(simulation.total_employer_contributions)}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-slate-500">Investment Growth</p>
                  <p className="text-xl font-bold text-success-600">
                    +{formatCurrency(simulation.total_growth)}
                  </p>
                </div>
              </div>
            </>
          ) : null}
        </CardContent>
      </Card>
    </div>
  )
}
