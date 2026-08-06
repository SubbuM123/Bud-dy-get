/**
 * Recharts line chart for the dashboard's combined simulation: one line per account (or
 * CD renewal segment / synthesized savings bucket) plus a bold "Total" line, sharing one
 * month-indexed dataset built from CombinedSimulationResponse. Series beyond the eight
 * validated categorical color slots are folded into a single "Other accounts" line
 * (summed) rather than cycling or generating new hues. Consumed by
 * CombinedSimulationSection with data from POST /bank-accounts/simulate-combined.
 *
 * Bug fixed here: a CD renewal segment's first projection point duplicates the prior
 * segment's last point (the same money, carried over at rollover - see
 * backend/app/services/combined_simulator.py). The "Other accounts" fold used to sum
 * every overflow series' point at each month without accounting for that duplicate,
 * so once enough renewals pushed a CD's segments into the overflow bucket, that shared
 * boundary month got counted twice - visibly reading higher than the "Total" line,
 * which the backend already computed correctly. Skipping a continuation segment's first
 * point (via `is_continuation`) when folding into "other" fixes it, mirroring what the
 * backend's own total calculation already does.
 */
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import { formatCurrency } from '@/lib/utils'
import type { CombinedSimulationResponse } from '@/types'

interface CombinedGrowthChartProps {
  data: CombinedSimulationResponse
}

// Validated 8-slot categorical order, assigned by series position and held fixed -
// never cycled or regenerated for a 9th+ series (those fold into "Other accounts").
const SERIES_COLORS = [
  '#2a78d6', '#eb6834', '#1baf7a', '#eda100',
  '#e87ba4', '#008300', '#4a3aa7', '#e34948',
]
const OTHER_COLOR = '#898781'
const TOTAL_COLOR = '#0b0b0b'
const GRID_COLOR = '#e1e0d9'
const AXIS_COLOR = '#c3c2b7'
const MAX_INDIVIDUAL_SERIES = SERIES_COLORS.length

// Builds the month-indexed row data Recharts plots from a CombinedSimulationResponse -
// pulled out as its own function (rather than inlined in the component) so the
// continuation-aware "other" folding can be unit tested directly without needing to
// inspect rendered SVG. See the module docstring above for the bug this guards against.
export function buildCombinedChartRows(
  data: CombinedSimulationResponse,
  maxIndividualSeries: number = MAX_INDIVIDUAL_SERIES
): Record<string, number>[] {
  const individualSeries = data.accounts.slice(0, maxIndividualSeries)
  const overflowSeries = data.accounts.slice(maxIndividualSeries)

  return data.total_projections.map((totalPoint) => {
    const row: Record<string, number> = {
      month: totalPoint.month,
      total: parseFloat(totalPoint.total_balance),
    }

    for (const series of individualSeries) {
      const point = series.projections.find((p) => p.month === totalPoint.month)
      if (point) row[series.account_id] = parseFloat(point.balance)
    }

    if (overflowSeries.length > 0) {
      row.other = overflowSeries.reduce((sum, series) => {
        const point = series.projections.find((p) => p.month === totalPoint.month)
        if (!point) return sum
        // A continuation segment's first point is the same money as the prior
        // segment's last point - skip it here so it isn't added twice into "other".
        const firstMonth = series.projections[0]?.month
        if (series.is_continuation && point.month === firstMonth) return sum
        return sum + parseFloat(point.balance)
      }, 0)
    }

    return row
  })
}

export default function CombinedGrowthChart({ data }: CombinedGrowthChartProps) {
  const individualSeries = data.accounts.slice(0, MAX_INDIVIDUAL_SERIES)
  const overflowSeries = data.accounts.slice(MAX_INDIVIDUAL_SERIES)
  const chartData = buildCombinedChartRows(data)

  return (
    <ResponsiveContainer width="100%" height={400}>
      <LineChart data={chartData} margin={{ top: 40, right: 30, left: 20, bottom: 24 }}>
        <CartesianGrid stroke={GRID_COLOR} />
        <XAxis
          dataKey="month"
          tick={{ fontSize: 12 }}
          tickLine={{ stroke: AXIS_COLOR }}
          axisLine={{ stroke: AXIS_COLOR }}
          label={{ value: 'Months', position: 'bottom', offset: 0 }}
        />
        <YAxis
          tick={{ fontSize: 12 }}
          tickLine={{ stroke: AXIS_COLOR }}
          axisLine={{ stroke: AXIS_COLOR }}
          tickFormatter={(value) => formatCurrency(value)}
          width={90}
        />
        <Tooltip
          formatter={(value: number) => formatCurrency(value)}
          labelFormatter={(label) => `Month ${label}`}
          contentStyle={{
            backgroundColor: 'white',
            border: '1px solid #e2e8f0',
            borderRadius: '8px',
            boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
          }}
        />
        <Legend verticalAlign="top" align="right" wrapperStyle={{ paddingBottom: 16 }} />

        <Line
          type="monotone"
          dataKey="total"
          name="Total"
          stroke={TOTAL_COLOR}
          strokeWidth={3}
          dot={false}
          activeDot={{ r: 6 }}
        />

        {individualSeries.map((series, index) => (
          <Line
            key={series.account_id}
            type="monotone"
            dataKey={series.account_id}
            name={series.account_name}
            stroke={SERIES_COLORS[index]}
            strokeWidth={2}
            dot={false}
          />
        ))}

        {overflowSeries.length > 0 && (
          <Line
            type="monotone"
            dataKey="other"
            name="Other accounts"
            stroke={OTHER_COLOR}
            strokeWidth={2}
            dot={false}
          />
        )}
      </LineChart>
    </ResponsiveContainer>
  )
}
