/**
 * Receipt inbox at /receipts: upload zone at the top, then every receipt as a grid of
 * ReceiptCard, filterable by processing status. useReceipts (hooks/useExpenses.ts) polls
 * on its own while anything is still pending/processing, so a batch upload's status moves
 * from queued -> processing -> ready for review without the user refreshing.
 */
import { useState } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { cn, getApiErrorMessage } from '@/lib/utils'
import ReceiptUploader from '../components/ReceiptUploader'
import ReceiptCard from '../components/ReceiptCard'
import { useReceipts, useUploadReceipts, useDeleteReceipt } from '../hooks/useExpenses'
import type { ReceiptProcessingStatus } from '@/types'

const STATUS_TABS: { value: ReceiptProcessingStatus | 'all'; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'needs_review', label: 'Needs Review' },
  { value: 'pending', label: 'Queued' },
  { value: 'processing', label: 'Processing' },
  { value: 'completed', label: 'Completed' },
  { value: 'failed', label: 'Failed' },
]

export default function ReceiptsPage() {
  const [activeTab, setActiveTab] = useState<ReceiptProcessingStatus | 'all'>('all')

  const { data: receipts, isLoading } = useReceipts(activeTab === 'all' ? undefined : activeTab)

  const uploadReceipts = useUploadReceipts()
  const deleteReceipt = useDeleteReceipt()

  const handleUpload = (files: File[]) => {
    uploadReceipts.mutate(files)
  }

  const handleDelete = (id: string) => {
    if (window.confirm('Delete this receipt? Any expense already created from it will be kept.')) {
      deleteReceipt.mutate(id)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-bold text-slate-900">Receipts</h1>
          <span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs font-semibold uppercase tracking-wide text-slate-600">
            Beta
          </span>
        </div>
        <p className="text-slate-500">
          Upload receipt photos or PDFs to extract merchant, total, and date automatically.
          This is a standalone digitization tool for now - it isn't connected to Expenses.
        </p>
      </div>

      <Card>
        <CardContent className="pt-6">
          {uploadReceipts.isError && (
            <div className="mb-4 rounded-md bg-danger-500/10 p-3 text-sm text-danger-500">
              {getApiErrorMessage(uploadReceipts.error, 'Failed to upload receipts')}
            </div>
          )}
          {uploadReceipts.data && (
            <div className="mb-4 rounded-md bg-slate-50 p-3 text-sm text-slate-600">
              Uploaded {uploadReceipts.data.results.filter((r) => r.receipt_id).length} of{' '}
              {uploadReceipts.data.results.length} file(s).{' '}
              {uploadReceipts.data.results
                .filter((r) => r.error)
                .map((r) => `${r.filename}: ${r.error}`)
                .join(' ')}
            </div>
          )}
          <ReceiptUploader onUpload={handleUpload} isUploading={uploadReceipts.isPending} />
        </CardContent>
      </Card>

      <div className="flex gap-2 overflow-x-auto pb-1">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => setActiveTab(tab.value)}
            className={cn(
              'shrink-0 rounded-full px-3 py-1.5 text-sm font-medium transition-colors',
              activeTab === tab.value
                ? 'bg-primary-600 text-white'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <p className="py-12 text-center text-slate-500">Loading receipts...</p>
      ) : receipts?.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <p className="text-slate-500">No receipts here yet</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
          {receipts?.map((receipt) => (
            <ReceiptCard key={receipt.id} receipt={receipt} onDelete={handleDelete} />
          ))}
        </div>
      )}
    </div>
  )
}
