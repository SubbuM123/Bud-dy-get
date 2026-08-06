/**
 * Stock Portfolio page at /stocks: the price chart (S&P 500 default, ticker search,
 * 1D/1M/3M/1Y/5Y ranges) plus buying/selling individual stock positions. Split out of a
 * single combined Investments page into its own page because cramming stocks, bonds, and
 * property onto one screen made the UI too busy - see docs/progress.md's 2026-08-04
 * "Phase 5 UI split" entry. Bonds and property investments live on
 * pages/InvestmentsPage.tsx instead. This page is deliberately named for a future merge
 * with options trading once that's built (see components/layout/Sidebar.tsx).
 */
import { useState } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import StockChart from '../components/StockChart'
import BuyStockForm from '../components/BuyStockForm'
import StockPositionCard from '../components/StockPositionCard'
import SellStockModal from '../components/SellStockModal'
import { useStockPositions } from '../hooks/useInvestments'
import type { StockPosition } from '@/types'

export default function StockPortfolioPage() {
  const { data: positions, isLoading } = useStockPositions()
  const [sellingPosition, setSellingPosition] = useState<StockPosition | null>(null)

  const heldPositions = (positions ?? []).filter((p) => parseFloat(p.shares) > 0)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Stock Portfolio</h1>
        <p className="text-slate-500">Track prices, buy, and sell individual stock positions</p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Card>
            <CardContent className="pt-6">
              <StockChart />
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Buy Stock</CardTitle>
          </CardHeader>
          <CardContent>
            <BuyStockForm />
          </CardContent>
        </Card>
      </div>

      <div className="space-y-3">
        <h2 className="text-lg font-semibold text-slate-900">Your Holdings</h2>
        {isLoading ? (
          <p className="text-sm text-slate-500">Loading...</p>
        ) : heldPositions.length === 0 ? (
          <p className="text-sm text-slate-500">No stock holdings yet - buy your first above.</p>
        ) : (
          <div className="flex gap-6 overflow-x-auto pb-2">
            {heldPositions.map((position) => (
              <div key={position.id} className="w-72 flex-shrink-0">
                <StockPositionCard position={position} onSell={setSellingPosition} />
              </div>
            ))}
          </div>
        )}
      </div>

      <SellStockModal position={sellingPosition} onClose={() => setSellingPosition(null)} />
    </div>
  )
}
