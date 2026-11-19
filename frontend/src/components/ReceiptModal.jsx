import { useState } from 'react'
import { createPortal } from 'react-dom'
import { HostelCareLogo } from './Brand'

function formatReceiptTimestamp(value) {
  if (!value) return '—'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return String(value)
  }
  return parsed.toLocaleString('en-IN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

export function ReceiptModal({ receipt, loading = false, error = '', onDownloadPdf, onClose }) {
  const isOpen = Boolean(receipt || loading || error)
  const [isDownloading, setIsDownloading] = useState(false)
  const [downloadError, setDownloadError] = useState('')

  if (!isOpen) return null

  const formattedDate = formatReceiptTimestamp(receipt?.paidAt)

  const handleDownloadPdf = async () => {
    if (!onDownloadPdf || isDownloading) return
    setIsDownloading(true)
    setDownloadError('')
    try {
      await onDownloadPdf()
    } catch (err) {
      setDownloadError(err?.message || 'Unable to download receipt PDF.')
    } finally {
      setIsDownloading(false)
    }
  }

  const modalContent = (
    <div
      className="fixed inset-0 z-50 bg-[#292039]/60 backdrop-blur-xs flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Official Payment Receipt"
    >
      <div className="bg-[#FFFCF7] rounded-3xl border border-[#E8DCCF] max-w-lg w-full p-6 sm:p-8 shadow-xl space-y-5">
        <div className="flex items-start justify-between border-b border-[#E8DCCF] pb-4">
          <div className="space-y-1">
            <HostelCareLogo compact />
            <p className="text-[11px] font-semibold text-[#368F83] uppercase tracking-wider">
              {receipt?.institution || 'HostelCare'} — Official Payment Receipt
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close receipt"
            className="text-xs font-bold text-[#292039]/60 hover:text-[#292039] px-2 py-1 rounded-lg"
          >
            ✕
          </button>
        </div>

        {loading && (
          <div className="py-10 text-center text-xs text-[#292039]/70">
            Loading official payment receipt...
          </div>
        )}

        {!loading && error && (
          <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 text-xs">
            {error}
          </div>
        )}

        {!loading && !error && receipt && (
          <>
            <div className="p-4 rounded-2xl bg-[#F7EFE6]/60 border border-[#E8DCCF] flex items-center justify-between">
              <div>
                <span className="text-[10px] uppercase tracking-wider text-[#292039]/60 block">
                  Receipt Number
                </span>
                <span className="font-mono text-sm font-bold text-[#292039] whitespace-nowrap">
                  {receipt.receiptNumber}
                </span>
              </div>
              <span className="px-2.5 py-1 rounded-full bg-emerald-100 text-emerald-800 text-[11px] font-bold uppercase">
                {receipt.paymentStatus || 'paid'}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs">
              <div>
                <span className="text-[10px] uppercase tracking-wider text-[#292039]/60 block">
                  Fine Reference
                </span>
                <span className="font-mono font-semibold text-[#292039] whitespace-nowrap">
                  {receipt.fineReference}
                </span>
              </div>
              <div>
                <span className="text-[10px] uppercase tracking-wider text-[#292039]/60 block">
                  Payment Date
                </span>
                <span className="font-medium text-[#292039] whitespace-nowrap">
                  {formattedDate}
                </span>
              </div>
              <div>
                <span className="text-[10px] uppercase tracking-wider text-[#292039]/60 block">
                  Student Name
                </span>
                <span className="font-semibold text-[#292039]">{receipt.studentName || '—'}</span>
              </div>
              <div>
                <span className="text-[10px] uppercase tracking-wider text-[#292039]/60 block">
                  Roll Number
                </span>
                <span className="font-mono font-medium text-[#292039]">
                  {receipt.studentRoll || '—'}
                </span>
              </div>
              <div>
                <span className="text-[10px] uppercase tracking-wider text-[#292039]/60 block">
                  Payment Method
                </span>
                <span className="font-medium text-[#292039] uppercase">
                  {receipt.paymentMethod || '—'}
                </span>
              </div>
              <div>
                <span className="text-[10px] uppercase tracking-wider text-[#292039]/60 block">
                  Transaction Reference
                </span>
                <span className="font-mono font-medium text-[#292039] whitespace-nowrap">
                  {receipt.transactionReference || '—'}
                </span>
              </div>
            </div>

            <div className="p-3.5 rounded-2xl bg-[#FFFDF9] border border-[#E8DCCF] space-y-1 text-xs">
              <span className="text-[10px] uppercase tracking-wider text-[#292039]/60 block">
                {receipt.fineCategory || 'Disciplinary Fine'}
              </span>
              <p className="text-[#292039]/85 leading-relaxed">{receipt.fineDescription}</p>
            </div>

            <div className="flex items-center justify-between pt-3 border-t border-[#E8DCCF]">
              <span className="text-xs font-semibold text-[#292039]/70">Total Amount Paid</span>
              <span className="font-serif text-2xl font-bold text-[#368F83]">
                ₹{receipt.amountInr}
              </span>
            </div>

            {downloadError && (
              <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs">
                {downloadError}
              </div>
            )}

            <div className="flex flex-wrap items-center justify-end gap-2.5 pt-2">
              {onDownloadPdf && (
                <button
                  type="button"
                  disabled={isDownloading}
                  onClick={handleDownloadPdf}
                  className="px-4 py-2 rounded-xl bg-[#368F83] text-white text-xs font-semibold hover:bg-[#2B7369] cursor-pointer disabled:opacity-50"
                >
                  {isDownloading ? 'Downloading PDF...' : 'Download PDF'}
                </button>
              )}
              <button
                type="button"
                onClick={() => {
                  setDownloadError('')
                  onClose()
                }}
                className="px-4 py-2 rounded-xl bg-[#292039] text-white text-xs font-semibold hover:bg-[#3A2F50] cursor-pointer"
              >
                Close
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )

  return createPortal(modalContent, document.body)
}
