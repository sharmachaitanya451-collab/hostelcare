import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useApp } from '../../../context/AppContext'
import { StatusBadge } from '../../../components/Brand'
import { ReceiptModal } from '../../../components/ReceiptModal'

export function StudentFineHistoryPage() {
  const {
    fines,
    finesLoading,
    finesError,
    fetchStudentFines,
    fetchFinePayments,
    fetchReceipt,
    downloadReceiptPdf,
  } = useApp()
  const [selectedReceipt, setSelectedReceipt] = useState(null)
  const [receiptLoadingId, setReceiptLoadingId] = useState(null)
  const [receiptError, setReceiptError] = useState('')

  useEffect(() => {
    fetchStudentFines().catch(() => {})
  }, [fetchStudentFines])

  const settledFines = fines.filter(
    (f) => f.status === 'Paid' || f.status === 'Waived' || f.status === 'Cancelled',
  )

  const handleViewReceipt = async (fine) => {
    setReceiptError('')
    setReceiptLoadingId(fine.id)
    try {
      let receiptNumber = fine.payment?.receiptNumber
      if (!receiptNumber) {
        const paymentInfo = await fetchFinePayments(fine.id, 'student')
        const verified = paymentInfo?.payments?.find(
          (p) => p?.receiptNumber && (!p.status || p.status === 'paid' || p.status === 'completed'),
        )
        receiptNumber = verified?.receiptNumber
      }
      if (!receiptNumber) {
        throw new Error('No receipt number found for this payment.')
      }
      const receipt = await fetchReceipt(receiptNumber, 'student')
      setSelectedReceipt(receipt)
    } catch (err) {
      setReceiptError(err.message || 'Unable to load payment receipt.')
    } finally {
      setReceiptLoadingId(null)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="space-y-1">
          <Link
            to="/student/fines"
            className="text-xs text-[#D94378] font-semibold hover:underline inline-flex items-center gap-1"
          >
            &larr; Back to Active Fines
          </Link>
          <h1 className="font-serif text-2xl sm:text-3xl font-bold text-[#292039]">
            Disciplinary &amp; Payment History
          </h1>
          <p className="text-xs text-[#292039]/70">
            Archived record of all paid fines, waived penalties, and issued clearance receipts
          </p>
        </div>
      </div>

      {finesError && (
        <div className="p-4 rounded-2xl bg-red-50 border border-red-200 flex items-center justify-between gap-4">
          <p className="text-xs text-red-700 font-medium">{finesError}</p>
          <button
            type="button"
            onClick={() => fetchStudentFines().catch(() => {})}
            className="px-3 py-1.5 rounded-lg bg-red-600 text-white text-xs font-semibold hover:bg-red-700"
          >
            Retry
          </button>
        </div>
      )}

      {receiptError && (
        <div className="p-4 rounded-2xl bg-red-50 border border-red-200 text-red-800 text-xs">
          {receiptError}
        </div>
      )}

      {finesLoading && fines.length === 0 ? (
        <div className="bg-[#FFFCF7] rounded-3xl border border-[#E8DCCF] p-12 text-center space-y-2">
          <p className="font-serif text-base font-bold text-[#292039]">Loading history...</p>
          <p className="text-xs text-[#292039]/60">Fetching settled fines and receipts.</p>
        </div>
      ) : settledFines.length === 0 ? (
        <div className="bg-[#FFFCF7] rounded-3xl border border-[#E8DCCF] p-12 text-center space-y-3">
          <div className="w-12 h-12 rounded-full bg-slate-100 text-slate-400 mx-auto flex items-center justify-center text-xl">
            📋
          </div>
          <h3 className="font-serif text-base font-bold text-[#292039]">No Settled History Yet</h3>
          <p className="text-xs text-[#292039]/70 max-w-sm mx-auto">
            You do not have any past cleared or waived fines on record.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {settledFines.map((fine) => (
            <div
              key={fine.id}
              className="p-5 rounded-2xl bg-[#FFFCF7] border border-[#E8DCCF] shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4"
            >
              <div className="space-y-1.5 flex-1">
                <div className="flex flex-wrap items-center gap-2.5">
                  <span className="font-mono text-xs font-bold text-[#292039]">
                    {fine.referenceNo || fine.id}
                  </span>
                  <span className="text-xs px-2 py-0.5 rounded-md bg-[#F7EFE6] text-[#292039]/80 font-medium">
                    {fine.category}
                  </span>
                  <StatusBadge status={fine.status} />
                </div>

                <p className="text-xs text-[#292039] font-medium leading-relaxed">
                  {fine.description}
                </p>

                <div className="flex flex-wrap items-center gap-4 text-[11px] text-[#292039]/70 pt-1">
                  <span>Issued: {fine.issueDate}</span>
                  {fine.payment && (
                    <span>
                      Paid on: <strong>{fine.payment.paidAt}</strong>
                    </span>
                  )}
                  {fine.status === 'Waived' && (
                    <span className="text-teal-700 font-semibold">
                      Waived by Warden Administration
                    </span>
                  )}
                </div>
              </div>

              <div className="flex sm:flex-col items-center sm:items-end justify-between gap-3 shrink-0 pt-2 sm:pt-0 border-t sm:border-t-0 border-[#E8DCCF]">
                <div className="text-left sm:text-right">
                  <span className="text-[10px] text-[#292039]/60 uppercase tracking-wider block">
                    Settled Amount
                  </span>
                  <span className="font-serif text-xl font-bold text-[#292039]">
                    ₹{fine.amount}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <Link
                    to={`/student/fines/${fine.id}`}
                    className="px-3 py-1.5 rounded-lg border border-[#D8CEBE] text-xs font-semibold text-[#292039] hover:bg-[#F7EFE6]"
                  >
                    Details
                  </Link>
                  {fine.status === 'Paid' && (
                    <button
                      type="button"
                      disabled={receiptLoadingId === fine.id}
                      onClick={() => handleViewReceipt(fine)}
                      className="px-3 py-1.5 rounded-lg bg-[#368F83] text-white text-xs font-semibold hover:bg-[#2B7369] transition-colors cursor-pointer disabled:opacity-50"
                    >
                      {receiptLoadingId === fine.id ? 'Loading...' : 'View Receipt'}
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <ReceiptModal
        receipt={selectedReceipt}
        onDownloadPdf={
          selectedReceipt?.receiptNumber
            ? () => downloadReceiptPdf(selectedReceipt.receiptNumber, 'student')
            : undefined
        }
        onClose={() => setSelectedReceipt(null)}
      />
    </div>
  )
}
