import { useEffect, useState } from 'react'
import { apiDownloadBlob } from '../lib/api'

function formatFileSize(bytes) {
  const num = Number(bytes || 0)
  if (!Number.isFinite(num) || num <= 0) return 'Image'
  if (num < 1024) return `${num} B`
  if (num < 1024 * 1024) return `${(num / 1024).toFixed(1)} KB`
  return `${(num / (1024 * 1024)).toFixed(2)} MB`
}

function AttachmentThumbnailCard({ attachment, onOpenPreview }) {
  const attachmentUrl = attachment?.url || ''
  const [state, setState] = useState({
    status: attachmentUrl ? 'loading' : 'error',
    objectUrl: null,
    errorMsg: attachmentUrl ? '' : 'Photo URL missing.',
  })
  const [retryCount, setRetryCount] = useState(0)

  useEffect(() => {
    if (!attachmentUrl) {
      return undefined
    }

    let cancelled = false
    let createdUrl = null

    apiDownloadBlob(attachmentUrl, {
      accept: 'image/jpeg,image/png,image/webp,image/*',
    })
      .then(({ blob }) => {
        if (cancelled) return
        if (typeof URL.createObjectURL === 'function') {
          createdUrl = URL.createObjectURL(blob)
          setState({ status: 'loaded', objectUrl: createdUrl, errorMsg: '' })
        } else {
          setState({
            status: 'error',
            objectUrl: null,
            errorMsg: 'Preview unavailable in this environment.',
          })
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setState({
            status: 'error',
            objectUrl: null,
            errorMsg: err?.message || 'Unable to load photo.',
          })
        }
      })

    return () => {
      cancelled = true
      if (createdUrl && typeof URL.revokeObjectURL === 'function') {
        URL.revokeObjectURL(createdUrl)
      }
    }
  }, [attachmentUrl, retryCount])

  const handleRetry = () => {
    setState({
      status: attachmentUrl ? 'loading' : 'error',
      objectUrl: null,
      errorMsg: attachmentUrl ? '' : 'Photo URL missing.',
    })
    setRetryCount((c) => c + 1)
  }

  const loading = Boolean(attachmentUrl) && state.status === 'loading'
  const objectUrl = state.objectUrl
  const errorMsg = !attachmentUrl ? 'Photo URL missing.' : state.errorMsg

  const displayName = attachment?.filename || attachment?.originalFilename || 'Attachment photo'
  const sizeLabel = formatFileSize(attachment?.fileSizeBytes ?? attachment?.file_size_bytes)

  return (
    <div className="rounded-2xl border border-[#E8DCCF] bg-[#FFFDF9] overflow-hidden flex flex-col shadow-2xs">
      <div className="aspect-[4/3] bg-[#F7EFE6]/70 relative flex items-center justify-center overflow-hidden">
        {loading ? (
          <span className="text-[11px] font-medium text-[#292039]/60">Loading photo...</span>
        ) : errorMsg || !objectUrl ? (
          <div className="p-3 text-center space-y-2">
            <p className="text-[11px] text-rose-700 font-medium">
              {errorMsg || 'Photo unavailable.'}
            </p>
            <button
              type="button"
              onClick={handleRetry}
              className="px-2.5 py-1 rounded-lg border border-[#D8CEBE] bg-white text-[11px] font-semibold text-[#292039] hover:bg-[#F7EFE6] cursor-pointer"
            >
              Retry
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => onOpenPreview({ src: objectUrl, name: displayName, sizeLabel })}
            aria-label={`View ${displayName}`}
            className="w-full h-full group focus:outline-none focus:ring-2 focus:ring-[#D94378] cursor-pointer"
          >
            <img
              src={objectUrl}
              alt={displayName}
              className="w-full h-full object-cover group-hover:scale-103 transition-transform duration-200"
            />
          </button>
        )}
      </div>
      <div className="px-3 py-2 flex items-center justify-between gap-2 text-[11px] border-t border-[#F0E4D4]">
        <span className="font-medium text-[#292039] truncate" title={displayName}>
          {displayName}
        </span>
        <span className="text-[#292039]/60 font-mono shrink-0">{sizeLabel}</span>
      </div>
    </div>
  )
}

export function ComplaintAttachmentsGallery({ attachments }) {
  const [previewItem, setPreviewItem] = useState(null)

  useEffect(() => {
    if (!previewItem) return undefined
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        setPreviewItem(null)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [previewItem])

  if (!Array.isArray(attachments) || attachments.length === 0) {
    return null
  }

  return (
    <div className="space-y-2.5">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-bold uppercase tracking-wider text-[#292039]/70">
          Attached Photos ({attachments.length})
        </span>
        <span className="text-[11px] text-[#292039]/55">Click any photo to enlarge</span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {attachments.map((att, idx) => (
          <AttachmentThumbnailCard
            key={att.id || att.publicId || att.url || idx}
            attachment={att}
            onOpenPreview={setPreviewItem}
          />
        ))}
      </div>

      {previewItem && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={`Photo preview: ${previewItem.name}`}
          onClick={() => setPreviewItem(null)}
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#292039]/80 backdrop-blur-xs"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="bg-[#FFFCF7] max-w-3xl w-full rounded-3xl border border-[#E8DCCF] shadow-2xl overflow-hidden"
          >
            <div className="px-5 py-3.5 border-b border-[#E8DCCF] flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="text-xs font-bold text-[#292039] truncate">{previewItem.name}</p>
                <p className="text-[11px] text-[#292039]/60 font-mono">{previewItem.sizeLabel}</p>
              </div>
              <button
                type="button"
                onClick={() => setPreviewItem(null)}
                aria-label="Close photo preview"
                className="px-3 py-1.5 rounded-xl bg-[#F7EFE6] text-xs font-bold text-[#292039] hover:bg-[#E8DCCF] cursor-pointer"
              >
                Close ✕
              </button>
            </div>
            <div className="p-4 bg-[#1E172A] flex items-center justify-center max-h-[75vh]">
              <img
                src={previewItem.src}
                alt={previewItem.name}
                className="max-h-[70vh] max-w-full object-contain rounded-lg"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
