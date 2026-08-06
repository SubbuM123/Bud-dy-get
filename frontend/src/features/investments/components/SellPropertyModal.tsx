/**
 * Sell popup for a property investment - opened from PropertyInvestmentCard's "Sell"
 * button. Mirrors SellBondModal.tsx exactly (a property is also sold whole, no partial
 * concept), just against `cost` instead of `purchase_price`.
 */
import { useEffect, useState } from 'react'
import { Modal } from '@/components/ui/modal'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { formatCurrency, getApiErrorMessage } from '@/lib/utils'
import { useSellPropertyInvestment } from '../hooks/useInvestments'
import type { PropertyInvestment } from '@/types'

interface SellPropertyModalProps {
  property: PropertyInvestment | null
  onClose: () => void
}

export default function SellPropertyModal({ property, onClose }: SellPropertyModalProps) {
  const sellProperty = useSellPropertyInvestment()
  const [salePrice, setSalePrice] = useState('')

  useEffect(() => {
    if (property) {
      setSalePrice(property.current_value)
    }
  }, [property])

  if (!property) {
    return null
  }

  const salePriceNum = parseFloat(salePrice) || 0
  const previewPnl = salePriceNum - parseFloat(property.cost)

  const handleConfirm = async () => {
    try {
      await sellProperty.mutateAsync({ id: property.id, data: { sale_price: salePriceNum } })
      onClose()
    } catch {
      // handled via sellProperty.error below
    }
  }

  return (
    <Modal open={!!property} onClose={onClose} title={`Sell ${property.name}`}>
      <div className="space-y-4">
        {sellProperty.isError && (
          <div className="rounded-md bg-danger-500/10 p-3 text-sm text-danger-500">
            {getApiErrorMessage(sellProperty.error, 'Failed to sell property investment')}
          </div>
        )}

        <p className="text-xs text-slate-500">
          Purchased for {formatCurrency(property.cost)}, current estimated value{' '}
          {formatCurrency(property.current_value)}.
        </p>

        <Input
          label="Selling Price ($)"
          type="number"
          step="0.01"
          min="0"
          value={salePrice}
          onChange={(e) => setSalePrice(e.target.value)}
        />

        <div
          className={`rounded-md p-3 text-sm font-medium ${
            previewPnl >= 0 ? 'bg-success-500/10 text-success-600' : 'bg-danger-500/10 text-danger-500'
          }`}
        >
          Estimated {previewPnl >= 0 ? 'Gain' : 'Loss'}: {formatCurrency(previewPnl)}
        </div>

        <div className="flex gap-3 pt-2">
          <Button onClick={handleConfirm} disabled={sellProperty.isPending || salePriceNum <= 0}>
            {sellProperty.isPending ? 'Selling...' : 'Confirm Sale'}
          </Button>
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
        </div>
      </div>
    </Modal>
  )
}
