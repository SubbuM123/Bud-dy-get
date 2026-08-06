/**
 * Form for creating or editing an education savings account (name, type, beneficiary name/
 * birth date, plan provider, balance, expected return rate), rendered inline on
 * EducationAccountsPage (create) and EducationAccountDetailPage (edit). Passing an
 * `account` prop switches the form into edit mode: fields are pre-filled, `account_type`
 * becomes a read-only label (the backend's EducationAccountUpdate schema doesn't allow
 * changing it after creation, matching RetirementAccountForm's precedent), and the submit
 * button reads "Save Changes". No employer/vesting fields here - 529s aren't
 * employer-sponsored, unlike RetirementAccountForm. Validation and string-to-number
 * coercion are handled by the Zod schema so the parent page only deals with the fully
 * parsed, typed output in its onSubmit handler.
 */
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { InfoTooltip } from '@/components/ui/info-tooltip'
import { EDUCATION_GLOSSARY, type GlossaryKey } from '../glossary'
import type { EducationAccount } from '@/types'

// Only 529 Plan is actually implemented; Coverdell/Custodial are recorded-but-not-yet
// supported placeholders, mirroring how RetirementAccountForm records SEP/SIMPLE/HSA
// without enforcing their limits.
const ACCOUNT_TYPE_OPTIONS = [
  { value: '529_plan', label: '529 Plan' },
  { value: 'coverdell_esa', label: 'Coverdell ESA (coming soon)' },
  { value: 'custodial_utma_ugma', label: 'Custodial UTMA/UGMA (coming soon)' },
]

const ACCOUNT_TYPE_LABELS: Record<string, string> = {
  '529_plan': '529 Plan',
  coverdell_esa: 'Coverdell ESA',
  custodial_utma_ugma: 'Custodial UTMA/UGMA',
}

// Raw form fields are strings (from <input>); transforms convert them to the numeric types
// the create/update-account API expects. expected_return_rate is entered as a whole-number
// percentage and converted to a decimal fraction here, matching RetirementAccountForm's convention.
const accountSchema = z.object({
  account_name: z.string().min(1, 'Account name is required'),
  account_type: z.enum(['529_plan', 'coverdell_esa', 'custodial_utma_ugma']),
  beneficiary_name: z.string().min(1, 'Beneficiary name is required'),
  beneficiary_birth_date: z
    .string()
    .optional()
    .transform((val) => (val ? val : undefined)),
  plan_provider: z.string().optional(),
  balance: z.string().transform((val) => parseFloat(val)),
  expected_return_rate: z.string().transform((val) => (val ? parseFloat(val) / 100 : 0.07)),
})

type AccountFormData = z.input<typeof accountSchema>

interface EducationAccountFormProps {
  account?: EducationAccount
  onSubmit: (data: z.output<typeof accountSchema>) => void
  isLoading?: boolean
  onCancel?: () => void
}

export default function EducationAccountForm({
  account,
  onSubmit,
  isLoading,
  onCancel,
}: EducationAccountFormProps) {
  const isEditMode = !!account

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<AccountFormData>({
    resolver: zodResolver(accountSchema),
    defaultValues: {
      account_type: account?.account_type ?? '529_plan',
      account_name: account?.account_name,
      beneficiary_name: account?.beneficiary_name,
      beneficiary_birth_date: account?.beneficiary_birth_date ?? undefined,
      plan_provider: account?.plan_provider ?? undefined,
      balance: account?.balance,
      expected_return_rate: account?.expected_return_rate
        ? String(parseFloat(account.expected_return_rate) * 100)
        : '7',
    },
  })

  const accountType = watch('account_type')

  // zodResolver runs the schema's .transform() at runtime, so the value handleSubmit
  // hands back is already the parsed z.output shape - the cast below just corrects the
  // type declaration to match, as in RetirementAccountForm.
  const handleValidSubmit = handleSubmit((data) =>
    onSubmit(data as unknown as z.output<typeof accountSchema>)
  )

  return (
    <form onSubmit={handleValidSubmit} className="space-y-4">
      <Input
        label="Account Name"
        placeholder="Jordan's College Fund"
        error={errors.account_name?.message}
        {...register('account_name')}
      />

      {isEditMode ? (
        <div>
          <div className="flex items-center gap-1.5">
            <p className="text-sm font-medium text-slate-700">Account Type</p>
            <InfoTooltip {...EDUCATION_GLOSSARY[account.account_type as GlossaryKey]} />
          </div>
          <p className="text-sm text-slate-500">
            {ACCOUNT_TYPE_LABELS[account.account_type]} (can't be changed after creation)
          </p>
        </div>
      ) : (
        <Select
          label="Account Type"
          tooltip={<InfoTooltip {...EDUCATION_GLOSSARY[accountType as GlossaryKey]} />}
          options={ACCOUNT_TYPE_OPTIONS}
          {...register('account_type')}
        />
      )}

      <Input
        label="Beneficiary Name"
        tooltip={<InfoTooltip {...EDUCATION_GLOSSARY.beneficiary} />}
        placeholder="Jordan Smith"
        error={errors.beneficiary_name?.message}
        {...register('beneficiary_name')}
      />

      <Input
        label="Beneficiary Birth Date (optional)"
        type="date"
        {...register('beneficiary_birth_date')}
      />

      <Input
        label="Plan Provider (optional)"
        tooltip={<InfoTooltip {...EDUCATION_GLOSSARY.plan_provider} />}
        placeholder="NY 529 College Savings Program"
        {...register('plan_provider')}
      />

      <Input
        label="Current Balance ($)"
        type="number"
        step="0.01"
        min="0"
        placeholder="10000"
        error={errors.balance?.message}
        {...register('balance')}
      />

      <Input
        label="Expected Annual Return (%)"
        tooltip={<InfoTooltip {...EDUCATION_GLOSSARY.expected_return} />}
        type="number"
        step="0.01"
        min="0"
        max="100"
        placeholder="7"
        error={errors.expected_return_rate?.message}
        {...register('expected_return_rate')}
      />

      <div className="flex gap-3 pt-4">
        <Button type="submit" disabled={isLoading}>
          {isLoading ? 'Saving...' : isEditMode ? 'Save Changes' : 'Create Account'}
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
