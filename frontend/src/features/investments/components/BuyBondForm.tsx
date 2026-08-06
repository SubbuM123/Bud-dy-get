/**
 * "Buy Bond" panel on InvestmentsPage: a simpler schema than stocks - purchase price,
 * face value, coupon rate, payment frequency, purchase/maturity dates, and the same
 * optional "which bank account is this coming from" selector BuyStockForm uses. Backing
 * these numbers is the straight-line amortization schedule computed server-side (see
 * services/investment_calculator.py) and viewable per-bond via AmortizationScheduleModal.
 */
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { useBankAccounts } from '@/features/bank-accounts/hooks/useBankAccounts'
import { useCreateBondHolding } from '../hooks/useInvestments'
import { getApiErrorMessage } from '@/lib/utils'

const buyBondSchema = z
  .object({
    name: z.string().min(1, 'Name is required').max(255),
    purchase_price: z.coerce.number().gt(0, 'Must be greater than 0'),
    face_value: z.coerce.number().gt(0, 'Must be greater than 0'),
    coupon_rate: z.coerce.number().min(0).max(1),
    payment_frequency: z.enum(['annually', 'semi_annually']),
    purchase_date: z.string().min(1, 'Purchase date is required'),
    maturity_date: z.string().min(1, 'Maturity date is required'),
    source_bank_account_id: z.string().optional(),
  })
  .superRefine((val, ctx) => {
    if (val.maturity_date <= val.purchase_date) {
      ctx.addIssue({
        code: 'custom',
        path: ['maturity_date'],
        message: 'Maturity date must be after purchase date',
      })
    }
  })

type BuyBondFormData = z.infer<typeof buyBondSchema>

export default function BuyBondForm() {
  const { data: bankAccounts } = useBankAccounts()
  const createBond = useCreateBondHolding()

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<BuyBondFormData>({
    resolver: zodResolver(buyBondSchema),
    defaultValues: { payment_frequency: 'semi_annually', coupon_rate: 0.05 },
  })

  const onSubmit = handleSubmit(async (data) => {
    try {
      await createBond.mutateAsync({
        name: data.name,
        purchase_price: data.purchase_price,
        face_value: data.face_value,
        coupon_rate: data.coupon_rate,
        payment_frequency: data.payment_frequency,
        purchase_date: data.purchase_date,
        maturity_date: data.maturity_date,
        source_bank_account_id: data.source_bank_account_id || undefined,
      })
      reset()
    } catch {
      // handled via createBond.error below
    }
  })

  return (
    <form onSubmit={onSubmit} className="space-y-3">
      {createBond.isError && (
        <div className="rounded-md bg-danger-500/10 p-2.5 text-xs text-danger-500">
          {getApiErrorMessage(createBond.error, 'Failed to buy bond')}
        </div>
      )}

      <Input label="Name" placeholder="US Treasury 2030" error={errors.name?.message} {...register('name')} />
      <div className="grid grid-cols-2 gap-2">
        <Input
          label="Purchase Price ($)"
          type="number"
          step="0.01"
          min="0"
          error={errors.purchase_price?.message}
          {...register('purchase_price')}
        />
        <Input
          label="Face Value ($)"
          type="number"
          step="0.01"
          min="0"
          error={errors.face_value?.message}
          {...register('face_value')}
        />
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Input
          label="Coupon Rate"
          type="number"
          step="0.001"
          min="0"
          max="1"
          error={errors.coupon_rate?.message}
          {...register('coupon_rate')}
        />
        <Select
          label="Payment Frequency"
          options={[
            { value: 'semi_annually', label: 'Semi-annually' },
            { value: 'annually', label: 'Annually' },
          ]}
          {...register('payment_frequency')}
        />
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Input
          label="Purchase Date"
          type="date"
          error={errors.purchase_date?.message}
          {...register('purchase_date')}
        />
        <Input
          label="Maturity Date"
          type="date"
          error={errors.maturity_date?.message}
          {...register('maturity_date')}
        />
      </div>
      <Select
        label="Funding Source (optional)"
        options={[
          { value: '', label: 'Not tracked' },
          ...(bankAccounts ?? []).map((a) => ({ value: a.id, label: a.account_name })),
        ]}
        {...register('source_bank_account_id')}
      />

      <Button type="submit" size="sm" disabled={createBond.isPending}>
        {createBond.isPending ? 'Buying...' : 'Buy Bond'}
      </Button>
    </form>
  )
}
