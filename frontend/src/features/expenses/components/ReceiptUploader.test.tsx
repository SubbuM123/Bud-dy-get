/**
 * Covers ReceiptUploader's two file-selection paths (the "Choose Files" input and native
 * drag-and-drop onto the drop zone) both calling onUpload with the selected files, plus
 * that the upload buttons disable while an upload is in flight.
 */
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import ReceiptUploader from './ReceiptUploader'

function makeFile(name: string, type: string) {
  return new File(['fake-bytes'], name, { type })
}

describe('ReceiptUploader', () => {
  it('calls onUpload with the files chosen via the file input', async () => {
    const user = userEvent.setup()
    const onUpload = vi.fn()
    render(<ReceiptUploader onUpload={onUpload} />)

    const file = makeFile('receipt.jpg', 'image/jpeg')
    const fileInput = screen.getByTestId('receipt-file-input')
    await user.upload(fileInput, file)

    expect(onUpload).toHaveBeenCalledWith([file])
  })

  it('calls onUpload with files dropped onto the zone', () => {
    const onUpload = vi.fn()
    render(<ReceiptUploader onUpload={onUpload} />)

    const file = makeFile('receipt.png', 'image/png')
    const dropZone = screen.getByText(/drag and drop receipt photos/i).closest('div')!

    fireEvent.drop(dropZone, { dataTransfer: { files: [file] } })

    expect(onUpload).toHaveBeenCalledWith([file])
  })

  it('disables the choose-files buttons while uploading', () => {
    render(<ReceiptUploader onUpload={vi.fn()} isUploading />)

    expect(screen.getByRole('button', { name: /choose files/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /choose folder/i })).toBeDisabled()
    expect(screen.getByText('Uploading...')).toBeInTheDocument()
  })
})
