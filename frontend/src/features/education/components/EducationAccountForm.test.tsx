/**
 * Covers the create/edit education account form's validation, the string->number
 * coercion its Zod schema is responsible for (balance as a float, expected return as a
 * whole-number percentage converted to a decimal fraction), and that beneficiary_name is
 * required while account_type stays locked to 529 Plan in edit mode.
 */
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import EducationAccountForm from './EducationAccountForm'
import type { EducationAccount } from '@/types'

function renderForm(props: Partial<React.ComponentProps<typeof EducationAccountForm>> = {}) {
  return render(<EducationAccountForm onSubmit={vi.fn()} {...props} />)
}

const FIVE_TWENTY_NINE_ACCOUNT: EducationAccount = {
  id: 'acct-1',
  user_id: 'user-1',
  account_name: "Jordan's College Fund",
  account_type: '529_plan',
  beneficiary_name: 'Jordan Smith',
  beneficiary_birth_date: '2015-06-01',
  plan_provider: 'NY 529 College Savings Program',
  balance: '5000.00',
  contribution_ytd: '0.00',
  expected_return_rate: '0.07',
  is_simulation: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

describe('EducationAccountForm', () => {
  it('rejects submission when the account name is missing', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    renderForm({ onSubmit })

    await user.type(screen.getByLabelText('Beneficiary Name'), 'Jordan Smith')
    await user.type(screen.getByLabelText('Current Balance ($)'), '10000')
    await user.click(screen.getByRole('button', { name: /create account/i }))

    expect(await screen.findByText('Account name is required')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('rejects submission when the beneficiary name is missing', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    renderForm({ onSubmit })

    await user.type(screen.getByLabelText('Account Name'), "Jordan's College Fund")
    await user.type(screen.getByLabelText('Current Balance ($)'), '10000')
    await user.click(screen.getByRole('button', { name: /create account/i }))

    expect(await screen.findByText('Beneficiary name is required')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('submits balance as a number and expected return as a decimal fraction', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    renderForm({ onSubmit })

    await user.type(screen.getByLabelText('Account Name'), "Jordan's College Fund")
    await user.type(screen.getByLabelText('Beneficiary Name'), 'Jordan Smith')
    await user.type(screen.getByLabelText('Current Balance ($)'), '20000')
    const returnInput = screen.getByLabelText('Expected Annual Return (%)')
    await user.clear(returnInput)
    await user.type(returnInput, '8')
    await user.click(screen.getByRole('button', { name: /create account/i }))

    expect(onSubmit).toHaveBeenCalledTimes(1)
    const submitted = onSubmit.mock.calls[0][0]
    expect(submitted.account_name).toBe("Jordan's College Fund")
    expect(submitted.beneficiary_name).toBe('Jordan Smith')
    expect(submitted.balance).toBe(20000)
    expect(submitted.expected_return_rate).toBeCloseTo(0.08)
    expect(submitted.account_type).toBe('529_plan')
  })

  it('shows a "coming soon" option for Coverdell ESA', () => {
    renderForm()

    const option = screen.getByRole('option', { name: /coverdell esa \(coming soon\)/i })
    expect(option).toBeInTheDocument()
  })

  it('calls onCancel when Cancel is clicked', async () => {
    const user = userEvent.setup()
    const onCancel = vi.fn()
    renderForm({ onCancel })

    await user.click(screen.getByRole('button', { name: /cancel/i }))

    expect(onCancel).toHaveBeenCalledTimes(1)
  })
})

describe('EducationAccountForm (edit mode)', () => {
  it('pre-fills fields and locks account_type', () => {
    renderForm({ account: FIVE_TWENTY_NINE_ACCOUNT })

    expect(screen.getByText(/529 plan \(can't be changed after creation\)/i)).toBeInTheDocument()
    expect(screen.queryByLabelText('Account Type')).not.toBeInTheDocument()
    expect(screen.getByDisplayValue("Jordan's College Fund")).toBeInTheDocument()
    expect(screen.getByDisplayValue('Jordan Smith')).toBeInTheDocument()
    expect(screen.getByDisplayValue('5000.00')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /save changes/i })).toBeInTheDocument()
  })
})
