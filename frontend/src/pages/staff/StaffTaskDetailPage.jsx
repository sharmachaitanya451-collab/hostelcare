import { useEffect, useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useApp } from '../../context/AppContext'
import { StatusBadge, PriorityBadge } from '../../components/Brand'
import { ComplaintAttachmentsGallery } from '../../components/ComplaintAttachmentsGallery'

export function StaffTaskDetailPage() {
  const { id } = useParams()
  const {
    user,
    complaints,
    fetchComplaintDetail,
    acceptTask,
    startTaskWork,
    updateTaskProgress,
    completeTaskWork,
  } = useApp()
  const navigate = useNavigate()

  const task = complaints.find((c) => c.id === id)
  const [loading, setLoading] = useState(!task && Boolean(id && fetchComplaintDetail))
  const [accessDenied, setAccessDenied] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [actionError, setActionError] = useState('')

  // Modals for actions
  const [activeModal, setActiveModal] = useState(null) // null | 'start' | 'progress' | 'complete'
  const [progressNote, setProgressNote] = useState('')
  const [completionNote, setCompletionNote] = useState('')
  const [feedbackNotice, setFeedbackNotice] = useState(null)

  useEffect(() => {
    let active = true
    if (id && fetchComplaintDetail) {
      fetchComplaintDetail(id)
        .then((res) => {
          if (!active) return
          if (res?.status === 403) {
            setAccessDenied(true)
          }
        })
        .catch(() => {})
        .finally(() => {
          if (active) setLoading(false)
        })
    }
    return () => {
      active = false
    }
  }, [id, fetchComplaintDetail])

  if (loading && !task) {
    return (
      <div className="bg-[#FFFCF7] p-8 sm:p-12 rounded-3xl border border-[#E8DCCF] text-center space-y-3 max-w-2xl mx-auto">
        <p className="text-xs font-semibold text-[#292039]/70">Loading work order {id}...</p>
      </div>
    )
  }

  if (accessDenied) {
    return (
      <div className="bg-[#FFFCF7] p-8 sm:p-12 rounded-3xl border border-rose-200 text-center space-y-4 max-w-2xl mx-auto shadow-sm">
        <div className="w-16 h-16 rounded-full bg-rose-100 text-rose-700 flex items-center justify-center text-3xl mx-auto font-bold">
          🚫
        </div>
        <h3 className="font-serif text-2xl font-bold text-[#292039]">Access Restricted</h3>
        <p className="text-xs text-[#292039]/80 max-w-md mx-auto leading-relaxed">
          You are only authorized to view work orders assigned specifically to your duty profile (
          <span className="font-semibold text-[#292039]">{user?.name || user?.fullName}</span>).
        </p>
        <div className="pt-2">
          <Link
            to="/staff/tasks"
            className="inline-block px-5 py-2.5 rounded-xl bg-[#292039] text-[#FFFCF7] text-xs font-semibold hover:bg-[#3D3252] transition-colors"
          >
            &larr; Return to Assigned Tasks
          </Link>
        </div>
      </div>
    )
  }

  if (!task) {
    return (
      <div className="bg-[#FFFCF7] p-8 sm:p-12 rounded-3xl border border-[#E8DCCF] text-center space-y-4 max-w-2xl mx-auto">
        <div className="w-16 h-16 rounded-full bg-rose-50 text-rose-600 flex items-center justify-center text-2xl mx-auto">
          ⚠️
        </div>
        <h3 className="font-serif text-2xl font-bold text-[#292039]">Work Order Not Found</h3>
        <p className="text-xs text-[#292039]/70">No task exists with identifier {id}.</p>
        <button
          onClick={() => navigate('/staff/tasks')}
          className="inline-block px-4 py-2 rounded-xl bg-[#292039] text-[#FFFCF7] text-xs font-semibold hover:bg-[#3D3252]"
        >
          Return to My Tasks &rarr;
        </button>
      </div>
    )
  }

  // Isolation check: Staff can access only their own assigned tasks
  const staffDisplayName = user?.name || user?.fullName || ''
  const isAssignedToCurrentUser =
    (task.assignedStaffId && user?.id && task.assignedStaffId === user.id) ||
    (staffDisplayName &&
      task.assignedStaff &&
      (task.assignedStaff === staffDisplayName ||
        task.assignedStaff.includes(staffDisplayName) ||
        staffDisplayName.includes(task.assignedStaff)))

  if (!isAssignedToCurrentUser) {
    return (
      <div className="bg-[#FFFCF7] p-8 sm:p-12 rounded-3xl border border-rose-200 text-center space-y-4 max-w-2xl mx-auto shadow-sm">
        <div className="w-16 h-16 rounded-full bg-rose-100 text-rose-700 flex items-center justify-center text-3xl mx-auto font-bold">
          🚫
        </div>
        <h3 className="font-serif text-2xl font-bold text-[#292039]">Access Restricted</h3>
        <p className="text-xs text-[#292039]/80 max-w-md mx-auto leading-relaxed">
          You are only authorized to view work orders assigned specifically to your duty profile (
          <span className="font-semibold text-[#292039]">{staffDisplayName}</span>). Work order{' '}
          {task.id} is assigned to{' '}
          <span className="font-semibold">{task.assignedStaff || 'Unassigned'}</span>.
        </p>
        <div className="pt-2">
          <Link
            to="/staff/tasks"
            className="inline-block px-5 py-2.5 rounded-xl bg-[#292039] text-[#FFFCF7] text-xs font-semibold hover:bg-[#3D3252] transition-colors"
          >
            &larr; Return to Assigned Tasks
          </Link>
        </div>
      </div>
    )
  }

  const handleAccept = async () => {
    setSubmitting(true)
    setActionError('')
    try {
      await acceptTask(task.id)
      setFeedbackNotice('Assignment accepted. Work scheduled for on-site dispatch.')
    } catch (err) {
      setActionError(err.message || 'Unable to accept assignment.')
    } finally {
      setSubmitting(false)
    }
  }

  const handleStartWork = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setActionError('')
    try {
      await startTaskWork(task.id, { note: progressNote.trim() })
      setActiveModal(null)
      setProgressNote('')
      setFeedbackNotice('Work status updated to In Progress. Student and warden notified.')
    } catch (err) {
      setActionError(err.message || 'Unable to start work.')
    } finally {
      setSubmitting(false)
    }
  }

  const handleUpdateProgress = async (e) => {
    e.preventDefault()
    if (!progressNote.trim()) return
    setSubmitting(true)
    setActionError('')
    try {
      await updateTaskProgress(task.id, { note: progressNote.trim() })
      setActiveModal(null)
      setProgressNote('')
      setFeedbackNotice('Progress update recorded in ticket history.')
    } catch (err) {
      setActionError(err.message || 'Unable to post progress update.')
    } finally {
      setSubmitting(false)
    }
  }

  const handleCompleteWork = async (e) => {
    e.preventDefault()
    if (!completionNote.trim()) return
    setSubmitting(true)
    setActionError('')
    try {
      await completeTaskWork(task.id, { completionNote: completionNote.trim() })
      setActiveModal(null)
      setCompletionNote('')
      setFeedbackNotice('Task marked as Completed! Ticket forwarded to Chief Warden for closure.')
    } catch (err) {
      setActionError(err.message || 'Unable to mark task completed.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Header with navigation */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#F0E4D4]">
        <div className="space-y-1">
          <Link
            to="/staff/tasks"
            className="text-xs font-semibold text-[#D94378] flex items-center gap-1 hover:underline"
          >
            <span>&larr;</span>
            <span>Back to duty roster &amp; tasks</span>
          </Link>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="font-serif text-2xl sm:text-3xl font-bold text-[#292039]">
              Work Order {task.id}
            </h1>
            <StatusBadge status={task.status} />
            <PriorityBadge priority={task.priority} />
          </div>
        </div>

        {/* Quick status summary chip */}
        <div className="text-right sm:text-right text-xs text-[#292039]/70 bg-white/70 px-3 py-1.5 rounded-xl border border-[#E8DCCF]">
          <span className="block font-semibold text-[#292039]">Room {task.room}</span>
          <span className="text-[11px] text-[#292039]/60">{task.block || 'Main Wing'}</span>
        </div>
      </div>

      {feedbackNotice && (
        <div className="p-4 rounded-2xl bg-emerald-50 border border-emerald-300 text-emerald-900 text-xs flex items-center justify-between shadow-xs">
          <span className="flex items-center gap-2">
            <span className="font-bold">✓</span>
            <span>{feedbackNotice}</span>
          </span>
          <button
            onClick={() => setFeedbackNotice(null)}
            className="font-bold text-emerald-800 hover:text-emerald-950 cursor-pointer"
          >
            ✕
          </button>
        </div>
      )}

      {actionError && (
        <div className="p-4 rounded-2xl bg-rose-50 border border-rose-300 text-rose-900 text-xs flex items-center justify-between shadow-xs">
          <span>{actionError}</span>
          <button
            onClick={() => setActionError('')}
            className="font-bold text-rose-800 hover:text-rose-950 cursor-pointer"
          >
            ✕
          </button>
        </div>
      )}

      {/* Rework Banner if returned by warden */}
      {task.reworkNote && (task.status === 'In Progress' || task.status === 'Accepted') && (
        <div className="p-4 sm:p-5 rounded-2xl bg-amber-50 border-2 border-amber-400 text-amber-900 text-xs space-y-1.5 shadow-sm">
          <div className="flex items-center gap-2 font-bold uppercase tracking-wider text-[11px] text-amber-950">
            <span className="text-base">⚠️</span>
            <span>Warden Instructions: Further Work Required</span>
          </div>
          <p className="text-sm font-medium text-[#292039] pl-6 bg-white/60 p-2.5 rounded-xl border border-amber-200">
            &quot;{task.reworkNote}&quot;
          </p>
          <p className="text-[11px] text-amber-800/80 pl-6">
            Please re-inspect the issue, address the warden&apos;s remarks above, and post a new
            progress or completion update.
          </p>
        </div>
      )}

      {/* Interactive Action Control Panel */}
      <div className="bg-[#FFFCF7] p-5 sm:p-6 rounded-3xl border border-[#E8DCCF] shadow-sm space-y-4">
        <h2 className="text-xs font-bold uppercase tracking-wider text-[#292039]/60">
          Action Control Panel
        </h2>

        {/* Action button states based on task lifecycle */}
        {task.status === 'Assigned' && (
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-2xl bg-[#FFF8EE] border border-[#F4AA35]/40">
            <div className="space-y-1">
              <span className="text-sm font-bold text-[#292039] block">
                Awaiting Assignment Acceptance
              </span>
              <p className="text-xs text-[#292039]/70">
                Confirm receipt of this work order to notify the student and warden that you have
                taken ownership.
              </p>
            </div>
            <button
              type="button"
              disabled={submitting}
              onClick={handleAccept}
              className="px-6 py-3 rounded-2xl bg-[#368F83] text-white text-sm font-bold hover:bg-[#2B7369] transition-all shadow-sm active:scale-98 cursor-pointer shrink-0 disabled:opacity-60"
            >
              {submitting ? 'Accepting...' : '✓ Accept Assignment'}
            </button>
          </div>
        )}

        {task.status === 'Accepted' && (
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-2xl bg-[#F0FDF4] border border-emerald-300">
            <div className="space-y-1">
              <span className="text-sm font-bold text-emerald-950 block">Assignment Accepted</span>
              <p className="text-xs text-emerald-900/80">
                When you arrive at Room {task.room} and begin diagnostic or repair operations, click
                Start Work.
              </p>
            </div>
            <button
              type="button"
              onClick={() => {
                setActiveModal('start')
                setProgressNote('')
              }}
              className="px-6 py-3 rounded-2xl bg-[#D94378] text-white text-sm font-bold hover:bg-[#B83262] transition-all shadow-sm active:scale-98 cursor-pointer shrink-0"
            >
              🛠️ Start Work
            </button>
          </div>
        )}

        {task.status === 'In Progress' && (
          <div className="p-4 rounded-2xl bg-[#F5F2EC] border border-[#D8CEBE] space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <span className="text-sm font-bold text-[#292039] block">
                  Repair Work In Progress
                </span>
                <p className="text-xs text-[#292039]/70">
                  Update your ongoing progress or submit final completion notes once resolved.
                </p>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-3 pt-2">
              <button
                type="button"
                onClick={() => {
                  setActiveModal('progress')
                  setProgressNote('')
                }}
                className="px-5 py-2.5 rounded-xl border border-[#292039]/30 bg-white text-[#292039] text-xs font-bold hover:bg-[#E8DCCF]/40 transition-colors cursor-pointer"
              >
                📝 Post Progress Update
              </button>
              <button
                type="button"
                onClick={() => {
                  setActiveModal('complete')
                  setCompletionNote('')
                }}
                className="px-6 py-2.5 rounded-xl bg-emerald-600 text-white text-xs font-bold hover:bg-emerald-700 transition-colors shadow-xs active:scale-98 cursor-pointer"
              >
                ✓ Mark Work Completed
              </button>
            </div>
          </div>
        )}

        {task.status === 'Completed' && (
          <div className="p-4 rounded-2xl bg-emerald-50 border border-emerald-300 space-y-2">
            <div className="flex items-center gap-2">
              <span className="text-emerald-700 font-bold text-sm">✓ Work Marked Completed</span>
              <span className="text-[11px] text-emerald-800 bg-emerald-100 px-2.5 py-0.5 rounded-full font-semibold">
                Pending Warden Verification
              </span>
            </div>
            <p className="text-xs text-emerald-900/80">
              Your completion report has been submitted. The Chief Warden office will review the
              repairs and confirm final ticket closure.
            </p>
            {task.completionNote && (
              <div className="mt-2 text-xs bg-white/80 p-3 rounded-xl border border-emerald-200 text-[#292039]">
                <span className="font-bold block text-[11px] text-[#292039]/60 uppercase">
                  Your Completion Report:
                </span>
                <p className="mt-1 italic">{task.completionNote}</p>
              </div>
            )}
          </div>
        )}

        {(task.status === 'Resolved' || task.status === 'Closed') && (
          <div className="p-4 rounded-2xl bg-emerald-50 border border-emerald-300 space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-emerald-800 font-bold text-sm">
                🔒 Task Verified &amp; {task.status}
              </span>
            </div>
            <p className="text-xs text-emerald-900/80">
              This work order has been fully inspected and officially concluded. No further action
              is required.
            </p>
          </div>
        )}
      </div>

      {/* Work Order Particulars */}
      <div className="bg-[#FFFCF7] p-6 sm:p-8 rounded-3xl border border-[#E8DCCF] shadow-xs space-y-6">
        {/* Core meta grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 pb-6 border-b border-[#E8DCCF]">
          <div>
            <span className="text-[10px] text-[#292039]/60 uppercase tracking-wider block font-semibold">
              Location / Room
            </span>
            <span className="text-sm font-bold text-[#292039]">Room {task.room}</span>
            <span className="text-xs text-[#292039]/70 block">{task.block || 'Hostel Campus'}</span>
          </div>

          <div>
            <span className="text-[10px] text-[#292039]/60 uppercase tracking-wider block font-semibold">
              Resident Contact
            </span>
            <span className="text-sm font-bold text-[#292039]">{task.reporterName}</span>
            <span className="text-xs text-[#292039]/70 block font-mono">
              Roll: {task.reporterRoll}
            </span>
          </div>

          <div>
            <span className="text-[10px] text-[#292039]/60 uppercase tracking-wider block font-semibold">
              Service Category
            </span>
            <span className="text-sm font-bold text-[#292039]">{task.category}</span>
            <span className="text-xs text-[#292039]/70 block">Trade: {user?.trade || 'Duty'}</span>
          </div>

          <div>
            <span className="text-[10px] text-[#292039]/60 uppercase tracking-wider block font-semibold">
              Assigned Date
            </span>
            <span className="text-sm font-bold text-[#292039]">
              {task.assignedDate || task.dateSubmitted}
            </span>
            <span className="text-xs text-[#292039]/70 block">
              By: {task.assignedBy || 'Warden'}
            </span>
          </div>
        </div>

        {/* Complaint Title & Unrestricted Problem Description */}
        <div className="space-y-2">
          <span className="text-[10px] text-[#292039]/60 uppercase tracking-wider block font-semibold">
            Student Problem Description
          </span>
          <h2 className="text-lg font-serif font-bold text-[#292039]">{task.title}</h2>
          <div className="bg-[#FFFDF9] p-4 rounded-2xl border border-[#F0E4D4] text-xs text-[#292039] whitespace-pre-wrap leading-relaxed">
            {task.description}
          </div>
        </div>

        {/* Attached Photos */}
        <ComplaintAttachmentsGallery attachments={task.attachments} />

        {/* Warden Assignment Instructions */}
        {task.assignmentNotes && (
          <div className="space-y-1.5 p-4 rounded-2xl bg-amber-50/60 border border-amber-200">
            <span className="text-[10px] text-amber-900 uppercase tracking-wider font-bold block flex items-center gap-1.5">
              <span>📋</span>
              <span>Warden Dispatch Instructions</span>
            </span>
            <p className="text-xs text-[#292039] leading-relaxed italic">{task.assignmentNotes}</p>
          </div>
        )}
      </div>

      {/* Chronological Lifecycle History Audit */}
      <div className="bg-[#FFFCF7] p-6 sm:p-8 rounded-3xl border border-[#E8DCCF] shadow-xs space-y-6">
        <div className="flex items-center justify-between pb-3 border-b border-[#E8DCCF]">
          <div>
            <h3 className="font-serif text-lg font-bold text-[#292039]">
              Work Order Audit History
            </h3>
            <p className="text-xs text-[#292039]/60">
              Chronological log of staff actions and status changes
            </p>
          </div>
          <span className="text-xs font-mono font-bold bg-[#E8DCCF]/50 text-[#292039] px-2.5 py-1 rounded-lg">
            {task.history ? task.history.length : 0} events
          </span>
        </div>

        <div className="relative pl-6 space-y-6 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-[#E8DCCF]">
          {task.history && task.history.length > 0 ? (
            task.history.map((event, idx) => (
              <div key={idx} className="relative group">
                {/* Timeline node */}
                <div className="absolute -left-6 top-1 w-2.5 h-2.5 rounded-full bg-[#D94378] ring-4 ring-[#FFFCF7]" />
                <div className="bg-[#FFFDF9] p-4 rounded-2xl border border-[#F0E4D4] space-y-1 text-xs">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-bold text-[#292039]">{event.action}</span>
                    <span className="text-[11px] text-[#292039]/60 font-mono">
                      {event.timestamp}
                    </span>
                  </div>
                  <div className="text-[11px] text-[#292039]/70">
                    By <span className="font-medium text-[#292039]">{event.actor}</span>
                  </div>
                  {event.note && (
                    <p className="pt-1.5 text-xs text-[#292039]/90 border-t border-[#F0E4D4]/60 mt-1 italic">
                      &quot;{event.note}&quot;
                    </p>
                  )}
                </div>
              </div>
            ))
          ) : (
            <p className="text-xs text-[#292039]/60">No history events recorded.</p>
          )}
        </div>
      </div>

      {/* Modal: Start Work with Note */}
      {activeModal === 'start' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#292039]/60 backdrop-blur-xs">
          <div className="bg-[#FFFCF7] w-full max-w-md rounded-3xl border border-[#E8DCCF] shadow-2xl p-6 space-y-4">
            <h3 className="font-serif text-lg font-bold text-[#292039]">Start Maintenance Work</h3>
            <p className="text-xs text-[#292039]/70">
              Confirm that you are on-site at Room {task.room} and initiating repairs.
            </p>
            <form onSubmit={handleStartWork} className="space-y-4">
              <div>
                <label className="block text-[11px] font-bold text-[#292039] uppercase tracking-wider mb-1">
                  On-site Initial Note (Optional)
                </label>
                <textarea
                  rows={3}
                  value={progressNote}
                  onChange={(e) => setProgressNote(e.target.value)}
                  placeholder="e.g. Arrived on-site. Inspected main switchboard and isolated faulty circuit..."
                  className="w-full px-3 py-2 rounded-xl border border-[#D8CEBE] text-xs focus:outline-none focus:border-[#D94378]"
                />
              </div>
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setActiveModal(null)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-[#E8DCCF] text-[#292039] hover:bg-[#D8CEBE]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-xl text-xs font-semibold bg-[#D94378] text-white hover:bg-[#B83262]"
                >
                  Confirm &amp; Start Work
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Progress Update */}
      {activeModal === 'progress' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#292039]/60 backdrop-blur-xs">
          <div className="bg-[#FFFCF7] w-full max-w-md rounded-3xl border border-[#E8DCCF] shadow-2xl p-6 space-y-4">
            <h3 className="font-serif text-lg font-bold text-[#292039]">Record Progress Update</h3>
            <p className="text-xs text-[#292039]/70">
              Provide an update on the status of parts, diagnosis, or timeline.
            </p>
            <form onSubmit={handleUpdateProgress} className="space-y-4">
              <div>
                <label className="block text-[11px] font-bold text-[#292039] uppercase tracking-wider mb-1">
                  Progress Note <span className="text-rose-600">*</span>
                </label>
                <textarea
                  required
                  rows={3}
                  value={progressNote}
                  onChange={(e) => setProgressNote(e.target.value)}
                  placeholder="e.g. Capacitor replaced; testing motor speed for next 15 minutes..."
                  className="w-full px-3 py-2 rounded-xl border border-[#D8CEBE] text-xs focus:outline-none focus:border-[#D94378]"
                />
              </div>
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setActiveModal(null)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-[#E8DCCF] text-[#292039] hover:bg-[#D8CEBE]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-xl text-xs font-semibold bg-[#292039] text-[#FFFCF7] hover:bg-[#3D3252]"
                >
                  Save Update
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Mark Work Completed (Mandatory Completion Note) */}
      {activeModal === 'complete' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#292039]/60 backdrop-blur-xs">
          <div className="bg-[#FFFCF7] w-full max-w-md rounded-3xl border border-[#E8DCCF] shadow-2xl p-6 space-y-4">
            <h3 className="font-serif text-lg font-bold text-[#292039]">Mark Work Completed</h3>
            <p className="text-xs text-[#292039]/70">
              A written completion report is{' '}
              <span className="font-bold text-[#292039]">mandatory</span>. Describe the exact repair
              or replacement completed for warden verification.
            </p>
            <form onSubmit={handleCompleteWork} className="space-y-4">
              <div>
                <label className="block text-[11px] font-bold text-[#292039] uppercase tracking-wider mb-1">
                  Completion Note &amp; Summary <span className="text-rose-600">*</span>
                </label>
                <textarea
                  required
                  rows={4}
                  value={completionNote}
                  onChange={(e) => setCompletionNote(e.target.value)}
                  placeholder="e.g. Replaced faulty 10A switchboard modular socket. Restored power and verified voltage with multimeter. Student verified normal operation."
                  className="w-full px-3 py-2 rounded-xl border border-[#D8CEBE] text-xs focus:outline-none focus:border-[#D94378]"
                />
              </div>
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setActiveModal(null)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-[#E8DCCF] text-[#292039] hover:bg-[#D8CEBE]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-xl text-xs font-semibold bg-emerald-600 text-white hover:bg-emerald-700"
                >
                  Confirm Completion
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
