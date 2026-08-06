/**
 * Investments hub at /investments: bonds and property investments - buy panels side by
 * side, holdings below. Stock positions moved to pages/StockPortfolioPage.tsx (/stocks) -
 * see that page's docstring and docs/progress.md's 2026-08-04 "Phase 5 UI split" entry
 * for why the three asset types were split across two pages instead of one crowded page.
 */
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import BuyBondForm from '../components/BuyBondForm'
import BuyPropertyForm from '../components/BuyPropertyForm'
import BondHoldingCard from '../components/BondHoldingCard'
import PropertyInvestmentCard from '../components/PropertyInvestmentCard'
import SellBondModal from '../components/SellBondModal'
import SellPropertyModal from '../components/SellPropertyModal'
import AmortizationScheduleModal from '../components/AmortizationScheduleModal'
import { useBondHoldings, usePropertyInvestments } from '../hooks/useInvestments'
import type { BondHolding, PropertyInvestment } from '@/types'

export default function InvestmentsPage() {
  const { data: bonds, isLoading: bondsLoading } = useBondHoldings()
  const { data: properties, isLoading: propertiesLoading } = usePropertyInvestments()

  const [sellingBond, setSellingBond] = useState<BondHolding | null>(null)
  const [sellingProperty, setSellingProperty] = useState<PropertyInvestment | null>(null)
  const [viewingSchedule, setViewingSchedule] = useState<BondHolding | null>(null)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Investments</h1>
        <p className="text-slate-500">
          Bonds and property - buy, sell, and track it all in one place. Looking for stocks?
          Visit <Link to="/stocks" className="font-medium text-primary-600 hover:underline">Stock Portfolio</Link>.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Buy Bond</CardTitle>
          </CardHeader>
          <CardContent>
            <BuyBondForm />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Buy Property</CardTitle>
          </CardHeader>
          <CardContent>
            <BuyPropertyForm />
          </CardContent>
        </Card>
      </div>

      <div className="space-y-3">
        <h2 className="text-lg font-semibold text-slate-900">Bonds</h2>
        {bondsLoading ? (
          <p className="text-sm text-slate-500">Loading...</p>
        ) : (bonds ?? []).length === 0 ? (
          <p className="text-sm text-slate-500">No bond holdings yet - buy your first above.</p>
        ) : (
          <div className="flex gap-6 overflow-x-auto pb-2">
            {(bonds ?? []).map((bond) => (
              <div key={bond.id} className="w-72 flex-shrink-0">
                <BondHoldingCard bond={bond} onSell={setSellingBond} onViewSchedule={setViewingSchedule} />
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="space-y-3">
        <h2 className="text-lg font-semibold text-slate-900">Property Investments</h2>
        {propertiesLoading ? (
          <p className="text-sm text-slate-500">Loading...</p>
        ) : (properties ?? []).length === 0 ? (
          <p className="text-sm text-slate-500">No property investments yet - buy your first above.</p>
        ) : (
          <div className="flex gap-6 overflow-x-auto pb-2">
            {(properties ?? []).map((property) => (
              <div key={property.id} className="w-72 flex-shrink-0">
                <PropertyInvestmentCard property={property} onSell={setSellingProperty} />
              </div>
            ))}
          </div>
        )}
      </div>

      <SellBondModal bond={sellingBond} onClose={() => setSellingBond(null)} />
      <SellPropertyModal property={sellingProperty} onClose={() => setSellingProperty(null)} />
      <AmortizationScheduleModal bond={viewingSchedule} onClose={() => setViewingSchedule(null)} />
    </div>
  )
}
