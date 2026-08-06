/**
 * Sell popup for a bond holding - opened from BondHoldingCard's "Sell" button. A bond is
 * sold whole (no partial-shares concept, unlike a stock), so this only asks for a selling
 * price, previewing the realized P/L against the bond's purchase_price before confirming.
 */
import { useEffect, useState } from 'react'
import { Modal } from '@/components/ui/modal'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { formatCurrency, getApiErrorMessage } from '@/lib/utils'
import { useSellBondHolding } from '../hooks/useInvestments'
import type { BondHolding } from '@/types'

interface SellBondModalProps {
  bond: BondHolding | null
  onClose: () => void
}

export default function SellBondModal({ bond, onClose }: SellBondModalProps) {
  const sellBond = useSellBondHolding()
  const [salePrice, setSalePrice] = useState('')

  useEffect(() => {
    if (bond) {
      setSalePrice(bond.current_book_value)
    }
  }, [bond])

  if (!bond) {
    return null
  }

  const salePriceNum = parseFloat(salePrice) || 0
  const previewPnl = salePriceNum - parseFloat(bond.purchase_price)

  const handleConfirm = async () => {
    try {
      await sellBond.mutateAsync({ id: bond.id, data: { sale_price: salePriceNum } })
      onClose()
    } catch {
      // handled via sellBond.error below
    }
  }

  return (
    <Modal open={!!bond} onClose={onClose} title={`Sell ${bond.name}`}>
      <div className="space-y-4">
        {sellBond.isError && (
          <div className="rounded-md bg-danger-500/10 p-3 text-sm text-danger-500">
            {getApiErrorMessage(sellBond.error, 'Failed to sell bond')}
          </div>
        )}

        <p className="text-xs text-slate-500">
          Purchased for {formatCurrency(bond.purchase_price)}, current book value{' '}
          {formatCurrency(bond.current_book_value)}.
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
          <Button onClick={handleConfirm} disabled={sellBond.isPending || salePriceNum <= 0}>
            {sellBond.isPending ? 'Selling...' : 'Confirm Sale'}
          </Button>
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
        </div>
      </div>
    </Modal>
  )
}
