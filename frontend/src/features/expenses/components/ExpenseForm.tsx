/**
 * Form for creating or editing a manual expense (merchant, amount, date, category,
 * optional bank account link, optional recurrence, description). Passing an `expense`
 * prop switches the form into edit mode. This is the only way to create an expense in
 * v1 - Receipts is a standalone beta tool for now, deliberately disconnected from
 * Expenses (see docs/plan.md's "Unified Money Flow Reform").
 */
import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import CategoryPicker from './CategoryPicker'
import { useExpenseCategories } from '../hooks/useExpenses'
import { useBankAccounts } from '@/features/bank-accounts/hooks/useBankAccounts'
import type { Expense } from '@/types'

const RECURRENCE_OPTIONS = [
  { value: 'weekly', label: 'Weekly' },
  { value: 'biweekly', label: 'Biweekly' },
  { value: 'monthly', label: 'Monthly' },
  { value: 'yearly', label: 'Yearly' },
]

const expenseSchema = z.object({
  merchant_name: z.string().min(1, 'Merchant name is required'),
  amount: z.string().transform((val) => parseFloat(val)),
  expense_date: z.string().min(1, 'Date is required'),
  category_id: z.string().optional(),
  // Leaving the "Not linked to an account" option selected submits '' (the empty
  // sentinel used for that <option>'s value), not undefined - `.optional()` alone
  // doesn't strip that, so a real '' would previously reach the backend and fail trying
  // to insert it into a UUID foreign-key column. Same fix as EducationAccountForm's
  // beneficiary_birth_date.
  bank_account_id: z.string().optional().transform((val) => (val ? val : undefined)),
  description: z.string().optional(),
  is_recurring: z.boolean().optional(),
  recurrence_pattern: z.string().optional(),
})

type ExpenseFormData = z.input<typeof expenseSchema>

interface ExpenseFormProps {
  expense?: Expense
  onSubmit: (data: z.output<typeof expenseSchema>) => void
  isLoading?: boolean
  onCancel?: () => void
  onRequestCreateCategory?: () => void
}

const todayIsoDate = () => new Date().toISOString().split('T')[0]

export default function ExpenseForm({
  expense,
  onSubmit,
  isLoading,
  onCancel,
  onRequestCreateCategory,
}: ExpenseFormProps) {
  const { data: categories } = useExpenseCategories()
  const { data: bankAccounts } = useBankAccounts()

  const {
    register,
    handleSubmit,
    watch,
    control,
    formState: { errors },
  } = useForm<ExpenseFormData>({
    resolver: zodResolver(expenseSchema),
    defaultValues: {
      merchant_name: expense?.merchant_name,
      amount: expense?.amount,
      expense_date: expense?.expense_date ?? todayIsoDate(),
      category_id: expense?.category_id ?? undefined,
      bank_account_id: expense?.bank_account_id ?? undefined,
      description: expense?.description ?? undefined,
      is_recurring: expense?.is_recurring ?? false,
      recurrence_pattern: expense?.recurrence_pattern ?? 'monthly',
    },
  })

  const isRecurring = watch('is_recurring')

  const handleValidSubmit = handleSubmit((data) =>
    onSubmit(data as unknown as z.output<typeof expenseSchema>)
  )

  const bankAccountOptions = [
    { value: '', label: 'Not linked to an account' },
    ...(bankAccounts?.map((a) => ({ value: a.id, label: a.account_name })) ?? []),
  ]

  return (
    <form onSubmit={handleValidSubmit} className="space-y-4">
      <Input
        label="Merchant"
        placeholder="Corner Store"
        error={errors.merchant_name?.message}
        {...register('merchant_name')}
      />

      <div className="grid grid-cols-2 gap-4">
        <Input
          label="Amount ($)"
          type="number"
          step="0.01"
          min="0.01"
          placeholder="25.00"
          error={errors.amount?.message}
          {...register('amount')}
        />
        <Input
          label="Date"
          type="date"
          error={errors.expense_date?.message}
          {...register('expense_date')}
        />
      </div>

      <Controller
        name="category_id"
        control={control}
        render={({ field }) => (
          <CategoryPicker
            categories={categories ?? []}
            value={field.value}
            onChange={field.onChange}
            onRequestCreate={onRequestCreateCategory}
          />
        )}
      />

      <Select
        label="Bank Account (optional)"
        options={bankAccountOptions}
        {...register('bank_account_id')}
      />

      <Input
        label="Notes (optional)"
        placeholder="What was this for?"
        {...register('description')}
      />

      <div className="flex items-center gap-2">
        <input
          id="expense_is_recurring"
          type="checkbox"
          className="h-4 w-4 rounded border-slate-300"
          {...register('is_recurring')}
        />
        <label htmlFor="expense_is_recurring" className="text-sm font-medium text-slate-700">
          This is a recurring expense (rent, subscription, etc.)
        </label>
      </div>

      {isRecurring && (
        <Select
          label="Recurs"
          options={RECURRENCE_OPTIONS}
          {...register('recurrence_pattern')}
        />
      )}

      <div className="flex gap-3 pt-2">
        <Button type="submit" disabled={isLoading}>
          {isLoading ? 'Saving...' : expense ? 'Save Changes' : 'Add Expense'}
        </Button>
        {onCancel && (
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  )
}
