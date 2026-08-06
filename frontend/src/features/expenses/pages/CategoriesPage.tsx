/**
 * Category management view at /expense-categories: every category as a card (icon, color,
 * optional monthly budget) with inline create/edit forms, matching every other module's
 * "grid of cards + inline form" pattern.
 */
import { useState } from 'react'
import { Plus, Pencil, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { formatCurrency, getApiErrorMessage } from '@/lib/utils'
import CategoryForm from '../components/CategoryForm'
import { getCategoryIcon } from '../icon-map'
import {
  useExpenseCategories,
  useCreateExpenseCategory,
  useUpdateExpenseCategory,
  useDeleteExpenseCategory,
} from '../hooks/useExpenses'
import type { ExpenseCategory } from '@/types'

export default function CategoriesPage() {
  const [showForm, setShowForm] = useState(false)
  const [editingCategory, setEditingCategory] = useState<ExpenseCategory | null>(null)

  const { data: categories, isLoading } = useExpenseCategories()
  const createCategory = useCreateExpenseCategory()
  const updateCategory = useUpdateExpenseCategory()
  const deleteCategory = useDeleteExpenseCategory()

  const handleCreate = async (data: Parameters<typeof createCategory.mutate>[0]) => {
    try {
      await createCategory.mutateAsync(data)
      setShowForm(false)
    } catch {
      // handled via createCategory.error
    }
  }

  const handleUpdate = async (data: Parameters<typeof createCategory.mutate>[0]) => {
    if (!editingCategory) return
    try {
      await updateCategory.mutateAsync({ id: editingCategory.id, data })
      setEditingCategory(null)
    } catch {
      // handled via updateCategory.error
    }
  }

  const handleDelete = (id: string) => {
    if (
      window.confirm(
        'Delete this category? Expenses using it will become uncategorized, not deleted.'
      )
    ) {
      deleteCategory.mutate(id)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-slate-500">Loading categories...</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Expense Categories</h1>
          <p className="text-slate-500">Organize your spending and set optional monthly budgets</p>
        </div>
        <Button
          onClick={() => {
            setEditingCategory(null)
            setShowForm(true)
          }}
        >
          <Plus className="h-4 w-4 mr-2" />
          Add Category
        </Button>
      </div>

      {showForm && (
        <Card>
          <CardHeader>
            <CardTitle>New Category</CardTitle>
          </CardHeader>
          <CardContent>
            {createCategory.isError && (
              <div className="mb-4 rounded-md bg-danger-500/10 p-3 text-sm text-danger-500">
                {getApiErrorMessage(createCategory.error, 'Failed to create category')}
              </div>
            )}
            <CategoryForm
              onSubmit={handleCreate}
              isLoading={createCategory.isPending}
              onCancel={() => setShowForm(false)}
            />
          </CardContent>
        </Card>
      )}

      {editingCategory && (
        <Card>
          <CardHeader>
            <CardTitle>Edit Category</CardTitle>
          </CardHeader>
          <CardContent>
            {updateCategory.isError && (
              <div className="mb-4 rounded-md bg-danger-500/10 p-3 text-sm text-danger-500">
                {getApiErrorMessage(updateCategory.error, 'Failed to update category')}
              </div>
            )}
            <CategoryForm
              category={editingCategory}
              onSubmit={handleUpdate}
              isLoading={updateCategory.isPending}
              onCancel={() => setEditingCategory(null)}
            />
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {categories?.map((category) => {
          const Icon = getCategoryIcon(category.icon)
          return (
            <Card key={category.id}>
              <CardContent className="pt-6">
                <div className="flex items-start justify-between">
                  <div
                    className="flex h-10 w-10 items-center justify-center rounded-full"
                    style={{ backgroundColor: `${category.color ?? '#64748b'}1a` }}
                  >
                    <Icon className="h-5 w-5" style={{ color: category.color ?? '#64748b' }} />
                  </div>
                  <div className="flex items-center">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-slate-400 hover:text-primary-600"
                      onClick={() => {
                        setShowForm(false)
                        setEditingCategory(category)
                      }}
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-slate-400 hover:text-danger-500"
                      onClick={() => handleDelete(category.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
                <p className="mt-3 font-medium text-slate-900">{category.name}</p>
                {category.monthly_budget && (
                  <p className="text-sm text-slate-500">
                    Budget: {formatCurrency(category.monthly_budget)}/mo
                  </p>
                )}
              </CardContent>
            </Card>
          )
        })}
      </div>
    </div>
  )
}
