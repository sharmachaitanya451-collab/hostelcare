import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useApp } from '../../../context/AppContext'
import { StatusBadge } from '../../../components/Brand'
import { ReceiptModal } from '../../../components/ReceiptModal'
import { useRazorpayFinePayment } from '../../../lib/useRazorpayFinePayment'

export function StudentFinesPage() {
  const {
    user,
    fines,
    finesLoading,
    finesError,
    fetchStudentFines,
    createRazorpayOrder,
    verifyRazorpayPayment,
    recordRazorpayAttemptFailure,
    downloadReceiptPdf,
  } = useApp()
  const [activeReceipt, setActiveReceipt] = useState(null)

  useEffect(() => {
    fetchStudentFines().catch(() => {})
  }, [fetchStudentFines])

  const {
    payingFineId,
    paymentPhase,
    paymentError,
    paymentNotice,
    isProcessingPayment,
    clearPaymentFeedback,
    startOnlinePayment,
  } = useRazorpayFinePayment({
    createRazorpayOrder,
    verifyRazorpayPayment,
    recordRazorpayAttemptFailure,
    onSuccess: async (verified) => {
      await fetchStudentFines().catch(() => {})
      if (verified?.receipt) {
        setActiveReceipt(verified.receipt)
      }
    },
  })

  const pendingFines = fines.filter(
    (f) => f.status === 'Pending' || f.status === 'Overdue' || f.status === 'Disputed',
  )
  const settledFines = fines.filter(
    (f) => f.status === 'Paid' || f.status === 'Waived' || f.status === 'Cancelled',
  )

  const totalOutstanding = pendingFines
    .filter((f) => f.status !== 'Waived' && f.status !== 'Cancelled')
    .reduce((sum, f) => sum + (f.status === 'Paid' ? 0 : f.amount), 0)

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <span className="text-[11px] font-bold text-[#D94378] uppercase tracking-wider">
            Hostel Discipline &amp; Dues
          </span>
          <h1 className="font-serif text-2xl sm:text-3xl font-bold text-[#292039]">
            My Fines &amp; Penalties
          </h1>
          <p className="text-xs text-[#292039]/70 mt-1">
            Official record of disciplinary notices, fine amounts, and payment clearing for{' '}
            {user?.fullName}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            to="/student/fines/history"
            className="px-4 py-2.5 rounded-xl border border-[#D8CEBE] bg-[#FFFCF7] text-xs font-semibold text-[#292039] hover:bg-[#F7EFE6] transition-colors"
          >
            Payment History &amp; Receipts ({settledFines.length})
          </Link>
        </div>
      </div>

      {paymentNotice && (
        <div className="p-4 rounded-2xl bg-emerald-50 border border-emerald-200 flex items-center justify-between gap-4 text-xs text-emerald-900">
          <span>{paymentNotice}</span>
          <button
            type="button"
            onClick={clearPaymentFeedback}
            className="font-bold text-emerald-800 cursor-pointer"
          >
            ✕
          </button>
        </div>
      )}

      {paymentError && (
        <div className="p-4 rounded-2xl bg-red-50 border border-red-200 flex items-center justify-between gap-4 text-xs text-red-800">
          <span>{paymentError}</span>
          <button
            type="button"
            onClick={clearPaymentFeedback}
            className="font-bold text-red-700 cursor-pointer"
          >
            ✕
          </button>
        </div>
      )}

      {finesError && (
        <div className="p-4 rounded-2xl bg-red-50 border border-red-200 flex items-center justify-between gap-4">
          <p className="text-xs text-red-700 font-medium">{finesError}</p>
          <button
            type="button"
            onClick={() => fetchStudentFines().catch(() => {})}
            className="px-3 py-1.5 rounded-lg bg-red-600 text-white text-xs font-semibold hover:bg-red-700 shrink-0"
          >
            Retry
          </button>
        </div>
      )}

      {/* Overview Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="p-5 rounded-2xl bg-[#FFFCF7] border border-[#E8DCCF] shadow-xs">
          <span className="text-xs text-[#292039]/70 font-medium">Total Outstanding Dues</span>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="font-serif text-2xl font-bold text-[#D94378]">
              ₹{totalOutstanding}
            </span>
            <span className="text-[11px] text-[#292039]/60">across pending fines</span>
          </div>
        </div>

        <div className="p-5 rounded-2xl bg-[#FFFCF7] border border-[#E8DCCF] shadow-xs">
          <span className="text-xs text-[#292039]/70 font-medium">Active Notices</span>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="font-serif text-2xl font-bold text-[#292039]">
              {pendingFines.length}
            </span>
            <span className="text-[11px] text-[#292039]/60">requiring action or review</span>
          </div>
        </div>

        <div className="p-5 rounded-2xl bg-[#FFFCF7] border border-[#E8DCCF] shadow-xs">
          <span className="text-xs text-[#292039]/70 font-medium">Resolved / Waived</span>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="font-serif text-2xl font-bold text-[#368F83]">
              {settledFines.length}
            </span>
            <span className="text-[11px] text-[#292039]/60">past settled infractions</span>
          </div>
        </div>
      </div>

      {/* Active Fines Section */}
      <div className="bg-[#FFFCF7] rounded-3xl border border-[#E8DCCF] p-6 shadow-xs space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-serif text-lg font-bold text-[#292039]">
            Active &amp; Pending Penalties
          </h2>
          <span className="text-xs text-[#292039]/60 font-medium">
            Due dates must be respected to avoid hostel clearance holds
          </span>
        </div>

        {finesLoading && fines.length === 0 ? (
          <div className="py-12 text-center space-y-2">
            <p className="font-serif text-base font-bold text-[#292039]">Loading fines...</p>
            <p className="text-xs text-[#292039]/60">Checking your hostel disciplinary ledger.</p>
          </div>
        ) : pendingFines.length === 0 ? (
          <div className="py-12 text-center space-y-3">
            <div className="w-12 h-12 rounded-full bg-emerald-100 text-emerald-600 mx-auto flex items-center justify-center text-xl">
              ✓
            </div>
            <h3 className="font-serif text-base font-bold text-[#292039]">No Outstanding Fines</h3>
            <p className="text-xs text-[#292039]/70 max-w-sm mx-auto">
              Your hostel disciplinary and dues account is clean. All previous obligations are
              settled.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {pendingFines.map((fine) => (
              <div
                key={fine.id}
                className="p-5 rounded-2xl bg-[#FFFDF9] border border-[#E8DCCF] hover:border-[#D94378]/40 transition-all flex flex-col md:flex-row md:items-center justify-between gap-4"
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
                    <span>
                      Due Date: <strong className="text-rose-700">{fine.dueDate}</strong>
                    </span>
                    <span>By: {fine.issuedBy}</span>
                  </div>
                </div>

                <div className="flex sm:flex-col items-center sm:items-end justify-between gap-3 shrink-0 pt-2 sm:pt-0 border-t sm:border-t-0 border-[#E8DCCF]">
                  <div className="text-left sm:text-right">
                    <span className="text-[10px] text-[#292039]/60 uppercase tracking-wider block">
                      Amount Payable
                    </span>
                    <span className="font-serif text-2xl font-bold text-[#D94378]">
                      ₹{fine.amount}
                    </span>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <Link
                      to={`/student/fines/${fine.id}`}
                      className="px-3 py-1.5 rounded-lg border border-[#D8CEBE] text-xs font-semibold text-[#292039] hover:bg-[#F7EFE6]"
                    >
                      View Details
                    </Link>

                    {(fine.dbStatus || String(fine.status || '').toLowerCase()) === 'pending' && (
                      <button
                        type="button"
                        disabled={isProcessingPayment}
                        onClick={() => startOnlinePayment(fine)}
                        className="px-3 py-1.5 rounded-lg bg-[#368F83] text-white text-xs font-semibold hover:bg-[#2B7369] cursor-pointer disabled:opacity-50"
                      >
                        {payingFineId === (fine.referenceNo || fine.id) && paymentPhase !== 'idle'
                          ? paymentPhase === 'verifying'
                            ? 'Verifying...'
                            : 'Processing...'
                          : 'Pay Now'}
                      </button>
                    )}

                    {fine.status !== 'Disputed' && !fine.dispute && (
                      <Link
                        to={`/student/fines/${fine.id}/dispute`}
                        className="px-3 py-1.5 rounded-lg bg-[#D94378] text-white text-xs font-semibold hover:bg-[#C23365]"
                      >
                        Dispute
                      </Link>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Disciplinary Policy Notice */}
      <div className="p-4 rounded-2xl bg-[#F7EFE6] border border-[#E8DCCF] text-xs text-[#292039]/80 space-y-1">
        <p className="font-semibold text-[#292039]">Hostel Rules &amp; Due Clearing Information:</p>
        <p>
          Disciplinary fines are levied as per College Hostel Council bylaws. Pending fines may be
          paid online via Razorpay or settled directly at the Warden office, and official PDF
          receipts are available under Payment History &amp; Receipts. If you believe a fine was
          issued mistakenly, submit a formal dispute before the specified due date.
        </p>
      </div>

      <ReceiptModal
        receipt={activeReceipt}
        onDownloadPdf={
          activeReceipt?.receiptNumber
            ? () => downloadReceiptPdf(activeReceipt.receiptNumber, 'student')
            : undefined
        }
        onClose={() => setActiveReceipt(null)}
      />
    </div>
  )
}
