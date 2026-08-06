/**
 * The Investments page's centerpiece: a price chart for one ticker at a time, defaulting
 * to the S&P 500 index (^GSPC) on mount - the only ticker ever loaded automatically, for
 * scalability (see docs/phase5-plan.md's Overview). A small search box lets the user look
 * up any other ticker, and five time-range buttons (1D/1M/3M/1Y/5Y) drive the fetched
 * period. Uses Recharts' AreaChart, matching this app's other chart components'
 * color/tooltip conventions (see components/charts/GrowthChart.tsx).
 */
import { useState, type FormEvent } from 'react'
import { Search } from 'lucide-react'
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { formatCurrency, formatDate } from '@/lib/utils'
import { useStockHistory, useStockPrice } from '../hooks/useInvestments'
import type { StockHistoryPeriod } from '@/types'

const DEFAULT_TICKER = '^GSPC'
const DEFAULT_TICKER_LABEL = 'S&P 500'

const RANGE_OPTIONS: { value: StockHistoryPeriod; label: string }[] = [
  { value: '1d', label: '1D' },
  { value: '1mo', label: '1M' },
  { value: '3mo', label: '3M' },
  { value: '1y', label: '1Y' },
  { value: '5y', label: '5Y' },
]

const CHART_COLOR = '#2a78d6'
const GRID_COLOR = '#e1e0d9'
const AXIS_COLOR = '#c3c2b7'

const tooltipStyle = {
  backgroundColor: 'white',
  border: '1px solid #e2e8f0',
  borderRadius: '8px',
  boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
}

export default function StockChart() {
  const [ticker, setTicker] = useState(DEFAULT_TICKER)
  const [searchValue, setSearchValue] = useState('')
  const [period, setPeriod] = useState<StockHistoryPeriod>('3mo')

  const { data: history, isLoading } = useStockHistory(ticker, period)
  const { data: priceInfo } = useStockPrice(ticker)

  const handleSearch = (e: FormEvent) => {
    e.preventDefault()
    const trimmed = searchValue.trim().toUpperCase()
    if (trimmed) {
      setTicker(trimmed)
    }
  }

  const chartData = (history?.data ?? []).map((point) => ({
    date: point.date,
    close: parseFloat(point.close),
  }))

  const displayTicker = ticker === DEFAULT_TICKER ? DEFAULT_TICKER_LABEL : ticker

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <form onSubmit={handleSearch} className="flex items-center gap-2">
          <div className="w-40">
            <Input
              placeholder="Search ticker..."
              value={searchValue}
              onChange={(e) => setSearchValue(e.target.value)}
            />
          </div>
          <Button type="submit" variant="outline" size="icon">
            <Search className="h-4 w-4" />
          </Button>
        </form>

        <div className="flex gap-1">
          {RANGE_OPTIONS.map((option) => (
            <button
              key={option.value}
              onClick={() => setPeriod(option.value)}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                period === option.value
                  ? 'bg-primary-600 text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      <div>
        <p className="text-lg font-semibold text-slate-900">{displayTicker}</p>
        {priceInfo?.price && (
          <p className="text-2xl font-bold text-slate-900">{formatCurrency(priceInfo.price)}</p>
        )}
      </div>

      {isLoading ? (
        <div className="flex h-72 items-center justify-center text-slate-400">Loading chart...</div>
      ) : chartData.length === 0 ? (
        <div className="flex h-72 items-center justify-center text-slate-400">
          No price data available for {displayTicker}
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={320}>
          <AreaChart data={chartData} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
            <defs>
              <linearGradient id="stockChartFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={CHART_COLOR} stopOpacity={0.3} />
                <stop offset="95%" stopColor={CHART_COLOR} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke={GRID_COLOR} />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11 }}
              tickLine={{ stroke: AXIS_COLOR }}
              axisLine={{ stroke: AXIS_COLOR }}
              tickFormatter={(value) => formatDate(value)}
              minTickGap={40}
            />
            <YAxis
              tick={{ fontSize: 12 }}
              tickLine={{ stroke: AXIS_COLOR }}
              axisLine={{ stroke: AXIS_COLOR }}
              domain={['auto', 'auto']}
              tickFormatter={(value) => formatCurrency(value)}
              width={80}
            />
            <Tooltip
              formatter={(value: number) => formatCurrency(value)}
              labelFormatter={(label) => formatDate(label)}
              contentStyle={tooltipStyle}
            />
            <Area
              type="monotone"
              dataKey="close"
              name="Close"
              stroke={CHART_COLOR}
              strokeWidth={2}
              fill="url(#stockChartFill)"
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
