import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useApp } from '../../context/AppContext'
import { StatusBadge, PriorityBadge } from '../../components/Brand'

export function StaffTasksPage() {
  const { user, complaints } = useApp()
  const navigate = useNavigate()

  const [filter, setFilter] = useState('ALL')
  const [searchTerm, setSearchTerm] = useState('')

  // Strict task isolation: Staff member can only see their own assigned tasks
  const staffDisplayName = user?.name || user?.fullName || ''
  const myTasks = complaints.filter(
    (c) =>
      (c.assignedStaffId && user?.id && c.assignedStaffId === user.id) ||
      (staffDisplayName &&
        c.assignedStaff &&
        (c.assignedStaff === staffDisplayName || c.assignedStaff.includes(staffDisplayName))),
  )

  const newCount = myTasks.filter((c) => c.status === 'Assigned').length
  const inProgressCount = myTasks.filter(
    (c) => c.status === 'Accepted' || c.status === 'In Progress' || c.status === 'in_progress',
  ).length
  const completedCount = myTasks.filter(
    (c) =>
      c.status === 'Completed' ||
      c.status === 'Resolved' ||
      c.status === 'Closed' ||
      c.status === 'resolved' ||
      c.status === 'closed',
  ).length

  const filteredTasks = myTasks.filter((t) => {
    const matchesSearch =
      t.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      t.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      t.room.toLowerCase().includes(searchTerm.toLowerCase()) ||
      t.reporterName.toLowerCase().includes(searchTerm.toLowerCase()) ||
      t.description.toLowerCase().includes(searchTerm.toLowerCase())

    let matchesFilter = true
    if (filter === 'NEW') {
      matchesFilter = t.status === 'Assigned'
    } else if (filter === 'IN_PROGRESS') {
      matchesFilter =
        t.status === 'Accepted' || t.status === 'In Progress' || t.status === 'in_progress'
    } else if (filter === 'COMPLETED') {
      matchesFilter =
        t.status === 'Completed' ||
        t.status === 'Resolved' ||
        t.status === 'Closed' ||
        t.status === 'resolved' ||
        t.status === 'closed'
    }

    return matchesSearch && matchesFilter
  })

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#F0E4D4]">
        <div>
          <span className="text-[11px] font-bold text-[#368F83] uppercase tracking-wider">
            Technician Task Queue
          </span>
          <h1 className="font-serif text-2xl sm:text-3xl font-bold text-[#292039]">
            My Assigned Work Orders
          </h1>
          <p className="text-xs text-[#292039]/70 mt-1">
            Accept tasks, record progress updates, and mark work completed for {user?.name}
          </p>
        </div>

        <Link
          to="/staff/dashboard"
          className="px-4 py-2 rounded-xl border border-[#D8CEBE] bg-[#FFFCF7] text-xs font-semibold text-[#292039] hover:bg-[#F7EFE6] self-start sm:self-auto"
        >
          &larr; Duty Dashboard
        </Link>
      </div>

      {/* Filter and Search Bar */}
      <div className="p-3.5 rounded-2xl bg-[#FFFCF7] border border-[#E8DCCF] shadow-xs flex flex-col sm:flex-row gap-3 items-center justify-between">
        <div className="relative w-full sm:w-72">
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search by room, ticket ID, student..."
            className="w-full pl-8 pr-3 py-2 rounded-xl border border-[#D8CEBE] text-xs focus:outline-none focus:border-[#368F83] bg-[#FFFDF9]"
          />
          <svg
            className="w-4 h-4 text-[#292039]/40 absolute left-2.5 top-2.5"
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

        {/* 4 Tabs: All tasks, New, In Progress, Completed */}
        <div className="flex items-center gap-1.5 overflow-x-auto w-full sm:w-auto pb-1 sm:pb-0">
          {[
            { id: 'ALL', label: `All (${myTasks.length})` },
            { id: 'NEW', label: `New (${newCount})` },
            { id: 'IN_PROGRESS', label: `In Progress (${inProgressCount})` },
            { id: 'COMPLETED', label: `Completed (${completedCount})` },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setFilter(tab.id)}
              className={`px-3.5 py-2 rounded-xl text-xs font-semibold whitespace-nowrap transition-colors cursor-pointer ${
                filter === tab.id
                  ? 'bg-[#292039] text-[#FFFCF7]'
                  : 'bg-[#F7EFE6] text-[#292039] hover:bg-[#EADBCA]'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Task Cards List */}
      {myTasks.length === 0 ? (
        <div className="bg-[#FFFCF7] p-12 rounded-3xl border border-[#E8DCCF] text-center space-y-3 shadow-xs">
          <div className="w-12 h-12 rounded-full bg-teal-50 text-[#368F83] mx-auto flex items-center justify-center text-xl">
            🛠️
          </div>
          <h2 className="font-serif text-lg font-bold text-[#292039]">No Work Orders Assigned</h2>
          <p className="text-xs text-[#292039]/70 max-w-sm mx-auto">
            You currently have no tasks assigned to your roster profile ({user?.trade}).
          </p>
        </div>
      ) : filteredTasks.length === 0 ? (
        <div className="bg-[#FFFCF7] p-10 rounded-3xl border border-[#E8DCCF] text-center text-xs text-[#292039]/60">
          No tasks match the selected &ldquo;{filter}&rdquo; filter.
        </div>
      ) : (
        <div className="space-y-3">
          {filteredTasks.map((task) => (
            <div
              key={task.id}
              onClick={() => navigate(`/staff/tasks/${task.id}`)}
              className="p-5 rounded-2xl bg-[#FFFCF7] border border-[#E8DCCF] hover:border-[#368F83] transition-all cursor-pointer shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4"
            >
              <div className="space-y-1.5 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-xs font-bold text-[#292039]">{task.id}</span>
                  <PriorityBadge priority={task.priority} />
                  <span className="text-xs font-bold px-2 py-0.5 rounded bg-[#F7EFE6] text-[#D94378]">
                    {task.locationType === 'common_area'
                      ? task.locationDetail || 'Common Area'
                      : `Room ${task.room} (${task.block || 'Wing'})`}
                  </span>
                  <span className="text-xs text-[#368F83] font-medium">{task.category}</span>
                </div>

                <h2 className="text-sm font-bold text-[#292039]">{task.title}</h2>
                <p className="text-xs text-[#292039]/75 line-clamp-2">{task.description}</p>

                <div className="flex flex-wrap items-center gap-4 text-[11px] text-[#292039]/60 pt-1">
                  <span>
                    Student: <strong>{task.reporterName}</strong> ({task.reporterRoll})
                  </span>
                  <span>Assigned: {task.assignedDate || task.dateSubmitted}</span>
                  {task.assignmentNotes && (
                    <span className="text-purple-800 italic truncate max-w-md">
                      Warden note: &ldquo;{task.assignmentNotes}&rdquo;
                    </span>
                  )}
                </div>
              </div>

              <div className="flex sm:flex-col items-center sm:items-end justify-between gap-3 shrink-0 pt-2 sm:pt-0 border-t sm:border-t-0 border-[#E8DCCF]">
                <StatusBadge status={task.status} />
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation()
                    navigate(`/staff/tasks/${task.id}`)
                  }}
                  className="px-4 py-2 rounded-xl bg-[#368F83] text-white text-xs font-semibold hover:bg-[#2B7369] transition-colors cursor-pointer shadow-xs"
                >
                  Open Task &rarr;
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
