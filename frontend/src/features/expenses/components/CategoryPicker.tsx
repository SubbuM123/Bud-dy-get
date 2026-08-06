/**
 * Dropdown for picking an expense category, with a color swatch preview and an "Add new
 * category" escape hatch that hands control back to the parent (CategoriesPage owns the
 * actual create form) rather than opening its own nested form - keeps this component a
 * simple controlled picker instead of a picker-that-also-mutates-data.
 */
import { Select } from '@/components/ui/select'
import type { ExpenseCategory } from '@/types'

interface CategoryPickerProps {
  categories: ExpenseCategory[]
  value: string | undefined
  onChange: (categoryId: string | undefined) => void
  onRequestCreate?: () => void
  label?: string
}

const CREATE_NEW_VALUE = '__create_new__'
const NONE_VALUE = ''

export default function CategoryPicker({
  categories,
  value,
  onChange,
  onRequestCreate,
  label = 'Category',
}: CategoryPickerProps) {
  const options = [
    { value: NONE_VALUE, label: 'Uncategorized' },
    ...categories.map((category) => ({ value: category.id, label: category.name })),
    ...(onRequestCreate ? [{ value: CREATE_NEW_VALUE, label: '+ Add new category...' }] : []),
  ]

  const selected = categories.find((c) => c.id === value)

  return (
    <div>
      <div className="flex items-center gap-2">
        {selected?.color && (
          <span
            className="h-3 w-3 shrink-0 rounded-full"
            style={{ backgroundColor: selected.color }}
            aria-hidden="true"
          />
        )}
        <div className="flex-1">
          <Select
            label={label}
            options={options}
            value={value ?? NONE_VALUE}
            onChange={(e) => {
              const newValue = e.target.value
              if (newValue === CREATE_NEW_VALUE) {
                onRequestCreate?.()
                return
              }
              onChange(newValue === NONE_VALUE ? undefined : newValue)
            }}
          />
        </div>
      </div>
    </div>
  )
}
