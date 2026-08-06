/**
 * Form for creating or editing an expense category: name, a color swatch picker, an icon
 * picker (a curated grid of lucide-react icons rather than a free-text name field, so a
 * typo can't silently produce a category with no visible icon anywhere in the app), and an
 * optional monthly budget. Passing a `category` prop switches the form into edit mode.
 */
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { EXPENSE_CATEGORY_ICON_OPTIONS } from '../icon-map'
import type { ExpenseCategory } from '@/types'

// Same 8-slot validated categorical palette used everywhere else in the app (see
// backend/app/models/expense_categories.py's DEFAULT_CATEGORIES comment for the
// data-viz-skill validation run), plus two muted overflow tones (used for the "Other"
// default category, and available for any other category that wants a neutral tone)
// offered as quick-pick swatches - a user can still type any hex.
const COLOR_SWATCHES = [
  '#2a78d6',
  '#eb6834',
  '#1baf7a',
  '#eda100',
  '#e87ba4',
  '#008300',
  '#4a3aa7',
  '#e34948',
  '#94a3b8',
  '#64748b',
]

const categorySchema = z.object({
  name: z.string().min(1, 'Category name is required'),
  color: z.string().optional(),
  icon: z.string().optional(),
  monthly_budget: z.string().optional().transform((val) => (val ? parseFloat(val) : undefined)),
})

type CategoryFormData = z.input<typeof categorySchema>

interface CategoryFormProps {
  category?: ExpenseCategory
  onSubmit: (data: z.output<typeof categorySchema>) => void
  isLoading?: boolean
  onCancel?: () => void
}

export default function CategoryForm({ category, onSubmit, isLoading, onCancel }: CategoryFormProps) {
  const [color, setColor] = useState(category?.color ?? COLOR_SWATCHES[0])
  const [icon, setIcon] = useState(category?.icon ?? EXPENSE_CATEGORY_ICON_OPTIONS[0].value)

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<CategoryFormData>({
    resolver: zodResolver(categorySchema),
    defaultValues: {
      name: category?.name,
      monthly_budget: category?.monthly_budget ?? undefined,
    },
  })

  const handleValidSubmit = handleSubmit((data) => {
    const output = data as unknown as z.output<typeof categorySchema>
    onSubmit({ ...output, color, icon })
  })

  return (
    <form onSubmit={handleValidSubmit} className="space-y-4">
      <Input
        label="Category Name"
        placeholder="Pet Supplies"
        error={errors.name?.message}
        {...register('name')}
      />

      <div>
        <p className="mb-1.5 text-sm font-medium text-slate-700">Color</p>
        <div className="flex flex-wrap items-center gap-2">
          {COLOR_SWATCHES.map((swatch) => (
            <button
              key={swatch}
              type="button"
              onClick={() => setColor(swatch)}
              className={cn(
                'h-7 w-7 rounded-full border-2',
                color === swatch ? 'border-slate-900' : 'border-transparent'
              )}
              style={{ backgroundColor: swatch }}
              aria-label={`Choose color ${swatch}`}
            />
          ))}
          <input
            type="color"
            value={color}
            onChange={(e) => setColor(e.target.value)}
            className="h-7 w-9 cursor-pointer rounded border border-slate-300"
            aria-label="Choose custom color"
          />
        </div>
      </div>

      <div>
        <p className="mb-1.5 text-sm font-medium text-slate-700">Icon</p>
        <div className="flex flex-wrap gap-2">
          {EXPENSE_CATEGORY_ICON_OPTIONS.map(({ value, Icon }) => (
            <button
              key={value}
              type="button"
              onClick={() => setIcon(value)}
              className={cn(
                'flex h-9 w-9 items-center justify-center rounded-md border',
                icon === value
                  ? 'border-primary-600 bg-primary-50 text-primary-600'
                  : 'border-slate-200 text-slate-500 hover:bg-slate-50'
              )}
              aria-label={`Choose icon ${value}`}
            >
              <Icon className="h-4 w-4" />
            </button>
          ))}
        </div>
      </div>

      <Input
        label="Monthly Budget ($, optional)"
        type="number"
        step="0.01"
        min="0"
        placeholder="300"
        error={errors.monthly_budget?.message}
        {...register('monthly_budget')}
      />

      <div className="flex gap-3 pt-2">
        <Button type="submit" disabled={isLoading}>
          {isLoading ? 'Saving...' : category ? 'Save Changes' : 'Create Category'}
        </Button>
        {onCancel && (
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  )
}
