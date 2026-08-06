/**
 * Unified transaction history at /transactions: every real (posted, not simulated) money
 * movement this app has recorded - income occurrences, retirement/education
 * contributions, investment buys/sells/RSU-vests, AND expenses (merged in read-only from
 * GET /expenses, not written into the `transactions` table - see this file's history and
 * backend/app/models/transactions.py's docstring on why Expense keeps its own single
 * source of truth rather than a redundant second ledger). `Transaction` rows get full
 * edit/delete here; expense rows link back to the Expenses page instead, since that's
 * where they're actually editable (mirrors how stock/bond/property transactions already
 * can't be edited from this page either - see api/v1/transactions.py's docstring).
 */
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Pencil, Trash2, ArrowUpRight, RefreshCw } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { cn, formatCurrency, formatDate, getApiErrorMessage } from '@/lib/utils'
import TransactionEditModal from '../components/TransactionEditModal'
import { useTransactions, useDeleteTransaction } from '../hooks/useTransactions'
import { useBankAccounts } from '@/features/bank-accounts/hooks/useBankAccounts'
import { useRetirementAccounts } from '@/features/retirement/hooks/useRetirementAccounts'
import { useEducationAccounts } from '@/features/education/hooks/useEducationAccounts'
import { useStockPositions } from '@/features/investments/hooks/useInvestments'
import { useExpenseList, useExpenseCategories } from '@/features/expenses/hooks/useExpenses'
import { useRunScheduler } from '@/features/scheduler/hooks/useScheduler'
import type { Transaction, TransactionType, SchedulerRunResult } from '@/types'

type LogFilter = TransactionType | 'expense' | 'all'

const TYPE_TABS: { value: LogFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'income', label: 'Income' },
  { value: 'retirement_contribution', label: 'Retirement' },
  { value: 'education_contribution', label: 'Education' },
  { value: 'stock_purchase', label: 'Stock Buys' },
  { value: 'stock_sale', label: 'Stock/Bond/Property Sales' },
  { value: 'rsu_vest', label: 'RSU Vests' },
  { value: 'interest', label: 'Interest' },
  { value: 'expense', label: 'Expenses' },
]

const TYPE_LABELS: Record<TransactionType, string> = {
  income: 'Income',
  retirement_contribution: 'Retirement Contribution',
  education_contribution: 'Education Contribution',
  stock_purchase: 'Investment Purchase',
  stock_sale: 'Investment Sale',
  rsu_vest: 'RSU Vest',
  interest: 'Interest',
}

const TYPE_BADGE_CLASSES: Record<TransactionType, string> = {
  income: 'bg-success-500/10 text-success-600',
  retirement_contribution: 'bg-primary-500/10 text-primary-600',
  education_contribution: 'bg-amber-100 text-amber-700',
  stock_purchase: 'bg-sky-100 text-sky-700',
  stock_sale: 'bg-slate-200 text-slate-700',
  rsu_vest: 'bg-violet-100 text-violet-700',
  interest: 'bg-emerald-100 text-emerald-700',
}

const EXPENSE_BADGE_CLASS = 'bg-rose-100 text-rose-700'

// Human-readable pieces of a SchedulerRunResult, in display order - only the non-zero
// ones are shown, so "nothing was due" reads as "Nothing to sync" rather than a wall of
// zeroes.
type SchedulerCountKey = Exclude<keyof SchedulerRunResult, 'as_of'>

const SCHEDULER_RESULT_LABELS: { key: SchedulerCountKey; label: (n: number) => string }[] = [
  { key: 'incomes_posted', label: (n) => `${n} income occurrence${n === 1 ? '' : 's'}` },
  { key: 'bank_interest_applied', label: (n) => `${n} bank interest credit${n === 1 ? '' : 's'}` },
  {
    key: 'retirement_interest_applied',
    label: (n) => `${n} retirement growth credit${n === 1 ? '' : 's'}`,
  },
  {
    key: 'education_interest_applied',
    label: (n) => `${n} education growth credit${n === 1 ? '' : 's'}`,
  },
  {
    key: 'retirement_contributions_posted',
    label: (n) => `${n} retirement contribution${n === 1 ? '' : 's'}`,
  },
  {
    key: 'education_contributions_posted',
    label: (n) => `${n} education contribution${n === 1 ? '' : 's'}`,
  },
  { key: 'expenses_created', label: (n) => `${n} recurring expense${n === 1 ? '' : 's'}` },
]

function summarizeSchedulerResult(result: SchedulerRunResult): string {
  const parts = SCHEDULER_RESULT_LABELS.filter(({ key }) => result[key] > 0).map(({ key, label }) =>
    label(result[key])
  )
  return parts.length === 0 ? 'Nothing was due - you\'re all caught up.' : `Synced: ${parts.join(', ')}.`
}

// One row of the merged log - a real Transaction or an Expense normalized to the same
// shape for display. `editable` gates whether the Pencil/Trash actions render at all.
interface LogRow {
  id: string
  date: string
  createdAt: string
  badgeLabel: string
  badgeClass: string
  accountLabel: string
  description: string
  amount: string
  editable: boolean
  transaction?: Transaction
}

export default function TransactionsPage() {
  const [activeTab, setActiveTab] = useState<LogFilter>('all')
  const [editingTransaction, setEditingTransaction] = useState<Transaction | null>(null)

  const { data: transactions, isLoading: transactionsLoading } = useTransactions()
  const { data: expenses, isLoading: expensesLoading } = useExpenseList()
  const { data: bankAccounts } = useBankAccounts()
  const { data: retirementAccounts } = useRetirementAccounts()
  const { data: educationAccounts } = useEducationAccounts()
  const { data: stockPositions } = useStockPositions()
  const { data: categories } = useExpenseCategories()
  const deleteTransaction = useDeleteTransaction()
  const runScheduler = useRunScheduler()

  const isLoading = transactionsLoading || expensesLoading

  const accountNames = new Map<string, string>()
  ;(bankAccounts ?? []).forEach((a) => accountNames.set(a.id, a.account_name))
  ;(retirementAccounts ?? []).forEach((a) => accountNames.set(a.id, a.account_name))
  ;(educationAccounts ?? []).forEach((a) => accountNames.set(a.id, a.account_name))
  ;(stockPositions ?? []).forEach((p) => accountNames.set(p.id, p.ticker_symbol))

  const categoryNames = new Map((categories ?? []).map((c) => [c.id, c.name]))

  const transactionRows: LogRow[] = (transactions ?? []).map((t) => ({
    id: `txn-${t.id}`,
    date: t.transaction_date,
    createdAt: t.created_at,
    badgeLabel: TYPE_LABELS[t.transaction_type],
    badgeClass: TYPE_BADGE_CLASSES[t.transaction_type],
    accountLabel: t.account_id ? (accountNames.get(t.account_id) ?? 'Deleted account') : '—',
    description: t.description ?? '—',
    amount: t.amount,
    editable: true,
    transaction: t,
  }))

  const expenseRows: LogRow[] = (expenses ?? []).map((e) => ({
    id: `exp-${e.id}`,
    date: e.expense_date,
    createdAt: e.created_at,
    badgeLabel: 'Expense',
    badgeClass: EXPENSE_BADGE_CLASS,
    accountLabel: e.bank_account_id ? (accountNames.get(e.bank_account_id) ?? 'Deleted account') : '—',
    description: [e.merchant_name, e.category_id ? categoryNames.get(e.category_id) : null]
      .filter(Boolean)
      .join(' · '),
    amount: e.amount,
    editable: false,
  }))

  const allRows = [...transactionRows, ...expenseRows].sort((a, b) => {
    const dateCompare = b.date.localeCompare(a.date)
    return dateCompare !== 0 ? dateCompare : b.createdAt.localeCompare(a.createdAt)
  })

  const rows =
    activeTab === 'all'
      ? allRows
      : activeTab === 'expense'
        ? allRows.filter((r) => !r.editable)
        : allRows.filter((r) => r.transaction?.transaction_type === activeTab)

  const handleDelete = (transaction: Transaction) => {
    if (
      window.confirm(
        'Delete this transaction? This will reverse its effect on the account it affected.'
      )
    ) {
      deleteTransaction.mutate(transaction.id)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Transactions</h1>
          <p className="text-slate-500">
            Every real income occurrence, retirement/education contribution, investment
            trade, and expense you've recorded. Expenses are edited on the Expenses page.
          </p>
        </div>
        <Button
          variant="outline"
          onClick={() => runScheduler.mutate()}
          disabled={runScheduler.isPending}
          className="shrink-0"
        >
          <RefreshCw className={cn('mr-2 h-4 w-4', runScheduler.isPending && 'animate-spin')} />
          {runScheduler.isPending ? 'Syncing...' : 'Sync Recurring Items'}
        </Button>
      </div>

      {runScheduler.isSuccess && (
        <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          {summarizeSchedulerResult(runScheduler.data)}
        </div>
      )}
      {runScheduler.isError && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
          {getApiErrorMessage(runScheduler.error, 'Failed to sync recurring items.')}
        </div>
      )}

      <div className="flex gap-2 overflow-x-auto pb-1">
        {TYPE_TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => setActiveTab(tab.value)}
            className={cn(
              'shrink-0 rounded-full px-3 py-1.5 text-sm font-medium transition-colors',
              activeTab === tab.value
                ? 'bg-primary-600 text-white'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <p className="py-12 text-center text-slate-500">Loading transactions...</p>
      ) : rows.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <p className="text-slate-500">No transactions here yet</p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-slate-500">
                    <th className="px-4 py-3 font-medium">Date</th>
                    <th className="px-4 py-3 font-medium">Type</th>
                    <th className="px-4 py-3 font-medium">Account</th>
                    <th className="px-4 py-3 font-medium">Description</th>
                    <th className="px-4 py-3 text-right font-medium">Amount</th>
                    <th className="px-4 py-3"></th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id} className="border-b border-slate-100 last:border-0">
                      <td className="px-4 py-3 text-slate-600">{formatDate(row.date)}</td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${row.badgeClass}`}
                        >
                          {row.badgeLabel}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-600">{row.accountLabel}</td>
                      <td className="px-4 py-3 text-slate-600">{row.description}</td>
                      <td className="px-4 py-3 text-right font-medium text-slate-900">
                        {formatCurrency(row.amount)}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-1">
                          {row.editable && row.transaction ? (
                            <>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7 text-slate-400 hover:text-primary-600"
                                onClick={() => setEditingTransaction(row.transaction!)}
                              >
                                <Pencil className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7 text-slate-400 hover:text-danger-500"
                                onClick={() => handleDelete(row.transaction!)}
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </>
                          ) : (
                            <Link
                              to="/expenses"
                              className="flex items-center gap-1 text-xs font-medium text-primary-600 hover:underline"
                            >
                              Edit in Expenses
                              <ArrowUpRight className="h-3 w-3" />
                            </Link>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      <TransactionEditModal transaction={editingTransaction} onClose={() => setEditingTransaction(null)} />
    </div>
  )
}
