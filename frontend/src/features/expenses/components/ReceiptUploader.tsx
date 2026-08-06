/**
 * Drag-and-drop + file-picker upload zone for receipts. Supports three ways of selecting
 * files - a single photo, several files picked at once, or an entire folder (the "Choose
 * Folder" button uses the non-standard but widely-supported `webkitdirectory` attribute,
 * which every major desktop browser implements despite the vendor-prefixed name) - all of
 * which end up as the same flat `File[]` handed to a single POST /receipts/upload batch
 * request, matching how the backend's upload endpoint treats every file in a batch
 * independently regardless of how the browser collected them. No drag-and-drop library is
 * used (e.g. react-dropzone) - native HTML5 drag events are enough for this and avoid a
 * new dependency, the same reasoning components/ui/info-tooltip.tsx used to avoid a
 * tooltip library.
 */
import { useRef, useState, type DragEvent, type ChangeEvent } from 'react'
import { Upload, FolderUp, FileImage } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

const ACCEPTED_EXTENSIONS = '.jpg,.jpeg,.png,.heic,.heif,.pdf'

interface ReceiptUploaderProps {
  onUpload: (files: File[]) => void
  isUploading?: boolean
}

export default function ReceiptUploader({ onUpload, isUploading }: ReceiptUploaderProps) {
  const [isDraggingOver, setIsDraggingOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const folderInputRef = useRef<HTMLInputElement>(null)

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setIsDraggingOver(false)
    const files = Array.from(event.dataTransfer.files)
    if (files.length > 0) {
      onUpload(files)
    }
  }

  const handleFileInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? [])
    if (files.length > 0) {
      onUpload(files)
    }
    // Reset so selecting the exact same file(s) again still fires onChange next time.
    event.target.value = ''
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault()
        setIsDraggingOver(true)
      }}
      onDragLeave={() => setIsDraggingOver(false)}
      onDrop={handleDrop}
      className={cn(
        'flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed p-10 text-center transition-colors',
        isDraggingOver ? 'border-primary-500 bg-primary-50' : 'border-slate-300 bg-slate-50'
      )}
    >
      <div className="rounded-full bg-primary-100 p-3">
        <FileImage className="h-6 w-6 text-primary-600" />
      </div>
      <p className="text-sm text-slate-600">
        Drag and drop receipt photos or PDFs here, or choose files below
      </p>
      <p className="text-xs text-slate-400">JPG, PNG, HEIC, or PDF - up to 10MB each</p>

      <div className="flex gap-3 pt-2">
        <Button
          type="button"
          variant="outline"
          disabled={isUploading}
          onClick={() => fileInputRef.current?.click()}
        >
          <Upload className="h-4 w-4 mr-2" />
          Choose Files
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={isUploading}
          onClick={() => folderInputRef.current?.click()}
        >
          <FolderUp className="h-4 w-4 mr-2" />
          Choose Folder
        </Button>
      </div>

      {isUploading && <p className="text-sm text-primary-600">Uploading...</p>}

      <input
        ref={fileInputRef}
        data-testid="receipt-file-input"
        type="file"
        multiple
        accept={ACCEPTED_EXTENSIONS}
        onChange={handleFileInputChange}
        className="hidden"
      />
      <input
        ref={folderInputRef}
        data-testid="receipt-folder-input"
        type="file"
        multiple
        // @ts-expect-error - webkitdirectory has no official React typing but is
        // supported by every major desktop browser for folder selection.
        webkitdirectory=""
        onChange={handleFileInputChange}
        className="hidden"
      />
    </div>
  )
}
