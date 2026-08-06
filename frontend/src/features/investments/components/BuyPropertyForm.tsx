/**
 * "Buy Property" panel on InvestmentsPage: the simplest schema in this module - name,
 * cost, and an expected annual return rate driving compound-growth projection (see
 * services/investment_calculator.calculate_property_current_value), plus the same
 * optional bank-account funding source BuyStockForm/BuyBondForm use.
 */
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { useBankAccounts } from '@/features/bank-accounts/hooks/useBankAccounts'
import { useCreatePropertyInvestment } from '../hooks/useInvestments'
import { getApiErrorMessage } from '@/lib/utils'

const buyPropertySchema = z.object({
  name: z.string().min(1, 'Name is required').max(255),
  cost: z.coerce.number().gt(0, 'Must be greater than 0'),
  expected_return_rate: z.coerce.number().min(0).max(1),
  purchase_date: z.string().min(1, 'Purchase date is required'),
  source_bank_account_id: z.string().optional(),
})

type BuyPropertyFormData = z.infer<typeof buyPropertySchema>

export default function BuyPropertyForm() {
  const { data: bankAccounts } = useBankAccounts()
  const createProperty = useCreatePropertyInvestment()

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<BuyPropertyFormData>({
    resolver: zodResolver(buyPropertySchema),
    defaultValues: { expected_return_rate: 0.05 },
  })

  const onSubmit = handleSubmit(async (data) => {
    try {
      await createProperty.mutateAsync({
        name: data.name,
        cost: data.cost,
        expected_return_rate: data.expected_return_rate,
        purchase_date: data.purchase_date,
        source_bank_account_id: data.source_bank_account_id || undefined,
      })
      reset()
    } catch {
      // handled via createProperty.error below
    }
  })

  return (
    <form onSubmit={onSubmit} className="space-y-3">
      {createProperty.isError && (
        <div className="rounded-md bg-danger-500/10 p-2.5 text-xs text-danger-500">
          {getApiErrorMessage(createProperty.error, 'Failed to buy property investment')}
        </div>
      )}

      <Input
        label="Name"
        placeholder="Rental Duplex"
        error={errors.name?.message}
        {...register('name')}
      />
      <div className="grid grid-cols-2 gap-2">
        <Input
          label="Cost ($)"
          type="number"
          step="0.01"
          min="0"
          error={errors.cost?.message}
          {...register('cost')}
        />
        <Input
          label="Expected Annual Return"
          type="number"
          step="0.001"
          min="0"
          max="1"
          error={errors.expected_return_rate?.message}
          {...register('expected_return_rate')}
        />
      </div>
      <Input
        label="Purchase Date"
        type="date"
        error={errors.purchase_date?.message}
        {...register('purchase_date')}
      />
      <Select
        label="Funding Source (optional)"
        options={[
          { value: '', label: 'Not tracked' },
          ...(bankAccounts ?? []).map((a) => ({ value: a.id, label: a.account_name })),
        ]}
        {...register('source_bank_account_id')}
      />

      <Button type="submit" size="sm" disabled={createProperty.isPending}>
        {createProperty.isPending ? 'Buying...' : 'Buy Property'}
      </Button>
    </form>
  )
}
