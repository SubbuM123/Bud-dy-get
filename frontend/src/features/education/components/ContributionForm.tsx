/**
 * Form for recording a real contribution to an education savings account, rendered inline
 * on EducationAccountDetailPage. Shows this beneficiary's remaining room before the
 * 2026 gift-tax exclusion (from GET /education-accounts/gift-tax-info) and an
 * informational note if the entered amount would exceed it - unlike retirement's
 * ContributionForm, this never disables submission or predicts a rejection, since 529s
 * have no IRS contribution cap for the backend to enforce.
 *
 * Also asks where the money is coming from, mirroring retirement's ContributionForm - see
 * that component's docstring and models/enums.py:ContributionSourceType.
 */
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { InfoTooltip } from '@/components/ui/info-tooltip'
import { formatCurrency } from '@/lib/utils'
import { useGiftTaxInfo } from '../hooks/useEducationAccounts'
import { useBankAccounts } from '@/features/bank-accounts/hooks/useBankAccounts'
import { EDUCATION_GLOSSARY } from '../glossary'
import type { ContributionSourceType } from '@/types'

const SOURCE_OPTIONS = [
  { value: 'track_only', label: 'Not tracked to a source' },
  { value: 'bank_account', label: 'From a bank account' },
  { value: 'pre_tax_salary', label: 'Pre-tax payroll deduction' },
]

const contributionSchema = z
  .object({
    amount: z.string().transform((val) => parseFloat(val)),
    source_type: z.enum(['track_only', 'bank_account', 'pre_tax_salary']),
    source_bank_account_id: z.string().optional(),
  })
  .refine((val) => val.source_type !== 'bank_account' || !!val.source_bank_account_id, {
    message: 'Choose which bank account this came from',
    path: ['source_bank_account_id'],
  })

type ContributionFormData = z.input<typeof contributionSchema>

export interface ContributionSubmitData {
  amount: number
  source_type: ContributionSourceType
  source_bank_account_id?: string
}

interface ContributionFormProps {
  beneficiaryName: string
  onSubmit: (data: ContributionSubmitData) => void
  isLoading?: boolean
  onCancel?: () => void
}

export default function ContributionForm({
  beneficiaryName,
  onSubmit,
  isLoading,
  onCancel,
}: ContributionFormProps) {
  const [enteredAmount, setEnteredAmount] = useState(0)
  const { data: giftTaxInfo } = useGiftTaxInfo(beneficiaryName, enteredAmount || undefined)
  const { data: bankAccounts } = useBankAccounts()

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<ContributionFormData>({
    resolver: zodResolver(contributionSchema),
    defaultValues: { source_type: 'track_only' },
  })

  const sourceType = watch('source_type')

  const handleValidSubmit = handleSubmit((data) => {
    const output = data as unknown as z.output<typeof contributionSchema>
    onSubmit(output)
  })

  return (
    <form onSubmit={handleValidSubmit} className="space-y-4">
      {giftTaxInfo && (
        <div className="rounded-md bg-slate-50 p-3 text-sm">
          <p className="flex items-center gap-1">
            Remaining before {beneficiaryName}'s 2026 gift-tax exclusion:{' '}
            <span className="font-semibold">
              {formatCurrency(giftTaxInfo.remaining_before_exclusion)}
            </span>
            <InfoTooltip {...EDUCATION_GLOSSARY.gift_tax_exclusion} />
          </p>
          <p className="mt-1 text-slate-500">{giftTaxInfo.note}</p>
        </div>
      )}

      <Input
        label="Contribution Amount ($)"
        type="number"
        step="0.01"
        min="0.01"
        placeholder="500"
        error={errors.amount?.message}
        {...register('amount', {
          onChange: (e) => setEnteredAmount(parseFloat(e.target.value) || 0),
        })}
      />

      {giftTaxInfo?.would_exceed_exclusion && (
        <p className="flex items-center gap-1 text-sm text-amber-600">
          This would put {beneficiaryName} over this year's gift-tax exclusion - it will
          still go through, but consider the 5-year superfunding election or a Form 709
          filing.
          <InfoTooltip {...EDUCATION_GLOSSARY.superfunding} />
        </p>
      )}

      <Select label="Where is this money coming from?" options={SOURCE_OPTIONS} {...register('source_type')} />

      {sourceType === 'bank_account' && (
        <Select
          label="Bank Account"
          options={[
            { value: '', label: 'Select an account...' },
            ...(bankAccounts?.map((a) => ({ value: a.id, label: a.account_name })) ?? []),
          ]}
          error={errors.source_bank_account_id?.message}
          {...register('source_bank_account_id')}
        />
      )}

      <div className="flex gap-3 pt-2">
        <Button type="submit" disabled={isLoading}>
          {isLoading ? 'Recording...' : 'Record Contribution'}
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
