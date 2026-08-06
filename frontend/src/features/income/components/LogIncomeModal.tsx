/**
 * Small popup for logging one real occurrence of a recurring income - opened from
 * IncomeCard's "Log Paycheck" button. Defaults to the income's own amount and today's
 * date, but both are editable (e.g. a paycheck that included overtime, or logging a
 * missed one for an earlier date) since real paychecks don't always match the recurring
 * rule exactly. Confirming splits the amount across the income's allocations and posts
 * real Transaction rows - see hooks/useIncome.ts:useLogIncome.
 */
import { useEffect, useState } from 'react'
import { Modal } from '@/components/ui/modal'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { getApiErrorMessage } from '@/lib/utils'
import { useLogIncome } from '../hooks/useIncome'
import type { Income } from '@/types'

interface LogIncomeModalProps {
  income: Income | null
  onClose: () => void
}

export default function LogIncomeModal({ income, onClose }: LogIncomeModalProps) {
  const logIncome = useLogIncome()
  const [amount, setAmount] = useState('')
  const [logDate, setLogDate] = useState('')

  useEffect(() => {
    if (income) {
      setAmount(income.amount)
      setLogDate(new Date().toISOString().slice(0, 10))
    }
  }, [income])

  const handleConfirm = async () => {
    if (!income) return
    try {
      await logIncome.mutateAsync({
        id: income.id,
        data: { amount: parseFloat(amount), log_date: logDate },
      })
      onClose()
    } catch {
      // handled via logIncome.error below - keep the popup open so the user can retry
    }
  }

  return (
    <Modal open={!!income} onClose={onClose} title={income ? `Log "${income.name}"` : ''}>
      <div className="space-y-4">
        {logIncome.isError && (
          <div className="rounded-md bg-danger-500/10 p-3 text-sm text-danger-500">
            {getApiErrorMessage(logIncome.error, 'Failed to log income')}
          </div>
        )}

        <Input
          label="Amount ($)"
          type="number"
          step="0.01"
          min="0.01"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
        />
        <Input label="Date" type="date" value={logDate} onChange={(e) => setLogDate(e.target.value)} />
        <p className="text-xs text-slate-400">
          This will split the amount across every destination in this income's allocation
          and update those accounts' real balances.
        </p>

        <div className="flex gap-3 pt-2">
          <Button onClick={handleConfirm} disabled={logIncome.isPending}>
            {logIncome.isPending ? 'Logging...' : 'Confirm'}
          </Button>
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
        </div>
      </div>
    </Modal>
  )
}
