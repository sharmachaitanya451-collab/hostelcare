import { useEffect, useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useApp } from '../../context/AppContext'
import { StatusBadge, PriorityBadge } from '../../components/Brand'
import { ComplaintAttachmentsGallery } from '../../components/ComplaintAttachmentsGallery'

export function AdminComplaintDetailPage() {
  const { id } = useParams()
  const {
    complaints,
    staff,
    fetchComplaintDetail,
    reviewComplaint,
    assignStaffToComplaint,
    closeComplaint,
    rejectComplaint,
    reopenComplaint,
    addInternalNote,
    returnTaskForRework,
  } = useApp()
  const navigate = useNavigate()

  const complaint = complaints.find((c) => c.id === id)

  // Modal / Action form states
  const [activeModal, setActiveModal] = useState(null) // null | 'assign' | 'review' | 'close' | 'reject' | 'rework' | 'reopen'
  const [selectedStaffId, setSelectedStaffId] = useState('')
  const [assignmentNotes, setAssignmentNotes] = useState('')
  const [actionNote, setActionNote] = useState('')
  const [rejectionReason, setRejectionReason] = useState('')
  const [reworkNote, setReworkNote] = useState('')
  const [reopenReason, setReopenReason] = useState('')
  const [internalNoteText, setInternalNoteText] = useState('')
  const [submittingAction, setSubmittingAction] = useState(false)
  const [feedbackNotice, setFeedbackNotice] = useState(null)
  const [errorBanner, setErrorBanner] = useState('')

  useEffect(() => {
    if (id) {
      fetchComplaintDetail(id).catch(() => {})
    }
  }, [fetchComplaintDetail, id])

  if (!complaint) {
    return (
      <div className="bg-[#FFFCF7] p-12 rounded-3xl border border-[#E8DCCF] text-center space-y-4">
        <h3 className="font-serif text-2xl font-bold text-[#292039]">Complaint Not Found</h3>
        <p className="text-xs text-[#292039]/70">No ticket exists matching ID {id}.</p>
        <button
          onClick={() => navigate('/admin/complaints')}
          className="text-xs font-semibold text-[#D94378] hover:underline"
        >
          Return to complaint queue &rarr;
        </button>
      </div>
    )
  }

  // Active staff list for assignment
  const activeStaffList = staff.filter(
    (s) =>
      s.status === 'Active' ||
      s.status === 'On Duty' ||
      s.status === 'active' ||
      s.display_status === 'Active',
  )

  const isPreAcceptance =
    complaint.status === 'Submitted' ||
    complaint.status === 'Under Review' ||
    complaint.status === 'Assigned' ||
    complaint.status === 'open'

  const canAssignOrReassign =
    complaint.status === 'Submitted' ||
    complaint.status === 'Under Review' ||
    complaint.status === 'Assigned' ||
    complaint.status === 'Accepted' ||
    complaint.status === 'In Progress' ||
    complaint.status === 'open'

  const isCompletedStatus = complaint.status === 'Resolved' || complaint.status === 'Completed'

  const handleReview = async () => {
    if (submittingAction) return
    setSubmittingAction(true)
    setErrorBanner('')
    try {
      await reviewComplaint(complaint.id, { note: actionNote })
      setActiveModal(null)
      setActionNote('')
      setFeedbackNotice(`Complaint ${complaint.id} marked as Under Review. Student notified.`)
    } catch (err) {
      setErrorBanner(err?.message || 'Unable to mark complaint under review.')
    } finally {
      setSubmittingAction(false)
    }
  }

  const handleAssign = async (e) => {
    e.preventDefault()
    if (!selectedStaffId || submittingAction) return
    setSubmittingAction(true)
    setErrorBanner('')
    try {
      await assignStaffToComplaint(complaint.id, {
        staffId: selectedStaffId,
        assignmentNotes,
      })
      setActiveModal(null)
      setSelectedStaffId('')
      setAssignmentNotes('')
      setFeedbackNotice(`Staff assigned successfully to ${complaint.id}. Notifications dispatched.`)
    } catch (err) {
      setErrorBanner(err?.message || 'Unable to assign staff member.')
    } finally {
      setSubmittingAction(false)
    }
  }

  const handleClose = async (e) => {
    e.preventDefault()
    if (submittingAction) return
    setSubmittingAction(true)
    setErrorBanner('')
    try {
      await closeComplaint(complaint.id, { closureNote: actionNote })
      setActiveModal(null)
      setActionNote('')
      setFeedbackNotice(`Complaint ${complaint.id} officially closed by warden verification.`)
    } catch (err) {
      setErrorBanner(err?.message || 'Unable to close complaint.')
    } finally {
      setSubmittingAction(false)
    }
  }

  const handleRework = async (e) => {
    e.preventDefault()
    if (!reworkNote.trim() || submittingAction) return
    setSubmittingAction(true)
    setErrorBanner('')
    try {
      await returnTaskForRework(complaint.id, { reworkNote: reworkNote.trim() })
      setActiveModal(null)
      setReworkNote('')
      setFeedbackNotice(
        `Complaint ${complaint.id} returned to assigned technician for further work.`,
      )
    } catch (err) {
      setErrorBanner(err?.message || 'Unable to return complaint for rework.')
    } finally {
      setSubmittingAction(false)
    }
  }

  const handleReject = async (e) => {
    e.preventDefault()
    if (!rejectionReason.trim() || submittingAction) return
    setSubmittingAction(true)
    setErrorBanner('')
    try {
      await rejectComplaint(complaint.id, { reason: rejectionReason.trim() })
      setActiveModal(null)
      setRejectionReason('')
      setFeedbackNotice(`Complaint ${complaint.id} rejected with official reason recorded.`)
    } catch (err) {
      setErrorBanner(err?.message || 'Unable to reject complaint.')
    } finally {
      setSubmittingAction(false)
    }
  }

  const handleReopen = async (e) => {
    e.preventDefault()
    if (!reopenReason.trim() || submittingAction) return
    setSubmittingAction(true)
    setErrorBanner('')
    try {
      await reopenComplaint(complaint.id, { reason: reopenReason.trim() })
      setActiveModal(null)
      setReopenReason('')
      setFeedbackNotice(
        `Complaint ${complaint.id} reopened and placed Under Review with audit history recorded.`,
      )
    } catch (err) {
      setErrorBanner(err?.message || 'Unable to reopen complaint.')
    } finally {
      setSubmittingAction(false)
    }
  }

  const handleAddInternalNote = async (e) => {
    e.preventDefault()
    if (!internalNoteText.trim() || submittingAction) return
    setSubmittingAction(true)
    setErrorBanner('')
    try {
      await addInternalNote(complaint.id, internalNoteText.trim())
      setInternalNoteText('')
      setFeedbackNotice('Internal administrative note recorded.')
    } catch (err) {
      setErrorBanner(err?.message || 'Unable to save internal note.')
    } finally {
      setSubmittingAction(false)
    }
  }

  const reporterName = complaint.studentName || complaint.reporterName || 'Resident Student'
  const reporterRoll = complaint.studentRoll || complaint.reporterRoll || 'N/A'
  const loggedDate = complaint.date || complaint.dateSubmitted

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Header bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#F0E4D4]">
        <div className="space-y-1">
          <Link
            to="/admin/complaints"
            className="text-xs font-semibold text-[#D94378] flex items-center gap-1 hover:underline"
          >
            <span>&larr;</span>
            <span>Back to complaint queue</span>
          </Link>
          <div className="flex items-center gap-3">
            <h1 className="font-serif text-2xl sm:text-3xl font-bold text-[#292039]">
              Ticket {complaint.id}
            </h1>
            <StatusBadge status={complaint.status} />
          </div>
        </div>

        {/* Action Buttons Toolbar */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Review action */}
          {(complaint.status === 'Submitted' || complaint.status === 'open') && (
            <button
              type="button"
              onClick={() => {
                setActiveModal('review')
                setActionNote('')
              }}
              className="px-3.5 py-2 rounded-xl bg-purple-700 text-white text-xs font-semibold hover:bg-purple-800 transition-colors cursor-pointer"
            >
              📋 Mark Under Review
            </button>
          )}

          {/* Assign / Reassign action */}
          {canAssignOrReassign && (
            <button
              type="button"
              onClick={() => {
                setActiveModal('assign')
                setSelectedStaffId('')
                setAssignmentNotes('')
              }}
              className="px-3.5 py-2 rounded-xl bg-[#292039] text-[#FFFCF7] text-xs font-semibold hover:bg-[#3D3252] transition-colors cursor-pointer"
            >
              {complaint.assignedStaff && complaint.assignedStaff !== 'Unassigned'
                ? '🔄 Reassign Staff'
                : '👷 Assign Duty Staff'}
            </button>
          )}

          {/* Close action */}
          {isCompletedStatus && (
            <button
              type="button"
              onClick={() => {
                setActiveModal('close')
                setActionNote('')
              }}
              className="px-4 py-2 rounded-xl bg-emerald-800 text-white text-xs font-semibold hover:bg-emerald-900 transition-colors cursor-pointer"
            >
              🔒 Confirm &amp; Close Ticket
            </button>
          )}

          {/* Return for further work action */}
          {isCompletedStatus && (
            <button
              type="button"
              onClick={() => {
                setActiveModal('rework')
                setReworkNote('')
              }}
              className="px-3.5 py-2 rounded-xl border border-amber-400 bg-amber-50 text-amber-900 text-xs font-semibold hover:bg-amber-100 transition-colors cursor-pointer"
            >
              ↩️ Return for Further Work
            </button>
          )}

          {/* Reject action (pre-acceptance only per D4/ADR-020) */}
          {isPreAcceptance && (
            <button
              type="button"
              onClick={() => {
                setActiveModal('reject')
                setRejectionReason('')
              }}
              className="px-3 py-2 rounded-xl border border-rose-300 bg-rose-50 text-rose-800 text-xs font-semibold hover:bg-rose-100 transition-colors cursor-pointer"
            >
              ✕ Reject Ticket
            </button>
          )}

          {/* Reopen action for Closed complaints (D3/ADR-020) */}
          {complaint.status === 'Closed' && (
            <button
              type="button"
              onClick={() => {
                setActiveModal('reopen')
                setReopenReason('')
              }}
              className="px-3.5 py-2 rounded-xl bg-amber-600 text-white text-xs font-semibold hover:bg-amber-700 transition-colors cursor-pointer"
            >
              🔓 Reopen Closed Ticket
            </button>
          )}
        </div>
      </div>

      {feedbackNotice && (
        <div className="p-4 rounded-2xl bg-emerald-50 border border-emerald-300 text-emerald-900 text-xs flex items-center justify-between">
          <span>✓ {feedbackNotice}</span>
          <button onClick={() => setFeedbackNotice(null)} className="font-bold">
            ✕
          </button>
        </div>
      )}

      {errorBanner && (
        <div
          role="alert"
          className="p-4 rounded-2xl bg-rose-50 border border-rose-300 text-rose-900 text-xs flex items-center justify-between"
        >
          <span>⚠️ {errorBanner}</span>
          <button onClick={() => setErrorBanner('')} className="font-bold">
            ✕
          </button>
        </div>
      )}

      {complaint.reworkNote && complaint.status === 'In Progress' && (
        <div className="p-4 rounded-2xl bg-amber-50 border border-amber-300 text-amber-900 text-xs flex items-start gap-3">
          <span className="text-base">⚠️</span>
          <div>
            <div className="font-bold uppercase tracking-wider text-[11px]">
              Rework Order Active
            </div>
            <p className="mt-0.5 text-[#292039]/80">
              This ticket was returned to technician for further work:{' '}
              <span className="italic font-medium">&quot;{complaint.reworkNote}&quot;</span>
            </p>
          </div>
        </div>
      )}

      {/* Main Details Card */}
      <div className="bg-[#FFFCF7] p-6 sm:p-8 rounded-3xl border border-[#E8DCCF] shadow-xs space-y-6">
        {/* Resident & Ticket Particulars Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 pb-6 border-b border-[#E8DCCF]">
          <div>
            <span className="text-[10px] text-[#292039]/60 uppercase tracking-wider block font-semibold">
              Reporting Resident
            </span>
            <span className="text-sm font-bold text-[#292039]">{reporterName}</span>
            <span className="text-xs text-[#292039]/70 block font-mono">Roll: {reporterRoll}</span>
          </div>

          <div>
            <span className="text-[10px] text-[#292039]/60 uppercase tracking-wider block font-semibold">
              {complaint.locationType === 'common_area' ? 'Common Area Location' : 'Room Location'}
            </span>
            <span className="font-serif text-lg font-bold text-[#D94378]">
              {complaint.locationType === 'common_area' ? complaint.room : `Room ${complaint.room}`}
            </span>
            <span className="text-xs text-[#292039]/70 block font-medium">
              {complaint.block || 'Wing Block'}
            </span>
          </div>

          <div>
            <span className="text-[10px] text-[#292039]/60 uppercase tracking-wider block font-semibold">
              Category &amp; Priority
            </span>
            <span className="text-xs font-bold text-[#368F83] block mt-0.5">
              {complaint.category}
            </span>
            <div className="mt-1">
              <PriorityBadge priority={complaint.priority} />
            </div>
          </div>

          <div>
            <span className="text-[10px] text-[#292039]/60 uppercase tracking-wider block font-semibold">
              Submission Date
            </span>
            <span className="text-xs font-semibold text-[#292039] block mt-0.5">{loggedDate}</span>
            <span className="text-[11px] text-[#292039]/60">System Registered</span>
          </div>
        </div>

        {/* Complaint Title & Problem Description */}
        <div className="space-y-2">
          <h2 className="font-serif text-xl font-bold text-[#292039]">{complaint.title}</h2>
          <div className="p-4 rounded-2xl bg-[#FFFDF9] border border-[#E8DCCF] text-xs sm:text-sm text-[#292039] leading-relaxed whitespace-pre-wrap font-sans">
            {complaint.description}
          </div>
        </div>

        {/* Attached Photos */}
        <ComplaintAttachmentsGallery attachments={complaint.attachments} />

        {/* Rejection Notice if rejected */}
        {complaint.status === 'Rejected' && complaint.rejectionReason && (
          <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-900 text-xs space-y-1">
            <span className="font-bold text-rose-800 uppercase tracking-wider block text-[11px]">
              Administrative Rejection Ground:
            </span>
            <p className="leading-relaxed">{complaint.rejectionReason}</p>
          </div>
        )}

        {/* Assigned Staff Card */}
        <div className="p-5 rounded-2xl bg-[#F7EFE6] border border-[#E8DCCF] space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="font-serif text-sm font-bold text-[#292039]">
              Assigned Maintenance Personnel
            </h3>
            <span className="text-xs font-mono font-bold text-[#292039]">
              Current Status: {complaint.status}
            </span>
          </div>

          {complaint.assignedStaff && complaint.assignedStaff !== 'Unassigned' ? (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
              <div>
                <span className="text-[10px] text-[#292039]/60 uppercase tracking-wider block">
                  Staff Member
                </span>
                <p className="font-bold text-[#292039] text-sm mt-0.5">{complaint.assignedStaff}</p>
                <span className="text-[11px] text-[#368F83] font-semibold block">
                  {complaint.assignedStaffRole || 'Duty Maintenance Staff'}
                </span>
              </div>

              <div>
                <span className="text-[10px] text-[#292039]/60 uppercase tracking-wider block">
                  Contact
                </span>
                <p className="font-medium text-[#292039] mt-0.5">
                  {complaint.assignedStaffContact || '+91 94421 88901'}
                </p>
                <span className="text-[10px] text-[#292039]/60">Hostel Maintenance Cell</span>
              </div>

              <div>
                <span className="text-[10px] text-[#292039]/60 uppercase tracking-wider block">
                  Assignment Log
                </span>
                <p className="font-medium text-[#292039] mt-0.5">{complaint.assignedDate}</p>
                <span className="text-[10px] text-[#292039]/60 block">
                  By: {complaint.assignedBy || 'Warden Desk'}
                </span>
                {complaint.assignmentNotes && (
                  <p className="text-[11px] text-[#292039]/80 italic mt-1">
                    &ldquo;{complaint.assignmentNotes}&rdquo;
                  </p>
                )}
              </div>
            </div>
          ) : (
            <div className="text-xs text-[#292039]/70 py-1 flex items-center justify-between">
              <span>No duty staff currently assigned to this ticket.</span>
              {canAssignOrReassign && (
                <button
                  type="button"
                  onClick={() => {
                    setActiveModal('assign')
                    setSelectedStaffId('')
                    setAssignmentNotes('')
                  }}
                  className="px-3 py-1.5 rounded-lg bg-[#292039] text-white text-xs font-semibold hover:bg-[#3D3252] cursor-pointer"
                >
                  + Assign Staff Now
                </button>
              )}
            </div>
          )}

          {/* Previous Assignment History if reassigned */}
          {complaint.previousAssignments && complaint.previousAssignments.length > 0 && (
            <div className="pt-3 border-t border-[#E8DCCF] space-y-2">
              <span className="text-[10px] font-bold uppercase tracking-wider text-[#292039]/60">
                Previous Assignment History
              </span>
              <div className="space-y-1.5">
                {complaint.previousAssignments.map((prev, idx) => (
                  <div
                    key={prev.id || idx}
                    className="p-2.5 rounded-xl bg-white/70 border border-[#E8DCCF] text-xs flex justify-between items-center"
                  >
                    <div>
                      <span className="font-semibold text-[#292039]">
                        {prev.staffName} ({prev.role || prev.staffRole})
                      </span>
                      {(prev.note || prev.notes) && (
                        <p className="text-[11px] text-[#292039]/70 italic mt-0.5">
                          Notes: {prev.note || prev.notes}
                        </p>
                      )}
                    </div>
                    <div className="text-right text-[10px] text-[#292039]/60 font-mono">
                      <span>{prev.assignedAt || prev.assignedDate}</span>
                      {prev.endedAt && <span className="block">Ended: {prev.endedAt}</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Private Administrative Internal Notes Section */}
        <div className="p-5 rounded-2xl bg-slate-50 border border-slate-200 space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-slate-200">
            <div className="flex items-center gap-1.5">
              <span className="text-sm">🔒</span>
              <h3 className="font-serif text-sm font-bold text-slate-800">
                Internal Administrative Notes (Private to Warden Desk)
              </h3>
            </div>
            <span className="text-[10px] font-semibold text-slate-500 bg-slate-200 px-2 py-0.5 rounded">
              Confidential — Not visible to residents
            </span>
          </div>

          <div className="space-y-2">
            {complaint.internalNotes && complaint.internalNotes.length > 0 ? (
              complaint.internalNotes.map((note) => (
                <div
                  key={note.id}
                  className="p-3 rounded-xl bg-white border border-slate-200 text-xs space-y-1"
                >
                  <p className="text-slate-800 leading-relaxed font-sans">
                    {note.note || note.body || note.text}
                  </p>
                  <div className="text-[10px] text-slate-500 flex justify-between pt-1 border-t border-slate-100">
                    <span>Logged by: {note.by || note.author}</span>
                    <span className="font-mono">{note.time || note.timestamp}</span>
                  </div>
                </div>
              ))
            ) : (
              <p className="text-xs text-slate-500 italic py-1">
                No internal administrative notes recorded yet.
              </p>
            )}
          </div>

          {/* Form to add internal note */}
          <form onSubmit={handleAddInternalNote} className="flex gap-2 pt-1">
            <input
              type="text"
              required
              value={internalNoteText}
              onChange={(e) => setInternalNoteText(e.target.value)}
              placeholder="Add private note for warden team (e.g. Parts requisitioned from central store)..."
              className="flex-1 px-3 py-2 rounded-xl border border-slate-300 text-xs bg-white focus:outline-none focus:border-slate-500"
            />
            <button
              type="submit"
              disabled={submittingAction}
              className="px-4 py-2 rounded-xl bg-slate-800 text-white text-xs font-semibold hover:bg-slate-900 disabled:opacity-50 transition-colors cursor-pointer shrink-0"
            >
              Add Private Note
            </button>
          </form>
        </div>

        {/* Audit & Dispatch History Timeline */}
        <div className="space-y-3 pt-4 border-t border-[#E8DCCF]">
          <h3 className="text-xs font-bold uppercase tracking-wider text-[#292039]">
            Comprehensive Complaint Audit Trail
          </h3>
          <div className="space-y-2">
            {complaint.history?.map((step, idx) => (
              <div
                key={step.id || idx}
                className="p-3.5 rounded-xl bg-[#FFFDF9] border border-[#E8DCCF] text-xs flex items-start gap-3"
              >
                <div className="w-2 h-2 rounded-full bg-[#368F83] mt-1.5 shrink-0" />
                <div className="flex-1 space-y-0.5">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-[#292039]">{step.action}</span>
                    <span className="text-[10px] text-[#292039]/60 font-mono">
                      {step.timestamp || step.time}
                    </span>
                  </div>
                  <p className="text-[11px] text-[#292039]/80 leading-relaxed">{step.note}</p>
                  <span className="text-[10px] text-[#292039]/60 block pt-0.5">
                    Actor: <em>{step.actor || step.by}</em>
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Modal: Review Complaint */}
      {activeModal === 'review' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#292039]/60 backdrop-blur-xs">
          <div className="bg-[#FFFCF7] w-full max-w-md rounded-3xl border border-[#E8DCCF] shadow-2xl p-6 space-y-4">
            <h3 className="font-serif text-lg font-bold text-[#292039]">
              Mark Complaint Under Review
            </h3>
            <p className="text-xs text-[#292039]/70">
              Acknowledge ticket {complaint.id} and change status to <strong>Under Review</strong>.
              The resident will receive an in-app notification.
            </p>
            <div className="space-y-3">
              <textarea
                rows={3}
                value={actionNote}
                onChange={(e) => setActionNote(e.target.value)}
                placeholder="Optional review remarks (e.g. Prioritized for duty plumber during afternoon shift)..."
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
                  type="button"
                  disabled={submittingAction}
                  onClick={handleReview}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-purple-700 text-white hover:bg-purple-800 disabled:opacity-50"
                >
                  Confirm Review
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Assign or Reassign Staff */}
      {activeModal === 'assign' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#292039]/60 backdrop-blur-xs">
          <div className="bg-[#FFFCF7] w-full max-w-lg rounded-3xl border border-[#E8DCCF] shadow-2xl p-6 space-y-4">
            <h3 className="font-serif text-lg font-bold text-[#292039]">
              {complaint.assignedStaff && complaint.assignedStaff !== 'Unassigned'
                ? 'Reassign Duty Staff'
                : 'Assign Maintenance Staff'}
            </h3>
            <p className="text-xs text-[#292039]/70">
              Select an active technician for {complaint.id} ({complaint.category}). Previous
              assignments will be archived in the ticket history.
            </p>

            <form onSubmit={handleAssign} className="space-y-4">
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-[#292039]">
                  Select Staff Member *
                </label>
                <select
                  required
                  value={selectedStaffId}
                  onChange={(e) => setSelectedStaffId(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-[#D8CEBE] text-xs bg-[#FFFDF9] text-[#292039]"
                >
                  <option value="">-- Choose active maintenance staff --</option>
                  {activeStaffList.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name || s.fullName} — {s.trade} ({s.phone})
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-[#292039]">
                  Assignment Notes / Special Instructions
                </label>
                <textarea
                  rows={3}
                  value={assignmentNotes}
                  onChange={(e) => setAssignmentNotes(e.target.value)}
                  placeholder="e.g. Bring replacement 2.5uF capacitor and check Room A-203 switchboard voltage..."
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
                  disabled={!selectedStaffId || submittingAction}
                  className="px-5 py-2 rounded-xl text-xs font-semibold bg-[#292039] text-[#FFFCF7] hover:bg-[#3D3252] disabled:opacity-50"
                >
                  Confirm Staff Assignment
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Confirm Closure */}
      {activeModal === 'close' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#292039]/60 backdrop-blur-xs">
          <div className="bg-[#FFFCF7] w-full max-w-md rounded-3xl border border-[#E8DCCF] shadow-2xl p-6 space-y-4">
            <h3 className="font-serif text-lg font-bold text-[#292039]">Confirm Closure</h3>
            <p className="text-xs text-[#292039]/70">
              Confirm that the repairs have been reviewed and satisfy hostel facility standards.
            </p>
            <form onSubmit={handleClose} className="space-y-4">
              <textarea
                rows={3}
                value={actionNote}
                onChange={(e) => setActionNote(e.target.value)}
                placeholder="Warden verification remarks (e.g. Inspected room and verified fan noise resolved)..."
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
                  disabled={submittingAction}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-emerald-800 text-white hover:bg-emerald-900 disabled:opacity-50"
                >
                  Confirm &amp; Close Ticket
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Reject Ticket */}
      {activeModal === 'reject' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#292039]/60 backdrop-blur-xs">
          <div className="bg-[#FFFCF7] w-full max-w-md rounded-3xl border border-[#E8DCCF] shadow-2xl p-6 space-y-4">
            <h3 className="font-serif text-lg font-bold text-[#292039]">
              Reject Maintenance Request
            </h3>
            <p className="text-xs text-[#292039]/70">
              Warden must provide a mandatory justification explaining why this ticket cannot be
              serviced (permitted only before staff acceptance).
            </p>
            <form onSubmit={handleReject} className="space-y-4">
              <textarea
                required
                rows={3}
                value={rejectionReason}
                onChange={(e) => setRejectionReason(e.target.value)}
                placeholder="State the official reason (e.g. Duplicate submission or unauthorized private appliance)..."
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
                  disabled={submittingAction}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-rose-600 text-white hover:bg-rose-700 disabled:opacity-50"
                >
                  Confirm Rejection
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Return for Further Work */}
      {activeModal === 'rework' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#292039]/60 backdrop-blur-xs">
          <div className="bg-[#FFFCF7] w-full max-w-md rounded-3xl border border-[#E8DCCF] shadow-2xl p-6 space-y-4">
            <h3 className="font-serif text-lg font-bold text-[#292039]">Return for Further Work</h3>
            <p className="text-xs text-[#292039]/70">
              Return this complaint to{' '}
              <span className="font-semibold text-[#292039]">{complaint.assignedStaff}</span> for
              rework or additional inspection. Staff will be immediately notified.
            </p>
            <form onSubmit={handleRework} className="space-y-4">
              <textarea
                required
                rows={3}
                value={reworkNote}
                onChange={(e) => setReworkNote(e.target.value)}
                placeholder="State specific deficiency or additional work needed (e.g. Switch repaired but earthing hum persists; inspect wiring joint again)..."
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
                  disabled={submittingAction}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-amber-600 text-white hover:bg-amber-700 disabled:opacity-50"
                >
                  Return for Rework
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Reopen Closed Complaint (D3 / ADR-020) */}
      {activeModal === 'reopen' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#292039]/60 backdrop-blur-xs">
          <div className="bg-[#FFFCF7] w-full max-w-md rounded-3xl border border-[#E8DCCF] shadow-2xl p-6 space-y-4">
            <h3 className="font-serif text-lg font-bold text-[#292039]">Reopen Closed Complaint</h3>
            <p className="text-xs text-[#292039]/70">
              Reopening {complaint.id} transitions it back to <strong>Under Review</strong> so a new
              maintenance assignment can be dispatched. A mandatory reason is required.
            </p>
            <form onSubmit={handleReopen} className="space-y-4">
              <textarea
                required
                rows={3}
                value={reopenReason}
                onChange={(e) => setReopenReason(e.target.value)}
                placeholder="State mandatory reason for reopening (e.g. Issue recurred within 24 hours of closure)..."
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
                  disabled={submittingAction}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-amber-600 text-white hover:bg-amber-700 disabled:opacity-50"
                >
                  Confirm Reopen
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
