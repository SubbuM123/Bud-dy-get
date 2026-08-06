/**
 * Row summary for a single expense, shown in the list on ExpensesPage: merchant, amount,
 * date, a category badge (icon + color, via icon-map.ts), and an indicator when the
 * expense came from a receipt vs. was entered manually. Edit/delete icons match the
 * pencil/trash pattern every other module's card uses.
 */
import { Link } from 'react-router-dom'
import { Pencil, Trash2, Receipt as ReceiptIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { formatCurrency, formatDate } from '@/lib/utils'
import { getCategoryIcon } from '../icon-map'
import type { Expense, ExpenseCategory } from '@/types'

interface ExpenseCardProps {
  expense: Expense
  category?: ExpenseCategory
  onEdit?: (expense: Expense) => void
  onDelete?: (id: string) => void
}

export default function ExpenseCard({ expense, category, onEdit, onDelete }: ExpenseCardProps) {
  const CategoryIcon = getCategoryIcon(category?.icon)

  return (
    <div className="flex items-center justify-between rounded-lg border border-slate-200 p-4">
      <div className="flex items-center gap-3">
        <div
          className="flex h-9 w-9 items-center justify-center rounded-full"
          style={{ backgroundColor: `${category?.color ?? '#64748b'}1a` }}
        >
          <CategoryIcon className="h-4 w-4" style={{ color: category?.color ?? '#64748b' }} />
        </div>
        <div>
          <p className="flex items-center gap-1.5 font-medium text-slate-900">
            {expense.merchant_name}
            {expense.receipt_id && (
              <ReceiptIcon className="h-3.5 w-3.5 text-slate-400" aria-label="From a receipt" />
            )}
          </p>
          <p className="text-sm text-slate-500">
            {category?.name ?? 'Uncategorized'} &middot; {formatDate(expense.expense_date)}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <p className="font-semibold text-slate-900">{formatCurrency(expense.amount)}</p>
        <div className="flex items-center">
          {expense.receipt_id && (
            <Link to={`/receipts/${expense.receipt_id}`}>
              <Button variant="ghost" size="icon" className="text-slate-400 hover:text-primary-600">
                <ReceiptIcon className="h-4 w-4" />
              </Button>
            </Link>
          )}
          {onEdit && (
            <Button
              variant="ghost"
              size="icon"
              className="text-slate-400 hover:text-primary-600"
              onClick={() => onEdit(expense)}
            >
              <Pencil className="h-4 w-4" />
            </Button>
          )}
          {onDelete && (
            <Button
              variant="ghost"
              size="icon"
              className="text-slate-400 hover:text-danger-500"
              onClick={() => onDelete(expense.id)}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
