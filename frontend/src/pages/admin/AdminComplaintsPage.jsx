import { useMemo } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useApp } from '../../context/AppContext'
import { StatusBadge, PriorityBadge } from '../../components/Brand'

const PAGE_SIZE = 20
const TERMINAL_STATUSES = new Set(['completed', 'closed', 'rejected'])

const STATUS_FILTER_LABELS = {
  submitted: 'Submitted (New)',
  under_review: 'Under Review',
  assigned: 'Assigned',
  accepted: 'Accepted',
  in_progress: 'In Progress',
  'completed,closed': 'Resolved (Completed & Closed)',
  completed: 'Completed',
  closed: 'Closed',
  rejected: 'Rejected',
}

function getCanonicalComplaintStatus(complaint) {
  const raw = String(complaint?.dbStatus || complaint?.status || '')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '_')
  if (raw === 'open') return 'submitted'
  if (raw === 'resolved') return 'completed'
  return raw
}

function normalizeStatusParam(raw) {
  const val = String(raw || '')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '_')
  if (!val || val === 'all') return 'ALL'
  if (val === 'open' || val === 'submitted') return 'submitted'
  if (val === 'under_review') return 'under_review'
  if (val === 'assigned') return 'assigned'
  if (val === 'accepted') return 'accepted'
  if (val === 'in_progress') return 'in_progress'
  if (val === 'completed,closed' || val === 'closed,completed' || val === 'resolved') {
    return 'completed,closed'
  }
  if (val === 'completed') return 'completed'
  if (val === 'closed') return 'closed'
  if (val === 'rejected') return 'rejected'
  return 'ALL'
}

function normalizeStaffParam(raw) {
  const val = String(raw || '').trim()
  if (!val || val.toUpperCase() === 'ALL') return 'ALL'
  if (val.toUpperCase() === 'UNASSIGNED') return 'UNASSIGNED'
  return val
}

export function AdminComplaintsPage() {
  const { complaints, staff, complaintsLoading, blocks = [] } = useApp()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const searchTerm = searchParams.get('q') || ''
  const statusFilter = normalizeStatusParam(searchParams.get('status'))
  const priorityFilter = searchParams.get('priority') || 'ALL'
  const categoryFilter = searchParams.get('category') || 'ALL'
  const staffFilter = normalizeStaffParam(searchParams.get('staff') || searchParams.get('assigned'))
  const blockFilter = searchParams.get('block') || 'ALL'
  const dateFilter = searchParams.get('date') || ''
  const rawPage = Number.parseInt(searchParams.get('page') || '1', 10)
  const requestedPage = Number.isFinite(rawPage) && rawPage >= 1 ? rawPage : 1

  const updateFilter = (key, value) => {
    const next = new URLSearchParams(searchParams)
    if (key === 'staff') {
      next.delete('assigned')
    }
    if (!value || value === 'ALL') {
      next.delete(key)
    } else if (key === 'staff' && value === 'UNASSIGNED') {
      next.set('staff', 'unassigned')
    } else {
      next.set(key, value)
    }
    next.delete('page')
    setSearchParams(next)
  }

  const clearAllFilters = () => {
    setSearchParams({})
  }

  const setPage = (nextPage) => {
    const next = new URLSearchParams(searchParams)
    if (nextPage <= 1) {
      next.delete('page')
    } else {
      next.set('page', String(nextPage))
    }
    setSearchParams(next)
  }

  // Calculate high-level metrics using canonical status & active-assignment rules
  const totalCount = complaints.length
  const newSubmissionsCount = complaints.filter(
    (c) => getCanonicalComplaintStatus(c) === 'submitted',
  ).length
  const inProgressCount = complaints.filter((c) => {
    const st = getCanonicalComplaintStatus(c)
    return st === 'accepted' || st === 'in_progress'
  }).length
  const unassignedCount = complaints.filter((c) => {
    const st = getCanonicalComplaintStatus(c)
    return !TERMINAL_STATUSES.has(st) && (!c.assignedStaff || c.assignedStaff === 'Unassigned')
  }).length
  const resolvedCount = complaints.filter((c) => {
    const st = getCanonicalComplaintStatus(c)
    return st === 'completed' || st === 'closed'
  }).length
  const highPriorityCount = complaints.filter((c) => c.priority === 'High').length

  // Categories list
  const categories = useMemo(() => {
    return Array.from(new Set(complaints.map((c) => c.category))).filter(Boolean)
  }, [complaints])

  // Blocks list
  const blocksList = useMemo(() => {
    const apiBlocks = Array.isArray(blocks) ? blocks.map((b) => b.name).filter(Boolean) : []
    const raw = complaints.map((c) => c.block).filter((b) => b && b !== 'Hostel')
    return Array.from(new Set([...apiBlocks, ...raw]))
  }, [blocks, complaints])

  const filtered = complaints.filter((c) => {
    const q = searchTerm.toLowerCase()
    const studentName = (c.studentName || c.reporterName || '').toLowerCase()
    const studentRoll = (c.studentRoll || c.reporterRoll || '').toLowerCase()
    const roomStr = (c.room || '').toLowerCase()

    const matchesSearch =
      !q ||
      (c.title || '').toLowerCase().includes(q) ||
      (c.id || '').toLowerCase().includes(q) ||
      studentName.includes(q) ||
      studentRoll.includes(q) ||
      roomStr.includes(q) ||
      (c.description || '').toLowerCase().includes(q)

    const canonicalStatus = getCanonicalComplaintStatus(c)
    const matchesStatus =
      statusFilter === 'ALL' ||
      (statusFilter === 'completed,closed'
        ? canonicalStatus === 'completed' || canonicalStatus === 'closed'
        : canonicalStatus === statusFilter)

    const matchesPriority = priorityFilter === 'ALL' || c.priority === priorityFilter
    const matchesCategory = categoryFilter === 'ALL' || c.category === categoryFilter

    let matchesStaff = true
    if (staffFilter === 'UNASSIGNED') {
      matchesStaff =
        !TERMINAL_STATUSES.has(canonicalStatus) &&
        (!c.assignedStaff || c.assignedStaff === 'Unassigned')
    } else if (staffFilter !== 'ALL') {
      matchesStaff = c.assignedStaffId === staffFilter || c.assignedStaff === staffFilter
    }

    const complaintBlock = c.block || ''
    const matchesBlock =
      blockFilter === 'ALL' || complaintBlock.toLowerCase().includes(blockFilter.toLowerCase())

    let matchesDate = true
    if (dateFilter) {
      // dateFilter is YYYY-MM-DD; c.date is DD/MM/YYYY or c.created_at is ISO
      const [yyyy, mm, dd] = dateFilter.split('-')
      const formattedTarget = `${dd}/${mm}/${yyyy}`
      const cDate = c.date || c.dateSubmitted || ''
      const cIso = (c.created_at || '').slice(0, 10)
      matchesDate = cDate === formattedTarget || cIso === dateFilter
    }

    return (
      matchesSearch &&
      matchesStatus &&
      matchesPriority &&
      matchesCategory &&
      matchesStaff &&
      matchesBlock &&
      matchesDate
    )
  })

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const currentPage = Math.min(requestedPage, totalPages)
  const paginated = filtered.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE)

  const activeFilterChips = []
  if (statusFilter !== 'ALL') {
    activeFilterChips.push(`Status: ${STATUS_FILTER_LABELS[statusFilter] || statusFilter}`)
  }
  if (staffFilter !== 'ALL') {
    activeFilterChips.push(
      `Staff: ${staffFilter === 'UNASSIGNED' ? 'Unassigned Only' : staffFilter}`,
    )
  }
  if (priorityFilter !== 'ALL') activeFilterChips.push(`Priority: ${priorityFilter}`)
  if (categoryFilter !== 'ALL') activeFilterChips.push(`Category: ${categoryFilter}`)
  if (blockFilter !== 'ALL') activeFilterChips.push(`Block: ${blockFilter}`)
  if (dateFilter) activeFilterChips.push(`Date: ${dateFilter}`)
  if (searchTerm.trim()) activeFilterChips.push(`Search: "${searchTerm.trim()}"`)
  const hasActiveFilters = activeFilterChips.length > 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#F0E4D4]">
        <div>
          <span className="text-[11px] font-bold text-[#D94378] uppercase tracking-wider">
            Hostel Operations &amp; Facility Desk
          </span>
          <h1 className="font-serif text-2xl sm:text-3xl font-bold text-[#292039]">
            Hostel Complaint Management
          </h1>
          <p className="text-xs text-[#292039]/70 mt-1">
            Dispatch duty staff, conduct warden reviews, track reassignments, and confirm repair
            resolutions
          </p>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 lg:grid-cols-6 gap-3">
        <div className="p-3.5 rounded-2xl bg-[#FFFCF7] border border-[#E8DCCF] shadow-xs">
          <span className="text-[10px] text-[#292039]/60 uppercase tracking-wider block font-semibold">
            Total Tickets
          </span>
          <span className="font-serif text-2xl font-bold text-[#292039] block mt-0.5">
            {totalCount}
          </span>
        </div>

        <div className="p-3.5 rounded-2xl bg-[#FFFCF7] border border-[#E8DCCF] shadow-xs">
          <span className="text-[10px] text-amber-700 uppercase tracking-wider block font-semibold">
            New Submissions
          </span>
          <span className="font-serif text-2xl font-bold text-amber-600 block mt-0.5">
            {newSubmissionsCount}
          </span>
        </div>

        <div className="p-3.5 rounded-2xl bg-[#FFFCF7] border border-[#E8DCCF] shadow-xs">
          <span className="text-[10px] text-purple-700 uppercase tracking-wider block font-semibold">
            Unassigned
          </span>
          <span className="font-serif text-2xl font-bold text-purple-700 block mt-0.5">
            {unassignedCount}
          </span>
        </div>

        <div className="p-3.5 rounded-2xl bg-[#FFFCF7] border border-[#E8DCCF] shadow-xs">
          <span className="text-[10px] text-teal-700 uppercase tracking-wider block font-semibold">
            In Progress
          </span>
          <span className="font-serif text-2xl font-bold text-[#368F83] block mt-0.5">
            {inProgressCount}
          </span>
        </div>

        <div className="p-3.5 rounded-2xl bg-[#FFFCF7] border border-[#E8DCCF] shadow-xs">
          <span className="text-[10px] text-rose-700 uppercase tracking-wider block font-semibold">
            High Priority
          </span>
          <span className="font-serif text-2xl font-bold text-rose-600 block mt-0.5">
            {highPriorityCount}
          </span>
        </div>

        <div className="p-3.5 rounded-2xl bg-[#FFFCF7] border border-[#E8DCCF] shadow-xs">
          <span className="text-[10px] text-emerald-700 uppercase tracking-wider block font-semibold">
            Resolved
          </span>
          <span className="font-serif text-2xl font-bold text-emerald-600 block mt-0.5">
            {resolvedCount}
          </span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="p-4 rounded-3xl bg-[#FFFCF7] border border-[#E8DCCF] shadow-xs space-y-3">
        <div className="flex flex-col md:flex-row gap-3 items-center justify-between">
          <div className="relative w-full md:w-72">
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => updateFilter('q', e.target.value)}
              placeholder="Search by student, roll no, room, ID, issue..."
              className="w-full pl-9 pr-3 py-2 rounded-xl border border-[#D8CEBE] text-xs focus:outline-none focus:border-[#D94378] bg-[#FFFDF9]"
            />
            <svg
              className="w-4 h-4 text-[#292039]/40 absolute left-3 top-2.5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
          </div>

          <div className="flex flex-wrap items-center gap-2 w-full md:w-auto">
            {/* Status Filter */}
            <select
              aria-label="Filter by status"
              value={statusFilter}
              onChange={(e) => updateFilter('status', e.target.value)}
              className="px-3 py-2 rounded-xl border border-[#D8CEBE] text-xs bg-[#FFFDF9] text-[#292039]"
            >
              <option value="ALL">All Statuses</option>
              <option value="submitted">Submitted (New)</option>
              <option value="under_review">Under Review</option>
              <option value="assigned">Assigned</option>
              <option value="accepted">Accepted</option>
              <option value="in_progress">In Progress</option>
              <option value="completed,closed">Resolved (Completed &amp; Closed)</option>
              <option value="completed">Completed</option>
              <option value="closed">Closed</option>
              <option value="rejected">Rejected</option>
            </select>

            {/* Priority Filter */}
            <select
              aria-label="Filter by priority"
              value={priorityFilter}
              onChange={(e) => updateFilter('priority', e.target.value)}
              className="px-3 py-2 rounded-xl border border-[#D8CEBE] text-xs bg-[#FFFDF9] text-[#292039]"
            >
              <option value="ALL">All Priorities</option>
              <option value="High">High Priority</option>
              <option value="Medium">Medium Priority</option>
              <option value="Low">Low Priority</option>
            </select>

            {/* Category Filter */}
            <select
              aria-label="Filter by category"
              value={categoryFilter}
              onChange={(e) => updateFilter('category', e.target.value)}
              className="px-3 py-2 rounded-xl border border-[#D8CEBE] text-xs bg-[#FFFDF9] text-[#292039]"
            >
              <option value="ALL">All Categories</option>
              {categories.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>

            {/* Assigned Staff Filter */}
            <select
              aria-label="Filter by assigned staff"
              value={staffFilter}
              onChange={(e) => updateFilter('staff', e.target.value)}
              className="px-3 py-2 rounded-xl border border-[#D8CEBE] text-xs bg-[#FFFDF9] text-[#292039]"
            >
              <option value="ALL">All Staff</option>
              <option value="UNASSIGNED">Unassigned Only</option>
              {staff.map((s) => (
                <option key={s.id} value={s.name || s.fullName}>
                  {s.name || s.fullName} ({s.trade})
                </option>
              ))}
            </select>

            {/* Block Filter */}
            <select
              aria-label="Filter by block"
              value={blockFilter}
              onChange={(e) => updateFilter('block', e.target.value)}
              className="px-3 py-2 rounded-xl border border-[#D8CEBE] text-xs bg-[#FFFDF9] text-[#292039]"
            >
              <option value="ALL">All Wings/Blocks</option>
              {blocksList.map((blk) => (
                <option key={blk} value={blk}>
                  {blk}
                </option>
              ))}
            </select>

            {/* Date Filter */}
            <input
              type="date"
              aria-label="Filter by date"
              value={dateFilter}
              onChange={(e) => updateFilter('date', e.target.value)}
              className="px-3 py-1.5 rounded-xl border border-[#D8CEBE] text-xs bg-[#FFFDF9] text-[#292039]"
            />
          </div>
        </div>

        {hasActiveFilters && (
          <div
            role="status"
            className="pt-2.5 border-t border-[#F0E4D4] flex flex-wrap items-center justify-between gap-2 text-xs"
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-semibold text-[#292039]/70">Active Filters:</span>
              {activeFilterChips.map((chip) => (
                <span
                  key={chip}
                  className="px-2.5 py-1 rounded-full bg-[#F7EFE6] border border-[#E8DCCF] text-[#292039] font-semibold text-[11px]"
                >
                  {chip}
                </span>
              ))}
              <span className="text-[11px] text-[#292039]/65">
                ({filtered.length} of {totalCount} complaints)
              </span>
            </div>
            <button
              type="button"
              onClick={clearAllFilters}
              className="px-3 py-1 rounded-xl border border-[#D8CEBE] hover:bg-[#F7EFE6] text-[#D94378] font-semibold text-[11px] transition-colors cursor-pointer"
            >
              Clear Filters
            </button>
          </div>
        )}
      </div>

      {/* Complaints List Table */}
      <div className="bg-[#FFFCF7] rounded-3xl border border-[#E8DCCF] shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#F7EFE6] text-[#292039]/80 font-semibold border-b border-[#E8DCCF]">
              <tr>
                <th className="py-3 px-4">Ticket ID</th>
                <th className="py-3 px-4">Title &amp; Problem</th>
                <th className="py-3 px-4">Resident &amp; Room</th>
                <th className="py-3 px-4">Category</th>
                <th className="py-3 px-4">Priority</th>
                <th className="py-3 px-4">Assigned Staff</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E8DCCF]/60">
              {complaintsLoading && complaints.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-[#292039]/60">
                    Loading hostel complaints...
                  </td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-[#292039]/60">
                    No maintenance complaints match the selected filter criteria.
                  </td>
                </tr>
              ) : (
                paginated.map((c) => {
                  const block =
                    c.block ||
                    ((c.room || '').startsWith('A')
                      ? 'Block A'
                      : (c.room || '').startsWith('B')
                        ? 'Block B'
                        : 'Hostel')
                  const reporterName = c.studentName || c.reporterName || 'Resident Student'
                  const reporterRoll = c.studentRoll || c.reporterRoll || 'N/A'
                  return (
                    <tr
                      key={c.id}
                      onClick={() => navigate(`/admin/complaints/${c.id}`)}
                      className="hover:bg-[#FFFDF9] transition-colors cursor-pointer"
                    >
                      <td className="py-3.5 px-4 font-mono font-bold text-[#292039]">{c.id}</td>
                      <td className="py-3.5 px-4 max-w-xs">
                        <div className="font-semibold text-[#292039] truncate">{c.title}</div>
                        <div className="text-[11px] text-[#292039]/60 truncate">
                          {c.description}
                        </div>
                      </td>
                      <td className="py-3.5 px-4">
                        <div className="font-medium text-[#292039]">{reporterName}</div>
                        <div className="text-[10px] text-[#292039]/60 font-mono">
                          {reporterRoll} •{' '}
                          {c.locationType === 'common_area' ? c.room : `Room ${c.room}`} ({block})
                        </div>
                      </td>
                      <td className="py-3.5 px-4 text-[#292039]/80 font-medium">{c.category}</td>
                      <td className="py-3.5 px-4">
                        <PriorityBadge priority={c.priority} />
                      </td>
                      <td className="py-3.5 px-4">
                        {c.assignedStaff && c.assignedStaff !== 'Unassigned' ? (
                          <div>
                            <div className="font-semibold text-[#292039]">{c.assignedStaff}</div>
                            <div className="text-[10px] text-[#368F83] font-medium">
                              {c.assignedStaffRole || 'Duty Staff'}
                            </div>
                          </div>
                        ) : (
                          <span className="text-[11px] text-amber-700 italic">Unassigned</span>
                        )}
                      </td>
                      <td className="py-3.5 px-4">
                        <StatusBadge status={c.status} />
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation()
                            navigate(`/admin/complaints/${c.id}`)
                          }}
                          className="px-3 py-1.5 rounded-lg border border-[#D8CEBE] hover:bg-[#F7EFE6] text-[#292039] font-semibold transition-colors cursor-pointer"
                        >
                          Manage &rarr;
                        </button>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
        {totalPages > 1 && (
          <div className="px-4 py-3 border-t border-[#E8DCCF] bg-[#FFFDF9] flex items-center justify-between text-xs">
            <span className="text-[#292039]/70">
              Page <strong className="text-[#292039]">{currentPage}</strong> of{' '}
              <strong className="text-[#292039]">{totalPages}</strong> ({filtered.length} matching)
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={currentPage <= 1}
                onClick={() => setPage(currentPage - 1)}
                className="px-3 py-1 rounded-xl border border-[#D8CEBE] hover:bg-[#F7EFE6] text-[#292039] font-semibold disabled:opacity-40 cursor-pointer disabled:cursor-not-allowed"
              >
                Previous
              </button>
              <button
                type="button"
                disabled={currentPage >= totalPages}
                onClick={() => setPage(currentPage + 1)}
                className="px-3 py-1 rounded-xl border border-[#D8CEBE] hover:bg-[#F7EFE6] text-[#292039] font-semibold disabled:opacity-40 cursor-pointer disabled:cursor-not-allowed"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
