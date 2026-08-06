/**
 * Summary card for a single bond holding, shown in the card strip on InvestmentsPage.
 * Displays purchase price/face value/current book value, a "View Amortization Schedule"
 * link (opens AmortizationScheduleModal), and Sell/Delete actions - Sell only offered
 * while `is_active`, matching how BondHolding stores its terminal sale state inline
 * rather than via a side transactions table (see models/investments.py's docstring).
 */
import { Trash2 } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { formatCurrency, formatPercent, formatDate } from '@/lib/utils'
import { useDeleteBondHolding } from '../hooks/useInvestments'
import type { BondHolding } from '@/types'

interface BondHoldingCardProps {
  bond: BondHolding
  onSell: (bond: BondHolding) => void
  onViewSchedule: (bond: BondHolding) => void
}

export default function BondHoldingCard({ bond, onSell, onViewSchedule }: BondHoldingCardProps) {
  const deleteBond = useDeleteBondHolding()

  const handleDelete = () => {
    if (window.confirm(`Remove ${bond.name} from your holdings?`)) {
      deleteBond.mutate(bond.id)
    }
  }

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardHeader className="flex flex-row items-start justify-between">
        <CardTitle className="text-base">{bond.name}</CardTitle>
        {!bond.is_active && (
          <span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs font-medium text-slate-600">
            Sold
          </span>
        )}
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          <div>
            <p className="text-sm text-slate-500">
              {bond.is_active ? 'Current Book Value' : 'Sold For'}
            </p>
            <p className="text-2xl font-bold text-slate-900">
              {formatCurrency(bond.is_active ? bond.current_book_value : bond.sale_price ?? '0')}
            </p>
          </div>

          <div className="text-sm space-y-1">
            <p className="text-slate-500">
              Purchased {formatCurrency(bond.purchase_price)}, face value {formatCurrency(bond.face_value)}
            </p>
            <p className="text-slate-500">
              {formatPercent(bond.coupon_rate)} coupon, matures {formatDate(bond.maturity_date)}
            </p>
            {!bond.is_active && bond.realized_pnl && (
              <p className={parseFloat(bond.realized_pnl) >= 0 ? 'text-success-600' : 'text-danger-500'}>
                {parseFloat(bond.realized_pnl) >= 0 ? '+' : ''}
                {formatCurrency(bond.realized_pnl)} realized
              </p>
            )}
          </div>

          <button
            onClick={() => onViewSchedule(bond)}
            className="text-sm font-medium text-primary-600 hover:underline"
          >
            View Amortization Schedule
          </button>

          <div className="flex items-center justify-between pt-3 border-t">
            {bond.is_active ? (
              <Button variant="outline" size="sm" onClick={() => onSell(bond)}>
                Sell
              </Button>
            ) : (
              <span />
            )}
            <Button
              variant="ghost"
              size="icon"
              className="text-slate-400 hover:text-danger-500"
              onClick={handleDelete}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
