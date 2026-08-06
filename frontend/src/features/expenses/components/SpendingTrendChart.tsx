/**
 * Single-line chart of total spending per month over the last N months. A single series,
 * so per the data-viz skill's form guidance ("trend over time -> line... sequential or 1
 * categorical") this needs no legend - the chart title already names what the line is -
 * and uses the app's slot-1 blue, the same color RetirementGrowthChart/
 * EducationGrowthChart use for their own single "the headline number over time" line.
 * `buildMonthlyTotals` is exported and unit-tested on its own (see
 * SpendingTrendChart.test.tsx) since it's the part with actual logic - bucketing a flat
 * expense list into calendar months, including months with zero spending so a quiet month
 * shows as a dip rather than a gap in the line.
 */
import {
  Line,
  LineChart,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { formatCurrency } from '@/lib/utils'
import type { Expense } from '@/types'

export interface MonthlyTotal {
  monthKey: string // "2026-01", used as a stable React key
  label: string // "Jan 2026", shown on the axis/tooltip
  total: number
}

const GRID_COLOR = '#e1e0d9'
const AXIS_COLOR = '#c3c2b7'
const LINE_COLOR = '#2a78d6'

const tooltipStyle = {
  backgroundColor: 'white',
  border: '1px solid #e2e8f0',
  borderRadius: '8px',
  boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
}

// Bucket a flat expense list into the last `monthsBack` calendar months (oldest first),
// summing amounts per month - including months with zero expenses, so the line shows a
// real dip instead of skipping straight past a quiet month.
export function buildMonthlyTotals(
  expenses: Expense[],
  monthsBack: number,
  today: Date = new Date()
): MonthlyTotal[] {
  const months: MonthlyTotal[] = []
  for (let i = monthsBack - 1; i >= 0; i--) {
    const d = new Date(today.getFullYear(), today.getMonth() - i, 1)
    const monthKey = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
    const label = d.toLocaleDateString('en-US', { month: 'short', year: 'numeric' })
    months.push({ monthKey, label, total: 0 })
  }

  const totalsByKey = new Map(months.map((m) => [m.monthKey, m]))
  for (const expense of expenses) {
    // expense_date is a plain "YYYY-MM-DD" string (no time component) - parsing it with
    // `new Date(str)` reads it as UTC midnight, and re-reading that back through local
    // getFullYear()/getMonth() shifts it a day earlier in any timezone behind UTC,
    // silently bucketing e.g. a March 1st expense into February. Slicing the string
    // directly sidesteps Date/timezone parsing entirely for what's just a label lookup.
    const key = expense.expense_date.slice(0, 7)
    const bucket = totalsByKey.get(key)
    if (bucket) {
      bucket.total += parseFloat(expense.amount)
    }
  }

  return months
}

interface SpendingTrendChartProps {
  expenses: Expense[]
  monthsBack?: number
}

export default function SpendingTrendChart({ expenses, monthsBack = 6 }: SpendingTrendChartProps) {
  const data = buildMonthlyTotals(expenses, monthsBack)

  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={data} margin={{ top: 16, right: 30, left: 20, bottom: 8 }}>
        <CartesianGrid stroke={GRID_COLOR} />
        <XAxis
          dataKey="label"
          tick={{ fontSize: 12 }}
          tickLine={{ stroke: AXIS_COLOR }}
          axisLine={{ stroke: AXIS_COLOR }}
        />
        <YAxis
          tick={{ fontSize: 12 }}
          tickLine={{ stroke: AXIS_COLOR }}
          axisLine={{ stroke: AXIS_COLOR }}
          tickFormatter={(value) => formatCurrency(value)}
          width={80}
        />
        <Tooltip
          formatter={(value: number) => formatCurrency(value)}
          contentStyle={tooltipStyle}
        />
        <Line
          type="monotone"
          dataKey="total"
          name="Spending"
          stroke={LINE_COLOR}
          strokeWidth={2}
          dot={{ r: 3 }}
          activeDot={{ r: 6 }}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
