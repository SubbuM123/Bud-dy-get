/**
 * Summary card for a single income (recurring salary/side income, or a one-time payment),
 * shown in the list on IncomePage. Shows the allocation split by destination account name
 * (resolved via `destinationNames`, a lookup built once on IncomePage from every bank/
 * retirement/education account the user owns, rather than each card re-fetching them) and,
 * for a recurring income, a "Log Paycheck" button that records one real occurrence - see
 * hooks/useIncome.ts:useLogIncome.
 */
import { Trash2, Repeat, Calendar } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { formatCurrency, formatDate } from '@/lib/utils'
import type { Income } from '@/types'

interface IncomeCardProps {
  income: Income
  destinationNames: Map<string, string>
  onLog?: (income: Income) => void
  onDelete?: (id: string) => void
  isLogging?: boolean
}

const FREQUENCY_LABELS: Record<string, string> = {
  weekly: 'Weekly',
  biweekly: 'Biweekly',
  semi_monthly: 'Semi-monthly',
  monthly: 'Monthly',
}

export default function IncomeCard({ income, destinationNames, onLog, onDelete, isLogging }: IncomeCardProps) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="font-medium text-slate-900">{income.name}</p>
            <p className="text-2xl font-bold text-slate-900">{formatCurrency(income.amount)}</p>
          </div>
          {onDelete && (
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 shrink-0 text-slate-400 hover:text-danger-500"
              onClick={() => onDelete(income.id)}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          )}
        </div>

        <div className="mt-2 flex items-center gap-1.5 text-sm text-slate-500">
          {income.is_recurring ? (
            <>
              <Repeat className="h-3.5 w-3.5" />
              {income.frequency ? FREQUENCY_LABELS[income.frequency] : 'Recurring'}
            </>
          ) : (
            <>
              <Calendar className="h-3.5 w-3.5" />
              One-time{income.income_date && ` · ${formatDate(income.income_date)}`}
            </>
          )}
        </div>

        <div className="mt-3 space-y-1 border-t border-slate-100 pt-3 text-sm">
          {income.allocations.map((allocation) => (
            <div key={allocation.id} className="flex items-center justify-between text-slate-600">
              <span className="truncate">
                {destinationNames.get(allocation.destination_id) ?? 'Deleted account'}
              </span>
              <span className="shrink-0 font-medium">{parseFloat(allocation.percentage)}%</span>
            </div>
          ))}
        </div>

        {income.is_recurring && onLog && (
          <Button size="sm" className="mt-4 w-full" disabled={isLogging} onClick={() => onLog(income)}>
            {isLogging ? 'Logging...' : 'Log Paycheck'}
          </Button>
        )}
      </CardContent>
    </Card>
  )
}
