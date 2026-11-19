import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useApp } from '../../../context/AppContext'
import { StatusBadge } from '../../../components/Brand'

const DISPUTE_STATUS_BADGE = {
  open: 'Disputed',
  approved: 'Waived',
  rejected: 'Pending',
}

export function AdminFineDisputesPage() {
  const { fetchAdminDisputes, reviewDispute } = useApp()

  const [disputes, setDisputes] = useState([])
  const [statusFilter, setStatusFilter] = useState('all')
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')

  // Selected fine for quick review
  const [activeFineId, setActiveFineId] = useState(null)
  const [activeReference, setActiveReference] = useState('')
  const [decision, setDecision] = useState('Approved')
  const [remarks, setRemarks] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [notice, setNotice] = useState(null)
  const [actionError, setActionError] = useState('')

  const loadDisputes = async (filterStatus = statusFilter) => {
    setLoading(true)
    setLoadError('')
    try {
      const data = await fetchAdminDisputes(filterStatus === 'all' ? {} : { status: filterStatus })
      setDisputes(Array.isArray(data?.disputes) ? data.disputes : [])
    } catch (err) {
      setLoadError(err.message || 'Unable to load fine disputes.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    let active = true
    fetchAdminDisputes(statusFilter === 'all' ? {} : { status: statusFilter })
      .then((data) => {
        if (!active) return
        setDisputes(Array.isArray(data?.disputes) ? data.disputes : [])
        setLoadError('')
      })
      .catch((err) => {
        if (!active) return
        setLoadError(err.message || 'Unable to load fine disputes.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [statusFilter, fetchAdminDisputes])

  const pendingDisputes = disputes.filter((d) => String(d.status).toLowerCase() === 'open')
  const resolvedDisputes = disputes.filter((d) => String(d.status).toLowerCase() !== 'open')

  const handleReviewSubmit = async (e) => {
    e.preventDefault()
    if (!activeFineId || !remarks.trim() || isSubmitting) return
    setIsSubmitting(true)
    setActionError('')
    try {
      await reviewDispute(activeFineId, {
        decision: decision === 'Approved' ? 'approve' : 'reject',
        reason: remarks.trim(),
      })
      setNotice(
        `Dispute decision recorded as ${decision} for fine ${activeReference || activeFineId}.`,
      )
      setActiveFineId(null)
      setActiveReference('')
      setRemarks('')
      await loadDisputes(statusFilter)
    } catch (err) {
      setActionError(err.message || 'Unable to submit dispute decision.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <span className="text-[11px] font-bold text-purple-700 uppercase tracking-wider">
            Disciplinary Grievance &amp; Appeals
          </span>
          <h1 className="font-serif text-2xl sm:text-3xl font-bold text-[#292039]">
            Fine Dispute Queue
          </h1>
          <p className="text-xs text-[#292039]/70 mt-1">
            Review resident written statements, verify claims, and deliver binding waiver or uphold
            decisions
          </p>
        </div>

        <div className="flex items-center gap-3">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            aria-label="Filter disputes by status"
            className="px-3 py-2 rounded-xl border border-[#D8CEBE] bg-[#FFFCF7] text-xs font-semibold text-[#292039]"
          >
            <option value="all">All Disputes</option>
            <option value="open">Open / Pending</option>
            <option value="approved">Approved (Waived)</option>
            <option value="rejected">Rejected (Upheld)</option>
          </select>
          <Link
            to="/admin/fines"
            className="px-4 py-2 rounded-xl border border-[#D8CEBE] bg-[#FFFCF7] text-xs font-semibold text-[#292039] hover:bg-[#F7EFE6]"
          >
            &larr; Fines Directory
          </Link>
        </div>
      </div>

      {notice && (
        <div className="p-4 rounded-2xl bg-emerald-50 border border-emerald-300 text-emerald-900 text-xs flex items-center justify-between">
          <span>✓ {notice}</span>
          <button type="button" onClick={() => setNotice(null)} className="font-bold">
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

      {loadError && (
        <div className="p-4 rounded-2xl bg-red-50 border border-red-200 flex items-center justify-between gap-4">
          <p className="text-xs text-red-700 font-medium">{loadError}</p>
          <button
            type="button"
            onClick={() => loadDisputes(statusFilter)}
            className="px-3 py-1.5 rounded-lg bg-red-600 text-white text-xs font-semibold hover:bg-red-700"
          >
            Retry
          </button>
        </div>
      )}

      {/* Pending Queue Section */}
      <div className="bg-[#FFFCF7] rounded-3xl border border-[#E8DCCF] p-6 shadow-xs space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <h2 className="font-serif text-lg font-bold text-[#292039]">
              Pending Appeals Awaiting Hearing
            </h2>
            <span className="px-2 py-0.5 rounded-full bg-purple-100 text-purple-800 text-xs font-bold font-mono">
              {pendingDisputes.length}
            </span>
          </div>
          <span className="text-xs text-[#292039]/60">Chief Warden Review Desk</span>
        </div>

        {loading ? (
          <div className="py-12 text-center space-y-2">
            <p className="font-serif text-base font-bold text-[#292039]">Loading disputes...</p>
            <p className="text-xs text-[#292039]/60">Fetching student appeals from the server.</p>
          </div>
        ) : pendingDisputes.length === 0 ? (
          <div className="py-12 text-center space-y-2">
            <div className="w-12 h-12 rounded-full bg-purple-50 text-purple-600 mx-auto flex items-center justify-center text-xl">
              ✓
            </div>
            <h3 className="font-serif text-base font-bold text-[#292039]">Dispute Queue Clear</h3>
            <p className="text-xs text-[#292039]/70 max-w-sm mx-auto">
              There are no pending resident appeals awaiting administrative adjudication.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {pendingDisputes.map((item) => {
              const fineId = item.fineId ?? item.fine?.id ?? item.id
              const fineRef = item.fineReference || item.fine?.referenceNo || fineId
              const studentName = item.studentName || item.fine?.studentName || 'Student'
              const studentRoll = item.studentRoll || item.fine?.studentRoll || ''
              const room = item.room || item.fine?.room || ''
              const amount = item.amountInr ?? item.fine?.amountInr ?? item.amount ?? 0
              const category = item.category || item.fine?.category || 'Disciplinary Violation'
              const description = item.description || item.fine?.description || ''
              const issueDate = item.issueDate || item.fine?.issueDate || ''
              const explanation = item.reason || item.explanation || ''
              const submittedAt = item.createdAt || item.submittedAt || ''

              return (
                <div
                  key={item.id || fineId}
                  className="p-5 rounded-2xl bg-[#FFFDF9] border border-purple-200 shadow-xs space-y-4"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-[#E8DCCF]">
                    <div className="flex items-center gap-2.5">
                      <span className="font-mono text-xs font-bold text-[#292039]">{fineRef}</span>
                      <span className="font-semibold text-xs text-[#292039]">
                        {studentName} {studentRoll ? `(${studentRoll})` : ''}
                      </span>
                      {room && (
                        <span className="text-[11px] text-[#292039]/70 font-mono">Room {room}</span>
                      )}
                    </div>

                    <div className="flex items-center gap-3">
                      <span className="font-serif text-base font-bold text-[#D94378]">
                        ₹{amount}
                      </span>
                      <StatusBadge
                        status={
                          DISPUTE_STATUS_BADGE[String(item.status).toLowerCase()] || 'Disputed'
                        }
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                    <div className="p-3.5 rounded-xl bg-[#F7EFE6] border border-[#E8DCCF] space-y-1">
                      <span className="font-semibold text-[#292039] block text-[11px]">
                        Original Allegation ({category}):
                      </span>
                      <p className="text-[#292039]/80 leading-relaxed">{description}</p>
                      {issueDate && (
                        <span className="text-[10px] text-[#292039]/60 block pt-1">
                          Issued on {issueDate}
                        </span>
                      )}
                    </div>

                    <div className="p-3.5 rounded-xl bg-purple-50/70 border border-purple-200 space-y-1">
                      <span className="font-semibold text-purple-900 block text-[11px]">
                        Student Written Explanation:
                      </span>
                      <p className="text-purple-950 italic leading-relaxed">
                        &ldquo;{explanation}&rdquo;
                      </p>
                      {submittedAt && (
                        <span className="text-[10px] text-purple-600 block pt-1">
                          Filed on {submittedAt}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="flex justify-end gap-2 pt-1">
                    <Link
                      to={`/admin/fines/${fineId}`}
                      className="px-3 py-1.5 rounded-lg border border-[#D8CEBE] text-xs font-semibold text-[#292039] hover:bg-[#F7EFE6]"
                    >
                      Full History
                    </Link>
                    <button
                      type="button"
                      onClick={() => {
                        setActionError('')
                        setActiveFineId(fineId)
                        setActiveReference(fineRef)
                        setDecision('Approved')
                        setRemarks('')
                      }}
                      className="px-4 py-1.5 rounded-lg bg-purple-700 text-white text-xs font-semibold hover:bg-purple-800 transition-colors cursor-pointer"
                    >
                      Adjudicate Now &rarr;
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Past Adjudications Section */}
      {resolvedDisputes.length > 0 && (
        <div className="bg-[#FFFCF7] rounded-3xl border border-[#E8DCCF] p-6 shadow-xs space-y-4">
          <h2 className="font-serif text-lg font-bold text-[#292039]">
            Past Adjudicated Disputes ({resolvedDisputes.length})
          </h2>

          <div className="space-y-3">
            {resolvedDisputes.map((item) => {
              const fineId = item.fineId ?? item.fine?.id ?? item.id
              const fineRef = item.fineReference || item.fine?.referenceNo || fineId
              const studentName = item.studentName || item.fine?.studentName || 'Student'
              const studentRoll = item.studentRoll || item.fine?.studentRoll || ''
              const amount = item.amountInr ?? item.fine?.amountInr ?? item.amount ?? 0
              const badgeStatus =
                DISPUTE_STATUS_BADGE[String(item.status).toLowerCase()] || 'Pending'

              return (
                <div
                  key={item.id || fineId}
                  className="p-4 rounded-2xl bg-[#FFFDF9] border border-[#E8DCCF] text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold text-[#292039]">{fineRef}</span>
                      <span className="font-semibold">
                        {studentName} {studentRoll ? `(${studentRoll})` : ''}
                      </span>
                      <StatusBadge status={badgeStatus} />
                    </div>
                    <p className="text-[#292039]/70 text-[11px]">
                      <strong>Outcome Remarks:</strong>{' '}
                      {item.decisionReason || item.reviewNote || 'Decision concluded'}
                    </p>
                  </div>

                  <div className="flex items-center gap-3 shrink-0">
                    <span className="font-serif font-bold text-[#292039]">₹{amount}</span>
                    <Link
                      to={`/admin/fines/${fineId}`}
                      className="px-3 py-1.5 rounded-lg border border-[#D8CEBE] hover:bg-[#F7EFE6] text-[#292039] font-medium"
                    >
                      View Record
                    </Link>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Adjudication Modal */}
      {activeFineId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#292039]/60 backdrop-blur-xs">
          <div className="bg-[#FFFCF7] w-full max-w-lg rounded-3xl border border-[#E8DCCF] shadow-2xl p-6 space-y-4">
            <h3 className="font-serif text-lg font-bold text-[#292039]">
              Record Dispute Determination
            </h3>
            <p className="text-xs text-[#292039]/70">
              Hearing decision for Fine {activeReference || activeFineId}. The verdict will update
              student dues and be permanently logged in the audit trail.
            </p>

            <form onSubmit={handleReviewSubmit} className="space-y-4">
              <div className="space-y-2">
                <label className="block text-xs font-semibold text-[#292039]">Determination</label>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setDecision('Approved')}
                    className={`py-2 px-3 rounded-xl border text-xs font-bold transition-all ${
                      decision === 'Approved'
                        ? 'border-teal-500 bg-teal-50 text-teal-800'
                        : 'border-[#E8DCCF] text-[#292039]/70'
                    }`}
                  >
                    ✓ Approve Appeal (Waive Fine)
                  </button>
                  <button
                    type="button"
                    onClick={() => setDecision('Rejected')}
                    className={`py-2 px-3 rounded-xl border text-xs font-bold transition-all ${
                      decision === 'Rejected'
                        ? 'border-rose-500 bg-rose-50 text-rose-800'
                        : 'border-[#E8DCCF] text-[#292039]/70'
                    }`}
                  >
                    ✕ Reject Appeal (Uphold Fine)
                  </button>
                </div>
              </div>

              <div className="space-y-1">
                <label className="block text-xs font-semibold text-[#292039]">
                  Official Finding &amp; Grounds *
                </label>
                <textarea
                  required
                  rows={3}
                  value={remarks}
                  onChange={(e) => setRemarks(e.target.value)}
                  placeholder="State the findings (e.g. Verified with dispensary doctor note; medical necessity established. Fine waived.)..."
                  className="w-full px-3 py-2 rounded-xl border border-[#D8CEBE] text-xs focus:outline-none focus:border-[#D94378]"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setActiveFineId(null)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-[#E8DCCF] text-[#292039]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-purple-700 text-white hover:bg-purple-800 disabled:opacity-50"
                >
                  {isSubmitting ? 'Submitting...' : 'Commit Determination'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
