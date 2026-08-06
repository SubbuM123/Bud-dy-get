/**
 * Form for adding or editing a recurring monthly or yearly contribution to a retirement
 * account (e.g. "$500/month via payroll" or "$7,500/year before the tax deadline"),
 * rendered inline on RetirementAccountDetailPage. Mirrors bank-accounts'
 * RecurringActionForm's start/end-date checkbox pattern, simplified since a retirement
 * recurring contribution has no action type or category - it's always money going in.
 * Passing a `contribution` prop switches the form into edit mode: fields are pre-filled,
 * `frequency`/start date become read-only (the backend's RecurringContributionUpdate
 * schema doesn't allow changing them after creation, matching RecurringActionForm's
 * precedent), and the submit button reads "Save Changes".
 */
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import type { RetirementRecurringContribution } from '@/types'

const contributionSchema = z.object({
  amount: z.string().transform((val) => parseFloat(val)),
  frequency: z.enum(['monthly', 'yearly']),
  start_date: z.string(),
  end_date: z.string().optional(),
})

type ContributionFormFieldsData = z.input<typeof contributionSchema>

interface RecurringContributionFormProps {
  contribution?: RetirementRecurringContribution
  onSubmit: (data: z.output<typeof contributionSchema>) => void
  isLoading?: boolean
  onCancel?: () => void
}

const todayIsoDate = () => new Date().toISOString().split('T')[0]

export default function RecurringContributionForm({
  contribution,
  onSubmit,
  isLoading,
  onCancel,
}: RecurringContributionFormProps) {
  const isEditMode = !!contribution
  const [startsImmediately, setStartsImmediately] = useState(!isEditMode)
  const [neverEnds, setNeverEnds] = useState(!contribution?.end_date)

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ContributionFormFieldsData>({
    resolver: zodResolver(contributionSchema),
    defaultValues: {
      amount: contribution?.amount ?? undefined,
      frequency: contribution?.frequency ?? 'monthly',
      start_date: contribution?.start_date ?? todayIsoDate(),
      end_date: contribution?.end_date ?? undefined,
    },
  })

  const handleValidSubmit = handleSubmit((data) => {
    const output = data as unknown as z.output<typeof contributionSchema>
    onSubmit({
      ...output,
      start_date: startsImmediately ? todayIsoDate() : output.start_date,
      end_date: neverEnds ? undefined : output.end_date,
    })
  })

  return (
    <form onSubmit={handleValidSubmit} className="space-y-4">
      <Input
        label="Amount ($)"
        type="number"
        step="0.01"
        min="0.01"
        placeholder="500"
        error={errors.amount?.message}
        {...register('amount')}
      />

      {isEditMode ? (
        <div>
          <p className="text-sm font-medium text-slate-700">Frequency</p>
          <p className="text-sm text-slate-500 capitalize">
            {contribution.frequency} (can't be changed after creation)
          </p>
        </div>
      ) : (
        <Select
          label="Frequency"
          options={[
            { value: 'monthly', label: 'Monthly' },
            { value: 'yearly', label: 'Yearly' },
          ]}
          {...register('frequency')}
        />
      )}

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
          <span className="text-sm">This contribution never ends</span>
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
          {isLoading ? 'Saving...' : isEditMode ? 'Save Changes' : 'Add Recurring Contribution'}
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
