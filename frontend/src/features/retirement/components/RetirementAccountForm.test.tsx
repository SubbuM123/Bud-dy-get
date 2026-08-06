/**
 * Covers the create/edit retirement account form's validation, the string->number
 * coercion its Zod schema is responsible for (balance/salary as floats, percent fields as
 * whole-number percentages converted to decimal fractions), and the conditional
 * employer/vesting fields that only apply to 401(k)/Roth 401(k) account types.
 */
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import RetirementAccountForm from './RetirementAccountForm'
import type { RetirementAccount } from '@/types'

function renderForm(props: Partial<React.ComponentProps<typeof RetirementAccountForm>> = {}) {
  return render(<RetirementAccountForm onSubmit={vi.fn()} {...props} />)
}

const IRA_ACCOUNT: RetirementAccount = {
  id: 'acct-1',
  user_id: 'user-1',
  account_name: 'My Roth IRA',
  account_type: 'roth_ira',
  balance: '5000.00',
  contribution_ytd: '0.00',
  employer_name: null,
  annual_salary: null,
  employer_match_percent: null,
  employer_match_limit_percent: null,
  vesting_type: null,
  vesting_years: null,
  vested_percent: '100.00',
  expected_return_rate: '0.07',
  is_simulation: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

describe('RetirementAccountForm', () => {
  it('rejects submission when the account name is missing', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    renderForm({ onSubmit })

    await user.type(screen.getByLabelText('Current Balance ($)'), '10000')
    await user.click(screen.getByRole('button', { name: /create account/i }))

    expect(await screen.findByText('Account name is required')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('submits balance as a number and expected return as a decimal fraction', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    renderForm({ onSubmit })

    await user.type(screen.getByLabelText('Account Name'), 'My 401k')
    await user.type(screen.getByLabelText('Current Balance ($)'), '20000')
    const returnInput = screen.getByLabelText('Expected Annual Return (%)')
    await user.clear(returnInput)
    await user.type(returnInput, '8')
    await user.click(screen.getByRole('button', { name: /create account/i }))

    expect(onSubmit).toHaveBeenCalledTimes(1)
    const submitted = onSubmit.mock.calls[0][0]
    expect(submitted.account_name).toBe('My 401k')
    expect(submitted.balance).toBe(20000)
    expect(submitted.expected_return_rate).toBeCloseTo(0.08)
    expect(submitted.account_type).toBe('traditional_401k')
  })

  it('shows employer/vesting fields for a 401(k) (the default account type)', () => {
    renderForm()

    expect(screen.getByLabelText('Employer Name')).toBeInTheDocument()
    expect(screen.getByLabelText('Employer Match (%)')).toBeInTheDocument()
  })

  it('hides employer/vesting fields once an IRA type is selected', async () => {
    const user = userEvent.setup()
    renderForm()

    await user.selectOptions(screen.getByLabelText('Account Type'), 'Roth IRA')

    expect(screen.queryByLabelText('Employer Name')).not.toBeInTheDocument()
  })

  it('calls onCancel when Cancel is clicked', async () => {
    const user = userEvent.setup()
    const onCancel = vi.fn()
    renderForm({ onCancel })

    await user.click(screen.getByRole('button', { name: /cancel/i }))

    expect(onCancel).toHaveBeenCalledTimes(1)
  })
})

describe('RetirementAccountForm (edit mode)', () => {
  it('pre-fills fields and locks account_type', () => {
    renderForm({ account: IRA_ACCOUNT })

    expect(screen.getByText(/roth ira \(can't be changed after creation\)/i)).toBeInTheDocument()
    expect(screen.queryByLabelText('Account Type')).not.toBeInTheDocument()
    expect(screen.getByDisplayValue('My Roth IRA')).toBeInTheDocument()
    expect(screen.getByDisplayValue('5000.00')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /save changes/i })).toBeInTheDocument()
  })
})
