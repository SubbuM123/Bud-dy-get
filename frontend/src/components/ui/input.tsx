/**
 * Base text input component with a built-in optional label and inline validation error
 * message, used by every form in the app (account creation, recurring actions, login,
 * registration) via react-hook-form's `register()` spread. Keeping label/error rendering
 * here avoids repeating the same markup around every raw `<input>` in the codebase. An
 * optional `tooltip` node (see ui/info-tooltip.tsx) renders next to the label as a
 * sibling, not a wrapper - it's outside the <label> element itself so clicking it never
 * triggers the label's default click-to-focus-input behavior.
 */
import { forwardRef, InputHTMLAttributes, ReactNode, useId } from 'react'
import { cn } from '@/lib/utils'

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  tooltip?: ReactNode
}

// Forwarding the ref is required for react-hook-form's register() to bind to the input.
const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, tooltip, type, id, ...props }, ref) => {
    const generatedId = useId()
    const inputId = id ?? generatedId

    return (
      <div className="space-y-1">
        {label && (
          <div className="flex items-center gap-1.5">
            <label htmlFor={inputId} className="text-sm font-medium text-slate-700">
              {label}
            </label>
            {tooltip}
          </div>
        )}
        <input
          id={inputId}
          type={type}
          className={cn(
            'flex h-10 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50',
            error && 'border-danger-500 focus:ring-danger-500',
            className
          )}
          ref={ref}
          {...props}
        />
        {error && <p className="text-sm text-danger-500">{error}</p>}
      </div>
    )
  }
)
Input.displayName = 'Input'

export { Input }
