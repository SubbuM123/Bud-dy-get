/**
 * Form for recording a real contribution to a retirement account, rendered inline on
 * RetirementAccountDetailPage. Shows the user's remaining contribution room for that
 * account's type (from GET /retirement-accounts/limits) and warns before submitting an
 * amount that would exceed it - the backend rejects it either way (400), but surfacing the
 * limit up front avoids a round-trip failure for the common case.
 *
 * Also asks where the money is coming from - a real bank account (debits its balance for
 * real), a pre-tax payroll deduction (never touches a bank balance, matching how a real
 * 401(k) contribution works), or untracked - mirroring how education's ContributionForm
 * asks the same question. See models/enums.py:ContributionSourceType.
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
import { useContributionLimits } from '../hooks/useRetirementAccounts'
import { useBankAccounts } from '@/features/bank-accounts/hooks/useBankAccounts'
import { RETIREMENT_GLOSSARY } from '../glossary'
import type { RetirementAccountType, ContributionSourceType } from '@/types'

const SOURCE_OPTIONS = [
  { value: 'track_only', label: 'Not tracked to a source' },
  { value: 'bank_account', label: 'From a bank account' },
  { value: 'pre_tax_salary', label: 'Pre-tax payroll deduction (401k, etc.)' },
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
  accountType: RetirementAccountType
  onSubmit: (data: ContributionSubmitData) => void
  isLoading?: boolean
  onCancel?: () => void
}

export default function ContributionForm({
  accountType,
  onSubmit,
  isLoading,
  onCancel,
}: ContributionFormProps) {
  const { data: limits } = useContributionLimits(accountType)
  const { data: bankAccounts } = useBankAccounts()
  const [enteredAmount, setEnteredAmount] = useState(0)

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

  const remaining = limits ? parseFloat(limits.remaining_contribution) : null
  const wouldExceedLimit = remaining !== null && enteredAmount > remaining

  return (
    <form onSubmit={handleValidSubmit} className="space-y-4">
      {limits && (
        <div className="rounded-md bg-slate-50 p-3 text-sm">
          <p className="flex items-center gap-1">
            Remaining 2026 contribution room:{' '}
            <span className="font-semibold">{formatCurrency(limits.remaining_contribution)}</span>
            <InfoTooltip {...RETIREMENT_GLOSSARY.contribution_limit} />
          </p>
          {limits.catch_up_eligible && (
            <p className="flex items-center gap-1 text-slate-500">
              Includes a {formatCurrency(limits.catch_up_amount)} catch-up contribution.
              <InfoTooltip {...RETIREMENT_GLOSSARY.catch_up} />
            </p>
          )}
          {!limits.eligible && limits.eligibility_note && (
            <p className="mt-1 text-danger-500">{limits.eligibility_note}</p>
          )}
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

      {wouldExceedLimit && (
        <p className="text-sm text-danger-500">
          This exceeds your remaining {formatCurrency(remaining!)} of contribution room and
          will be rejected.
        </p>
      )}

      {limits?.employer_match_this_contribution && parseFloat(limits.employer_match_this_contribution) > 0 && (
        <p className="text-sm text-success-600">
          Employer match on your last contribution: {formatCurrency(limits.employer_match_this_contribution)}
        </p>
      )}

      {limits?.total_limit && (
        <p className="text-xs text-slate-400">
          Combined employee + employer limit: {formatCurrency(limits.total_limit)}
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
        <Button type="submit" disabled={isLoading || wouldExceedLimit}>
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
