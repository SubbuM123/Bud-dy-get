/**
 * Form for adding or editing a recurring deposit or withdrawal (e.g. monthly salary,
 * weekly rent) on a bank account, rendered inline on AccountDetailPage. Frequency is
 * expressed as a value + unit pair (e.g. "every 2 weeks") matching the backend's
 * RecurringAction schema. Passing an `action` prop switches the form into edit mode:
 * fields are pre-filled, `action_type`/start date become read-only (the backend's
 * RecurringActionUpdate schema doesn't allow changing them after creation - it never
 * made sense to retroactively rewrite when something started), and the submit button
 * reads "Save Changes". The caller decides which subset of the emitted fields to send
 * to the create vs. update endpoint.
 */
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import type { RecurringAction } from '@/types'

const CATEGORY_OPTIONS = [
  { value: 'salary', label: 'Salary' },
  { value: 'housing', label: 'Housing' },
  { value: 'utilities', label: 'Utilities' },
  { value: 'insurance', label: 'Insurance' },
  { value: 'retirement', label: 'Retirement' },
  { value: 'investment', label: 'Investment' },
  { value: 'healthcare', label: 'Healthcare' },
  { value: 'entertainment', label: 'Entertainment' },
  { value: 'transportation', label: 'Transportation' },
  { value: 'other', label: 'Other' },
]

// Raw form fields are strings; transforms coerce amount/frequency_value to numbers before
// the parsed output is handed to the create/update-recurring-action API calls. end_date is
// wiped to undefined at submit time when the "never ends" checkbox is on, regardless of
// whatever stale value the (hidden) date input holds.
const actionSchema = z.object({
  action_type: z.enum(['deposit', 'withdrawal']),
  amount: z.string().transform((val) => parseFloat(val)),
  description: z.string().optional(),
  // The "Uncategorized" option submits an empty string; normalize it to undefined so
  // it doesn't fail enum validation and the field is simply omitted from the payload.
  category: z.preprocess(
    (val) => (val === '' ? undefined : val),
    z.enum([
      'salary', 'housing', 'utilities', 'insurance', 'retirement',
      'investment', 'healthcare', 'entertainment', 'transportation', 'other',
    ]).optional()
  ),
  frequency_value: z.string().transform((val) => parseInt(val, 10)),
  frequency_unit: z.enum(['days', 'weeks', 'months']),
  start_date: z.string(),
  end_date: z.string().optional(),
})

type ActionFormData = z.input<typeof actionSchema>

interface RecurringActionFormProps {
  action?: RecurringAction
  onSubmit: (data: z.output<typeof actionSchema>) => void
  isLoading?: boolean
  onCancel?: () => void
}

const todayIsoDate = () => new Date().toISOString().split('T')[0]

export default function RecurringActionForm({
  action,
  onSubmit,
  isLoading,
  onCancel,
}: RecurringActionFormProps) {
  const isEditMode = !!action
  const [startsImmediately, setStartsImmediately] = useState(!isEditMode)
  const [neverEnds, setNeverEnds] = useState(!action?.end_date)

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ActionFormData>({
    resolver: zodResolver(actionSchema),
    defaultValues: {
      action_type: action?.action_type ?? 'deposit',
      amount: action?.amount ?? undefined,
      description: action?.description ?? undefined,
      category: action?.category ?? undefined,
      frequency_value: String(action?.frequency_value ?? '1'),
      frequency_unit: action?.frequency_unit ?? 'months',
      start_date: action?.start_date ?? todayIsoDate(),
      end_date: action?.end_date ?? undefined,
    },
  })

  // zodResolver runs the schema's .transform() at runtime, so the value handleSubmit
  // hands back is already the parsed z.output shape (numbers, not strings) - the cast
  // below just corrects the type declaration to match, since @hookform/resolvers'
  // installed types don't propagate transformed output types.
  const handleValidSubmit = handleSubmit((data) => {
    const output = data as unknown as z.output<typeof actionSchema>
    onSubmit({
      ...output,
      start_date: startsImmediately ? todayIsoDate() : output.start_date,
      end_date: neverEnds ? undefined : output.end_date,
    })
  })

  return (
    <form onSubmit={handleValidSubmit} className="space-y-4">
      {isEditMode ? (
        <div>
          <p className="text-sm font-medium text-slate-700">Action Type</p>
          <p className="text-sm text-slate-500 capitalize">
            {action.action_type} (can't be changed after creation)
          </p>
        </div>
      ) : (
        <Select
          label="Action Type"
          options={[
            { value: 'deposit', label: 'Deposit (Add Money)' },
            { value: 'withdrawal', label: 'Withdrawal (Remove Money)' },
          ]}
          {...register('action_type')}
        />
      )}

      <Input
        label="Amount ($)"
        type="number"
        step="0.01"
        min="0.01"
        placeholder="500"
        error={errors.amount?.message}
        {...register('amount')}
      />

      <Input
        label="Description"
        placeholder="e.g., Monthly salary, Rent payment"
        {...register('description')}
      />

      <Select
        label="Category"
        options={[{ value: '', label: 'Uncategorized' }, ...CATEGORY_OPTIONS]}
        {...register('category')}
      />

      <div className="grid grid-cols-2 gap-4">
        <Input
          label="Every"
          type="number"
          min="1"
          placeholder="1"
          error={errors.frequency_value?.message}
          {...register('frequency_value')}
        />

        <Select
          label="Period"
          options={[
            { value: 'days', label: 'Days' },
            { value: 'weeks', label: 'Weeks' },
            { value: 'months', label: 'Months' },
          ]}
          {...register('frequency_unit')}
        />
      </div>

      {!isEditMode && (
        <div className="space-y-2">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={startsImmediately}
              onChange={(e) => setStartsImmediately(e.target.checked)}
              className="rounded border-slate-300"
            />
            <span className="text-sm">Start immediately</span>
          </label>
          {startsImmediately ? (
            <p className="text-sm text-slate-500">Starts today</p>
          ) : (
            <Input
              label="Start Date"
              type="date"
              error={errors.start_date?.message}
              {...register('start_date')}
            />
          )}
        </div>
      )}

      <div className="space-y-2">
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={neverEnds}
            onChange={(e) => setNeverEnds(e.target.checked)}
            className="rounded border-slate-300"
          />
          <span className="text-sm">This action never ends</span>
        </label>
        {!neverEnds && (
          <Input
            label="End Date"
            type="date"
            error={errors.end_date?.message}
            {...register('end_date')}
          />
        )}
      </div>

      <div className="flex gap-3 pt-4">
        <Button type="submit" disabled={isLoading}>
          {isLoading ? 'Saving...' : isEditMode ? 'Save Changes' : 'Add Recurring Action'}
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
