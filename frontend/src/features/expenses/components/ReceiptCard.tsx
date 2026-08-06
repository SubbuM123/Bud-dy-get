/**
 * Summary card for a single uploaded receipt, shown in the grid on ReceiptsPage. Shows an
 * image thumbnail (or a generic file icon for PDFs, which don't have a browser-renderable
 * thumbnail without extra work this app doesn't do), a processing-status badge, and
 * whichever of the three core fields (merchant/total/date) extraction has produced so far,
 * each flagged if its confidence is low enough that services/receipt_parser.py's
 * REVIEW_CONFIDENCE_THRESHOLD would call it out. Links through to ReceiptDetailPage for
 * the full review flow.
 *
 * The primary action varies by status: needs_review gets a "Review" button that opens
 * ReceiptReviewModal (a human confirming the fields promotes the receipt to completed -
 * see api/v1/receipts.py's update_receipt); completed gets a pencil "Edit" icon for later
 * corrections without changing its status; failed - reserved for genuine extraction/system
 * failures, not just low-confidence reads, since should_flag_for_review already routes
 * those to needs_review - gets a "Try Again" button that re-enqueues processing.
 */
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { FileText, Trash2, AlertTriangle, Pencil, RefreshCw } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { formatCurrency } from '@/lib/utils'
import ReceiptReviewModal from './ReceiptReviewModal'
import { useReprocessReceipt } from '../hooks/useExpenses'
import type { Receipt } from '@/types'

interface ReceiptCardProps {
  receipt: Receipt
  onDelete?: (id: string) => void
}

const STATUS_LABELS: Record<Receipt['processing_status'], string> = {
  pending: 'Queued',
  processing: 'Processing...',
  completed: 'Completed',
  needs_review: 'Needs review',
  failed: 'Failed',
}

const STATUS_BADGE_CLASSES: Record<Receipt['processing_status'], string> = {
  pending: 'bg-slate-100 text-slate-600',
  processing: 'bg-blue-100 text-blue-700',
  completed: 'bg-success-500/10 text-success-600',
  needs_review: 'bg-amber-100 text-amber-700',
  failed: 'bg-danger-500/10 text-danger-500',
}

// Below this, a field's own extraction is flagged with a warning icon on the card - kept
// in sync with services/receipt_parser.py's REVIEW_CONFIDENCE_THRESHOLD (0.6).
const LOW_CONFIDENCE_THRESHOLD = 0.6

function isLowConfidence(confidence: string | null): boolean {
  return confidence === null || parseFloat(confidence) < LOW_CONFIDENCE_THRESHOLD
}

export default function ReceiptCard({ receipt, onDelete }: ReceiptCardProps) {
  const isImage = receipt.file_type.startsWith('image/')
  const [isReviewOpen, setIsReviewOpen] = useState(false)
  const reprocessReceipt = useReprocessReceipt()

  return (
    <Card className="hover:shadow-md transition-shadow">
      <Link to={`/receipts/${receipt.id}`}>
        <div className="flex h-36 items-center justify-center overflow-hidden rounded-t-lg bg-slate-100">
          {isImage ? (
            <img
              src={receipt.file_url}
              alt={receipt.original_filename}
              className="h-full w-full object-cover"
            />
          ) : (
            <FileText className="h-10 w-10 text-slate-400" />
          )}
        </div>
      </Link>

      <CardContent className="pt-4">
        <div className="flex items-start justify-between gap-2">
          <p className="truncate text-sm font-medium text-slate-700" title={receipt.original_filename}>
            {receipt.original_filename}
          </p>
          <div className="flex shrink-0 items-center gap-1">
            {receipt.processing_status === 'completed' && (
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-slate-400 hover:text-primary-600"
                onClick={() => setIsReviewOpen(true)}
                title="Edit reviewed fields"
              >
                <Pencil className="h-4 w-4" />
              </Button>
            )}
            {onDelete && (
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-slate-400 hover:text-danger-500"
                onClick={() => onDelete(receipt.id)}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>

        <span
          className={`mt-2 inline-block rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_BADGE_CLASSES[receipt.processing_status]}`}
        >
          {STATUS_LABELS[receipt.processing_status]}
        </span>

        {(receipt.merchant_name || receipt.total_amount || receipt.transaction_date) && (
          <div className="mt-3 space-y-1 text-sm">
            {receipt.merchant_name && (
              <p className="flex items-center gap-1 font-medium text-slate-900">
                {receipt.merchant_name}
                {isLowConfidence(receipt.merchant_name_confidence) && (
                  <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
                )}
              </p>
            )}
            <div className="flex items-center justify-between text-slate-500">
              <span className="flex items-center gap-1">
                {receipt.total_amount ? formatCurrency(receipt.total_amount) : '—'}
                {isLowConfidence(receipt.total_amount_confidence) && (
                  <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
                )}
              </span>
              <span className="flex items-center gap-1">
                {receipt.transaction_date ?? '—'}
                {isLowConfidence(receipt.transaction_date_confidence) && (
                  <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
                )}
              </span>
            </div>
          </div>
        )}

        {receipt.processing_error && (
          <p className="mt-2 text-xs text-danger-500">{receipt.processing_error}</p>
        )}

        {receipt.processing_status === 'needs_review' && (
          <Button size="sm" className="mt-3 w-full" onClick={() => setIsReviewOpen(true)}>
            Review
          </Button>
        )}

        {receipt.processing_status === 'failed' && (
          <Button
            size="sm"
            variant="outline"
            className="mt-3 w-full"
            disabled={reprocessReceipt.isPending}
            onClick={() => reprocessReceipt.mutate(receipt.id)}
          >
            <RefreshCw className="mr-2 h-3.5 w-3.5" />
            {reprocessReceipt.isPending ? 'Retrying...' : 'Try Again'}
          </Button>
        )}
      </CardContent>

      <ReceiptReviewModal
        receipt={receipt}
        open={isReviewOpen}
        onClose={() => setIsReviewOpen(false)}
      />
    </Card>
  )
}
