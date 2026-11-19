import { useCallback, useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useApp } from '../../../context/AppContext'
import { StatusBadge } from '../../../components/Brand'
import { ReceiptModal } from '../../../components/ReceiptModal'
import { useRazorpayFinePayment } from '../../../lib/useRazorpayFinePayment'

export function StudentFineDetailPage() {
  const { id } = useParams()
  const {
    user,
    fines,
    fetchFineDetail,
    fetchFinePayments,
    fetchReceipt,
    downloadReceiptPdf,
    createRazorpayOrder,
    verifyRazorpayPayment,
    recordRazorpayAttemptFailure,
  } = useApp()

  const cachedFine = fines.find(
    (f) => String(f.id) === String(id) || (f.referenceNo && f.referenceNo === id),
  )
  const [fineDetail, setFineDetail] = useState(cachedFine || null)
  const [paymentsData, setPaymentsData] = useState(null)
  const [loading, setLoading] = useState(!cachedFine)
  const [errorState, setErrorState] = useState({ status: null, message: '' })
  const [receiptError, setReceiptError] = useState('')
  const [activeReceipt, setActiveReceipt] = useState(null)

  const loadDetail = useCallback(async () => {
    setLoading(true)
    setErrorState({ status: null, message: '' })
    try {
      const [detail, paymentInfo] = await Promise.all([
        fetchFineDetail(id, 'student'),
        fetchFinePayments(id, 'student').catch(() => null),
      ])
      setFineDetail(detail)
      if (paymentInfo) {
        setPaymentsData(paymentInfo)
      }
    } catch (err) {
      setErrorState({
        status: err.status || null,
        message: err.message || 'Unable to load fine details.',
      })
    } finally {
      setLoading(false)
    }
  }, [fetchFineDetail, fetchFinePayments, id])

  const {
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
      await loadDetail()
      if (verified?.receipt) {
        setActiveReceipt(verified.receipt)
      }
    },
  })

  useEffect(() => {
    let active = true
    Promise.all([
      fetchFineDetail(id, 'student'),
      fetchFinePayments(id, 'student').catch(() => null),
    ])
      .then(([detail, paymentInfo]) => {
        if (!active) return
        setFineDetail(detail)
        if (paymentInfo) {
          setPaymentsData(paymentInfo)
        }
        setErrorState({ status: null, message: '' })
      })
      .catch((err) => {
        if (!active) return
        setErrorState({
          status: err.status || null,
          message: err.message || 'Unable to load fine details.',
        })
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [id, fetchFineDetail, fetchFinePayments])

  const fine = fineDetail || cachedFine

  if (loading && !fine) {
    return (
      <div className="py-16 text-center space-y-2">
        <h2 className="font-serif text-xl font-bold text-[#292039]">Loading Fine Details...</h2>
        <p className="text-xs text-[#292039]/65">Fetching your disciplinary record.</p>
      </div>
    )
  }

  if (errorState.status === 403) {
    return (
      <div className="py-16 text-center space-y-4">
        <div className="w-12 h-12 rounded-full bg-rose-100 text-rose-600 mx-auto flex items-center justify-center font-bold">
          !
        </div>
        <h2 className="font-serif text-2xl font-bold text-[#292039]">Access Restricted</h2>
        <p className="text-xs text-[#292039]/70">
          {errorState.message ||
            'Disciplinary notices are confidential to the assigned resident and warden administration.'}
        </p>
        <Link
          to="/student/fines"
          className="inline-block px-4 py-2 rounded-xl bg-[#D94378] text-white text-xs font-semibold"
        >
          &larr; Return to My Fines
        </Link>
      </div>
    )
  }

  if (errorState.message && !fine) {
    return (
      <div className="py-16 text-center space-y-4">
        <h2 className="font-serif text-2xl font-bold text-[#292039]">
          {errorState.status === 404 ? 'Fine Notice Not Found' : 'Unable to Load Fine Notice'}
        </h2>
        <p className="text-xs text-[#292039]/70">{errorState.message}</p>
        <div className="flex justify-center gap-3">
          {errorState.status !== 404 && (
            <button
              type="button"
              onClick={loadDetail}
              className="px-4 py-2 rounded-xl bg-[#D94378] text-white text-xs font-semibold"
            >
              Retry
            </button>
          )}
          <Link
            to="/student/fines"
            className="inline-block px-4 py-2 rounded-xl border border-[#D8CEBE] text-[#292039] text-xs font-semibold"
          >
            &larr; Back to Fines
          </Link>
        </div>
      </div>
    )
  }

  if (!fine) {
    return (
      <div className="py-16 text-center space-y-4">
        <h2 className="font-serif text-2xl font-bold text-[#292039]">Fine Notice Not Found</h2>
        <p className="text-xs text-[#292039]/70">
          The requested penalty record {id} could not be located.
        </p>
        <Link
          to="/student/fines"
          className="inline-block px-4 py-2 rounded-xl bg-[#D94378] text-white text-xs font-semibold"
        >
          &larr; Back to Fines
        </Link>
      </div>
    )
  }

  // Secondary ownership check when loaded from client cache
  const isOwner =
    !fine.studentId ||
    fine.studentRoll === user?.rollNumber ||
    String(fine.studentId) === String(user?.id)
  if (!isOwner) {
    return (
      <div className="py-16 text-center space-y-4">
        <div className="w-12 h-12 rounded-full bg-rose-100 text-rose-600 mx-auto flex items-center justify-center font-bold">
          !
        </div>
        <h2 className="font-serif text-2xl font-bold text-[#292039]">Access Restricted</h2>
        <p className="text-xs text-[#292039]/70">
          Disciplinary notices are confidential to the assigned resident and warden administration.
        </p>
        <Link
          to="/student/fines"
          className="inline-block px-4 py-2 rounded-xl bg-[#D94378] text-white text-xs font-semibold"
        >
          &larr; Return to My Fines
        </Link>
      </div>
    )
  }

  const handleOpenReceipt = async (receiptNumber) => {
    if (!receiptNumber) return
    setReceiptError('')
    try {
      const receipt = await fetchReceipt(receiptNumber, 'student')
      setActiveReceipt(receipt)
    } catch (err) {
      setReceiptError(err.message || 'Unable to load receipt.')
    }
  }

  const latestCompletedPayment =
    paymentsData?.payments?.find(
      (p) => p?.receiptNumber && (!p.status || p.status === 'paid' || p.status === 'completed'),
    ) ||
    fine.payment ||
    null

  const rawDbStatus = fine.dbStatus || String(fine.status || '').toLowerCase()
  const isPayable = rawDbStatus === 'pending' && !latestCompletedPayment
  const onlineGatewayDisabled = paymentsData?.onlinePaymentEnabled === false
  const payButtonLabel =
    paymentPhase === 'creating_order'
      ? 'Starting Checkout...'
      : paymentPhase === 'verifying'
        ? 'Verifying Payment...'
        : paymentPhase === 'checkout_open'
          ? 'Checkout Open...'
          : 'Pay Now'

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Header breadcrumb & actions */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="space-y-1">
          <Link
            to="/student/fines"
            className="text-xs text-[#D94378] font-semibold hover:underline inline-flex items-center gap-1"
          >
            &larr; Back to My Fines
          </Link>
          <div className="flex items-center gap-3">
            <h1 className="font-serif text-2xl sm:text-3xl font-bold text-[#292039]">
              Fine Notice: {fine.referenceNo || fine.id}
            </h1>
            <StatusBadge status={fine.status} />
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {isPayable && !onlineGatewayDisabled && (
            <button
              type="button"
              disabled={isProcessingPayment}
              onClick={() => startOnlinePayment(fine)}
              className="px-4 py-2 rounded-xl bg-[#368F83] text-white text-xs font-semibold hover:bg-[#2B7369] shadow-xs cursor-pointer disabled:opacity-50"
            >
              {payButtonLabel}
            </button>
          )}
          {fine.status !== 'Paid' &&
            fine.status !== 'Waived' &&
            fine.status !== 'Cancelled' &&
            fine.status !== 'Disputed' &&
            !fine.dispute && (
              <Link
                to={`/student/fines/${fine.id}/dispute`}
                className="px-4 py-2 rounded-xl bg-[#D94378] text-white text-xs font-semibold hover:bg-[#C23365] shadow-xs"
              >
                Submit Dispute
              </Link>
            )}
          {latestCompletedPayment?.receiptNumber && (
            <button
              type="button"
              onClick={() => handleOpenReceipt(latestCompletedPayment.receiptNumber)}
              className="px-4 py-2 rounded-xl bg-[#368F83] text-white text-xs font-semibold hover:bg-[#2B7369] shadow-xs cursor-pointer"
            >
              View Official Receipt
            </button>
          )}
        </div>
      </div>

      {isPayable && onlineGatewayDisabled && (
        <div className="p-4 rounded-2xl bg-amber-50 border border-amber-200 text-amber-900 text-xs">
          Online Razorpay checkout is currently not configured on this server. Please settle this
          fine at the Warden office.
        </div>
      )}

      {paymentNotice && (
        <div className="p-4 rounded-2xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs flex items-center justify-between gap-3">
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
        <div className="p-4 rounded-2xl bg-red-50 border border-red-200 text-red-800 text-xs flex items-center justify-between gap-3">
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

      {receiptError && (
        <div className="p-4 rounded-2xl bg-red-50 border border-red-200 text-red-800 text-xs">
          {receiptError}
        </div>
      )}

      {/* Main Details Card */}
      <div className="bg-[#FFFCF7] rounded-3xl border border-[#E8DCCF] p-6 shadow-xs space-y-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 pb-6 border-b border-[#E8DCCF]">
          <div>
            <span className="text-[10px] text-[#292039]/60 uppercase tracking-wider block">
              Amount
            </span>
            <span className="font-serif text-2xl font-bold text-[#D94378]">₹{fine.amount}</span>
          </div>
          <div>
            <span className="text-[10px] text-[#292039]/60 uppercase tracking-wider block">
              Issue Date
            </span>
            <span className="text-xs font-semibold text-[#292039]">{fine.issueDate}</span>
          </div>
          <div>
            <span className="text-[10px] text-[#292039]/60 uppercase tracking-wider block">
              Payment Due Date
            </span>
            <span className="text-xs font-semibold text-rose-700">{fine.dueDate}</span>
          </div>
          <div>
            <span className="text-[10px] text-[#292039]/60 uppercase tracking-wider block">
              Issuing Authority
            </span>
            <span className="text-xs font-semibold text-[#292039]">{fine.issuedBy}</span>
          </div>
        </div>

        {/* Violation Description */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-[#292039]">
              Violation Description
            </h3>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-[#F7EFE6] text-[#292039]/80 font-medium">
              Category: {fine.category}
            </span>
          </div>
          <div className="p-4 rounded-2xl bg-[#FFFDF9] border border-[#E8DCCF] text-xs text-[#292039] leading-relaxed whitespace-pre-wrap font-sans">
            {fine.description}
          </div>
        </div>

        {/* Dispute Details Section (if any) */}
        {fine.dispute && (
          <div className="space-y-3 p-5 rounded-2xl bg-purple-50/50 border border-purple-200">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-bold text-purple-900 uppercase tracking-wider">
                Student Dispute Record
              </h4>
              <span className="text-[11px] font-semibold text-purple-700 bg-purple-100 px-2.5 py-0.5 rounded-full">
                Status: {fine.dispute.status}
              </span>
            </div>
            <div className="text-xs text-purple-950 space-y-1">
              <span className="text-[10px] text-purple-700 block">
                Submitted on: {fine.dispute.submittedAt}
              </span>
              <p className="bg-white/80 p-3 rounded-xl border border-purple-100 leading-relaxed">
                &ldquo;{fine.dispute.explanation}&rdquo;
              </p>
            </div>
            {fine.dispute.reviewNote && (
              <div className="pt-2 border-t border-purple-200 text-xs text-purple-900">
                <span className="font-semibold">Warden Review Remarks:</span>
                <p className="mt-1 text-purple-800">{fine.dispute.reviewNote}</p>
                <span className="text-[10px] text-purple-600 block mt-1">
                  Reviewed by {fine.dispute.reviewedBy} on {fine.dispute.reviewedAt}
                </span>
              </div>
            )}
          </div>
        )}

        {/* Payment Receipt Section (if paid) */}
        {latestCompletedPayment && (
          <div className="p-5 rounded-2xl bg-emerald-50/60 border border-emerald-200 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h4 className="text-xs font-bold text-emerald-900 uppercase tracking-wider">
                Official Settlement Receipt
              </h4>
              <div className="flex items-center gap-3">
                <span className="text-[11px] font-mono font-bold text-emerald-800">
                  {latestCompletedPayment.receiptNumber}
                </span>
                {latestCompletedPayment.receiptNumber && (
                  <button
                    type="button"
                    onClick={() => handleOpenReceipt(latestCompletedPayment.receiptNumber)}
                    className="px-3 py-1 rounded-lg bg-emerald-700 text-white text-[11px] font-semibold hover:bg-emerald-800 cursor-pointer"
                  >
                    View Receipt
                  </button>
                )}
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs text-emerald-950 pt-1 font-mono">
              <div>
                <span className="text-[10px] text-emerald-700 block">Transaction ID:</span>
                <span className="font-semibold">
                  {latestCompletedPayment.transactionReference ||
                    latestCompletedPayment.gatewayPaymentId ||
                    latestCompletedPayment.manualReference ||
                    latestCompletedPayment.reference ||
                    latestCompletedPayment.transactionId ||
                    'N/A'}
                </span>
              </div>
              <div>
                <span className="text-[10px] text-emerald-700 block">Settled At:</span>
                <span className="font-semibold">{latestCompletedPayment.paidAt}</span>
              </div>
              <div>
                <span className="text-[10px] text-emerald-700 block">Payment Mode:</span>
                <span className="font-semibold uppercase">
                  {latestCompletedPayment.paymentMethod}
                  {latestCompletedPayment.channel === 'razorpay' ? ' (Online)' : ''}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Audit History Timeline */}
        <div className="space-y-3 pt-4 border-t border-[#E8DCCF]">
          <h3 className="text-xs font-bold uppercase tracking-wider text-[#292039]">
            Official Timeline &amp; Audit Trail
          </h3>
          <div className="space-y-2">
            {fine.history?.map((step, idx) => (
              <div
                key={idx}
                className="p-3 rounded-xl bg-[#F7EFE6] text-xs flex items-start gap-3 text-[#292039]"
              >
                <div className="w-2 h-2 rounded-full bg-[#D94378] mt-1.5 shrink-0" />
                <div className="flex-1 space-y-0.5">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-xs">{step.action.replace(/_/g, ' ')}</span>
                    <span className="text-[10px] text-[#292039]/60">{step.timestamp}</span>
                  </div>
                  <p className="text-[11px] text-[#292039]/80">{step.note}</p>
                  <span className="text-[10px] text-[#292039]/60 block">By: {step.actor}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
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
