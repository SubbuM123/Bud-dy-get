/**
 * Main expense view at /expenses: header stats for the current period, the category
 * breakdown bar chart and spending trend line side by side, an inline "add expense" form,
 * and the filterable expense list itself. Mirrors the "stats + chart + list" layout every
 * other module's main page uses (e.g. RetirementAccountDetailPage's stat tiles above its
 * chart).
 */
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Settings, ScanLine } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card'
import { Select } from '@/components/ui/select'
import { formatCurrency, getApiErrorMessage } from '@/lib/utils'
import ExpenseCard from '../components/ExpenseCard'
import ExpenseForm from '../components/ExpenseForm'
import CategoryForm from '../components/CategoryForm'
import SpendingByCategoryChart from '../components/SpendingByCategoryChart'
import SpendingTrendChart from '../components/SpendingTrendChart'
import {
  useExpenseList,
  useCreateExpense,
  useUpdateExpense,
  useDeleteExpense,
  useExpenseSummary,
  useExpenseCategories,
  useCreateExpenseCategory,
} from '../hooks/useExpenses'
import type { Expense } from '@/types'

export default function ExpensesPage() {
  const [showForm, setShowForm] = useState(false)
  const [editingExpense, setEditingExpense] = useState<Expense | null>(null)
  const [showCategoryForm, setShowCategoryForm] = useState(false)
  const [categoryFilter, setCategoryFilter] = useState<string>('')

  const { data: categories } = useExpenseCategories()
  const { data: summary } = useExpenseSummary()
  const { data: trendExpenses } = useExpenseList()
  const { data: expenses, isLoading } = useExpenseList(
    categoryFilter ? { category_id: categoryFilter } : undefined
  )

  const createExpense = useCreateExpense()
  const updateExpense = useUpdateExpense()
  const deleteExpense = useDeleteExpense()
  const createCategory = useCreateExpenseCategory()

  const categoriesById = new Map((categories ?? []).map((c) => [c.id, c]))

  const handleCreate = async (data: Parameters<typeof createExpense.mutate>[0]) => {
    try {
      await createExpense.mutateAsync(data)
      setShowForm(false)
    } catch {
      // handled via createExpense.error
    }
  }

  const handleUpdate = async (data: Parameters<typeof createExpense.mutate>[0]) => {
    if (!editingExpense) return
    try {
      await updateExpense.mutateAsync({ id: editingExpense.id, data })
      setEditingExpense(null)
    } catch {
      // handled via updateExpense.error
    }
  }

  const handleDelete = (id: string) => {
    if (window.confirm('Delete this expense?')) {
      deleteExpense.mutate(id)
    }
  }

  const handleCreateCategory = async (data: Parameters<typeof createCategory.mutate>[0]) => {
    await createCategory.mutateAsync(data)
    setShowCategoryForm(false)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Expenses</h1>
          <p className="text-slate-500">Track and categorize your spending</p>
        </div>
        <div className="flex gap-3">
          <Link to="/receipts">
            <Button variant="outline">
              <ScanLine className="h-4 w-4 mr-2" />
              Receipts
            </Button>
          </Link>
          <Link to="/expense-categories">
            <Button variant="outline">
              <Settings className="h-4 w-4 mr-2" />
              Categories
            </Button>
          </Link>
          <Button
            onClick={() => {
              setEditingExpense(null)
              setShowForm(true)
            }}
          >
            <Plus className="h-4 w-4 mr-2" />
            Add Expense
          </Button>
        </div>
      </div>

      {summary && (
        <div className="grid gap-6 md:grid-cols-3">
          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-slate-500">This Month</p>
              <p className="text-2xl font-bold">{formatCurrency(summary.total_amount)}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-slate-500">Transactions</p>
              <p className="text-2xl font-bold">{summary.expense_count}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-slate-500">Top Category</p>
              <p className="text-2xl font-bold">
                {summary.by_category[0]?.category_name ?? '—'}
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Spending by Category</CardTitle>
            <CardDescription>This calendar month</CardDescription>
          </CardHeader>
          <CardContent>
            {summary && <SpendingByCategoryChart data={summary.by_category} />}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Spending Trend</CardTitle>
            <CardDescription>Last 6 months</CardDescription>
          </CardHeader>
          <CardContent>
            <SpendingTrendChart expenses={trendExpenses ?? []} monthsBack={6} />
          </CardContent>
        </Card>
      </div>

      {showForm && (
        <Card>
          <CardHeader>
            <CardTitle>Add Expense</CardTitle>
          </CardHeader>
          <CardContent>
            {createExpense.isError && (
              <div className="mb-4 rounded-md bg-danger-500/10 p-3 text-sm text-danger-500">
                {getApiErrorMessage(createExpense.error, 'Failed to create expense')}
              </div>
            )}
            <ExpenseForm
              onSubmit={handleCreate}
              isLoading={createExpense.isPending}
              onCancel={() => setShowForm(false)}
              onRequestCreateCategory={() => setShowCategoryForm(true)}
            />
          </CardContent>
        </Card>
      )}

      {editingExpense && (
        <Card>
          <CardHeader>
            <CardTitle>Edit Expense</CardTitle>
          </CardHeader>
          <CardContent>
            {updateExpense.isError && (
              <div className="mb-4 rounded-md bg-danger-500/10 p-3 text-sm text-danger-500">
                {getApiErrorMessage(updateExpense.error, 'Failed to update expense')}
              </div>
            )}
            <ExpenseForm
              expense={editingExpense}
              onSubmit={handleUpdate}
              isLoading={updateExpense.isPending}
              onCancel={() => setEditingExpense(null)}
              onRequestCreateCategory={() => setShowCategoryForm(true)}
            />
          </CardContent>
        </Card>
      )}

      {showCategoryForm && (
        <Card>
          <CardHeader>
            <CardTitle>New Category</CardTitle>
          </CardHeader>
          <CardContent>
            <CategoryForm
              onSubmit={handleCreateCategory}
              isLoading={createCategory.isPending}
              onCancel={() => setShowCategoryForm(false)}
            />
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>All Expenses</CardTitle>
            <div className="w-56">
              <Select
                options={[
                  { value: '', label: 'All Categories' },
                  ...(categories?.map((c) => ({ value: c.id, label: c.name })) ?? []),
                ]}
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
              />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="py-8 text-center text-slate-500">Loading expenses...</p>
          ) : expenses?.length === 0 ? (
            <p className="py-8 text-center text-slate-500">No expenses yet</p>
          ) : (
            <div className="space-y-2">
              {expenses?.map((expense) => (
                <ExpenseCard
                  key={expense.id}
                  expense={expense}
                  category={expense.category_id ? categoriesById.get(expense.category_id) : undefined}
                  onEdit={setEditingExpense}
                  onDelete={handleDelete}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
