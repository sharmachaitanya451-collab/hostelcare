import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useApp } from '../../context/AppContext'
import { StatusBadge, PriorityBadge } from '../../components/Brand'
import { AdminComplaintAnalytics } from '../../components/AdminComplaintAnalytics'

const PRESET_OPTIONS = [
  { id: '7d', label: 'Last 7 Days' },
  { id: '30d', label: 'Last 30 Days' },
  { id: 'this_month', label: 'This Month' },
  { id: 'custom', label: 'Custom Range' },
]

function formatInr(value) {
  const num = Number(value ?? 0)
  const safeNum = Number.isFinite(num) ? num : 0
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(safeNum)
}

function formatDisplayDate(isoDate) {
  if (!isoDate) return ''
  const parsed = new Date(`${isoDate}T00:00:00`)
  if (Number.isNaN(parsed.getTime())) return isoDate
  return parsed.toLocaleDateString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

export function AdminOverviewPage() {
  const {
    adminOverview,
    adminOverviewLoading,
    adminOverviewError,
    fetchAdminOverview,
    complaintAnalytics,
    complaintAnalyticsLoading,
    complaintAnalyticsError,
    fetchComplaintAnalytics,
  } = useApp()
  const navigate = useNavigate()

  const [preset, setPreset] = useState('30d')
  const [draftFrom, setDraftFrom] = useState('')
  const [draftTo, setDraftTo] = useState('')
  const [appliedRange, setAppliedRange] = useState({ preset: '30d', dateFrom: '', dateTo: '' })
  const [customValidationError, setCustomValidationError] = useState('')

  const loadOverview = useCallback(
    (range) => {
      const params = { preset: range.preset }
      if (range.preset === 'custom') {
        params.dateFrom = range.dateFrom
        params.dateTo = range.dateTo
      }
      fetchAdminOverview(params).catch(() => {})
      fetchComplaintAnalytics(params).catch(() => {})
    },
    [fetchAdminOverview, fetchComplaintAnalytics],
  )

  useEffect(() => {
    loadOverview(appliedRange)
  }, [appliedRange, loadOverview])

  const handleSelectPreset = (nextPreset) => {
    setPreset(nextPreset)
    setCustomValidationError('')
    if (nextPreset === 'custom') {
      if (!draftFrom && adminOverview?.dateRange?.dateFrom) {
        setDraftFrom(adminOverview.dateRange.dateFrom)
      }
      if (!draftTo && adminOverview?.dateRange?.dateTo) {
        setDraftTo(adminOverview.dateRange.dateTo)
      }
      return
    }
    setAppliedRange({ preset: nextPreset, dateFrom: '', dateTo: '' })
  }

  const handleApplyCustomRange = (e) => {
    e.preventDefault()
    if (!draftFrom || !draftTo) {
      setCustomValidationError('Please select both start and end dates.')
      return
    }
    if (draftFrom > draftTo) {
      setCustomValidationError('Start date cannot be after end date.')
      return
    }
    const startMs = new Date(`${draftFrom}T00:00:00Z`).getTime()
    const endMs = new Date(`${draftTo}T00:00:00Z`).getTime()
    const spanDays = Math.floor((endMs - startMs) / (1000 * 60 * 60 * 24)) + 1
    if (spanDays > 365) {
      setCustomValidationError('Custom date range cannot exceed 365 days.')
      return
    }
    setCustomValidationError('')
    setAppliedRange({ preset: 'custom', dateFrom: draftFrom, dateTo: draftTo })
  }

  const handleRetry = () => {
    loadOverview(appliedRange)
  }

  const complaints = adminOverview?.complaints
  const approvals = adminOverview?.approvals
  const occupancy = adminOverview?.occupancy
  const residents = adminOverview?.residents
  const finances = adminOverview?.finances
  const recentActivity = Array.isArray(adminOverview?.recentActivity)
    ? adminOverview.recentActivity
    : []
  const dateRange = adminOverview?.dateRange

  return (
    <div className="space-y-8">
      {/* Section A — Dashboard Header & Date Filter Bar */}
      <div className="flex flex-col xl:flex-row xl:items-end justify-between gap-4">
        <div>
          <span className="text-[11px] font-bold text-[#D94378] uppercase tracking-wider">
            HostelCare Administrative Intelligence
          </span>
          <h1 className="font-serif text-3xl font-bold text-[#292039]">
            Hostel Operations &amp; Maintenance Dashboard
          </h1>
          <p className="text-xs text-[#292039]/70 mt-1">
            Real-time snapshot of resident admissions, active maintenance queue, room occupancy, and
            verified fine collections.
          </p>
        </div>

        <div className="flex flex-col items-start xl:items-end gap-2">
          <div
            className="inline-flex flex-wrap items-center gap-1.5 bg-[#FFFCF7] p-1.5 rounded-2xl border border-[#E8DCCF] shadow-xs"
            role="group"
            aria-label="Dashboard Date Range"
          >
            {PRESET_OPTIONS.map((opt) => {
              const active = preset === opt.id
              return (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => handleSelectPreset(opt.id)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-colors cursor-pointer ${
                    active
                      ? 'bg-[#292039] text-[#FFFCF7]'
                      : 'text-[#292039]/75 hover:bg-[#F7EFE6] hover:text-[#292039]'
                  }`}
                >
                  {opt.label}
                </button>
              )
            })}
          </div>

          {preset === 'custom' && (
            <form
              onSubmit={handleApplyCustomRange}
              className="flex flex-wrap items-center gap-2 bg-[#FFFCF7] px-3 py-2 rounded-2xl border border-[#E8DCCF] shadow-xs"
            >
              <label className="text-[11px] font-semibold text-[#292039]/70 flex items-center gap-1.5">
                <span>From</span>
                <input
                  type="date"
                  aria-label="Date From"
                  value={draftFrom}
                  onChange={(e) => setDraftFrom(e.target.value)}
                  className="px-2 py-1 rounded-lg border border-[#E8DCCF] bg-white text-xs text-[#292039]"
                />
              </label>
              <label className="text-[11px] font-semibold text-[#292039]/70 flex items-center gap-1.5">
                <span>To</span>
                <input
                  type="date"
                  aria-label="Date To"
                  value={draftTo}
                  onChange={(e) => setDraftTo(e.target.value)}
                  className="px-2 py-1 rounded-lg border border-[#E8DCCF] bg-white text-xs text-[#292039]"
                />
              </label>
              <button
                type="submit"
                disabled={adminOverviewLoading}
                className="px-3 py-1.5 rounded-xl bg-[#D94378] text-white text-xs font-semibold hover:bg-[#C33668] transition-colors cursor-pointer disabled:opacity-60"
              >
                Apply
              </button>
            </form>
          )}

          {customValidationError && (
            <p role="alert" className="text-xs font-semibold text-rose-700">
              {customValidationError}
            </p>
          )}

          <div className="flex items-center gap-2 text-[11px] text-[#292039]/65">
            {dateRange?.dateFrom && dateRange?.dateTo && (
              <span>
                Window: <strong className="text-[#292039]">{formatDisplayDate(dateRange.dateFrom)}</strong>{' '}
                &ndash; <strong className="text-[#292039]">{formatDisplayDate(dateRange.dateTo)}</strong>{' '}
                (IST)
              </span>
            )}
            {adminOverviewLoading && adminOverview && (
              <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 font-semibold">
                Refreshing...
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Section F — API Error State */}
      {adminOverviewError && (
        <div
          role="alert"
          className="p-4 rounded-2xl bg-rose-50 border border-rose-300 text-rose-900 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3"
        >
          <div>
            <p className="font-bold">Unable to load administrative analytics</p>
            <p className="mt-0.5 text-rose-800">{adminOverviewError}</p>
          </div>
          <button
            type="button"
            onClick={handleRetry}
            className="px-3.5 py-1.5 rounded-xl bg-rose-700 text-white font-semibold text-xs hover:bg-rose-800 transition-colors cursor-pointer self-start sm:self-auto shrink-0"
          >
            Retry
          </button>
        </div>
      )}

      {/* Section F — Initial Loading State */}
      {adminOverviewLoading && !adminOverview && (
        <div className="p-10 rounded-3xl bg-[#FFFCF7] border border-[#E8DCCF] text-center space-y-2 shadow-xs">
          <p className="text-sm font-semibold text-[#292039]">
            Loading hostel administrative analytics...
          </p>
          <p className="text-xs text-[#292039]/65">
            Aggregating complaints, occupancy, admissions, and verified collections from PostgreSQL.
          </p>
        </div>
      )}

      {/* Render Dashboard Content ONLY when authoritative backend payload is loaded */}
      {adminOverview && complaints && approvals && occupancy && finances && (
        <>
          {/* Quick Action Alert: Pending Approvals */}
          {approvals.pendingCount > 0 && (
            <div className="p-5 rounded-3xl bg-amber-50/90 border border-amber-300 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-xs">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-amber-500 animate-pulse" />
                  <h3 className="text-sm font-bold text-amber-900">
                    {approvals.pendingCount} Student Registration(s) Awaiting Warden Verification
                  </h3>
                </div>
                <p className="text-xs text-amber-800">
                  Verify applicant roll numbers and identity before activating room allotment keys.
                </p>
              </div>
              <Link
                to="/admin/approvals"
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-[#292039] text-white hover:bg-[#3D3252] transition-colors shrink-0"
              >
                Review Approvals &rarr;
              </Link>
            </div>
          )}

          {/* Section B — Primary Complaint & Admission KPI Cards */}
          <div className="space-y-3">
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3.5">
              <Link
                to="/admin/complaints"
                aria-label={`View all ${complaints.total} complaints in Complaint Queue`}
                className="bg-[#FFFCF7] p-4 rounded-2xl border border-[#E8DCCF] shadow-xs hover:border-[#D94378]/50 hover:shadow-sm transition-all cursor-pointer block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#D94378] focus-visible:ring-offset-2 focus-visible:ring-offset-[#FBF7F0]"
              >
                <span className="text-[10px] text-[#292039]/60 uppercase tracking-wider block font-semibold">
                  Total Complaints
                </span>
                <div className="font-serif text-2xl font-bold text-[#292039] mt-1">
                  {complaints.total}
                </div>
                <span className="text-[10px] text-[#292039]/60">in selected period</span>
              </Link>

              <Link
                to="/admin/complaints?status=submitted"
                aria-label={`View ${complaints.newSubmissions} submitted complaints in Complaint Queue`}
                className="bg-[#FFFCF7] p-4 rounded-2xl border border-[#E8DCCF] shadow-xs hover:border-[#D94378]/50 hover:shadow-sm transition-all cursor-pointer block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#D94378] focus-visible:ring-offset-2 focus-visible:ring-offset-[#FBF7F0]"
              >
                <span className="text-[10px] text-amber-700 uppercase tracking-wider block font-semibold">
                  New Submissions
                </span>
                <div className="font-serif text-2xl font-bold text-amber-600 mt-1">
                  {complaints.newSubmissions}
                </div>
                <span className="text-[10px] text-amber-800">awaiting review</span>
              </Link>

              <Link
                to="/admin/complaints?staff=unassigned"
                aria-label={`View ${complaints.unassigned} unassigned complaints in Complaint Queue`}
                className="bg-[#FFFCF7] p-4 rounded-2xl border border-[#E8DCCF] shadow-xs hover:border-[#D94378]/50 hover:shadow-sm transition-all cursor-pointer block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#D94378] focus-visible:ring-offset-2 focus-visible:ring-offset-[#FBF7F0]"
              >
                <span className="text-[10px] text-purple-700 uppercase tracking-wider block font-semibold">
                  Unassigned
                </span>
                <div className="font-serif text-2xl font-bold text-purple-700 mt-1">
                  {complaints.unassigned}
                </div>
                <span className="text-[10px] text-purple-600">needs duty tech</span>
              </Link>

              <Link
                to="/admin/complaints?status=in_progress"
                aria-label={`View ${complaints.inProgress} in-progress complaints in Complaint Queue`}
                className="bg-[#FFFCF7] p-4 rounded-2xl border border-[#E8DCCF] shadow-xs hover:border-[#D94378]/50 hover:shadow-sm transition-all cursor-pointer block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#D94378] focus-visible:ring-offset-2 focus-visible:ring-offset-[#FBF7F0]"
              >
                <span className="text-[10px] text-teal-700 uppercase tracking-wider block font-semibold">
                  In Progress
                </span>
                <div className="font-serif text-2xl font-bold text-[#368F83] mt-1">
                  {complaints.inProgress}
                </div>
                <span className="text-[10px] text-teal-700">active repairs</span>
              </Link>

              <Link
                to="/admin/complaints?status=completed,closed"
                aria-label={`View ${complaints.resolved} resolved (completed and closed) complaints in Complaint Queue`}
                className="bg-[#FFFCF7] p-4 rounded-2xl border border-[#E8DCCF] shadow-xs hover:border-[#D94378]/50 hover:shadow-sm transition-all cursor-pointer block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#D94378] focus-visible:ring-offset-2 focus-visible:ring-offset-[#FBF7F0]"
              >
                <span className="text-[10px] text-emerald-700 uppercase tracking-wider block font-semibold">
                  Resolved
                </span>
                <div className="font-serif text-2xl font-bold text-emerald-600 mt-1">
                  {complaints.resolved}
                </div>
                <span className="text-[10px] text-emerald-700">
                  {complaints.completed} completed &middot; {complaints.closed} closed
                </span>
              </Link>
            </div>

            {/* Secondary Lifecycle Status Breakdown Strip */}
            <div className="bg-[#FFFCF7] px-4 py-2.5 rounded-2xl border border-[#E8DCCF] flex flex-wrap items-center gap-x-3 gap-y-1.5 text-[11px] text-[#292039]/75">
              <span className="font-semibold text-[#292039] mr-1">Lifecycle Breakdown:</span>
              {[
                { label: 'Under Review', status: 'under_review', count: complaints.underReview },
                { label: 'Assigned', status: 'assigned', count: complaints.assigned },
                { label: 'Accepted', status: 'accepted', count: complaints.accepted },
                { label: 'Completed', status: 'completed', count: complaints.completed },
                { label: 'Closed', status: 'closed', count: complaints.closed },
                { label: 'Rejected', status: 'rejected', count: complaints.rejected },
              ].map((item) => (
                <Link
                  key={item.status}
                  to={`/admin/complaints?status=${item.status}`}
                  aria-label={`Filter complaint queue by ${item.label} (${item.count})`}
                  className="px-2 py-0.5 rounded-lg hover:bg-[#F7EFE6] hover:text-[#D94378] transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#D94378]"
                >
                  {item.label}: <strong className="text-[#292039]">{item.count}</strong>
                </Link>
              ))}
            </div>

            {/* Resident & Admission KPI Row */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
              <Link
                to="/admin/students"
                aria-label={`View ${residents?.activeCount ?? 0} active residents in Resident Directory`}
                className="bg-[#FFFCF7] p-4 rounded-2xl border border-[#E8DCCF] shadow-xs hover:border-[#D94378]/50 hover:shadow-sm transition-all cursor-pointer flex items-center justify-between gap-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#D94378] focus-visible:ring-offset-2 focus-visible:ring-offset-[#FBF7F0]"
              >
                <div>
                  <span className="text-[10px] text-teal-700 uppercase tracking-wider block font-semibold">
                    Active Residents
                  </span>
                  <div className="font-serif text-2xl font-bold text-[#368F83] mt-1">
                    {residents?.activeCount ?? 0}
                  </div>
                  <span className="text-[10px] text-[#292039]/65">
                    Students with active hostel allocations
                  </span>
                </div>
                <div
                  aria-hidden="true"
                  className="h-10 w-10 rounded-xl bg-[#F7EFE6] text-[#368F83] flex items-center justify-center shrink-0"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2"
                      d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"
                    />
                  </svg>
                </div>
              </Link>

              <Link
                to="/admin/approvals"
                aria-label={`Review ${approvals.pendingCount} pending student registrations`}
                className="bg-[#FFFCF7] p-4 rounded-2xl border border-[#E8DCCF] shadow-xs hover:border-[#D94378]/50 hover:shadow-sm transition-all cursor-pointer flex items-center justify-between gap-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#D94378] focus-visible:ring-offset-2 focus-visible:ring-offset-[#FBF7F0]"
              >
                <div>
                  <span className="text-[10px] text-[#D94378] uppercase tracking-wider block font-semibold">
                    Pending Approvals
                  </span>
                  <div className="font-serif text-2xl font-bold text-[#292039] mt-1">
                    {approvals.pendingCount}
                  </div>
                  <span className="text-[10px] text-[#292039]/65">
                    {approvals.approvedCount} approved students
                  </span>
                </div>
                <div
                  aria-hidden="true"
                  className="h-10 w-10 rounded-xl bg-[#F7EFE6] text-[#D94378] flex items-center justify-center shrink-0"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2"
                      d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                    />
                  </svg>
                </div>
              </Link>
            </div>
          </div>

          {/* Section C & D — Operational Occupancy & Financial Summary */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Section C — Operational Overview (Occupancy) */}
            <div className="bg-[#FFFCF7] p-6 rounded-3xl border border-[#E8DCCF] space-y-5 shadow-xs">
              <div className="flex items-start justify-between gap-3 pb-3 border-b border-[#F0E4D4]">
                <div>
                  <h2 className="font-serif text-lg font-bold text-[#292039]">
                    Hostel Occupancy Overview
                  </h2>
                  <p className="text-xs text-[#292039]/65">
                    Active bed allocations as of {formatDisplayDate(occupancy.referenceDate)} across{' '}
                    {occupancy.activeRoomsCount} active room(s)
                  </p>
                </div>
                <Link
                  to="/admin/rooms"
                  className="text-xs font-semibold text-[#D94378] hover:underline shrink-0"
                >
                  Manage Rooms &rarr;
                </Link>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-3 rounded-2xl bg-[#FBF7F0] border border-[#F0E4D4]">
                  <span className="text-[10px] text-[#292039]/60 uppercase font-semibold block">
                    Total Beds
                  </span>
                  <div className="font-serif text-xl font-bold text-[#292039] mt-0.5">
                    {occupancy.totalCapacity}
                  </div>
                </div>
                <div className="p-3 rounded-2xl bg-[#FBF7F0] border border-[#F0E4D4]">
                  <span className="text-[10px] text-teal-700 uppercase font-semibold block">
                    Occupied Beds
                  </span>
                  <div className="font-serif text-xl font-bold text-[#368F83] mt-0.5">
                    {occupancy.occupiedBeds}
                  </div>
                </div>
                <div className="p-3 rounded-2xl bg-[#FBF7F0] border border-[#F0E4D4]">
                  <span className="text-[10px] text-amber-700 uppercase font-semibold block">
                    Vacant Beds
                  </span>
                  <div className="font-serif text-xl font-bold text-amber-600 mt-0.5">
                    {occupancy.vacantBeds}
                  </div>
                </div>
                <div className="p-3 rounded-2xl bg-[#FBF7F0] border border-[#F0E4D4]">
                  <span className="text-[10px] text-[#D94378] uppercase font-semibold block">
                    Occupancy Rate
                  </span>
                  <div className="font-serif text-xl font-bold text-[#D94378] mt-0.5">
                    {occupancy.occupancyRate}%
                  </div>
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between text-[11px] font-semibold text-[#292039]/75 mb-1.5">
                  <span>Overall Bed Utilization</span>
                  <span>
                    {occupancy.occupiedBeds} / {occupancy.totalCapacity} beds ({occupancy.occupancyRate}
                    %)
                  </span>
                </div>
                <div className="w-full h-2.5 rounded-full bg-[#F0E4D4] overflow-hidden">
                  <div
                    className="h-full rounded-full bg-[#368F83] transition-all"
                    style={{ width: `${Math.min(100, Math.max(0, occupancy.occupancyRate))}%` }}
                  />
                </div>
              </div>

              <div className="space-y-2.5 pt-1">
                <h3 className="text-[11px] font-bold uppercase tracking-wider text-[#292039]/60">
                  Block-Wise Breakdown
                </h3>
                {occupancy.blocks.length === 0 ? (
                  <p className="text-xs text-[#292039]/60 italic py-2">
                    No active hostel blocks configured.
                  </p>
                ) : (
                  <div className="space-y-2.5">
                    {occupancy.blocks.map((blk) => (
                      <div key={blk.blockId} className="space-y-1">
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-semibold text-[#292039]">
                            {blk.name}{' '}
                            <span className="text-[10px] font-mono text-[#292039]/60">
                              ({blk.code})
                            </span>
                          </span>
                          <span className="text-[#292039]/75 text-[11px]">
                            {blk.occupiedBeds}/{blk.totalCapacity} occupied &middot;{' '}
                            <strong className="text-[#292039]">{blk.vacantBeds} vacant</strong> (
                            {blk.occupancyRate}%)
                          </span>
                        </div>
                        <div className="w-full h-1.5 rounded-full bg-[#F0E4D4] overflow-hidden">
                          <div
                            className="h-full rounded-full bg-[#D94378]"
                            style={{ width: `${Math.min(100, Math.max(0, blk.occupancyRate))}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Section D — Financial Overview */}
            <div className="bg-[#FFFCF7] p-6 rounded-3xl border border-[#E8DCCF] space-y-5 shadow-xs">
              <div className="flex items-start justify-between gap-3 pb-3 border-b border-[#F0E4D4]">
                <div>
                  <h2 className="font-serif text-lg font-bold text-[#292039]">
                    Disciplinary Fines &amp; Collections
                  </h2>
                  <p className="text-xs text-[#292039]/65">
                    Verified payments and live unpaid fine balances
                  </p>
                </div>
                <Link
                  to="/admin/fines"
                  className="text-xs font-semibold text-[#D94378] hover:underline shrink-0"
                >
                  Open Fines Ledger &rarr;
                </Link>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="p-4 rounded-2xl bg-[#FBF7F0] border border-[#F0E4D4]">
                  <span className="text-[10px] text-[#292039]/60 uppercase font-semibold block">
                    Fines Levied
                  </span>
                  <div className="font-serif text-xl font-bold text-[#292039] mt-1">
                    {formatInr(finances.leviedAmount)}
                  </div>
                  <span className="text-[10px] text-[#292039]/60">
                    {finances.leviedCount} fine(s) issued in period
                  </span>
                </div>

                <div className="p-4 rounded-2xl bg-[#FBF7F0] border border-[#F0E4D4]">
                  <span className="text-[10px] text-emerald-700 uppercase font-semibold block">
                    Verified Collections
                  </span>
                  <div className="font-serif text-xl font-bold text-emerald-600 mt-1">
                    {formatInr(finances.collectedAmount)}
                  </div>
                  <span className="text-[10px] text-emerald-700">
                    {finances.collectedCount} verified payment(s)
                  </span>
                </div>

                <div className="p-4 rounded-2xl bg-[#FBF7F0] border border-[#F0E4D4]">
                  <span className="text-[10px] text-rose-700 uppercase font-semibold block">
                    Outstanding Balance
                  </span>
                  <div className="font-serif text-xl font-bold text-rose-600 mt-1">
                    {formatInr(finances.outstandingAmount)}
                  </div>
                  <span className="text-[10px] text-rose-700">
                    {finances.outstandingCount} live unpaid fine(s)
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3 pt-1">
                <div className="p-3 rounded-2xl bg-white border border-[#F0E4D4]">
                  <span className="text-[10px] text-[#292039]/60 uppercase font-semibold block">
                    Waived (Period)
                  </span>
                  <div className="text-sm font-bold text-[#292039] mt-0.5">
                    {formatInr(finances.waivedAmount)}
                  </div>
                  <span className="text-[10px] text-[#292039]/60">{finances.waivedCount} waived</span>
                </div>

                <div className="p-3 rounded-2xl bg-white border border-[#F0E4D4]">
                  <span className="text-[10px] text-[#292039]/60 uppercase font-semibold block">
                    Cancelled (Period)
                  </span>
                  <div className="text-sm font-bold text-[#292039] mt-0.5">
                    {formatInr(finances.cancelledAmount)}
                  </div>
                  <span className="text-[10px] text-[#292039]/60">
                    {finances.cancelledCount} cancelled
                  </span>
                </div>

                <Link
                  to="/admin/fine-disputes"
                  className="p-3 rounded-2xl bg-white border border-[#F0E4D4] hover:border-purple-300 transition-colors block"
                >
                  <span className="text-[10px] text-purple-700 uppercase font-semibold block">
                    Pending Disputes
                  </span>
                  <div className="text-sm font-bold text-purple-700 mt-0.5">
                    {finances.pendingDisputesCount}
                  </div>
                  <span className="text-[10px] text-purple-600">Review queue &rarr;</span>
                </Link>
              </div>
            </div>
          </div>

          {/* Phase 4.2 — Complaint Telemetry, SLA Compliance & Staff Performance */}
          <AdminComplaintAnalytics
            data={complaintAnalytics}
            loading={complaintAnalyticsLoading}
            error={complaintAnalyticsError}
            onRetry={() => {
              const params = { preset: appliedRange.preset }
              if (appliedRange.preset === 'custom') {
                params.dateFrom = appliedRange.dateFrom
                params.dateTo = appliedRange.dateTo
              }
              fetchComplaintAnalytics(params).catch(() => {})
            }}
          />

          {/* Section E — Recent Maintenance Activity Table */}
          <div className="bg-[#FFFCF7] p-6 rounded-3xl border border-[#E8DCCF] space-y-4 shadow-xs">
            <div className="flex items-center justify-between pb-3 border-b border-[#F0E4D4]">
              <div>
                <h2 className="font-serif text-lg font-bold text-[#292039]">
                  Recent Maintenance Activity
                </h2>
                <p className="text-xs text-[#292039]/65">
                  Latest complaint activity across electrical, plumbing, carpentry, and internet
                  facilities
                </p>
              </div>
              <Link
                to="/admin/complaints"
                className="text-xs font-semibold text-[#D94378] hover:underline"
              >
                Manage All Tickets ({complaints.total}) &rarr;
              </Link>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-[#F0E4D4] text-[#292039]/60 font-semibold">
                    <th className="pb-2.5">Ticket ID</th>
                    <th className="pb-2.5">Room</th>
                    <th className="pb-2.5">Category</th>
                    <th className="pb-2.5">Title &amp; Problem</th>
                    <th className="pb-2.5">Assigned Staff</th>
                    <th className="pb-2.5">Priority</th>
                    <th className="pb-2.5">Status</th>
                    <th className="pb-2.5 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#F7EFE6]">
                  {recentActivity.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="py-8 text-center text-[#292039]/60 italic">
                        No maintenance complaints recorded during the selected reporting window.
                      </td>
                    </tr>
                  ) : (
                    recentActivity.map((c) => (
                      <tr
                        key={c.id}
                        onClick={() => navigate(`/admin/complaints/${c.id}`)}
                        className="hover:bg-[#FFFDF9] cursor-pointer"
                      >
                        <td className="py-3 font-mono font-bold text-[#292039]">{c.id}</td>
                        <td className="py-3 font-semibold text-[#D94378]">{c.room}</td>
                        <td className="py-3 text-[#368F83] font-medium">{c.category}</td>
                        <td className="py-3 font-medium text-[#292039] max-w-xs truncate">
                          {c.title}
                        </td>
                        <td className="py-3 text-[#292039]/80 font-medium">
                          {c.assignedStaff && c.assignedStaff !== 'Unassigned' ? (
                            <span>{c.assignedStaff}</span>
                          ) : (
                            <span className="text-amber-700 italic">Unassigned</span>
                          )}
                        </td>
                        <td className="py-3">
                          <PriorityBadge priority={c.priority} />
                        </td>
                        <td className="py-3">
                          <StatusBadge status={c.status} />
                        </td>
                        <td className="py-3 text-right">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation()
                              navigate(`/admin/complaints/${c.id}`)
                            }}
                            className="text-[#D94378] font-semibold hover:underline cursor-pointer"
                          >
                            Inspect &rarr;
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
