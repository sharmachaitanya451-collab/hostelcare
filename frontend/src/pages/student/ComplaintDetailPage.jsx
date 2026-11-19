import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { isComplaintOwnedByStudent, useApp } from '../../context/AppContext'
import { StatusBadge, PriorityBadge } from '../../components/Brand'
import { ComplaintAttachmentsGallery } from '../../components/ComplaintAttachmentsGallery'

export function ComplaintDetailPage() {
  const { id } = useParams()
  const { user, complaints, fetchComplaintDetail, authLoading } = useApp()
  const [loading, setLoading] = useState(true)
  const [forbiddenError, setForbiddenError] = useState(false)
  const [notFoundError, setNotFoundError] = useState(false)
  const [fetchError, setFetchError] = useState(null)
  const [retryKey, setRetryKey] = useState(0)

  const complaint = complaints.find(
    (c) => String(c.id) === String(id) || String(c.referenceNo || '') === String(id),
  )
  const isOwner = complaint ? isComplaintOwnedByStudent(complaint, user) : false
  const userId = user?.id

  useEffect(() => {
    let active = true

    // If authentication session is still resolving or no id, hold off
    if (authLoading || !id) {
      return
    }

    async function loadDetail() {
      setLoading(true)
      setForbiddenError(false)
      setNotFoundError(false)
      setFetchError(null)

      try {
        const loaded = await fetchComplaintDetail(id)
        if (!active) return
        if (!loaded) {
          setNotFoundError(true)
        }
      } catch (err) {
        if (!active) return
        if (err?.status === 403 || err?.code === 'forbidden') {
          setForbiddenError(true)
        } else if (
          err?.status === 404 ||
          err?.code === 'complaint_not_found' ||
          err?.code === 'not_found'
        ) {
          setNotFoundError(true)
        } else {
          setFetchError(
            err?.message ||
              'Failed to load complaint details. Please check your connection and try again.',
          )
        }
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }

    loadDetail()

    return () => {
      active = false
    }
  }, [fetchComplaintDetail, id, userId, authLoading, retryKey])

  if (forbiddenError || (complaint && !isOwner)) {
    return (
      <div className="bg-[#FFFCF7] p-12 rounded-3xl border border-[#E8DCCF] text-center space-y-4 max-w-md mx-auto">
        <div className="w-12 h-12 rounded-full bg-rose-100 text-rose-600 mx-auto flex items-center justify-center font-bold text-lg">
          !
        </div>
        <h3 className="font-serif text-xl font-bold text-[#292039]">Access Restricted</h3>
        <p className="text-xs text-[#292039]/70">
          Maintenance complaints contain residential allotment details and may only be viewed by the
          student resident who filed the request.
        </p>
        <Link
          to="/student/complaints"
          className="inline-block px-4 py-2 rounded-xl bg-[#D94378] text-white text-xs font-semibold"
        >
          Return to My Complaints
        </Link>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="bg-[#FFFCF7] p-12 rounded-3xl border border-[#E8DCCF] text-center text-xs text-[#292039]/60">
        Loading complaint details...
      </div>
    )
  }

  if (notFoundError || (!complaint && !fetchError)) {
    return (
      <div className="bg-[#FFFCF7] p-12 rounded-3xl border border-[#E8DCCF] text-center space-y-4">
        <h3 className="font-serif text-2xl font-bold text-[#292039]">Complaint Not Found</h3>
        <p className="text-xs text-[#292039]/70">No ticket exists matching ID {id}.</p>
        <Link
          to="/student/complaints"
          className="inline-block px-4 py-2 rounded-xl bg-[#D94378] text-white text-xs font-semibold"
        >
          &larr; Return to Complaints
        </Link>
      </div>
    )
  }

  if (fetchError && !complaint) {
    return (
      <div className="bg-[#FFFCF7] p-12 rounded-3xl border border-rose-200 text-center space-y-4 max-w-md mx-auto">
        <div className="w-12 h-12 rounded-full bg-rose-100 text-rose-600 mx-auto flex items-center justify-center font-bold text-lg">
          !
        </div>
        <h3 className="font-serif text-xl font-bold text-[#292039]">Unable to Load Complaint</h3>
        <p className="text-xs text-[#292039]/70">{fetchError}</p>
        <div className="flex items-center justify-center gap-3">
          <button
            onClick={() => setRetryKey((k) => k + 1)}
            className="inline-block px-4 py-2 rounded-xl bg-[#D94378] text-white text-xs font-semibold hover:bg-[#c23667]"
          >
            Try Again
          </button>
          <Link
            to="/student/complaints"
            className="inline-block px-4 py-2 rounded-xl border border-[#E8DCCF] text-[#292039] text-xs font-semibold hover:bg-[#F0E4D4]/30"
          >
            Back to Complaints
          </Link>
        </div>
      </div>
    )
  }

  const reporterName = complaint.studentName || complaint.reporterName || user?.fullName
  const reporterRoll = complaint.studentRoll || complaint.reporterRoll || user?.rollNumber
  const loggedDate = complaint.date || complaint.dateSubmitted

  return (
    <div className="bg-[#FFFCF7] p-6 sm:p-8 rounded-3xl border border-[#E8DCCF] space-y-6 max-w-4xl mx-auto shadow-xs">
      {/* Top Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-[#F0E4D4]">
        <Link
          to="/student/complaints"
          className="text-xs font-semibold text-[#D94378] flex items-center gap-1 hover:underline"
        >
          <span>&larr;</span>
          <span>Back to all complaints</span>
        </Link>
        <div className="flex items-center gap-2.5">
          <span className="text-xs font-mono font-bold text-[#292039]">{complaint.id}</span>
          <StatusBadge status={complaint.status} />
        </div>
      </div>

      {/* Header Info */}
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <PriorityBadge priority={complaint.priority} />
          <span className="text-xs font-semibold text-[#368F83]">{complaint.category}</span>
          <span className="text-xs text-[#292039]/50">
            •{' '}
            {complaint.locationType === 'common_area'
              ? `${complaint.room} (${complaint.block})`
              : `Room ${complaint.room} (${complaint.block})`}
          </span>
        </div>
        <h1 className="font-serif text-2xl sm:text-3xl font-bold text-[#292039]">
          {complaint.title}
        </h1>
        <p className="text-xs text-[#292039]/60">
          Logged on {loggedDate} by {reporterName} ({reporterRoll})
        </p>
      </div>

      {/* Description Box */}
      <div className="space-y-1.5">
        <span className="text-[10px] font-bold uppercase tracking-wider text-[#292039]/70">
          Problem Description (Student Written)
        </span>
        <div className="p-5 rounded-2xl bg-[#FFFDF9] border border-[#E8DCCF] text-xs sm:text-sm text-[#292039] leading-relaxed whitespace-pre-wrap font-sans">
          {complaint.description}
        </div>
      </div>

      {/* Attached Photos */}
      <ComplaintAttachmentsGallery attachments={complaint.attachments} />

      {/* Rejection Notice if rejected */}
      {complaint.status === 'Rejected' && complaint.rejectionReason && (
        <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-900 text-xs space-y-1">
          <div className="font-bold flex items-center gap-1.5 text-rose-800">
            <span>✕</span>
            <span>Warden Rejection Reason:</span>
          </div>
          <p className="leading-relaxed pl-5">{complaint.rejectionReason}</p>
        </div>
      )}

      {/* Completion Summary if completed/closed */}
      {complaint.completionNote && (
        <div className="p-4 rounded-2xl bg-emerald-50/70 border border-emerald-200 text-emerald-950 text-xs space-y-1">
          <div className="font-bold flex items-center gap-1.5 text-emerald-800">
            <span>✓</span>
            <span>Maintenance Completion Summary:</span>
          </div>
          <p className="leading-relaxed pl-5">{complaint.completionNote}</p>
        </div>
      )}

      {/* Assigned Staff & Technician Visibility Box */}
      <div className="p-5 rounded-2xl border border-[#E8DCCF] bg-[#F7EFE6] space-y-3">
        <div className="flex items-center justify-between pb-2 border-b border-[#E8DCCF]">
          <h4 className="font-serif text-sm font-bold text-[#292039]">
            Assigned Duty Staff &amp; Progress
          </h4>
          <span className="text-[11px] font-mono text-[#368F83] font-semibold">
            Status: {complaint.status}
          </span>
        </div>

        {complaint.assignedStaff && complaint.assignedStaff !== 'Unassigned' ? (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
            <div>
              <span className="text-[10px] text-[#292039]/60 uppercase tracking-wider block">
                Technician Name
              </span>
              <p className="font-bold text-[#292039] text-sm mt-0.5">{complaint.assignedStaff}</p>
              <span className="text-[11px] text-[#368F83] font-medium block">
                {complaint.assignedStaffRole || 'Duty Maintenance Staff'}
              </span>
            </div>

            <div>
              <span className="text-[10px] text-[#292039]/60 uppercase tracking-wider block">
                Contact Details
              </span>
              <p className="font-semibold text-[#292039] mt-0.5">
                {complaint.assignedStaffContact || '+91 94421 88901'}
              </p>
              <span className="text-[10px] text-[#292039]/60 block">Hostel Maintenance Cell</span>
            </div>

            <div>
              <span className="text-[10px] text-[#292039]/60 uppercase tracking-wider block">
                Assignment Time
              </span>
              <p className="font-medium text-[#292039] mt-0.5">
                {complaint.assignedDate || 'Scheduled'}
              </p>
            </div>
          </div>
        ) : (
          <div className="text-xs text-[#292039]/70 py-2">
            <span className="font-semibold text-amber-800">Pending Staff Assignment:</span> The
            warden desk has logged your request and will allocate the duty electrician, plumber, or
            carpenter during the next shift roster.
          </div>
        )}
      </div>

      {/* Student-Visible Staff Progress Updates */}
      {Array.isArray(complaint.updates) && complaint.updates.length > 0 && (
        <div className="space-y-3 pt-2 border-t border-[#F0E4D4]">
          <h4 className="font-serif text-base font-bold text-[#292039]">
            Technician Progress Updates
          </h4>
          <div className="space-y-2.5">
            {complaint.updates.map((upd, idx) => (
              <div
                key={upd.id || idx}
                className="p-3.5 rounded-xl bg-teal-50/50 border border-teal-200/80 text-xs space-y-1"
              >
                <div className="flex items-center justify-between">
                  <span className="font-bold text-[#246A60]">
                    {upd.authorName} ({upd.authorRole})
                  </span>
                  <span className="text-[11px] font-mono text-[#292039]/60">{upd.time}</span>
                </div>
                <p className="text-[#292039]/90 leading-relaxed">{upd.body}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* History Timeline */}
      <div className="space-y-3 pt-2 border-t border-[#F0E4D4]">
        <h4 className="font-serif text-base font-bold text-[#292039]">
          Official Complaint History &amp; Audit Trail
        </h4>
        <div className="space-y-2.5">
          {complaint.history?.map((h, i) => (
            <div
              key={h.id || i}
              className="flex items-start gap-3 text-xs bg-[#FFFDF9] p-3.5 rounded-xl border border-[#E8DCCF]"
            >
              <div className="w-2 h-2 rounded-full bg-[#D94378] mt-1.5 shrink-0" />
              <div className="flex-1 space-y-0.5">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-[#292039]">{h.action}</span>
                  <span className="text-[11px] text-[#292039]/50 font-mono">
                    {h.timestamp || h.time}
                  </span>
                </div>
                <p className="text-[#292039]/80 mt-0.5 leading-relaxed">{h.note}</p>
                <span className="text-[10px] text-[#292039]/60 block pt-0.5">
                  Actor: <em>{h.actor || h.by}</em>
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
