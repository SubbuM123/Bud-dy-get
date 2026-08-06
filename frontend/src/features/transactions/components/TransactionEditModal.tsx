/**
 * Small popup for correcting a transaction's amount/date/description - opened from a row's
 * pencil icon on TransactionsPage. Saving applies the amount change as a delta to
 * whatever account the transaction originally affected (see api/v1/transactions.py's
 * update_transaction), so e.g. correcting a $500 contribution logged as $50 bumps that
 * account's balance by the missing $450 rather than requiring a manual fix elsewhere.
 */
import { useEffect, useState } from 'react'
import { Modal } from '@/components/ui/modal'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { getApiErrorMessage } from '@/lib/utils'
import { useUpdateTransaction } from '../hooks/useTransactions'
import type { Transaction } from '@/types'

interface TransactionEditModalProps {
  transaction: Transaction | null
  onClose: () => void
}

export default function TransactionEditModal({ transaction, onClose }: TransactionEditModalProps) {
  const updateTransaction = useUpdateTransaction()
  const [amount, setAmount] = useState('')
  const [date, setDate] = useState('')
  const [description, setDescription] = useState('')

  useEffect(() => {
    if (transaction) {
      setAmount(transaction.amount)
      setDate(transaction.transaction_date)
      setDescription(transaction.description ?? '')
    }
  }, [transaction])

  const handleSave = async () => {
    if (!transaction) return
    try {
      await updateTransaction.mutateAsync({
        id: transaction.id,
        data: {
          amount: parseFloat(amount),
          transaction_date: date,
          description: description || undefined,
        },
      })
      onClose()
    } catch {
      // handled via updateTransaction.error below - keep the popup open so the user can retry
    }
  }

  return (
    <Modal open={!!transaction} onClose={onClose} title="Edit Transaction">
      <div className="space-y-4">
        {updateTransaction.isError && (
          <div className="rounded-md bg-danger-500/10 p-3 text-sm text-danger-500">
            {getApiErrorMessage(updateTransaction.error, 'Failed to update transaction')}
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
        <Input label="Date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        <Input
          label="Description (optional)"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
        <p className="text-xs text-slate-400">
          Changing the amount adjusts the affected account's balance by the difference.
        </p>

        <div className="flex gap-3 pt-2">
          <Button onClick={handleSave} disabled={updateTransaction.isPending}>
            {updateTransaction.isPending ? 'Saving...' : 'Save'}
          </Button>
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
        </div>
      </div>
    </Modal>
  )
}
