/**
 * Base dropdown/select component styled to match Input, used anywhere a form needs to
 * pick from a closed set of options (account type, compounding frequency, recurring
 * action type/frequency unit). Options are passed as a typed array rather than raw
 * `<option>` children so callers get type-checked value/label pairs. An optional
 * `tooltip` node (see ui/info-tooltip.tsx) renders next to the label as a sibling, not a
 * wrapper - see input.tsx's identical pattern for why.
 */
import { forwardRef, ReactNode, SelectHTMLAttributes, useId } from 'react'
import { cn } from '@/lib/utils'

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string
  error?: string
  tooltip?: ReactNode
  options: { value: string; label: string }[]
}

// Forwarding the ref is required for react-hook-form's register() to bind to the select.
const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, label, error, tooltip, options, id, ...props }, ref) => {
    const generatedId = useId()
    const selectId = id ?? generatedId

    return (
      <div className="space-y-1">
        {label && (
          <div className="flex items-center gap-1.5">
            <label htmlFor={selectId} className="text-sm font-medium text-slate-700">
              {label}
            </label>
            {tooltip}
          </div>
        )}
        <select
          id={selectId}
          className={cn(
            'flex h-10 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50',
            error && 'border-danger-500 focus:ring-danger-500',
            className
          )}
          ref={ref}
          {...props}
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        {error && <p className="text-sm text-danger-500">{error}</p>}
      </div>
    )
  }
)
Select.displayName = 'Select'

export { Select }
