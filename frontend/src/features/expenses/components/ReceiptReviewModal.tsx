/**
 * Small popup for reviewing/correcting a receipt's known extracted fields, opened from
 * ReceiptCard's "Review" button (needs_review/failed receipts) or pencil icon (completed
 * receipts, for later corrections). Saving submits whatever the user left in each field
 * (blank clears it) plus user_verified: true - the backend (api/v1/receipts.py's
 * update_receipt) treats that as "a human confirmed this is good" and promotes
 * needs_review/failed receipts into completed. Cancel discards the edits and closes
 * without calling the API, so a receipt only ever changes on an explicit Save.
 */
import { useEffect, useState } from 'react'
import { Modal } from '@/components/ui/modal'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useUpdateReceipt } from '../hooks/useExpenses'
import { getApiErrorMessage } from '@/lib/utils'
import type { Receipt } from '@/types'

interface ReceiptReviewModalProps {
  receipt: Receipt
  open: boolean
  onClose: () => void
}

export default function ReceiptReviewModal({ receipt, open, onClose }: ReceiptReviewModalProps) {
  const updateReceipt = useUpdateReceipt()

  const [merchantName, setMerchantName] = useState('')
  const [totalAmount, setTotalAmount] = useState('')
  const [transactionDate, setTransactionDate] = useState('')
  const [taxAmount, setTaxAmount] = useState('')
  const [subtotalAmount, setSubtotalAmount] = useState('')
  const [paymentMethod, setPaymentMethod] = useState('')
  const [receiptNumber, setReceiptNumber] = useState('')

  // Re-seed from the receipt every time the popup opens, so a prior cancelled edit never
  // lingers into the next open.
  useEffect(() => {
    if (!open) return
    setMerchantName(receipt.merchant_name ?? '')
    setTotalAmount(receipt.total_amount ?? '')
    setTransactionDate(receipt.transaction_date ?? '')
    setTaxAmount(receipt.tax_amount ?? '')
    setSubtotalAmount(receipt.subtotal_amount ?? '')
    setPaymentMethod(receipt.payment_method ?? '')
    setReceiptNumber(receipt.receipt_number ?? '')
  }, [open, receipt])

  const handleSave = async () => {
    try {
      await updateReceipt.mutateAsync({
        id: receipt.id,
        data: {
          merchant_name: merchantName || undefined,
          total_amount: totalAmount ? parseFloat(totalAmount) : undefined,
          transaction_date: transactionDate || undefined,
          tax_amount: taxAmount ? parseFloat(taxAmount) : undefined,
          subtotal_amount: subtotalAmount ? parseFloat(subtotalAmount) : undefined,
          payment_method: paymentMethod || undefined,
          receipt_number: receiptNumber || undefined,
          user_verified: true,
        },
      })
      onClose()
    } catch {
      // handled via updateReceipt.error below - keep the popup open so the user can retry
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Review Receipt">
      <div className="space-y-4">
        {updateReceipt.isError && (
          <div className="rounded-md bg-danger-500/10 p-3 text-sm text-danger-500">
            {getApiErrorMessage(updateReceipt.error, 'Failed to save receipt')}
          </div>
        )}

        <Input
          label="Merchant"
          value={merchantName}
          onChange={(e) => setMerchantName(e.target.value)}
        />
        <Input
          label="Total Amount ($)"
          type="number"
          step="0.01"
          value={totalAmount}
          onChange={(e) => setTotalAmount(e.target.value)}
        />
        <Input
          label="Date"
          type="date"
          value={transactionDate}
          onChange={(e) => setTransactionDate(e.target.value)}
        />
        <div className="grid grid-cols-2 gap-3">
          <Input
            label="Tax ($)"
            type="number"
            step="0.01"
            value={taxAmount}
            onChange={(e) => setTaxAmount(e.target.value)}
          />
          <Input
            label="Subtotal ($)"
            type="number"
            step="0.01"
            value={subtotalAmount}
            onChange={(e) => setSubtotalAmount(e.target.value)}
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Input
            label="Payment Method"
            value={paymentMethod}
            onChange={(e) => setPaymentMethod(e.target.value)}
          />
          <Input
            label="Receipt #"
            value={receiptNumber}
            onChange={(e) => setReceiptNumber(e.target.value)}
          />
        </div>

        <div className="flex gap-3 pt-2">
          <Button onClick={handleSave} disabled={updateReceipt.isPending}>
            {updateReceipt.isPending ? 'Saving...' : 'Save'}
          </Button>
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
        </div>
      </div>
    </Modal>
  )
}
