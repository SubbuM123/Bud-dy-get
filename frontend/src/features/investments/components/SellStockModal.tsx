/**
 * Sell popup for a stock position - opened from StockPositionCard's "Sell" button. Asks
 * for shares and a sale price per share, live-previewing the realized P/L (a client-side
 * mirror of services/investment_calculator.calculate_realized_pnl) before the user
 * confirms, following LogIncomeModal.tsx's small-popup-with-live-preview shape.
 */
import { useEffect, useState } from 'react'
import { Modal } from '@/components/ui/modal'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { formatCurrency, getApiErrorMessage } from '@/lib/utils'
import { useSellStock } from '../hooks/useInvestments'
import type { StockPosition } from '@/types'

interface SellStockModalProps {
  position: StockPosition | null
  onClose: () => void
}

export default function SellStockModal({ position, onClose }: SellStockModalProps) {
  const sellStock = useSellStock()
  const [shares, setShares] = useState('')
  const [pricePerShare, setPricePerShare] = useState('')

  useEffect(() => {
    if (position) {
      setShares(position.shares)
      setPricePerShare(position.current_price ?? position.average_cost_per_share)
    }
  }, [position])

  if (!position) {
    return null
  }

  const sharesNum = parseFloat(shares) || 0
  const priceNum = parseFloat(pricePerShare) || 0
  const avgCost = parseFloat(position.average_cost_per_share)
  const previewPnl = (priceNum - avgCost) * sharesNum
  const exceedsHeld = sharesNum > parseFloat(position.shares)

  const handleConfirm = async () => {
    try {
      await sellStock.mutateAsync({
        positionId: position.id,
        data: { shares: sharesNum, price_per_share: priceNum },
      })
      onClose()
    } catch {
      // handled via sellStock.error below - keep the popup open so the user can retry
    }
  }

  return (
    <Modal open={!!position} onClose={onClose} title={`Sell ${position.ticker_symbol}`}>
      <div className="space-y-4">
        {sellStock.isError && (
          <div className="rounded-md bg-danger-500/10 p-3 text-sm text-danger-500">
            {getApiErrorMessage(sellStock.error, 'Failed to sell stock')}
          </div>
        )}

        <p className="text-xs text-slate-500">
          Currently holding {position.shares} shares @ {formatCurrency(position.average_cost_per_share)} avg cost.
        </p>

        <Input
          label="Shares to Sell"
          type="number"
          step="0.0001"
          min="0"
          value={shares}
          onChange={(e) => setShares(e.target.value)}
          error={exceedsHeld ? 'Cannot sell more shares than you hold' : undefined}
        />
        <Input
          label="Sale Price per Share ($)"
          type="number"
          step="0.01"
          min="0"
          value={pricePerShare}
          onChange={(e) => setPricePerShare(e.target.value)}
        />

        <div
          className={`rounded-md p-3 text-sm font-medium ${
            previewPnl >= 0 ? 'bg-success-500/10 text-success-600' : 'bg-danger-500/10 text-danger-500'
          }`}
        >
          Estimated {previewPnl >= 0 ? 'Gain' : 'Loss'}: {formatCurrency(previewPnl)}
        </div>

        <div className="flex gap-3 pt-2">
          <Button
            onClick={handleConfirm}
            disabled={sellStock.isPending || exceedsHeld || sharesNum <= 0}
          >
            {sellStock.isPending ? 'Selling...' : 'Confirm Sale'}
          </Button>
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
        </div>
      </div>
    </Modal>
  )
}
