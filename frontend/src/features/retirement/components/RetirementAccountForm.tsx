/**
 * Form for creating or editing a retirement account (name, type, balance, expected return
 * rate, and - for 401(k)/Roth 401(k) accounts - employer name, salary, match percent/limit,
 * and a vesting schedule), rendered inline on RetirementAccountsPage (create) and
 * RetirementAccountDetailPage (edit). Passing an `account` prop switches the form into edit
 * mode: fields are pre-filled, `account_type` becomes a read-only label (the backend's
 * RetirementAccountUpdate schema doesn't allow changing it after creation, matching
 * AccountForm's bank-accounts precedent), and the submit button reads "Save Changes".
 * Validation and string-to-number coercion are handled by the Zod schema so the parent
 * page only deals with the fully parsed, typed output in its onSubmit handler.
 */
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { InfoTooltip } from '@/components/ui/info-tooltip'
import { RETIREMENT_GLOSSARY, type GlossaryKey } from '../glossary'
import type { RetirementAccount } from '@/types'

const ACCOUNT_TYPE_OPTIONS = [
  { value: 'traditional_401k', label: 'Traditional 401(k)' },
  { value: 'roth_401k', label: 'Roth 401(k)' },
  { value: 'traditional_ira', label: 'Traditional IRA' },
  { value: 'roth_ira', label: 'Roth IRA' },
  { value: 'sep_ira', label: 'SEP IRA' },
  { value: 'simple_ira', label: 'SIMPLE IRA' },
  { value: 'hsa', label: 'HSA' },
]

const ACCOUNT_TYPE_LABELS: Record<string, string> = Object.fromEntries(
  ACCOUNT_TYPE_OPTIONS.map((o) => [o.value, o.label])
)

const FOUR_OH_ONE_K_TYPES = ['traditional_401k', 'roth_401k']

// Raw form fields are strings (from <input>); transforms convert them to the numeric types
// the create/update-account API expects. Percent-style fields (expected return, employer
// match, match limit) are entered as whole-number percentages and converted to decimal
// fractions here, matching AccountForm's interest_rate convention.
const accountSchema = z.object({
  account_name: z.string().min(1, 'Account name is required'),
  account_type: z.enum([
    'traditional_401k', 'roth_401k', 'traditional_ira', 'roth_ira',
    'sep_ira', 'simple_ira', 'hsa',
  ]),
  balance: z.string().transform((val) => parseFloat(val)),
  expected_return_rate: z.string().transform((val) => (val ? parseFloat(val) / 100 : 0.07)),
  employer_name: z.string().optional(),
  annual_salary: z.string().optional().transform((val) => (val ? parseFloat(val) : undefined)),
  employer_match_percent: z
    .string()
    .optional()
    .transform((val) => (val ? parseFloat(val) / 100 : undefined)),
  employer_match_limit_percent: z
    .string()
    .optional()
    .transform((val) => (val ? parseFloat(val) / 100 : undefined)),
  vesting_type: z.preprocess(
    (val) => (val === '' ? undefined : val),
    z.enum(['immediate', 'cliff', 'graded']).optional()
  ),
  vesting_years: z.string().optional().transform((val) => (val ? parseInt(val, 10) : undefined)),
})

type AccountFormData = z.input<typeof accountSchema>

interface RetirementAccountFormProps {
  account?: RetirementAccount
  onSubmit: (data: z.output<typeof accountSchema>) => void
  isLoading?: boolean
  onCancel?: () => void
}

export default function RetirementAccountForm({
  account,
  onSubmit,
  isLoading,
  onCancel,
}: RetirementAccountFormProps) {
  const isEditMode = !!account

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<AccountFormData>({
    resolver: zodResolver(accountSchema),
    defaultValues: {
      account_type: account?.account_type ?? 'traditional_401k',
      account_name: account?.account_name,
      balance: account?.balance,
      expected_return_rate: account?.expected_return_rate
        ? String(parseFloat(account.expected_return_rate) * 100)
        : '7',
      employer_name: account?.employer_name ?? undefined,
      annual_salary: account?.annual_salary ?? undefined,
      employer_match_percent: account?.employer_match_percent
        ? String(parseFloat(account.employer_match_percent) * 100)
        : undefined,
      employer_match_limit_percent: account?.employer_match_limit_percent
        ? String(parseFloat(account.employer_match_limit_percent) * 100)
        : undefined,
      vesting_type: account?.vesting_type ?? undefined,
      vesting_years: account?.vesting_years ? String(account.vesting_years) : undefined,
    },
  })

  const accountType = watch('account_type')
  const isEmployerSponsored = FOUR_OH_ONE_K_TYPES.includes(accountType)

  // zodResolver runs the schema's .transform() at runtime, so the value handleSubmit
  // hands back is already the parsed z.output shape - the cast below just corrects the
  // type declaration to match, as in AccountForm/RecurringActionForm.
  const handleValidSubmit = handleSubmit((data) =>
    onSubmit(data as unknown as z.output<typeof accountSchema>)
  )

  return (
    <form onSubmit={handleValidSubmit} className="space-y-4">
      <Input
        label="Account Name"
        placeholder="My 401(k)"
        error={errors.account_name?.message}
        {...register('account_name')}
      />

      {isEditMode ? (
        <div>
          <div className="flex items-center gap-1.5">
            <p className="text-sm font-medium text-slate-700">Account Type</p>
            <InfoTooltip {...RETIREMENT_GLOSSARY[account.account_type as GlossaryKey]} />
          </div>
          <p className="text-sm text-slate-500">
            {ACCOUNT_TYPE_LABELS[account.account_type]} (can't be changed after creation)
          </p>
        </div>
      ) : (
        <Select
          label="Account Type"
          tooltip={<InfoTooltip {...RETIREMENT_GLOSSARY[accountType as GlossaryKey]} />}
          options={ACCOUNT_TYPE_OPTIONS}
          {...register('account_type')}
        />
      )}

      <Input
        label="Current Balance ($)"
        type="number"
        step="0.01"
        min="0"
        placeholder="20000"
        error={errors.balance?.message}
        {...register('balance')}
      />

      <Input
        label="Expected Annual Return (%)"
        tooltip={<InfoTooltip {...RETIREMENT_GLOSSARY.expected_return} />}
        type="number"
        step="0.01"
        min="0"
        max="100"
        placeholder="7"
        error={errors.expected_return_rate?.message}
        {...register('expected_return_rate')}
      />

      {isEmployerSponsored && (
        <div className="space-y-3 rounded-md border border-slate-200 p-4">
          <Input
            label="Employer Name"
            placeholder="Acme Corp"
            {...register('employer_name')}
          />
          <Input
            label="Annual Salary ($)"
            type="number"
            step="0.01"
            min="0"
            placeholder="120000"
            {...register('annual_salary')}
          />
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Employer Match (%)"
              tooltip={<InfoTooltip {...RETIREMENT_GLOSSARY.employer_match} />}
              type="number"
              step="0.01"
              min="0"
              max="100"
              placeholder="50"
              {...register('employer_match_percent')}
            />
            <Input
              label="Match Limit (% of Salary)"
              tooltip={<InfoTooltip {...RETIREMENT_GLOSSARY.match_limit} />}
              type="number"
              step="0.01"
              min="0"
              max="100"
              placeholder="6"
              {...register('employer_match_limit_percent')}
            />
          </div>
          <Select
            label="Vesting Schedule"
            tooltip={<InfoTooltip {...RETIREMENT_GLOSSARY.vesting_type} />}
            options={[
              { value: '', label: 'No vesting schedule (fully vested)' },
              { value: 'immediate', label: 'Immediate' },
              { value: 'cliff', label: 'Cliff' },
              { value: 'graded', label: 'Graded' },
            ]}
            {...register('vesting_type')}
          />
          <Input
            label="Vesting Years"
            type="number"
            min="1"
            max="10"
            placeholder="3"
            {...register('vesting_years')}
          />
        </div>
      )}

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
