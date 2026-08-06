/**
 * Covers CategoryForm's name validation, the default color/icon selection, and that
 * picking a different color/icon swatch updates what gets submitted alongside the
 * react-hook-form-managed name/budget fields.
 */
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import CategoryForm from './CategoryForm'
import type { ExpenseCategory } from '@/types'

function renderForm(props: Partial<React.ComponentProps<typeof CategoryForm>> = {}) {
  return render(<CategoryForm onSubmit={vi.fn()} {...props} />)
}

describe('CategoryForm', () => {
  it('rejects submission when the category name is missing', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    renderForm({ onSubmit })

    await user.click(screen.getByRole('button', { name: /create category/i }))

    expect(await screen.findByText('Category name is required')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('submits the name plus the default color and icon', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    renderForm({ onSubmit })

    await user.type(screen.getByLabelText('Category Name'), 'Pet Supplies')
    await user.click(screen.getByRole('button', { name: /create category/i }))

    expect(onSubmit).toHaveBeenCalledTimes(1)
    const submitted = onSubmit.mock.calls[0][0]
    expect(submitted.name).toBe('Pet Supplies')
    expect(submitted.color).toBe('#2a78d6')
    expect(submitted.icon).toBe('shopping-cart')
  })

  it('submits whichever color/icon swatch was clicked', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    renderForm({ onSubmit })

    await user.type(screen.getByLabelText('Category Name'), 'Home Repairs')
    await user.click(screen.getByLabelText('Choose color #eb6834'))
    await user.click(screen.getByLabelText('Choose icon wrench'))
    await user.click(screen.getByRole('button', { name: /create category/i }))

    const submitted = onSubmit.mock.calls[0][0]
    expect(submitted.color).toBe('#eb6834')
    expect(submitted.icon).toBe('wrench')
  })

  it('pre-fills fields in edit mode', () => {
    const category: ExpenseCategory = {
      id: 'cat-1',
      user_id: 'user-1',
      name: 'Groceries',
      color: '#1baf7a',
      icon: 'car',
      monthly_budget: '500.00',
      is_system: true,
      created_at: '2026-01-01T00:00:00Z',
    }
    renderForm({ category })

    expect(screen.getByDisplayValue('Groceries')).toBeInTheDocument()
    expect(screen.getByDisplayValue('500.00')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /save changes/i })).toBeInTheDocument()
  })

  it('calls onCancel when Cancel is clicked', async () => {
    const user = userEvent.setup()
    const onCancel = vi.fn()
    renderForm({ onCancel })

    await user.click(screen.getByRole('button', { name: /cancel/i }))

    expect(onCancel).toHaveBeenCalledTimes(1)
  })
})
