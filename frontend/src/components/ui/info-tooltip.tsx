/**
 * Small "(i)" popup button that shows a short explanation of a term or account type on
 * hover, focus, or click - added for the Retirement module, where many field labels and
 * account type names (401(k), vesting, catch-up contribution, MAGI, ...) are unfamiliar
 * jargon. Deliberately its own tiny component rather than a dependency (no tooltip
 * library is installed) so it stays consistent with the rest of the app's styling and
 * needs no new dependency. The popup is a sibling of whatever it's placed next to, not a
 * wrapper around it, so it never interferes with a parent <label>'s click-to-focus
 * behavior on its associated input.
 */
import { useId, useState, type ReactNode } from 'react'
import { Info } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface InfoTooltipProps {
  title?: string
  content: ReactNode
  className?: string
}

export function InfoTooltip({ title, content, className }: InfoTooltipProps) {
  const [open, setOpen] = useState(false)
  const panelId = useId()

  return (
    <span
      className={cn('relative inline-flex', className)}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        type="button"
        aria-label={title ? `About ${title}` : 'More information'}
        aria-describedby={open ? panelId : undefined}
        // A button is focused right before its click event fires, so onFocus already
        // opens the panel by the time onClick runs - onClick just re-affirms open=true
        // (rather than toggling) so mouse/touch clicks can't race onFocus into closing it
        // again. Closing happens via onBlur, onMouseLeave, or Escape instead.
        onClick={() => setOpen(true)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={(e) => {
          if (e.key === 'Escape') setOpen(false)
        }}
        className="inline-flex items-center justify-center rounded-full text-slate-400 hover:text-primary-600 focus:text-primary-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-1"
      >
        <Info className="h-3.5 w-3.5" />
      </button>

      {open && (
        <span
          id={panelId}
          role="tooltip"
          className="absolute left-1/2 top-full z-20 mt-1.5 w-64 -translate-x-1/2 rounded-md border border-slate-200 bg-white p-3 text-left text-xs font-normal normal-case leading-relaxed text-slate-600 shadow-lg"
        >
          {title && <span className="mb-1 block font-semibold text-slate-800">{title}</span>}
          {content}
        </span>
      )}
    </span>
  )
}
