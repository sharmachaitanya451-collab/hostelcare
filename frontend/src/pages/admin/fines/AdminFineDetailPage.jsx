import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useApp } from '../../../context/AppContext'
import { StatusBadge } from '../../../components/Brand'
import { ReceiptModal } from '../../../components/ReceiptModal'

export function AdminFineDetailPage() {
  const { id } = useParams()
  const {
    fines,
    fetchFineDetail,
    waiveFine,
    cancelFine,
    reviewDispute,
    recordFinePayment,
    fetchFinePayments,
    fetchReceipt,
    downloadReceiptPdf,
  } = useApp()

  const cachedFine = fines.find(
    (f) => String(f.id) === String(id) || (f.referenceNo && f.referenceNo === id),
  )
  const [fineDetail, setFineDetail] = useState(cachedFine || null)
  const [loading, setLoading] = useState(!cachedFine)
  const [loadError, setLoadError] = useState('')
  const [paymentsData, setPaymentsData] = useState(null)

  // Modal / Action states
  const [activeModal, setActiveModal] = useState(null) // null | 'waive' | 'cancel' | 'dispute' | 'manualPay'
  const [reasonInput, setReasonInput] = useState('')
  const [disputeDecision, setDisputeDecision] = useState('Approved') // 'Approved' | 'Rejected'
  const [paymentMethod, setPaymentMethod] = useState('cash')
  const [manualReference, setManualReference] = useState('')
  const [paymentConfirmed, setPaymentConfirmed] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [actionNotice, setActionNotice] = useState(null)
  const [actionError, setActionError] = useState('')
  const [activeReceipt, setActiveReceipt] = useState(null)

  const loadDetail = async () => {
    setLoading(true)
    setLoadError('')
    try {
      const [detail, paymentInfo] = await Promise.all([
        fetchFineDetail(id, 'admin'),
        fetchFinePayments(id, 'admin').catch(() => null),
      ])
      setFineDetail(detail)
      if (paymentInfo) {
        setPaymentsData(paymentInfo)
      }
    } catch (err) {
      setLoadError(err.message || 'Unable to load fine details.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    let active = true
    Promise.all([fetchFineDetail(id, 'admin'), fetchFinePayments(id, 'admin').catch(() => null)])
      .then(([detail, paymentInfo]) => {
        if (!active) return
        setFineDetail(detail)
        if (paymentInfo) {
          setPaymentsData(paymentInfo)
        }
        setLoadError('')
      })
      .catch((err) => {
        if (!active) return
        setLoadError(err.message || 'Unable to load fine details.')
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
        <p className="text-xs text-[#292039]/65">
          Fetching disciplinary record and payment ledger.
        </p>
      </div>
    )
  }

  if (loadError && !fine) {
    return (
      <div className="py-16 text-center space-y-4">
        <h2 className="font-serif text-2xl font-bold text-[#292039]">Unable to Load Fine Notice</h2>
        <p className="text-xs text-red-700">{loadError}</p>
        <div className="flex justify-center gap-3">
          <button
            type="button"
            onClick={loadDetail}
            className="px-4 py-2 rounded-xl bg-[#D94378] text-white text-xs font-semibold"
          >
            Retry
          </button>
          <Link
            to="/admin/fines"
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
        <p className="text-xs text-[#292039]/70">No fine record matches identifier {id}.</p>
        <Link
          to="/admin/fines"
          className="inline-block px-4 py-2 rounded-xl bg-[#D94378] text-white text-xs font-semibold"
        >
          &larr; Back to Fines
        </Link>
      </div>
    )
  }

  const handleWaiveSubmit = async (e) => {
    e.preventDefault()
    if (!reasonInput.trim() || isSubmitting) return
    setIsSubmitting(true)
    setActionError('')
    try {
      const updated = await waiveFine(fine.id, reasonInput.trim())
      setFineDetail(updated)
      setActiveModal(null)
      setReasonInput('')
      setActionNotice(`Fine ${updated.referenceNo || updated.id} has been waived.`)
    } catch (err) {
      setActionError(err.message || 'Failed to waive fine.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleCancelSubmit = async (e) => {
    e.preventDefault()
    if (!reasonInput.trim() || isSubmitting) return
    setIsSubmitting(true)
    setActionError('')
    try {
      const updated = await cancelFine(fine.id, reasonInput.trim())
      setFineDetail(updated)
      setActiveModal(null)
      setReasonInput('')
      setActionNotice(`Fine ${updated.referenceNo || updated.id} cancelled.`)
    } catch (err) {
      setActionError(err.message || 'Failed to cancel fine.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleDisputeSubmit = async (e) => {
    e.preventDefault()
    if (!reasonInput.trim() || isSubmitting) return
    setIsSubmitting(true)
    setActionError('')
    try {
      const decision = disputeDecision === 'Approved' ? 'approve' : 'reject'
      const updated = await reviewDispute(fine.id, {
        decision,
        reason: reasonInput.trim(),
      })
      setFineDetail(updated)
      setActiveModal(null)
      setReasonInput('')
      setActionNotice(
        `Dispute ${disputeDecision.toLowerCase()}. Fine status updated to ${updated.status}.`,
      )
    } catch (err) {
      setActionError(err.message || 'Failed to submit dispute decision.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleManualPaymentSubmit = async (e) => {
    e.preventDefault()
    if (!paymentConfirmed || isSubmitting) return
    setIsSubmitting(true)
    setActionError('')
    try {
      const amountInr = paymentsData?.outstandingInr || fine.amountInr || String(fine.amount)
      const result = await recordFinePayment(fine.id, {
        amountInr,
        paymentMethod,
        manualReference: manualReference.trim(),
      })
      setFineDetail(result.fine)
      const refreshedPayments = await fetchFinePayments(fine.id, 'admin').catch(() => null)
      if (refreshedPayments) {
        setPaymentsData(refreshedPayments)
      }
      setActiveModal(null)
      setManualReference('')
      setPaymentConfirmed(false)
      if (result.receipt) {
        setActiveReceipt(result.receipt)
      }
      setActionNotice(
        `Payment recorded for ${result.fine.referenceNo || result.fine.id}. Receipt: ${result.receipt?.receiptNumber || result.payment?.receiptNumber || 'Generated'}.`,
      )
    } catch (err) {
      setActionError(err.message || 'Failed to record payment.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleOpenReceipt = async (receiptNumber) => {
    if (!receiptNumber) return
    setActionError('')
    try {
      const receipt = await fetchReceipt(receiptNumber, 'admin')
      setActiveReceipt(receipt)
    } catch (err) {
      setActionError(err.message || 'Unable to load receipt.')
    }
  }

  const latestCompletedPayment =
    paymentsData?.payments?.find(
      (p) => p?.receiptNumber && (!p.status || p.status === 'paid' || p.status === 'completed'),
    ) ||
    fine.payment ||
    null

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Header breadcrumb & actions */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="space-y-1">
          <Link
            to="/admin/fines"
            className="text-xs text-[#D94378] font-semibold hover:underline inline-flex items-center gap-1"
          >
            &larr; Back to Fines Directory
          </Link>
          <div className="flex items-center gap-3">
            <h1 className="font-serif text-2xl sm:text-3xl font-bold text-[#292039]">
              Fine Notice: {fine.referenceNo || fine.id}
            </h1>
            <StatusBadge status={fine.status} />
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap items-center gap-2">
          {fine.status === 'Disputed' && (
            <button
              type="button"
              onClick={() => {
                setActionError('')
                setActiveModal('dispute')
                setReasonInput('')
              }}
              className="px-4 py-2 rounded-xl bg-purple-700 text-white text-xs font-semibold hover:bg-purple-800 shadow-xs cursor-pointer"
            >
              ⚖️ Adjudicate Dispute
            </button>
          )}

          {fine.status !== 'Paid' && fine.status !== 'Waived' && fine.status !== 'Cancelled' && (
            <>
              <button
                type="button"
                onClick={() => {
                  setActionError('')
                  setPaymentMethod('cash')
                  setManualReference('')
                  setPaymentConfirmed(false)
                  setActiveModal('manualPay')
                }}
                className="px-3.5 py-2 rounded-xl bg-[#368F83] text-white text-xs font-semibold hover:bg-[#2B7369] shadow-xs cursor-pointer"
              >
                💵 Record Payment
              </button>
              <button
                type="button"
                onClick={() => {
                  setActionError('')
                  setActiveModal('waive')
                  setReasonInput('')
                }}
                className="px-3.5 py-2 rounded-xl border border-teal-300 bg-teal-50 text-teal-800 text-xs font-semibold hover:bg-teal-100 cursor-pointer"
              >
                Waive Fine
              </button>
              <button
                type="button"
                onClick={() => {
                  setActionError('')
                  setActiveModal('cancel')
                  setReasonInput('')
                }}
                className="px-3.5 py-2 rounded-xl border border-rose-300 bg-rose-50 text-rose-800 text-xs font-semibold hover:bg-rose-100 cursor-pointer"
              >
                Void / Cancel
              </button>
            </>
          )}
        </div>
      </div>

      {actionNotice && (
        <div className="p-4 rounded-2xl bg-emerald-50 border border-emerald-300 text-emerald-900 text-xs flex items-center justify-between">
          <span>✓ {actionNotice}</span>
          <button type="button" onClick={() => setActionNotice(null)} className="font-bold">
            ✕
          </button>
        </div>
      )}

      {actionError && (
        <div className="p-4 rounded-2xl bg-red-50 border border-red-200 text-red-800 text-xs flex items-center justify-between">
          <span>{actionError}</span>
          <button type="button" onClick={() => setActionError('')} className="font-bold">
            ✕
          </button>
        </div>
      )}

      {/* Main Details Card */}
      <div className="bg-[#FFFCF7] rounded-3xl border border-[#E8DCCF] p-6 sm:p-8 shadow-xs space-y-6">
        {/* Student & Financial Info Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 pb-6 border-b border-[#E8DCCF]">
          <div>
            <span className="text-[10px] text-[#292039]/60 uppercase tracking-wider block">
              Resident Student
            </span>
            <span className="text-sm font-bold text-[#292039]">{fine.studentName}</span>
            <span className="text-xs text-[#292039]/70 block font-mono">
              {fine.studentRoll} • {fine.room} ({fine.block})
            </span>
          </div>

          <div>
            <span className="text-[10px] text-[#292039]/60 uppercase tracking-wider block">
              Levied Amount
            </span>
            <span className="font-serif text-2xl font-bold text-[#D94378]">₹{fine.amount}</span>
          </div>

          <div>
            <span className="text-[10px] text-[#292039]/60 uppercase tracking-wider block">
              Issue &amp; Due Dates
            </span>
            <span className="text-xs text-[#292039] font-medium block">
              Issued: {fine.issueDate}
            </span>
            <span className="text-xs text-rose-700 font-semibold block">Due: {fine.dueDate}</span>
          </div>

          <div>
            <span className="text-[10px] text-[#292039]/60 uppercase tracking-wider block">
              Issuing Administrator
            </span>
            <span className="text-xs font-semibold text-[#292039]">{fine.issuedBy}</span>
          </div>
        </div>

        {/* Free-Text Description */}
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

        {/* Dispute Section if exists */}
        {fine.dispute && (
          <div className="p-5 rounded-2xl bg-purple-50/60 border border-purple-200 space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-bold text-purple-900 uppercase tracking-wider">
                Student Dispute Hearing Record
              </h4>
              <span className="text-[11px] font-semibold text-purple-700 bg-purple-100 px-2.5 py-0.5 rounded-full">
                Status: {fine.dispute.status}
              </span>
            </div>

            <div className="text-xs text-purple-950 space-y-1">
              <span className="text-[10px] text-purple-700 block">
                Submitted at: {fine.dispute.submittedAt}
              </span>
              <p className="bg-white/90 p-3.5 rounded-xl border border-purple-200 leading-relaxed font-sans">
                &ldquo;{fine.dispute.explanation}&rdquo;
              </p>
            </div>

            {fine.dispute.reviewNote && (
              <div className="pt-2 border-t border-purple-200 text-xs text-purple-900 space-y-1">
                <span className="font-semibold">Warden Bench Decision:</span>
                <p className="text-purple-800">{fine.dispute.reviewNote}</p>
                <span className="text-[10px] text-purple-600 block">
                  Reviewed by {fine.dispute.reviewedBy} on {fine.dispute.reviewedAt}
                </span>
              </div>
            )}
          </div>
        )}

        {/* Payment Receipt Info if paid */}
        {latestCompletedPayment && (
          <div className="p-5 rounded-2xl bg-emerald-50/60 border border-emerald-200 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h4 className="text-xs font-bold text-emerald-900 uppercase tracking-wider">
                Official Payment Clearance
              </h4>
              <div className="flex items-center gap-3">
                <span className="text-xs font-mono font-bold text-emerald-800">
                  Receipt: {latestCompletedPayment.receiptNumber}
                </span>
                {latestCompletedPayment.receiptNumber && (
                  <button
                    type="button"
                    onClick={() => handleOpenReceipt(latestCompletedPayment.receiptNumber)}
                    className="px-3 py-1 rounded-lg bg-emerald-700 text-white text-[11px] font-semibold hover:bg-emerald-800 transition-colors cursor-pointer"
                  >
                    View Official Receipt
                  </button>
                )}
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs text-emerald-950 pt-1 font-mono">
              <div>
                <span className="text-[10px] text-emerald-700 block">Payment Channel:</span>
                <span className="font-semibold">
                  {latestCompletedPayment.channel === 'razorpay'
                    ? 'Online (Razorpay)'
                    : `Manual (${latestCompletedPayment.recordedBy || 'Warden Office'})`}
                </span>
              </div>
              <div>
                <span className="text-[10px] text-emerald-700 block">Txn Reference:</span>
                <span className="font-semibold break-all">
                  {latestCompletedPayment.transactionReference ||
                    latestCompletedPayment.gatewayPaymentId ||
                    latestCompletedPayment.manualReference ||
                    latestCompletedPayment.transactionId ||
                    'N/A'}
                </span>
                {latestCompletedPayment.gatewayOrderId && (
                  <span className="text-[10px] text-emerald-800/80 block mt-0.5 break-all">
                    Order: {latestCompletedPayment.gatewayOrderId}
                  </span>
                )}
              </div>
              <div>
                <span className="text-[10px] text-emerald-700 block">Clearance Date:</span>
                <span className="font-semibold">
                  {latestCompletedPayment.paidAt || latestCompletedPayment.verifiedAt || '—'}
                </span>
              </div>
              <div>
                <span className="text-[10px] text-emerald-700 block">
                  Method &amp; Verification:
                </span>
                <span className="font-semibold uppercase">
                  {latestCompletedPayment.paymentMethod || '—'}
                </span>
                {latestCompletedPayment.verificationMethod && (
                  <span className="text-[10px] text-emerald-800/80 block mt-0.5">
                    Verified via: {latestCompletedPayment.verificationMethod.replace(/_/g, ' ')}
                  </span>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Gateway / Payment Attempts Log (visible when attempts exist) */}
        {Array.isArray(paymentsData?.attempts) && paymentsData.attempts.length > 0 && (
          <div className="p-5 rounded-2xl bg-[#FFFDF9] border border-[#E8DCCF] space-y-3">
            <h4 className="text-xs font-bold text-[#292039] uppercase tracking-wider">
              Online &amp; Gateway Payment Attempts
            </h4>
            <div className="space-y-2">
              {paymentsData.attempts.map((attempt) => {
                const isReview = attempt.status === 'captured_unapplied'
                const isFailed = attempt.status === 'failed'
                return (
                  <div
                    key={attempt.id}
                    className={`p-3 rounded-xl border text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-2 ${
                      isReview
                        ? 'bg-amber-50 border-amber-300 text-amber-950'
                        : isFailed
                          ? 'bg-rose-50/60 border-rose-200 text-rose-950'
                          : 'bg-[#F7EFE6]/60 border-[#E8DCCF] text-[#292039]'
                    }`}
                  >
                    <div className="space-y-0.5">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono font-bold uppercase text-[11px]">
                          {attempt.status.replace(/_/g, ' ')}
                        </span>
                        {attempt.paymentMethod && (
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/80 border border-[#E8DCCF] uppercase font-medium">
                            {attempt.paymentMethod}
                          </span>
                        )}
                        <span className="font-mono text-[11px]">₹{attempt.amountInr}</span>
                      </div>
                      {(attempt.gatewayOrderId || attempt.gatewayPaymentId) && (
                        <div className="font-mono text-[10px] opacity-80">
                          {attempt.gatewayOrderId && <span>Order: {attempt.gatewayOrderId} </span>}
                          {attempt.gatewayPaymentId && (
                            <span>• Payment: {attempt.gatewayPaymentId}</span>
                          )}
                        </div>
                      )}
                      {attempt.failureReason && (
                        <p className="text-[11px] font-medium">{attempt.failureReason}</p>
                      )}
                    </div>
                    <span className="text-[10px] opacity-70 font-mono shrink-0">
                      {attempt.verifiedAt || attempt.createdAt || '—'}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Audit Timeline */}
        <div className="space-y-3 pt-4 border-t border-[#E8DCCF]">
          <h3 className="text-xs font-bold uppercase tracking-wider text-[#292039]">
            Audit Trail &amp; Action Log
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

      {/* Modal: Waive Fine */}
      {activeModal === 'waive' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#292039]/60 backdrop-blur-xs">
          <div className="bg-[#FFFCF7] w-full max-w-md rounded-3xl border border-[#E8DCCF] shadow-2xl p-6 space-y-4">
            <h3 className="font-serif text-lg font-bold text-[#292039]">Waive Disciplinary Fine</h3>
            <p className="text-xs text-[#292039]/70">
              Provide an official administrative justification for waiving fine {fine.id} of ₹
              {fine.amount}.
            </p>
            <form onSubmit={handleWaiveSubmit} className="space-y-4">
              <textarea
                required
                rows={3}
                value={reasonInput}
                onChange={(e) => setReasonInput(e.target.value)}
                placeholder="State the administrative justification (e.g. First-time infraction, medical concession verified, or Dean of Student Affairs directive)..."
                className="w-full px-3 py-2 rounded-xl border border-[#D8CEBE] text-xs focus:outline-none focus:border-[#D94378]"
              />
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setActiveModal(null)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-[#E8DCCF] text-[#292039]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-[#368F83] text-white hover:bg-[#2B7369] disabled:opacity-50"
                >
                  {isSubmitting ? 'Submitting...' : 'Confirm Fine Waiver'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Cancel Fine */}
      {activeModal === 'cancel' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#292039]/60 backdrop-blur-xs">
          <div className="bg-[#FFFCF7] w-full max-w-md rounded-3xl border border-[#E8DCCF] shadow-2xl p-6 space-y-4">
            <h3 className="font-serif text-lg font-bold text-[#292039]">Void / Cancel Notice</h3>
            <p className="text-xs text-[#292039]/70">
              Voiding cancels fine {fine.referenceNo || fine.id} due to clerical error or duplicate
              record. State reason:
            </p>
            <form onSubmit={handleCancelSubmit} className="space-y-4">
              <textarea
                required
                rows={3}
                value={reasonInput}
                onChange={(e) => setReasonInput(e.target.value)}
                placeholder="State reason for cancellation (e.g. Wrong room tagged during corridor inspection)..."
                className="w-full px-3 py-2 rounded-xl border border-[#D8CEBE] text-xs focus:outline-none focus:border-[#D94378]"
              />
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setActiveModal(null)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-[#E8DCCF] text-[#292039]"
                >
                  Back
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-rose-600 text-white hover:bg-rose-700 disabled:opacity-50"
                >
                  {isSubmitting ? 'Cancelling...' : 'Confirm Cancellation'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Dispute Review */}
      {activeModal === 'dispute' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#292039]/60 backdrop-blur-xs">
          <div className="bg-[#FFFCF7] w-full max-w-lg rounded-3xl border border-[#E8DCCF] shadow-2xl p-6 space-y-4">
            <h3 className="font-serif text-lg font-bold text-[#292039]">
              Adjudicate Student Dispute
            </h3>
            <div className="p-3.5 rounded-xl bg-purple-50 text-xs text-purple-900 border border-purple-200">
              <span className="font-bold">Student Statement:</span>
              <p className="mt-1 italic">&ldquo;{fine.dispute?.explanation}&rdquo;</p>
            </div>

            <form onSubmit={handleDisputeSubmit} className="space-y-4">
              <div className="space-y-2">
                <label className="block text-xs font-semibold text-[#292039]">Decision</label>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setDisputeDecision('Approved')}
                    className={`py-2 px-3 rounded-xl border text-xs font-bold transition-all ${
                      disputeDecision === 'Approved'
                        ? 'border-teal-500 bg-teal-50 text-teal-800'
                        : 'border-[#E8DCCF] text-[#292039]/70'
                    }`}
                  >
                    ✓ Accept (Waives Fine)
                  </button>
                  <button
                    type="button"
                    onClick={() => setDisputeDecision('Rejected')}
                    className={`py-2 px-3 rounded-xl border text-xs font-bold transition-all ${
                      disputeDecision === 'Rejected'
                        ? 'border-rose-500 bg-rose-50 text-rose-800'
                        : 'border-[#E8DCCF] text-[#292039]/70'
                    }`}
                  >
                    ✕ Reject (Uphold Fine)
                  </button>
                </div>
              </div>

              <div className="space-y-1">
                <label className="block text-xs font-semibold text-[#292039]">
                  Review Remarks / Findings *
                </label>
                <textarea
                  required
                  rows={3}
                  value={reasonInput}
                  onChange={(e) => setReasonInput(e.target.value)}
                  placeholder="State the findings of the warden inquiry..."
                  className="w-full px-3 py-2 rounded-xl border border-[#D8CEBE] text-xs focus:outline-none focus:border-[#D94378]"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setActiveModal(null)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-[#E8DCCF] text-[#292039]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-purple-700 text-white hover:bg-purple-800 disabled:opacity-50"
                >
                  {isSubmitting ? 'Recording...' : 'Record Official Decision'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Record Manual Payment (Full Settlement) */}
      {activeModal === 'manualPay' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#292039]/60 backdrop-blur-xs">
          <div className="bg-[#FFFCF7] w-full max-w-md rounded-3xl border border-[#E8DCCF] shadow-2xl p-6 space-y-4">
            <h3 className="font-serif text-lg font-bold text-[#292039]">
              Record Manual Fine Payment
            </h3>
            <p className="text-xs text-[#292039]/70">
              Full settlement for{' '}
              <span className="font-mono font-bold">{fine.referenceNo || fine.id}</span>. Partial
              payments are not permitted.
            </p>

            <form onSubmit={handleManualPaymentSubmit} className="space-y-4">
              <div className="p-3 rounded-xl bg-[#F7EFE6] border border-[#E8DCCF] flex items-center justify-between">
                <span className="text-xs font-semibold text-[#292039]">Full Settlement Amount</span>
                <span className="font-serif text-lg font-bold text-[#D94378]">
                  ₹{paymentsData?.outstandingInr || fine.amountInr || fine.amount}
                </span>
              </div>

              <div className="space-y-1">
                <label className="block text-xs font-semibold text-[#292039]">
                  Payment Method *
                </label>
                <select
                  value={paymentMethod}
                  onChange={(e) => setPaymentMethod(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-[#D8CEBE] text-xs bg-[#FFFDF9]"
                >
                  <option value="cash">Cash (Warden Office)</option>
                  <option value="bank_transfer">Bank Transfer / NEFT / IMPS</option>
                  <option value="upi">UPI Transfer</option>
                  <option value="card">Card / POS</option>
                  <option value="netbanking">NetBanking</option>
                  <option value="wallet">Wallet</option>
                  <option value="other">Other (DD / Cheque)</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="block text-xs font-semibold text-[#292039]">
                  Transaction / Receipt Reference *
                </label>
                <input
                  type="text"
                  required
                  value={manualReference}
                  onChange={(e) => setManualReference(e.target.value)}
                  placeholder="e.g. CASH-REG-104 or UTR123456789"
                  className="w-full px-3 py-2 rounded-xl border border-[#D8CEBE] text-xs bg-[#FFFDF9] focus:outline-none focus:border-[#D94378]"
                />
              </div>

              <label className="flex items-start gap-2 text-xs text-[#292039]/80 cursor-pointer">
                <input
                  type="checkbox"
                  checked={paymentConfirmed}
                  onChange={(e) => setPaymentConfirmed(e.target.checked)}
                  className="mt-0.5"
                  required
                />
                <span>
                  I confirm full payment of ₹
                  {paymentsData?.outstandingInr || fine.amountInr || fine.amount} has been verified
                  and received.
                </span>
              </label>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setActiveModal(null)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-[#E8DCCF] text-[#292039]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting || !paymentConfirmed}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-[#368F83] text-white hover:bg-[#2B7369] disabled:opacity-50"
                >
                  {isSubmitting ? 'Recording...' : 'Confirm Full Payment'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <ReceiptModal
        receipt={activeReceipt}
        onDownloadPdf={
          activeReceipt?.receiptNumber
            ? () => downloadReceiptPdf(activeReceipt.receiptNumber, 'admin')
            : undefined
        }
        onClose={() => setActiveReceipt(null)}
      />
    </div>
  )
}
