/**
 * Form for the profile fields services/retirement_rules.py needs to compute real
 * contribution limits: birth_date (age-based catch-up eligibility), filing_status +
 * annual_income (Roth IRA income phaseout, Traditional IRA deductibility), and
 * has_employer_retirement_plan (also feeds Traditional IRA deductibility). Rendered inline
 * on RetirementAccountsPage above the account list - without these set, limit
 * calculations fall back to conservative defaults (see backend's
 * _age_from_birth_date/age 30 default) rather than being wrong for a real user.
 */
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { InfoTooltip } from '@/components/ui/info-tooltip'
import { RETIREMENT_GLOSSARY } from '../glossary'
import type { UserProfile } from '@/types'

const profileSchema = z.object({
  birth_date: z.string().optional(),
  filing_status: z.preprocess(
    (val) => (val === '' ? undefined : val),
    z
      .enum(['single', 'married_filing_jointly', 'married_filing_separately', 'head_of_household'])
      .optional()
  ),
  annual_income: z.string().optional().transform((val) => (val ? parseFloat(val) : undefined)),
  has_employer_retirement_plan: z.boolean().optional(),
})

type ProfileFormData = z.input<typeof profileSchema>

interface ProfileFormProps {
  profile?: UserProfile
  onSubmit: (data: z.output<typeof profileSchema>) => void
  isLoading?: boolean
  onCancel?: () => void
}

export default function ProfileForm({ profile, onSubmit, isLoading, onCancel }: ProfileFormProps) {
  const {
    register,
    handleSubmit,
  } = useForm<ProfileFormData>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      birth_date: profile?.birth_date ?? undefined,
      filing_status: profile?.filing_status ?? undefined,
      annual_income: profile?.annual_income ?? undefined,
      has_employer_retirement_plan: profile?.has_employer_retirement_plan ?? false,
    },
  })

  const handleValidSubmit = handleSubmit((data) =>
    onSubmit(data as unknown as z.output<typeof profileSchema>)
  )

  return (
    <form onSubmit={handleValidSubmit} className="space-y-4">
      <p className="text-sm text-slate-500">
        Used to compute your real 2026 contribution limits and Roth/Traditional IRA
        eligibility - not shared outside this app.
      </p>

      <Input label="Birth Date" type="date" {...register('birth_date')} />

      <Select
        label="Tax Filing Status"
        tooltip={<InfoTooltip {...RETIREMENT_GLOSSARY.filing_status} />}
        options={[
          { value: '', label: 'Not set' },
          { value: 'single', label: 'Single' },
          { value: 'married_filing_jointly', label: 'Married Filing Jointly' },
          { value: 'married_filing_separately', label: 'Married Filing Separately' },
          { value: 'head_of_household', label: 'Head of Household' },
        ]}
        {...register('filing_status')}
      />

      <Input
        label="Annual Income (MAGI, $)"
        tooltip={<InfoTooltip {...RETIREMENT_GLOSSARY.magi} />}
        type="number"
        step="0.01"
        min="0"
        placeholder="120000"
        {...register('annual_income')}
      />

      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          className="rounded border-slate-300"
          {...register('has_employer_retirement_plan')}
        />
        <span className="text-sm">I'm covered by an employer retirement plan</span>
        <InfoTooltip
          title="Employer Retirement Plan"
          content="Being covered by a workplace plan (like a 401(k)) - even if you don't contribute to it - can reduce or eliminate how much of a Traditional IRA contribution is tax-deductible."
        />
      </label>

      <div className="flex gap-3 pt-2">
        <Button type="submit" disabled={isLoading}>
          {isLoading ? 'Saving...' : 'Save Profile'}
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
