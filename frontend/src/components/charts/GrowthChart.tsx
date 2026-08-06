/**
 * Recharts line charts visualizing a bank account growth simulation. Two charts are
 * rendered, stacked: Balance + Principal (same unit, naturally share one y-axis) on top,
 * and Interest Earned - a full order of magnitude smaller than the other two early in a
 * simulation - on its own chart below with its own appropriately-scaled axis. A single
 * shared axis for all three would flatten Interest Earned into an indistinguishable line
 * near zero; a second y-axis on the same plot would fix the visibility but invent a
 * misleading correlation between two differently-scaled measures (the classic dual-axis
 * chart mistake). Two single-axis charts is the correct fix for both. Consumed by
 * AccountDetailPage with data from the /bank-accounts/{id}/simulate endpoint.
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
import type { ProjectionPoint } from '@/types'

interface GrowthChartProps {
  data: ProjectionPoint[]
  showPrincipal?: boolean
  showInterest?: boolean
}

// Validated categorical palette slots (blue/aqua/orange) held fixed for these series
// across every chart in the app, rather than reassigned per chart.
const COLOR_BALANCE = '#2a78d6'
const COLOR_PRINCIPAL = '#1baf7a'
const COLOR_INTEREST = '#eb6834'
const GRID_COLOR = '#e1e0d9'
const AXIS_COLOR = '#c3c2b7'

const tooltipStyle = {
  backgroundColor: 'white',
  border: '1px solid #e2e8f0',
  borderRadius: '8px',
  boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
}

export default function GrowthChart({
  data,
  showPrincipal = true,
  showInterest = true,
}: GrowthChartProps) {
  // The API returns Decimal fields as strings; convert to numbers for Recharts.
  const chartData = data.map((point) => ({
    month: point.month,
    date: point.date,
    balance: parseFloat(point.balance),
    principal: parseFloat(point.principal),
    interest: parseFloat(point.interest_earned),
  }))

  return (
    <div className="space-y-8">
      <ResponsiveContainer width="100%" height={360}>
        <LineChart data={chartData} margin={{ top: 36, right: 30, left: 20, bottom: 24 }}>
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
            contentStyle={tooltipStyle}
          />
          {/* Legend sits above the plot area so it never competes with the XAxis
              label for the same space at the bottom of the chart. */}
          <Legend verticalAlign="top" align="right" wrapperStyle={{ paddingBottom: 16 }} />

          <Line
            type="monotone"
            dataKey="balance"
            name="Balance"
            stroke={COLOR_BALANCE}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 6 }}
          />

          {showPrincipal && (
            <Line
              type="monotone"
              dataKey="principal"
              name="Principal"
              stroke={COLOR_PRINCIPAL}
              strokeWidth={2}
              strokeDasharray="5 5"
              dot={false}
            />
          )}
        </LineChart>
      </ResponsiveContainer>

      {showInterest && (
        <div>
          {/* A single-series chart needs no legend box - this heading names the series. */}
          <p className="mb-2 text-sm font-medium text-slate-700">Interest Earned</p>
          <ResponsiveContainer width="100%" height={160}>
            <LineChart data={chartData} margin={{ top: 10, right: 30, left: 20, bottom: 24 }}>
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
                contentStyle={tooltipStyle}
              />
              <Line
                type="monotone"
                dataKey="interest"
                name="Interest Earned"
                stroke={COLOR_INTEREST}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
