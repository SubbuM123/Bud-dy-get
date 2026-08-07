/**
 * Ranked horizontal bar chart of net worth by category (Bank Accounts, Retirement,
 * Education, Investments). Bar chart, not a pie/donut, for the same reason
 * features/expenses/components/SpendingByCategoryChart.tsx picks one - "part-to-whole"
 * is the classic pie-chart pitch, but a ranked bar handles close-value comparisons better
 * and gives every category a direct label instead of a legend to decode. Unlike that
 * chart, these are four fixed structural categories rather than user-defined ones, so
 * colors are a validated fixed categorical set (see CATEGORY_COLORS) instead of a
 * per-record color field - validated via the dataviz skill's validate_palette.js
 * (light mode: all four pairs pass; #d97706<->#059669 sits in the 6-8 CVD-separation
 * floor band, legal here because every bar already carries a direct category-name label).
 */
import { Bar, BarChart, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { formatCurrency } from '@/lib/utils'

export interface NetWorthCategoryDatum {
  name: string
  amount: number
}

const GRID_COLOR = '#e1e0d9'
const AXIS_COLOR = '#c3c2b7'

// Fixed categorical order (Bank, Retirement, Education, Investments) - never reassigned
// or cycled, so a category's color stays constant across renders/filters.
const CATEGORY_COLORS: Record<string, string> = {
  'Bank Accounts': '#2563eb',
  Retirement: '#059669',
  Education: '#d97706',
  Investments: '#7c3aed',
}
const FALLBACK_COLOR = '#64748b'

const tooltipStyle = {
  backgroundColor: 'white',
  border: '1px solid #e2e8f0',
  borderRadius: '8px',
  boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
}

export default function NetWorthByCategoryChart({ data }: { data: NetWorthCategoryDatum[] }) {
  const chartData = data.filter((item) => item.amount > 0).sort((a, b) => b.amount - a.amount)

  if (chartData.length === 0) {
    return <p className="py-12 text-center text-slate-500">Add an account to see your net worth breakdown</p>
  }

  const chartHeight = Math.max(120, chartData.length * 48)

  return (
    <ResponsiveContainer width="100%" height={chartHeight}>
      <BarChart
        data={chartData}
        layout="vertical"
        margin={{ top: 8, right: 40, left: 8, bottom: 8 }}
        barCategoryGap={14}
      >
        <CartesianGrid stroke={GRID_COLOR} horizontal={false} />
        <XAxis
          type="number"
          tick={{ fontSize: 12 }}
          tickLine={{ stroke: AXIS_COLOR }}
          axisLine={{ stroke: AXIS_COLOR }}
          tickFormatter={(value) => formatCurrency(value)}
        />
        <YAxis
          type="category"
          dataKey="name"
          tick={{ fontSize: 13 }}
          tickLine={false}
          axisLine={{ stroke: AXIS_COLOR }}
          width={110}
        />
        <Tooltip formatter={(value: number) => formatCurrency(value)} contentStyle={tooltipStyle} />
        <Bar dataKey="amount" radius={[0, 4, 4, 0]} maxBarSize={32}>
          {chartData.map((entry) => (
            <Cell key={entry.name} fill={CATEGORY_COLORS[entry.name] || FALLBACK_COLOR} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
