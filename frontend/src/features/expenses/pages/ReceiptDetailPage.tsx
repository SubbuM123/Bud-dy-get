/**
 * Review/detail view for a single receipt at /receipts/:receiptId: the uploaded image (or
 * a file icon for PDFs) side by side with editable fields for the three core values
 * (merchant/total/date) plus the secondary ones, each flagged if its extraction
 * confidence is low. Saving corrections goes through PUT /receipts/{id}. Receipts is a
 * standalone beta digitization tool for v1 - see docs/plan.md's "Unified Money Flow
 * Reform" - so there is deliberately no "create an Expense from this receipt" action
 * here; a reviewed receipt's fields are just for the user's own reference until this
 * module is reconnected to Expenses in a later pass.
 */
import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, FileText, RefreshCw, CheckCircle2, AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card'
import { useReceipt, useUpdateReceipt, useReprocessReceipt } from '../hooks/useExpenses'
import { getApiErrorMessage } from '@/lib/utils'

const LOW_CONFIDENCE_THRESHOLD = 0.6

function isLowConfidence(confidence: string | null): boolean {
  return confidence === null || parseFloat(confidence) < LOW_CONFIDENCE_THRESHOLD
}

export default function ReceiptDetailPage() {
  const { receiptId } = useParams<{ receiptId: string }>()

  const { data: receipt, isLoading } = useReceipt(receiptId!)
  const updateReceipt = useUpdateReceipt()
  const reprocessReceipt = useReprocessReceipt()

  const [merchantName, setMerchantName] = useState('')
  const [totalAmount, setTotalAmount] = useState('')
  const [transactionDate, setTransactionDate] = useState('')

  // Seed the editable fields once the receipt loads (or reloads after a reprocess).
  useEffect(() => {
    if (receipt) {
      setMerchantName(receipt.merchant_name ?? '')
      setTotalAmount(receipt.total_amount ?? '')
      setTransactionDate(receipt.transaction_date ?? '')
    }
  }, [receipt?.id, receipt?.merchant_name, receipt?.total_amount, receipt?.transaction_date])

  const handleSaveCorrections = async () => {
    await updateReceipt.mutateAsync({
      id: receiptId!,
      data: {
        merchant_name: merchantName || undefined,
        total_amount: totalAmount ? parseFloat(totalAmount) : undefined,
        transaction_date: transactionDate || undefined,
        user_verified: true,
      },
    })
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-slate-500">Loading receipt...</p>
      </div>
    )
  }

  if (!receipt) {
    return (
      <div className="text-center py-12">
        <p className="text-slate-500">Receipt not found</p>
        <Link to="/receipts" className="text-primary-600 hover:underline">
          Back to receipts
        </Link>
      </div>
    )
  }

  const isImage = receipt.file_type.startsWith('image/')

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link to="/receipts">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-5 w-5" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{receipt.original_filename}</h1>
          <p className="text-slate-500">Uploaded {new Date(receipt.created_at).toLocaleString()}</p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardContent className="pt-6">
            {isImage ? (
              <img
                src={receipt.file_url}
                alt={receipt.original_filename}
                className="w-full rounded-md border border-slate-200 object-contain"
              />
            ) : (
              <div className="flex flex-col items-center justify-center gap-3 py-12">
                <FileText className="h-12 w-12 text-slate-400" />
                <a
                  href={receipt.file_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-primary-600 hover:underline"
                >
                  Open PDF
                </a>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Review Extracted Fields</CardTitle>
                <CardDescription>
                  Fields flagged with a warning had low-confidence extraction - double check
                  them
                </CardDescription>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => reprocessReceipt.mutate(receiptId!)}
                title="Re-run extraction"
              >
                <RefreshCw className="h-4 w-4" />
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {updateReceipt.isError && (
              <div className="rounded-md bg-danger-500/10 p-3 text-sm text-danger-500">
                {getApiErrorMessage(updateReceipt.error, 'Failed to save corrections')}
              </div>
            )}

            <Input
              label="Merchant"
              value={merchantName}
              onChange={(e) => setMerchantName(e.target.value)}
              tooltip={
                isLowConfidence(receipt.merchant_name_confidence) ? (
                  <AlertTriangle className="h-4 w-4 text-amber-500" />
                ) : (
                  <CheckCircle2 className="h-4 w-4 text-success-500" />
                )
              }
            />

            <Input
              label="Total Amount ($)"
              type="number"
              step="0.01"
              value={totalAmount}
              onChange={(e) => setTotalAmount(e.target.value)}
              tooltip={
                isLowConfidence(receipt.total_amount_confidence) ? (
                  <AlertTriangle className="h-4 w-4 text-amber-500" />
                ) : (
                  <CheckCircle2 className="h-4 w-4 text-success-500" />
                )
              }
            />

            <Input
              label="Date"
              type="date"
              value={transactionDate}
              onChange={(e) => setTransactionDate(e.target.value)}
              tooltip={
                isLowConfidence(receipt.transaction_date_confidence) ? (
                  <AlertTriangle className="h-4 w-4 text-amber-500" />
                ) : (
                  <CheckCircle2 className="h-4 w-4 text-success-500" />
                )
              }
            />

            {receipt.tax_amount && (
              <p className="text-sm text-slate-500">Tax detected: ${receipt.tax_amount}</p>
            )}

            <Button onClick={handleSaveCorrections} disabled={updateReceipt.isPending} variant="outline">
              {updateReceipt.isPending ? 'Saving...' : 'Save Corrections'}
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
