/**
 * "Buy Stock" panel on InvestmentsPage: ticker + shares + cost, with an optional "which
 * bank account is this coming from" selector - the same "where is this money coming from"
 * pattern retirement/education's ContributionForm already uses. Submitting chains two
 * calls - get-or-create the StockPosition for this ticker (see api.ts's
 * createStockPosition), then record the buy against it - so from the user's perspective
 * this is one action, even though the backend models it as create-then-buy (mirroring how
 * a retirement account is created once, then contributed to repeatedly).
 */
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { useBankAccounts } from '@/features/bank-accounts/hooks/useBankAccounts'
import { useCreateStockPosition, useBuyStock } from '../hooks/useInvestments'
import { getApiErrorMessage } from '@/lib/utils'

const buyStockSchema = z.object({
  ticker_symbol: z.string().min(1, 'Ticker is required').max(10),
  shares: z.coerce.number().gt(0, 'Must be greater than 0'),
  price_per_share: z.coerce.number().gt(0, 'Must be greater than 0'),
  source_bank_account_id: z.string().optional(),
})

type BuyStockFormData = z.infer<typeof buyStockSchema>

export default function BuyStockForm() {
  const { data: bankAccounts } = useBankAccounts()
  const createPosition = useCreateStockPosition()
  const buyStock = useBuyStock()

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<BuyStockFormData>({ resolver: zodResolver(buyStockSchema) })

  const isLoading = createPosition.isPending || buyStock.isPending
  const error = createPosition.error ?? buyStock.error

  const onSubmit = handleSubmit(async (data) => {
    try {
      const position = await createPosition.mutateAsync(data.ticker_symbol)
      await buyStock.mutateAsync({
        positionId: position.id,
        data: {
          shares: data.shares,
          price_per_share: data.price_per_share,
          source_bank_account_id: data.source_bank_account_id || undefined,
        },
      })
      reset()
    } catch {
      // handled via createPosition.error / buyStock.error below
    }
  })

  return (
    <form onSubmit={onSubmit} className="space-y-3">
      {error && (
        <div className="rounded-md bg-danger-500/10 p-2.5 text-xs text-danger-500">
          {getApiErrorMessage(error, 'Failed to buy stock')}
        </div>
      )}

      <Input
        label="Ticker Symbol"
        placeholder="AAPL"
        error={errors.ticker_symbol?.message}
        {...register('ticker_symbol')}
      />
      <div className="grid grid-cols-2 gap-2">
        <Input
          label="Shares"
          type="number"
          step="0.0001"
          min="0"
          error={errors.shares?.message}
          {...register('shares')}
        />
        <Input
          label="Cost per Share ($)"
          type="number"
          step="0.01"
          min="0"
          error={errors.price_per_share?.message}
          {...register('price_per_share')}
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

      <Button type="submit" size="sm" disabled={isLoading}>
        {isLoading ? 'Buying...' : 'Buy Stock'}
      </Button>
    </form>
  )
}
