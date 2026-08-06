/**
 * Form for creating a new income (recurring salary/side income, or a one-time bonus/
 * gift/refund), rendered inline on IncomePage. The centerpiece is the allocation list:
 * one row per destination (a bank account, a retirement account, or an education
 * account) with a percentage of `amount` going to it - rows are added/removed freely,
 * and the running total must land on exactly 100% before the form can submit (see
 * `allocatedTotal` below), mirroring how a real paycheck's direct-deposit split works.
 *
 * `amount` is always post-tax - this app doesn't model tax withholding (see
 * api/v1/income.py's docstring) - so the placeholder/help text nudges anyone unsure of
 * their take-home pay toward "roughly 70% of your gross" as a starting estimate rather
 * than leaving them guessing.
 */
import { useForm, useFieldArray } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Plus, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { useBankAccounts } from '@/features/bank-accounts/hooks/useBankAccounts'
import { useRetirementAccounts } from '@/features/retirement/hooks/useRetirementAccounts'
import { useEducationAccounts } from '@/features/education/hooks/useEducationAccounts'
import type { AllocationDestinationType } from '@/types'
import type { IncomePayload } from '../api'

const FREQUENCY_OPTIONS = [
  { value: 'weekly', label: 'Weekly' },
  { value: 'biweekly', label: 'Biweekly' },
  { value: 'semi_monthly', label: 'Semi-monthly (twice a month)' },
  { value: 'monthly', label: 'Monthly' },
]

// Encodes destination_type + destination_id into one <select> value, since a single flat
// list of options (bank + retirement + education accounts together) is simpler for a
// per-row picker than three dependent selects. Decoded back out in handleValidSubmit.
function encodeDestination(type: AllocationDestinationType, id: string): string {
  return `${type}:${id}`
}

function decodeDestination(value: string): { destination_type: AllocationDestinationType; destination_id: string } {
  const [type, id] = value.split(':')
  return { destination_type: type as AllocationDestinationType, destination_id: id }
}

const allocationRowSchema = z.object({
  destination: z.string().min(1, 'Choose a destination'),
  percentage: z.coerce.number().gt(0, 'Must be greater than 0').max(100),
  // Only meaningful when destination is a retirement/education account - see
  // handleValidSubmit, which drops it for a bank_account destination rather than sending
  // a value the backend's model_validator would reject.
  preTaxSalary: z.boolean().optional(),
})

const incomeSchema = z
  .object({
    name: z.string().min(1, 'Name is required'),
    amount: z.coerce.number().gt(0, 'Must be greater than 0'),
    is_recurring: z.boolean(),
    frequency: z.string().optional(),
    start_date: z.string().optional(),
    income_date: z.string().optional(),
    allocations: z.array(allocationRowSchema).min(1, 'Add at least one destination'),
  })
  .superRefine((val, ctx) => {
    const total = val.allocations.reduce((sum, a) => sum + a.percentage, 0)
    if (Math.abs(total - 100) > 0.02) {
      ctx.addIssue({
        code: 'custom',
        path: ['allocations'],
        message: `Allocations must sum to 100% (currently ${total.toFixed(2)}%)`,
      })
    }
    if (val.is_recurring && !val.frequency) {
      ctx.addIssue({ code: 'custom', path: ['frequency'], message: 'Frequency is required' })
    }
    if (!val.is_recurring && !val.income_date) {
      ctx.addIssue({ code: 'custom', path: ['income_date'], message: 'Date is required' })
    }
  })

type IncomeFormData = z.infer<typeof incomeSchema>

interface IncomeFormProps {
  onSubmit: (data: IncomePayload) => void
  isLoading?: boolean
  onCancel?: () => void
}

export default function IncomeForm({ onSubmit, isLoading, onCancel }: IncomeFormProps) {
  const { data: bankAccounts } = useBankAccounts()
  const { data: retirementAccounts } = useRetirementAccounts()
  const { data: educationAccounts } = useEducationAccounts()

  const destinationOptions = [
    ...(bankAccounts ?? []).map((a) => ({
      value: encodeDestination('bank_account', a.id),
      label: `${a.account_name} (Bank Account)`,
    })),
    ...(retirementAccounts ?? []).map((a) => ({
      value: encodeDestination('retirement_account', a.id),
      label: `${a.account_name} (Retirement)`,
    })),
    ...(educationAccounts ?? []).map((a) => ({
      value: encodeDestination('education_account', a.id),
      label: `${a.account_name} (Education)`,
    })),
  ]

  const {
    register,
    control,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<IncomeFormData>({
    resolver: zodResolver(incomeSchema),
    defaultValues: {
      is_recurring: true,
      frequency: 'monthly',
      allocations: [{ destination: '', percentage: 100 }],
    },
  })

  const { fields, append, remove } = useFieldArray({ control, name: 'allocations' })

  const isRecurring = watch('is_recurring')
  const allocationValues = watch('allocations')
  const allocatedTotal = (allocationValues ?? []).reduce(
    (sum, a) => sum + (parseFloat(String(a.percentage)) || 0),
    0
  )

  const handleValidSubmit = handleSubmit((data) => {
    const payload: IncomePayload = {
      name: data.name,
      amount: data.amount,
      is_recurring: data.is_recurring,
      frequency: data.is_recurring ? (data.frequency as IncomePayload['frequency']) : undefined,
      start_date: data.is_recurring ? data.start_date || undefined : undefined,
      income_date: !data.is_recurring ? data.income_date : undefined,
      allocations: data.allocations.map((a) => {
        const destination = decodeDestination(a.destination)
        const supportsPreTax = destination.destination_type !== 'bank_account'
        return {
          ...destination,
          percentage: a.percentage,
          source_type: supportsPreTax && a.preTaxSalary ? 'pre_tax_salary' : undefined,
        }
      }),
    }
    onSubmit(payload)
  })

  return (
    <form onSubmit={handleValidSubmit} className="space-y-4">
      <Input
        label="Name"
        placeholder="Primary Salary"
        error={errors.name?.message}
        {...register('name')}
      />

      <Input
        label="Post-Tax Amount ($)"
        type="number"
        step="0.01"
        min="0.01"
        placeholder="5000"
        error={errors.amount?.message}
        {...register('amount')}
      />
      <p className="text-xs text-slate-400">
        Enter what actually lands in your bank account, not your gross pay. Not sure?
        Roughly 70% of your gross salary is a reasonable starting estimate.
      </p>

      <div className="flex items-center gap-2">
        <input
          id="is_recurring"
          type="checkbox"
          className="h-4 w-4 rounded border-slate-300"
          {...register('is_recurring')}
        />
        <label htmlFor="is_recurring" className="text-sm font-medium text-slate-700">
          This is a recurring income (salary, regular side income)
        </label>
      </div>

      {isRecurring ? (
        <div className="grid grid-cols-2 gap-3">
          <Select
            label="Frequency"
            options={FREQUENCY_OPTIONS}
            error={errors.frequency?.message}
            {...register('frequency')}
          />
          <Input label="Start Date (optional)" type="date" {...register('start_date')} />
        </div>
      ) : (
        <Input
          label="Date Received"
          type="date"
          error={errors.income_date?.message}
          {...register('income_date')}
        />
      )}

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <p className="text-sm font-medium text-slate-700">Allocate to</p>
          <span
            className={
              Math.abs(allocatedTotal - 100) < 0.02
                ? 'text-sm font-medium text-success-600'
                : 'text-sm font-medium text-danger-500'
            }
          >
            {allocatedTotal.toFixed(2)}% / 100%
          </span>
        </div>

        {fields.map((field, index) => {
          const destinationValue = allocationValues?.[index]?.destination ?? ''
          const supportsPreTax =
            destinationValue !== '' && !destinationValue.startsWith('bank_account:')

          return (
            <div key={field.id} className="space-y-1">
              <div className="flex items-end gap-2">
                <div className="flex-1">
                  <Select
                    label={index === 0 ? 'Destination' : undefined}
                    options={[{ value: '', label: 'Select an account...' }, ...destinationOptions]}
                    {...register(`allocations.${index}.destination` as const)}
                  />
                </div>
                <div className="w-28">
                  <Input
                    label={index === 0 ? 'Percent' : undefined}
                    type="number"
                    step="0.01"
                    min="0"
                    max="100"
                    placeholder="60"
                    {...register(`allocations.${index}.percentage` as const)}
                  />
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="mb-0.5 shrink-0 text-slate-400 hover:text-danger-500"
                  onClick={() => remove(index)}
                  disabled={fields.length === 1}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
              {supportsPreTax && (
                <label className="flex items-center gap-2 pl-1 text-xs text-slate-500">
                  <input
                    type="checkbox"
                    className="h-3.5 w-3.5 rounded border-slate-300"
                    {...register(`allocations.${index}.preTaxSalary` as const)}
                  />
                  Funded pre-tax (payroll deduction) - logs as a contribution, not income
                </label>
              )}
            </div>
          )
        })}

        {errors.allocations?.message && (
          <p className="text-sm text-danger-500">{errors.allocations.message}</p>
        )}
        {errors.allocations?.root?.message && (
          <p className="text-sm text-danger-500">{errors.allocations.root.message}</p>
        )}

        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => append({ destination: '', percentage: 0 })}
        >
          <Plus className="mr-1 h-3.5 w-3.5" />
          Add Destination
        </Button>
      </div>

      <div className="flex gap-3 pt-2">
        <Button type="submit" disabled={isLoading}>
          {isLoading ? 'Saving...' : 'Create Income'}
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
