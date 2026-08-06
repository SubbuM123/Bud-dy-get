/**
 * Horizontal bar chart ranking spending by category for the selected period. Deliberately
 * a bar chart, not a pie/donut, despite "spending by category" being the classic pie-chart
 * pitch: the data-viz skill's guidance is explicit that a pie/donut is only appropriate for
 * "part-to-whole at a glance, <=6 segments" and is an anti-pattern for comparing close
 * values - this app can have up to 10 default categories plus whatever a user adds, and
 * users very plausibly want to compare two categories that are close in spend. A ranked
 * horizontal bar handles both an arbitrary category count and close-value comparison
 * cleanly, with each bar's category name as a direct label so a reader is never stuck
 * decoding a legend. Each bar uses that category's own `color` field (the same hex shown
 * on its badge in CategoryPicker/ExpenseCard elsewhere in the app) rather than a
 * re-derived palette slot, so the color-to-category association stays consistent across
 * every screen the user sees it on.
 */
import { Bar, BarChart, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { formatCurrency } from '@/lib/utils'
import type { ExpenseCategorySummaryItem } from '@/types'

interface SpendingByCategoryChartProps {
  data: ExpenseCategorySummaryItem[]
}

const GRID_COLOR = '#e1e0d9'
const AXIS_COLOR = '#c3c2b7'
// Fallback for a category with no color set (shouldn't normally happen - every category
// gets a color at creation - but keeps the chart from rendering a blank/invisible bar).
const FALLBACK_COLOR = '#64748b'

const tooltipStyle = {
  backgroundColor: 'white',
  border: '1px solid #e2e8f0',
  borderRadius: '8px',
  boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
}

export default function SpendingByCategoryChart({ data }: SpendingByCategoryChartProps) {
  const chartData = data
    .map((item) => ({
      name: item.category_name,
      amount: parseFloat(item.total_amount),
      count: item.expense_count,
      color: item.category_color || FALLBACK_COLOR,
    }))
    .sort((a, b) => b.amount - a.amount)

  if (chartData.length === 0) {
    return <p className="py-12 text-center text-slate-500">No spending in this period yet</p>
  }

  // Height grows with the number of categories so bars never feel cramped.
  const chartHeight = Math.max(120, chartData.length * 40)

  return (
    <ResponsiveContainer width="100%" height={chartHeight}>
      <BarChart
        data={chartData}
        layout="vertical"
        margin={{ top: 8, right: 40, left: 8, bottom: 8 }}
        barCategoryGap={10}
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
          width={120}
        />
        <Tooltip
          formatter={(value: number, _name, item) => [
            `${formatCurrency(value)} (${item.payload.count} expense${item.payload.count === 1 ? '' : 's'})`,
            item.payload.name,
          ]}
          contentStyle={tooltipStyle}
        />
        <Bar dataKey="amount" radius={[0, 4, 4, 0]} maxBarSize={28}>
          {chartData.map((entry) => (
            <Cell key={entry.name} fill={entry.color} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
