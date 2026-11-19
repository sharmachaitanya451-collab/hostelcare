import { Link, useNavigate } from 'react-router-dom'
import { useApp } from '../../context/AppContext'
import { StatusBadge, PriorityBadge } from '../../components/Brand'

export function StaffDashboardPage() {
  const { user, complaints } = useApp()
  const navigate = useNavigate()

  // Strict task isolation: Staff can only access their own assigned tasks
  const staffDisplayName = user?.name || user?.fullName || ''
  const myTasks = complaints.filter(
    (c) =>
      (c.assignedStaffId && user?.id && c.assignedStaffId === user.id) ||
      (staffDisplayName &&
        c.assignedStaff &&
        (c.assignedStaff === staffDisplayName || c.assignedStaff.includes(staffDisplayName))),
  )

  const totalTasksCount = myTasks.length
  const newAssignmentsCount = myTasks.filter((c) => c.status === 'Assigned').length
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
  const highPriorityCount = myTasks.filter(
    (c) => c.priority === 'High' && c.status !== 'Closed' && c.status !== 'Completed',
  ).length

  return (
    <div className="space-y-6">
      {/* Duty Status Banner */}
      <div className="bg-gradient-to-r from-[#231E2F] to-[#352B47] text-[#FFFCF7] p-5 sm:p-7 rounded-3xl shadow-sm border border-[#483B5E] flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="space-y-1.5">
          <div className="inline-flex items-center gap-2 px-2.5 py-0.5 rounded-full bg-[#368F83]/30 text-emerald-300 text-xs font-semibold">
            <span className="h-2 w-2 rounded-full bg-emerald-400" />
            Duty Status: {user?.status || 'Active'} • {user?.trade || 'Duty Staff'}
          </div>
          <h1 className="font-serif text-2xl sm:text-3xl font-bold">
            Namaste, {user?.name || 'Technician'}
          </h1>
          <p className="text-xs text-[#D8CEBE]">
            Shift: <strong>{user?.shift || 'General Shift'}</strong> • You have{' '}
            <strong className="text-[#F4AA35]">
              {newAssignmentsCount + inProgressCount} active task(s)
            </strong>{' '}
            assigned on campus.
          </p>
        </div>

        <Link
          to="/staff/tasks"
          className="px-5 py-3 rounded-2xl bg-[#368F83] hover:bg-[#2B7369] text-white text-xs sm:text-sm font-semibold transition-all shadow-md shrink-0 flex items-center gap-2"
        >
          <span>📋 View All Assigned Tasks</span>
        </Link>
      </div>

      {/* 5 Core Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 sm:gap-4">
        <div className="p-4 rounded-2xl bg-[#FFFCF7] border border-[#E8DCCF] shadow-xs">
          <span className="text-[10px] text-[#292039]/60 uppercase tracking-wider block font-semibold">
            Total Work Orders
          </span>
          <span className="font-serif text-2xl font-bold text-[#292039] block mt-1">
            {totalTasksCount}
          </span>
          <span className="text-[11px] text-[#292039]/60">Assigned to you</span>
        </div>

        <div className="p-4 rounded-2xl bg-[#FFFCF7] border border-[#E8DCCF] shadow-xs">
          <span className="text-[10px] text-amber-700 uppercase tracking-wider block font-semibold">
            New Assignments
          </span>
          <span className="font-serif text-2xl font-bold text-amber-600 block mt-1">
            {newAssignmentsCount}
          </span>
          <span className="text-[11px] text-amber-800">Needs acceptance</span>
        </div>

        <div className="p-4 rounded-2xl bg-[#FFFCF7] border border-[#E8DCCF] shadow-xs">
          <span className="text-[10px] text-teal-700 uppercase tracking-wider block font-semibold">
            In Progress
          </span>
          <span className="font-serif text-2xl font-bold text-[#368F83] block mt-1">
            {inProgressCount}
          </span>
          <span className="text-[11px] text-teal-700">Currently active</span>
        </div>

        <div className="p-4 rounded-2xl bg-[#FFFCF7] border border-[#E8DCCF] shadow-xs">
          <span className="text-[10px] text-rose-700 uppercase tracking-wider block font-semibold">
            Needs Urgent Action
          </span>
          <span className="font-serif text-2xl font-bold text-rose-600 block mt-1">
            {highPriorityCount}
          </span>
          <span className="text-[11px] text-rose-700">High priority SLA</span>
        </div>

        <div className="p-4 rounded-2xl bg-[#FFFCF7] border border-[#E8DCCF] shadow-xs col-span-2 lg:col-span-1">
          <span className="text-[10px] text-emerald-700 uppercase tracking-wider block font-semibold">
            Completed Tasks
          </span>
          <span className="font-serif text-2xl font-bold text-emerald-600 block mt-1">
            {completedCount}
          </span>
          <span className="text-[11px] text-emerald-700">Finished &amp; resolved</span>
        </div>
      </div>

      {/* Recent Assignments Task Overview (Mobile-friendly large cards) */}
      <div className="bg-[#FFFCF7] p-5 sm:p-7 rounded-3xl border border-[#E8DCCF] shadow-xs space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-[#F0E4D4]">
          <div>
            <h2 className="font-serif text-lg font-bold text-[#292039]">Recent Work Orders</h2>
            <p className="text-xs text-[#292039]/70">
              Assigned hostel maintenance tasks for {user?.name}
            </p>
          </div>
          <Link to="/staff/tasks" className="text-xs font-semibold text-[#368F83] hover:underline">
            Manage All Tasks ({totalTasksCount}) &rarr;
          </Link>
        </div>

        {myTasks.length === 0 ? (
          <div className="py-12 text-center space-y-2">
            <div className="w-12 h-12 rounded-full bg-teal-50 text-[#368F83] mx-auto flex items-center justify-center text-xl">
              ✓
            </div>
            <h3 className="font-serif text-base font-bold text-[#292039]">All Caught Up</h3>
            <p className="text-xs text-[#292039]/70 max-w-sm mx-auto">
              You do not have any pending tasks assigned right now. When the warden allocates
              repairs, they will appear here.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {myTasks.slice(0, 4).map((task) => (
              <div
                key={task.id}
                onClick={() => navigate(`/staff/tasks/${task.id}`)}
                className="p-4 sm:p-5 rounded-2xl bg-[#FFFDF9] border border-[#E8DCCF] hover:border-[#368F83] transition-all cursor-pointer flex flex-col sm:flex-row sm:items-center justify-between gap-4"
              >
                <div className="space-y-1.5 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-xs font-bold text-[#292039]">{task.id}</span>
                    <PriorityBadge priority={task.priority} />
                    <span className="text-xs px-2.5 py-0.5 rounded-md bg-[#F7EFE6] text-[#292039] font-bold">
                      {task.locationType === 'common_area'
                        ? task.locationDetail || 'Common Area'
                        : `Room ${task.room} (${task.block || 'Wing'})`}
                    </span>
                    <span className="text-xs text-[#368F83] font-medium">{task.category}</span>
                  </div>

                  <h3 className="text-sm font-bold text-[#292039] leading-tight">{task.title}</h3>
                  <p className="text-xs text-[#292039]/70 line-clamp-2">{task.description}</p>

                  <div className="flex flex-wrap items-center gap-3 text-[11px] text-[#292039]/60 pt-1">
                    <span>
                      Resident: <strong>{task.reporterName}</strong>
                    </span>
                    <span>Assigned: {task.assignedDate || task.dateSubmitted}</span>
                    {task.assignmentNotes && (
                      <span className="text-purple-800 italic truncate max-w-md">
                        &ldquo;{task.assignmentNotes}&rdquo;
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex sm:flex-col items-center sm:items-end justify-between gap-2 shrink-0 pt-2 sm:pt-0 border-t sm:border-t-0 border-[#E8DCCF]">
                  <StatusBadge status={task.status} />
                  <span className="text-xs font-bold text-[#368F83] flex items-center gap-1">
                    <span>Open Task</span>
                    <span>&rarr;</span>
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
