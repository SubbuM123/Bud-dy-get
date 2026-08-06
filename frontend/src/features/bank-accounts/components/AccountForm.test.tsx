/**
 * Covers the create-account form's validation and the string->number coercion its Zod
 * schema is responsible for (principal as a float, interest rate as a whole-number
 * percentage converted to a decimal fraction) - the exact values the backend's
 * BankAccountCreate schema expects.
 */
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import AccountForm from './AccountForm'
import type { BankAccount } from '@/types'

const CD_ACCOUNT: BankAccount = {
  id: 'account-1',
  user_id: 'user-1',
  account_name: '3yr CD',
  account_type: 'cd',
  principal: '5000.00',
  current_balance: '5000.00',
  interest_rate: '0.03',
  compounding_frequency: 'monthly',
  cd_start_date: '2026-01-01',
  cd_term_months: 36,
  cd_auto_renew: false,
  is_simulation: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

describe('AccountForm', () => {
  it('rejects submission when the account name is missing', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<AccountForm onSubmit={onSubmit} />)

    await user.type(screen.getByLabelText('Principal Amount ($)'), '10000')
    await user.click(screen.getByRole('button', { name: /create account/i }))

    expect(await screen.findByText('Account name is required')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('submits principal as a number and interest rate as a decimal fraction', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<AccountForm onSubmit={onSubmit} />)

    await user.type(screen.getByLabelText('Account Name'), 'My Savings')
    await user.type(screen.getByLabelText('Principal Amount ($)'), '10000')
    await user.type(screen.getByLabelText('Interest Rate (% APY)'), '4.25')
    await user.click(screen.getByRole('button', { name: /create account/i }))

    expect(onSubmit).toHaveBeenCalledTimes(1)
    const submitted = onSubmit.mock.calls[0][0]
    expect(submitted.account_name).toBe('My Savings')
    expect(submitted.principal).toBe(10000)
    expect(submitted.interest_rate).toBeCloseTo(0.0425)
    expect(submitted.account_type).toBe('savings')
    expect(submitted.compounding_frequency).toBe('monthly')
  })

  it('omits interest rate when left blank', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<AccountForm onSubmit={onSubmit} />)

    await user.type(screen.getByLabelText('Account Name'), 'My Checking')
    await user.type(screen.getByLabelText('Principal Amount ($)'), '500')
    await user.click(screen.getByRole('button', { name: /create account/i }))

    expect(onSubmit).toHaveBeenCalledTimes(1)
    expect(onSubmit.mock.calls[0][0].interest_rate).toBeUndefined()
  })

  it('calls onCancel when Cancel is clicked', async () => {
    const user = userEvent.setup()
    const onCancel = vi.fn()
    render(<AccountForm onSubmit={vi.fn()} onCancel={onCancel} />)

    await user.click(screen.getByRole('button', { name: /cancel/i }))

    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('does not show CD fields for a savings account being created', () => {
    render(<AccountForm onSubmit={vi.fn()} />)

    expect(screen.queryByLabelText('Term Length (months)')).not.toBeInTheDocument()
  })

  it('shows CD start date/term/auto-renew fields once "cd" is selected', async () => {
    const user = userEvent.setup()
    render(<AccountForm onSubmit={vi.fn()} />)

    await user.selectOptions(
      screen.getByLabelText('Account Type'),
      'Certificate of Deposit (CD)'
    )

    expect(screen.getByLabelText('CD Start Date')).toBeInTheDocument()
    expect(screen.getByLabelText('Term Length (months)')).toBeInTheDocument()
    expect(screen.getByText(/keep cding this money after maturity/i)).toBeInTheDocument()
  })

  it('shows a computed maturity date once start date and term are both filled in', async () => {
    const user = userEvent.setup()
    render(<AccountForm onSubmit={vi.fn()} />)

    await user.selectOptions(screen.getByLabelText('Account Type'), 'Certificate of Deposit (CD)')
    const startInput = screen.getByLabelText('CD Start Date')
    await user.clear(startInput)
    await user.type(startInput, '2026-01-01')
    await user.type(screen.getByLabelText('Term Length (months)'), '36')

    expect(await screen.findByText(/matures jan 1, 2029/i)).toBeInTheDocument()
  })
})

describe('AccountForm (edit mode)', () => {
  it('pre-fills fields and locks account_type', () => {
    render(<AccountForm account={CD_ACCOUNT} onSubmit={vi.fn()} />)

    expect(screen.getByText(/cd \(can't be changed after creation\)/i)).toBeInTheDocument()
    expect(screen.queryByLabelText('Account Type')).not.toBeInTheDocument()
    expect(screen.getByDisplayValue('3yr CD')).toBeInTheDocument()
    expect(screen.getByDisplayValue('5000.00')).toBeInTheDocument()
    expect(screen.getByDisplayValue('3')).toBeInTheDocument() // interest rate, as a whole-number percent
    expect(screen.getByRole('button', { name: /save changes/i })).toBeInTheDocument()
  })

  it('shows CD fields pre-filled since the locked type is cd', () => {
    render(<AccountForm account={CD_ACCOUNT} onSubmit={vi.fn()} />)

    expect(screen.getByLabelText('CD Start Date')).toHaveValue('2026-01-01')
    expect(screen.getByLabelText('Term Length (months)')).toHaveValue(36)
    expect(screen.getByText(/matures jan 1, 2029/i)).toBeInTheDocument()
  })

  it('submits edited fields, keeping the locked account_type in the output', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<AccountForm account={CD_ACCOUNT} onSubmit={onSubmit} />)

    const nameInput = screen.getByLabelText('Account Name')
    await user.clear(nameInput)
    await user.type(nameInput, 'Renamed CD')
    await user.click(screen.getByRole('button', { name: /save changes/i }))

    expect(onSubmit).toHaveBeenCalledTimes(1)
    expect(onSubmit.mock.calls[0][0].account_name).toBe('Renamed CD')
    // account_type still comes through in the form's raw output (it's read-only in the
    // UI, not stripped here) - the caller (AccountDetailPage) is responsible for
    // dropping it before sending the PUT request, since BankAccountUpdate rejects it.
    expect(onSubmit.mock.calls[0][0].account_type).toBe('cd')
  })
})
