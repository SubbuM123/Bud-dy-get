/**
 * Summary card for a single property investment, shown in the card strip on
 * InvestmentsPage. Mirrors BondHoldingCard.tsx's shape minus the amortization link -
 * property has no face-value-at-maturity concept, just compound-growth projection (see
 * services/investment_calculator.calculate_property_current_value).
 */
import { Trash2 } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { formatCurrency, formatPercent } from '@/lib/utils'
import { useDeletePropertyInvestment } from '../hooks/useInvestments'
import type { PropertyInvestment } from '@/types'

interface PropertyInvestmentCardProps {
  property: PropertyInvestment
  onSell: (property: PropertyInvestment) => void
}

export default function PropertyInvestmentCard({ property, onSell }: PropertyInvestmentCardProps) {
  const deleteProperty = useDeletePropertyInvestment()

  const handleDelete = () => {
    if (window.confirm(`Remove ${property.name} from your holdings?`)) {
      deleteProperty.mutate(property.id)
    }
  }

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardHeader className="flex flex-row items-start justify-between">
        <CardTitle className="text-base">{property.name}</CardTitle>
        {!property.is_active && (
          <span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs font-medium text-slate-600">
            Sold
          </span>
        )}
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          <div>
            <p className="text-sm text-slate-500">
              {property.is_active ? 'Estimated Value' : 'Sold For'}
            </p>
            <p className="text-2xl font-bold text-slate-900">
              {formatCurrency(property.is_active ? property.current_value : property.sale_price ?? '0')}
            </p>
          </div>

          <div className="text-sm space-y-1">
            <p className="text-slate-500">Purchased for {formatCurrency(property.cost)}</p>
            <p className="text-slate-500">
              {formatPercent(property.expected_return_rate)} expected annual return
            </p>
            {!property.is_active && property.realized_pnl && (
              <p className={parseFloat(property.realized_pnl) >= 0 ? 'text-success-600' : 'text-danger-500'}>
                {parseFloat(property.realized_pnl) >= 0 ? '+' : ''}
                {formatCurrency(property.realized_pnl)} realized
              </p>
            )}
          </div>

          <div className="flex items-center justify-between pt-3 border-t">
            {property.is_active ? (
              <Button variant="outline" size="sm" onClick={() => onSell(property)}>
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
