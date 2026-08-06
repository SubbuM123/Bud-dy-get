/**
 * Covers the recurring-action form's new fields: the category select, the
 * "start immediately"/"never ends" checkboxes and the date inputs they toggle, and edit
 * mode (pre-filled fields, start date hidden, action_type locked, category clearable).
 */
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import RecurringActionForm from './RecurringActionForm'
import type { RecurringAction } from '@/types'

const EXISTING_ACTION: RecurringAction = {
  id: 'action-1',
  bank_account_id: 'account-1',
  action_type: 'deposit',
  amount: '500.00',
  description: 'Monthly salary',
  category: 'salary',
  frequency_value: 1,
  frequency_unit: 'months',
  start_date: '2026-01-01',
  end_date: '2027-01-01',
  next_execution_date: '2026-02-01',
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
}

describe('RecurringActionForm (create mode)', () => {
  it('defaults to starting immediately and never ending, with no date pickers shown', () => {
    render(<RecurringActionForm onSubmit={vi.fn()} />)

    expect(screen.getByText('Starts today')).toBeInTheDocument()
    expect(screen.queryByLabelText('Start Date')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('End Date')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /add recurring action/i })).toBeInTheDocument()
  })

  it('reveals a start date picker when "Start immediately" is unchecked', async () => {
    const user = userEvent.setup()
    render(<RecurringActionForm onSubmit={vi.fn()} />)

    await user.click(screen.getByLabelText('Start immediately'))

    expect(screen.getByLabelText('Start Date')).toBeInTheDocument()
    expect(screen.queryByText('Starts today')).not.toBeInTheDocument()
  })

  it('reveals an end date picker when "This action never ends" is unchecked', async () => {
    const user = userEvent.setup()
    render(<RecurringActionForm onSubmit={vi.fn()} />)

    await user.click(screen.getByLabelText('This action never ends'))

    expect(screen.getByLabelText('End Date')).toBeInTheDocument()
  })

  it('submits a category and omits end_date when "never ends" stays checked', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<RecurringActionForm onSubmit={onSubmit} />)

    await user.type(screen.getByLabelText('Amount ($)'), '500')
    await user.selectOptions(screen.getByLabelText('Category'), 'housing')
    await user.click(screen.getByRole('button', { name: /add recurring action/i }))

    expect(onSubmit).toHaveBeenCalledTimes(1)
    const submitted = onSubmit.mock.calls[0][0]
    expect(submitted.category).toBe('housing')
    expect(submitted.end_date).toBeUndefined()
    expect(submitted.start_date).toBeTruthy()
  })
})

describe('RecurringActionForm (edit mode)', () => {
  it('pre-fills fields, locks action_type, and hides the start-date section', () => {
    render(<RecurringActionForm action={EXISTING_ACTION} onSubmit={vi.fn()} />)

    expect(screen.getByText(/deposit \(can't be changed after creation\)/i)).toBeInTheDocument()
    expect(screen.queryByLabelText('Start immediately')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Start Date')).not.toBeInTheDocument()
    expect(screen.getByDisplayValue('500.00')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Monthly salary')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /save changes/i })).toBeInTheDocument()
  })

  it('starts with "never ends" unchecked when the action already has an end date', () => {
    render(<RecurringActionForm action={EXISTING_ACTION} onSubmit={vi.fn()} />)

    expect(screen.getByLabelText('End Date')).toHaveValue('2027-01-01')
  })

  it('submits null end_date when "never ends" is checked during edit', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<RecurringActionForm action={EXISTING_ACTION} onSubmit={onSubmit} />)

    await user.click(screen.getByLabelText('This action never ends'))
    await user.click(screen.getByRole('button', { name: /save changes/i }))

    expect(onSubmit).toHaveBeenCalledTimes(1)
    expect(onSubmit.mock.calls[0][0].end_date).toBeUndefined()
  })
})
