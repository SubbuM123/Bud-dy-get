/**
 * Recharts line charts visualizing an education savings account growth simulation.
 * Adapted from RetirementGrowthChart.tsx with the employer/employee contribution split
 * removed - 529s aren't employer-sponsored, so there's a single "Contributions" series
 * instead of two. Follows the same two-chart split as RetirementGrowthChart and for the
 * same reason: Balance and Contributions share a unit and scale together, while Growth is
 * a full order of magnitude smaller early in a simulation. Consumed by
 * EducationAccountDetailPage with data from /education-accounts/{id}/simulate.
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
import type { EducationProjectionPoint } from '@/types'

interface EducationGrowthChartProps {
  data: EducationProjectionPoint[]
}

// Same validated categorical palette slots used by RetirementGrowthChart, held fixed across the app.
const COLOR_BALANCE = '#2a78d6'
const COLOR_CONTRIBUTIONS = '#1baf7a'
const COLOR_GROWTH = '#eb6834'
const GRID_COLOR = '#e1e0d9'
const AXIS_COLOR = '#c3c2b7'

const tooltipStyle = {
  backgroundColor: 'white',
  border: '1px solid #e2e8f0',
  borderRadius: '8px',
  boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
}

export default function EducationGrowthChart({ data }: EducationGrowthChartProps) {
  // The API returns Decimal fields as strings; convert to numbers for Recharts.
  const chartData = data.map((point) => ({
    month: point.month,
    date: point.date,
    balance: parseFloat(point.balance),
    contributions: parseFloat(point.contributions),
    growth: parseFloat(point.growth),
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

          <Line
            type="monotone"
            dataKey="contributions"
            name="Total Contributions"
            stroke={COLOR_CONTRIBUTIONS}
            strokeWidth={2}
            strokeDasharray="5 5"
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>

      <div>
        <p className="mb-2 text-sm font-medium text-slate-700">Investment Growth</p>
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
              dataKey="growth"
              name="Investment Growth"
              stroke={COLOR_GROWTH}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 5 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
