/**
 * Form for creating or editing a bank account (name, type, principal, interest rate,
 * compounding frequency, and - for CDs - a start date, term length in months, and
 * auto-renew option), rendered inline on BankAccountsPage (create) and AccountDetailPage
 * (edit). A CD's term is entered as an explicit start date + duration rather than a
 * maturity date so the length used to schedule *renewals* is never ambiguous - see
 * backend/app/models/bank_accounts.py's BankAccount docstring for why a maturity-date-only
 * field was a real bug. Passing an `account` prop switches the form into edit mode: fields
 * are pre-filled, `account_type` becomes a read-only label (the backend's
 * BankAccountUpdate schema doesn't allow changing it after creation), and the submit
 * button reads "Save Changes". Validation and string-to-number coercion are handled by
 * the Zod schema so the parent page only deals with the fully parsed, typed output in its
 * onSubmit handler.
 */
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { addMonths, format } from 'date-fns'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import type { BankAccount } from '@/types'

// Raw form fields are strings (from <input>); transforms convert them to the numeric
// types the create/update-account API expects. Interest rate is entered as a whole-number
// percentage (e.g. 4.25) and converted to a decimal fraction (0.0425) here.
const accountSchema = z.object({
  account_name: z.string().min(1, 'Account name is required'),
  account_type: z.enum(['savings', 'checking', 'cd']),
  principal: z.string().transform((val) => parseFloat(val)),
  interest_rate: z.string().optional().transform((val) => (val ? parseFloat(val) / 100 : undefined)),
  compounding_frequency: z.enum(['daily', 'monthly', 'quarterly', 'annually']),
  cd_start_date: z.string().optional(),
  cd_term_months: z.string().optional().transform((val) => (val ? parseInt(val, 10) : undefined)),
  cd_auto_renew: z.boolean().optional(),
})

type AccountFormData = z.input<typeof accountSchema>

interface AccountFormProps {
  account?: BankAccount
  onSubmit: (data: z.output<typeof accountSchema>) => void
  isLoading?: boolean
  onCancel?: () => void
}

export default function AccountForm({ account, onSubmit, isLoading, onCancel }: AccountFormProps) {
  const isEditMode = !!account

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<AccountFormData>({
    resolver: zodResolver(accountSchema),
    defaultValues: {
      account_type: account?.account_type ?? 'savings',
      account_name: account?.account_name,
      principal: account?.principal,
      interest_rate: account?.interest_rate
        ? String(parseFloat(account.interest_rate) * 100)
        : undefined,
      compounding_frequency: account?.compounding_frequency ?? 'monthly',
      cd_start_date: account?.cd_start_date ?? format(new Date(), 'yyyy-MM-dd'),
      cd_term_months: account?.cd_term_months ? String(account.cd_term_months) : undefined,
      cd_auto_renew: account?.cd_auto_renew ?? false,
    },
  })

  const accountType = watch('account_type')
  const cdStartDate = watch('cd_start_date')
  const cdTermMonths = watch('cd_term_months')

  // zodResolver runs the schema's .transform() at runtime, so the value handleSubmit
  // hands back is already the parsed z.output shape (numbers, not strings) - the cast
  // below just corrects the type declaration to match, since @hookform/resolvers'
  // installed types don't propagate transformed output types.
  const handleValidSubmit = handleSubmit((data) => onSubmit(data as unknown as z.output<typeof accountSchema>))

  return (
    <form onSubmit={handleValidSubmit} className="space-y-4">
      <Input
        label="Account Name"
        placeholder="My Savings Account"
        error={errors.account_name?.message}
        {...register('account_name')}
      />

      {isEditMode ? (
        <div>
          <p className="text-sm font-medium text-slate-700">Account Type</p>
          <p className="text-sm text-slate-500 capitalize">
            {account.account_type} (can't be changed after creation)
          </p>
        </div>
      ) : (
        <Select
          label="Account Type"
          options={[
            { value: 'savings', label: 'Savings' },
            { value: 'checking', label: 'Checking' },
            { value: 'cd', label: 'Certificate of Deposit (CD)' },
          ]}
          {...register('account_type')}
        />
      )}

      <Input
        label="Principal Amount ($)"
        type="number"
        step="0.01"
        min="0"
        placeholder="10000"
        error={errors.principal?.message}
        {...register('principal')}
      />

      <Input
        label="Interest Rate (% APY)"
        type="number"
        step="0.01"
        min="0"
        max="100"
        placeholder="4.25"
        error={errors.interest_rate?.message}
        {...register('interest_rate')}
      />

      <Select
        label="Compounding Frequency"
        options={[
          { value: 'daily', label: 'Daily' },
          { value: 'monthly', label: 'Monthly' },
          { value: 'quarterly', label: 'Quarterly' },
          { value: 'annually', label: 'Annually' },
        ]}
        {...register('compounding_frequency')}
      />

      {accountType === 'cd' && (
        <div className="space-y-3 rounded-md border border-slate-200 p-4">
          <Input
            label="CD Start Date"
            type="date"
            error={errors.cd_start_date?.message}
            {...register('cd_start_date')}
          />
          <Input
            label="Term Length (months)"
            type="number"
            min="1"
            max="600"
            placeholder="36"
            error={errors.cd_term_months?.message}
            {...register('cd_term_months')}
          />
          {cdStartDate && cdTermMonths && !isNaN(parseInt(cdTermMonths, 10)) && (
            <p className="text-sm text-slate-500">
              Matures {format(addMonths(new Date(`${cdStartDate}T00:00:00`), parseInt(cdTermMonths, 10)), 'MMM d, yyyy')}
              {' '}- this is also the term length used every time the CD renews.
            </p>
          )}
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              className="rounded border-slate-300"
              {...register('cd_auto_renew')}
            />
            <span className="text-sm">
              Keep CDing this money after maturity (roll into a new CD term instead of
              moving to savings)
            </span>
          </label>
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
