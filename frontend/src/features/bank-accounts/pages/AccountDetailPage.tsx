/**
 * Detail view for a single bank account, mounted at /bank-accounts/:accountId. This is
 * where the actual "simulate growth" feature lives: the user picks a number of months and
 * toggles recurring actions on/off, and the page renders GrowthChart plus running totals.
 * It also manages the account's recurring deposit/withdrawal rules and the account's own
 * editable fields (name, principal, rate, compounding, CD maturity/auto-renew) inline.
 */
import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Plus, Trash2, Pencil } from 'lucide-react'
import { addMonths, format } from 'date-fns'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card'
import GrowthChart from '@/components/charts/GrowthChart'
import RecurringActionForm from '../components/RecurringActionForm'
import AccountForm from '../components/AccountForm'
import {
  formatCurrency,
  formatPercent,
  compoundingPeriodsElapsed,
  compoundingPeriodLabel,
} from '@/lib/utils'
import {
  useBankAccount,
  useSimulation,
  useUpdateBankAccount,
  useRecurringActions,
  useCreateRecurringAction,
  useUpdateRecurringAction,
  useDeleteRecurringAction,
} from '../hooks/useBankAccounts'

export default function AccountDetailPage() {
  const { accountId } = useParams<{ accountId: string }>()
  const [months, setMonths] = useState(12)
  const [includeRecurring, setIncludeRecurring] = useState(true)
  const [showActionForm, setShowActionForm] = useState(false)
  const [editingActionId, setEditingActionId] = useState<string | null>(null)
  const [showAccountEditForm, setShowAccountEditForm] = useState(false)

  const { data: account, isLoading: accountLoading } = useBankAccount(accountId!)
  const updateAccount = useUpdateBankAccount()
  const { data: simulation, isLoading: simLoading } = useSimulation(
    accountId!,
    months,
    includeRecurring
  )
  const { data: recurringActions } = useRecurringActions(accountId!)
  const createAction = useCreateRecurringAction()
  const updateAction = useUpdateRecurringAction()
  const deleteAction = useDeleteRecurringAction()

  // Submit the recurring-action form, then collapse it back down on success.
  const handleCreateAction = async (data: Parameters<typeof createAction.mutate>[0]['data']) => {
    await createAction.mutateAsync({ accountId: accountId!, data })
    setShowActionForm(false)
  }

  // Submit an in-place edit of an existing recurring action - only the fields
  // RecurringActionUpdate actually accepts are forwarded (action_type/start_date are
  // immutable and dropped even though the form still emits them for create's sake).
  const handleUpdateAction = async (
    actionId: string,
    data: Parameters<typeof createAction.mutate>[0]['data']
  ) => {
    await updateAction.mutateAsync({
      actionId,
      data: {
        amount: data.amount,
        description: data.description,
        category: data.category,
        frequency_value: data.frequency_value,
        frequency_unit: data.frequency_unit,
        end_date: data.end_date ?? null,
      },
    })
    setEditingActionId(null)
  }

  // account_type is intentionally not forwarded - BankAccountUpdate doesn't accept it
  // (locked after creation), even though the shared AccountForm still emits it.
  const handleUpdateAccount = async (data: {
    account_name: string
    principal: number
    interest_rate?: number
    compounding_frequency: string
    cd_start_date?: string
    cd_term_months?: number
    cd_auto_renew?: boolean
  }) => {
    await updateAccount.mutateAsync({
      id: accountId!,
      data: {
        account_name: data.account_name,
        principal: data.principal,
        interest_rate: data.interest_rate,
        compounding_frequency: data.compounding_frequency,
        cd_start_date: data.cd_start_date,
        cd_term_months: data.cd_term_months,
        cd_auto_renew: data.cd_auto_renew,
      },
    })
    setShowAccountEditForm(false)
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
        <Link to="/bank-accounts" className="text-primary-600 hover:underline">
          Back to accounts
        </Link>
      </div>
    )
  }

  const avgInterestPerPeriod = simulation
    ? (() => {
        const periods = compoundingPeriodsElapsed(account.compounding_frequency, months)
        return periods > 0 ? parseFloat(simulation.total_interest) / periods : 0
      })()
    : null

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link to="/bank-accounts">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-5 w-5" />
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">{account.account_name}</h1>
            <p className="text-slate-500 capitalize">{account.account_type} Account</p>
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
            <AccountForm
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
            <p className="text-2xl font-bold">{formatCurrency(account.current_balance)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-slate-500">Principal</p>
            <p className="text-2xl font-bold">{formatCurrency(account.principal)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-slate-500">Interest Rate</p>
            <p className="text-2xl font-bold text-success-600">
              {account.interest_rate ? formatPercent(account.interest_rate) : 'N/A'}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-slate-500">Compounding</p>
            <p className="text-2xl font-bold capitalize">{account.compounding_frequency}</p>
          </CardContent>
        </Card>
      </div>

      {account.account_type === 'cd' && account.cd_start_date && account.cd_term_months && (
        <Card>
          <CardContent className="pt-6 flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-500">Term</p>
              <p className="text-lg font-semibold">
                {account.cd_term_months} months, starting {account.cd_start_date}
              </p>
            </div>
            <div>
              <p className="text-sm text-slate-500">Maturity Date</p>
              <p className="text-lg font-semibold">
                {format(
                  addMonths(new Date(`${account.cd_start_date}T00:00:00`), account.cd_term_months),
                  'MMM d, yyyy'
                )}
              </p>
            </div>
            <div className="text-right">
              <p className="text-sm text-slate-500">At Maturity</p>
              <p className="text-lg font-semibold">
                {account.cd_auto_renew
                  ? 'Rolls into a new CD term'
                  : 'Deposits into a savings account'}
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Growth Simulation</CardTitle>
              <CardDescription>
                Project your account balance over time
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
        </CardHeader>
        <CardContent>
          {simLoading ? (
            <div className="flex items-center justify-center h-96">
              <p className="text-slate-500">Calculating projection...</p>
            </div>
          ) : simulation ? (
            <>
              <GrowthChart data={simulation.projections} />

              <div className="grid grid-cols-2 gap-4 mt-6 pt-6 border-t md:grid-cols-5">
                <div>
                  <p className="text-sm text-slate-500">Final Balance</p>
                  <p className="text-xl font-bold">
                    {formatCurrency(simulation.final_balance)}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-slate-500">Total Interest</p>
                  <p className="text-xl font-bold text-success-600">
                    +{formatCurrency(simulation.total_interest)}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-slate-500">Total Deposits</p>
                  <p className="text-xl font-bold text-primary-600">
                    +{formatCurrency(simulation.total_deposits)}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-slate-500">Total Withdrawals</p>
                  <p className="text-xl font-bold text-danger-500">
                    -{formatCurrency(simulation.total_withdrawals)}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-slate-500">
                    Avg. Interest / {compoundingPeriodLabel(account.compounding_frequency)}
                  </p>
                  <p className="text-xl font-bold text-success-600">
                    {avgInterestPerPeriod !== null ? formatCurrency(avgInterestPerPeriod) : '--'}
                  </p>
                </div>
              </div>
            </>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Recurring Actions</CardTitle>
              <CardDescription>
                Scheduled deposits and withdrawals
              </CardDescription>
            </div>
            <Button onClick={() => setShowActionForm(true)} size="sm">
              <Plus className="h-4 w-4 mr-2" />
              Add Action
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {showActionForm && (
            <div className="mb-6 pb-6 border-b">
              <RecurringActionForm
                onSubmit={handleCreateAction}
                isLoading={createAction.isPending}
                onCancel={() => setShowActionForm(false)}
              />
            </div>
          )}

          {recurringActions?.length === 0 ? (
            <p className="text-slate-500 text-center py-6">
              No recurring actions set up yet
            </p>
          ) : (
            <div className="space-y-3">
              {recurringActions?.map((action) =>
                editingActionId === action.id ? (
                  <div key={action.id} className="p-4 rounded-lg bg-slate-50">
                    <RecurringActionForm
                      action={action}
                      onSubmit={(data) => handleUpdateAction(action.id, data)}
                      isLoading={updateAction.isPending}
                      onCancel={() => setEditingActionId(null)}
                    />
                  </div>
                ) : (
                  <div
                    key={action.id}
                    className="flex items-center justify-between p-4 rounded-lg bg-slate-50"
                  >
                    <div>
                      <p className="font-medium">
                        {action.action_type === 'deposit' ? '+' : '-'}
                        {formatCurrency(action.amount)}
                      </p>
                      <p className="text-sm text-slate-500">
                        {action.description || `${action.action_type}`} - Every{' '}
                        {action.frequency_value} {action.frequency_unit}
                        {action.category && ` - ${action.category}`}
                      </p>
                      <p className="text-xs text-slate-400">
                        {action.end_date ? `Ends ${action.end_date}` : 'Never ends'}
                      </p>
                    </div>
                    <div className="flex items-center gap-4">
                      <span
                        className={`px-2 py-1 rounded text-xs font-medium ${
                          action.action_type === 'deposit'
                            ? 'bg-success-500/10 text-success-600'
                            : 'bg-danger-500/10 text-danger-500'
                        }`}
                      >
                        {action.action_type}
                      </span>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="text-slate-400 hover:text-primary-600"
                        onClick={() => setEditingActionId(action.id)}
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="text-slate-400 hover:text-danger-500"
                        onClick={() => deleteAction.mutate(action.id)}
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
    </div>
  )
}
