/**
 * Summary card for a single stock position, shown in the card strip on InvestmentsPage.
 * Displays shares held, average cost, cached market value/unrealized P/L (both null until
 * a price has been fetched - see StockPositionResponse's docstring), and a Sell action -
 * no direct edit/delete the way retirement/education account cards have, since a stock
 * position's numbers only ever change through buy/sell/RSU-vest events, not a manual PUT.
 */
import { Trash2 } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { formatCurrency } from '@/lib/utils'
import { useDeleteStockPosition } from '../hooks/useInvestments'
import type { StockPosition } from '@/types'

interface StockPositionCardProps {
  position: StockPosition
  onSell: (position: StockPosition) => void
}

export default function StockPositionCard({ position, onSell }: StockPositionCardProps) {
  const deletePosition = useDeleteStockPosition()
  const shares = parseFloat(position.shares)
  const unrealizedPnl = position.unrealized_pnl ? parseFloat(position.unrealized_pnl) : null

  const handleDelete = () => {
    if (window.confirm(`Remove ${position.ticker_symbol} from your holdings?`)) {
      deletePosition.mutate(position.id)
    }
  }

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardHeader className="flex flex-row items-start justify-between">
        <CardTitle className="text-base">{position.ticker_symbol}</CardTitle>
        {position.is_simulation && (
          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
            Simulation
          </span>
        )}
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          <div>
            <p className="text-sm text-slate-500">Shares</p>
            <p className="text-2xl font-bold text-slate-900">{shares.toLocaleString()}</p>
          </div>

          <div className="text-sm">
            <p className="text-slate-500">Average Cost</p>
            <p className="font-medium">{formatCurrency(position.average_cost_per_share)}</p>
          </div>

          {position.market_value !== null && (
            <div className="text-sm">
              <p className="text-slate-500">Market Value</p>
              <p className="font-medium">{formatCurrency(position.market_value)}</p>
              {unrealizedPnl !== null && (
                <p className={unrealizedPnl >= 0 ? 'text-success-600' : 'text-danger-500'}>
                  {unrealizedPnl >= 0 ? '+' : ''}
                  {formatCurrency(unrealizedPnl)} unrealized
                </p>
              )}
            </div>
          )}

          <div className="flex items-center justify-between pt-3 border-t">
            <Button variant="outline" size="sm" onClick={() => onSell(position)} disabled={shares <= 0}>
              Sell
            </Button>
            {shares === 0 && (
              <Button
                variant="ghost"
                size="icon"
                className="text-slate-400 hover:text-danger-500"
                onClick={handleDelete}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
