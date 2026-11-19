import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { isComplaintOwnedByStudent, useApp } from '../../context/AppContext'
import { StatusBadge, PriorityBadge } from '../../components/Brand'

export function StudentComplaintsPage() {
  const { user, complaints, complaintsLoading } = useApp()
  const navigate = useNavigate()

  const [statusFilter, setStatusFilter] = useState('ALL')
  const [searchTerm, setSearchTerm] = useState('')

  // Students can access only their own complaints (never by room equality)
  const studentComplaints = complaints.filter((c) => isComplaintOwnedByStudent(c, user))

  const activeCount = studentComplaints.filter(
    (c) =>
      c.status === 'Submitted' ||
      c.status === 'Under Review' ||
      c.status === 'Assigned' ||
      c.status === 'Accepted' ||
      c.status === 'In Progress' ||
      c.status === 'open' ||
      c.status === 'in_progress',
  ).length

  const resolvedCount = studentComplaints.filter(
    (c) => c.status === 'Resolved' || c.status === 'Completed' || c.status === 'resolved',
  ).length

  const closedCount = studentComplaints.filter(
    (c) => c.status === 'Closed' || c.status === 'closed',
  ).length

  const filtered = studentComplaints.filter((c) => {
    const matchesSearch =
      c.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (c.assignedStaff && c.assignedStaff.toLowerCase().includes(searchTerm.toLowerCase()))

    let matchesStatus = true
    if (statusFilter === 'ACTIVE') {
      matchesStatus =
        c.status === 'Submitted' ||
        c.status === 'Under Review' ||
        c.status === 'Assigned' ||
        c.status === 'Accepted' ||
        c.status === 'In Progress' ||
        c.status === 'open' ||
        c.status === 'in_progress'
    } else if (statusFilter === 'RESOLVED') {
      matchesStatus = c.status === 'Resolved' || c.status === 'Completed' || c.status === 'resolved'
    } else if (statusFilter === 'CLOSED') {
      matchesStatus = c.status === 'Closed' || c.status === 'closed'
    }

    return matchesSearch && matchesStatus
  })

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#F0E4D4]">
        <div>
          <span className="text-[11px] font-bold text-[#D94378] uppercase tracking-wider">
            Hostel Maintenance System
          </span>
          <h1 className="font-serif text-2xl sm:text-3xl font-bold text-[#292039]">
            My Maintenance Complaints
          </h1>
          <p className="text-xs text-[#292039]/70">
            Active and historical repair requests for{' '}
            {user?.room && user.room !== 'Unassigned'
              ? `Room ${user.room}`
              : 'Campus & Common Areas'}
          </p>
        </div>
        <Link
          to="/student/complaints/new"
          className="px-4 py-2.5 rounded-xl text-xs font-semibold bg-[#D94378] text-white hover:bg-[#C23365] transition-colors self-start sm:self-auto shadow-xs flex items-center gap-1.5"
        >
          <span>+ Submit New Complaint</span>
        </Link>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="p-4 rounded-2xl bg-[#FFFCF7] border border-[#E8DCCF] shadow-xs">
          <span className="text-xs text-[#292039]/70 font-medium">Pending / Active Work</span>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="font-serif text-2xl font-bold text-[#D94378]">{activeCount}</span>
            <span className="text-[11px] text-[#292039]/60">tickets in pipeline</span>
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-[#FFFCF7] border border-[#E8DCCF] shadow-xs">
          <span className="text-xs text-[#292039]/70 font-medium">Work Completed (Resolved)</span>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="font-serif text-2xl font-bold text-[#368F83]">{resolvedCount}</span>
            <span className="text-[11px] text-[#292039]/60">awaiting closure verification</span>
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-[#FFFCF7] border border-[#E8DCCF] shadow-xs">
          <span className="text-xs text-[#292039]/70 font-medium">Closed &amp; Verified</span>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="font-serif text-2xl font-bold text-[#292039]">{closedCount}</span>
            <span className="text-[11px] text-[#292039]/60">archived maintenance records</span>
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="p-3.5 rounded-2xl bg-[#FFFCF7] border border-[#E8DCCF] shadow-xs flex flex-col sm:flex-row gap-3 items-center justify-between">
        <div className="relative w-full sm:w-72">
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search by title, ID, problem..."
            className="w-full pl-8 pr-3 py-1.5 rounded-xl border border-[#D8CEBE] text-xs focus:outline-none focus:border-[#D94378] bg-[#FFFDF9]"
          />
          <svg
            className="w-3.5 h-3.5 text-[#292039]/40 absolute left-2.5 top-2"
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

        <div className="flex items-center gap-1.5 overflow-x-auto w-full sm:w-auto">
          {[
            { id: 'ALL', label: `All (${studentComplaints.length})` },
            { id: 'ACTIVE', label: `Active (${activeCount})` },
            { id: 'RESOLVED', label: `Resolved (${resolvedCount})` },
            { id: 'CLOSED', label: `Closed (${closedCount})` },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setStatusFilter(tab.id)}
              className={`px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-colors cursor-pointer ${
                statusFilter === tab.id
                  ? 'bg-[#292039] text-[#FFFCF7]'
                  : 'bg-[#F7EFE6] text-[#292039] hover:bg-[#EADBCA]'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Complaints List */}
      {complaintsLoading && studentComplaints.length === 0 ? (
        <div className="bg-[#FFFCF7] p-10 rounded-3xl border border-[#E8DCCF] text-center text-xs text-[#292039]/60">
          Loading your maintenance complaints...
        </div>
      ) : studentComplaints.length === 0 ? (
        <div className="bg-[#FFFCF7] p-12 rounded-3xl border border-[#E8DCCF] text-center space-y-3 shadow-xs">
          <span className="text-3xl">🛠️</span>
          <h3 className="font-serif text-lg font-bold text-[#292039]">No Complaints Filed</h3>
          <p className="text-xs text-[#292039]/60 max-w-sm mx-auto">
            You have not logged any maintenance requests yet. If anything in your room or common
            area needs fixing, click Submit New Complaint.
          </p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="bg-[#FFFCF7] p-10 rounded-3xl border border-[#E8DCCF] text-center text-xs text-[#292039]/60">
          No complaints match the selected filter or search keyword.
        </div>
      ) : (
        <div className="bg-[#FFFCF7] rounded-3xl border border-[#E8DCCF] overflow-hidden shadow-xs divide-y divide-[#F0E4D4]">
          {filtered.map((c) => (
            <div
              key={c.id}
              onClick={() => navigate(`/student/complaints/${c.id}`)}
              className="p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-[#FFFDF9] transition-colors cursor-pointer"
            >
              <div className="space-y-1.5 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-xs font-bold text-[#292039]">{c.id}</span>
                  <PriorityBadge priority={c.priority} />
                  <span className="text-xs text-[#368F83] font-medium">{c.category}</span>
                  <span className="text-[11px] text-[#292039]/50">
                    • {c.locationType === 'common_area' ? c.room : `Room ${c.room}`}
                  </span>
                </div>
                <h4 className="text-sm font-semibold text-[#292039]">{c.title}</h4>
                <p className="text-xs text-[#292039]/70 line-clamp-1">{c.description}</p>
                <div className="flex flex-wrap items-center gap-3 text-[11px] text-[#292039]/60 pt-0.5">
                  <span>Logged: {c.date || c.dateSubmitted}</span>
                  {c.assignedStaff && c.assignedStaff !== 'Unassigned' ? (
                    <span className="text-[#368F83] font-semibold">
                      Assigned to: {c.assignedStaff}{' '}
                      {c.assignedStaffRole ? `(${c.assignedStaffRole})` : ''}
                    </span>
                  ) : (
                    <span className="text-amber-700 italic">Awaiting staff assignment</span>
                  )}
                </div>
              </div>

              <div className="flex sm:flex-col items-center sm:items-end justify-between gap-2 shrink-0">
                <StatusBadge status={c.status} />
                <span className="text-xs font-semibold text-[#D94378] hidden sm:block">
                  View Tracking &rarr;
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
