import { Link, useNavigate } from 'react-router-dom'
import { isComplaintOwnedByStudent, useApp } from '../../context/AppContext'
import { StatusBadge, PriorityBadge } from '../../components/Brand'

export function StudentDashboardPage() {
  const { user, complaints } = useApp()
  const navigate = useNavigate()

  // Complaints belonging strictly to the logged-in student
  const studentComplaints = complaints.filter((c) => isComplaintOwnedByStudent(c, user))

  const totalComplaintsCount = studentComplaints.length

  const pendingComplaintsCount = studentComplaints.filter(
    (c) =>
      c.status === 'Submitted' ||
      c.status === 'Under Review' ||
      c.status === 'Assigned' ||
      c.status === 'open',
  ).length

  const inProgressComplaintsCount = studentComplaints.filter(
    (c) => c.status === 'In Progress' || c.status === 'in_progress',
  ).length

  const resolvedComplaintsCount = studentComplaints.filter(
    (c) =>
      c.status === 'Resolved' ||
      c.status === 'Closed' ||
      c.status === 'resolved' ||
      c.status === 'closed',
  ).length

  return (
    <div className="space-y-8">
      {/* Welcome Banner */}
      <div className="bg-gradient-to-r from-[#292039] to-[#3B2C52] text-[#FFFCF7] p-6 sm:p-8 rounded-3xl shadow-sm border border-[#4F3E6B] flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        <div className="space-y-2">
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-[#368F83]/30 text-emerald-300 text-xs font-semibold">
            <span className="h-2 w-2 rounded-full bg-emerald-400" />
            Resident Status: Verified &amp; Active
          </div>
          <h1 className="font-serif text-2xl sm:text-3xl font-bold">Namaste, {user?.fullName}</h1>
          <p className="text-xs sm:text-sm text-[#D8CEBE] max-w-xl">
            Room {user?.room} • {user?.block}, {user?.floor}. You have{' '}
            <strong>{pendingComplaintsCount + inProgressComplaintsCount} active</strong> maintenance
            ticket(s) in progress.
          </p>
        </div>

        <Link
          to="/student/complaints/new"
          className="px-4 py-2.5 rounded-xl text-xs sm:text-sm font-semibold bg-[#D94378] hover:bg-[#C23365] text-white shadow-md shadow-[#D94378]/25 transition-all flex items-center gap-1.5 shrink-0"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
          </svg>
          <span>Submit Complaint</span>
        </Link>
      </div>

      {/* Metrics Cards: Total, Pending, In-Progress, Resolved */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-[#FFFCF7] p-4 rounded-2xl border border-[#E8DCCF] shadow-xs">
          <span className="text-xs text-[#292039]/70 font-medium">Total Complaints</span>
          <div className="font-serif text-2xl font-bold text-[#292039] mt-1">
            {totalComplaintsCount}
          </div>
          <div className="text-[11px] text-[#292039]/60 font-medium mt-1">
            Historical tickets filed
          </div>
        </div>

        <div className="bg-[#FFFCF7] p-4 rounded-2xl border border-[#E8DCCF] shadow-xs">
          <span className="text-xs text-[#292039]/70 font-medium">Pending Review / Assigned</span>
          <div className="font-serif text-2xl font-bold text-amber-600 mt-1">
            {pendingComplaintsCount}
          </div>
          <div className="text-[11px] text-amber-800 font-medium mt-1">
            Awaiting technician start
          </div>
        </div>

        <div className="bg-[#FFFCF7] p-4 rounded-2xl border border-[#E8DCCF] shadow-xs">
          <span className="text-xs text-[#292039]/70 font-medium">Work In-Progress</span>
          <div className="font-serif text-2xl font-bold text-[#368F83] mt-1">
            {inProgressComplaintsCount}
          </div>
          <div className="text-[11px] text-teal-800 font-medium mt-1">
            Repairs actively underway
          </div>
        </div>

        <div className="bg-[#FFFCF7] p-4 rounded-2xl border border-[#E8DCCF] shadow-xs">
          <span className="text-xs text-[#292039]/70 font-medium">Resolved / Completed</span>
          <div className="font-serif text-2xl font-bold text-emerald-600 mt-1">
            {resolvedComplaintsCount}
          </div>
          <div className="text-[11px] text-emerald-700 font-medium mt-1">
            Repairs finished &amp; verified
          </div>
        </div>
      </div>

      {/* Recently Updated Complaints & Assigned Staff Visibility */}
      <div className="bg-[#FFFCF7] p-6 rounded-3xl border border-[#E8DCCF] shadow-xs space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-[#F0E4D4]">
          <div>
            <h2 className="font-serif text-lg font-bold text-[#292039]">
              Recently Updated Room Maintenance
            </h2>
            <p className="text-xs text-[#292039]/70">
              Live tracking and technician visibility for your room
            </p>
          </div>
          <Link
            to="/student/complaints"
            className="text-xs font-semibold text-[#D94378] hover:underline"
          >
            View All ({totalComplaintsCount}) &rarr;
          </Link>
        </div>

        {studentComplaints.length === 0 ? (
          <div className="text-center py-8 text-xs text-[#292039]/60">
            No complaints logged yet. Everything in {user?.room} is in order!
          </div>
        ) : (
          <div className="divide-y divide-[#F7EFE6]">
            {studentComplaints.slice(0, 4).map((item) => (
              <div
                key={item.id}
                onClick={() => navigate(`/student/complaints/${item.id}`)}
                className="py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-[#FFFDF9] px-2 rounded-xl transition-colors cursor-pointer"
              >
                <div className="space-y-1.5 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-mono font-bold text-[#292039]">{item.id}</span>
                    <PriorityBadge priority={item.priority} />
                    <span className="text-xs text-[#292039]/70 font-medium">({item.category})</span>
                  </div>
                  <h3 className="text-sm font-semibold text-[#292039]">{item.title}</h3>
                  <p className="text-xs text-[#292039]/65 line-clamp-1">{item.description}</p>

                  {/* Assigned Staff Visibility */}
                  <div className="flex flex-wrap items-center gap-3 text-[11px] text-[#292039]/70 pt-0.5">
                    <span>Date: {item.dateSubmitted}</span>
                    {item.assignedStaff && item.assignedStaff !== 'Unassigned' ? (
                      <span className="text-[#368F83] font-semibold flex items-center gap-1">
                        <span>👷 Assigned:</span>
                        <span>{item.assignedStaff}</span>
                        {item.assignedStaffRole && <span>({item.assignedStaffRole})</span>}
                      </span>
                    ) : (
                      <span className="text-amber-700 italic">
                        ⏳ Awaiting technician assignment
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-3 shrink-0">
                  <StatusBadge status={item.status} />
                  <span className="text-xs text-[#D94378] font-semibold hidden sm:inline">
                    &rarr;
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Quick Action Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Link
          to="/student/room"
          className="p-5 rounded-2xl bg-[#F7EFE6] border border-[#E5D7C5] hover:border-[#D94378]/40 transition-colors flex items-center justify-between"
        >
          <div>
            <h3 className="font-semibold text-sm text-[#292039]">
              View Roommate &amp; Bed Details
            </h3>
            <p className="text-xs text-[#292039]/70 mt-0.5">
              Check inventory checklist and room allotment record
            </p>
          </div>
          <span className="text-base text-[#D94378]">&rarr;</span>
        </Link>

        <Link
          to="/student/fines"
          className="p-5 rounded-2xl bg-[#F7EFE6] border border-[#E5D7C5] hover:border-[#D94378]/40 transition-colors flex items-center justify-between"
        >
          <div>
            <h3 className="font-semibold text-sm text-[#292039]">
              Check Disciplinary &amp; Fine Dues
            </h3>
            <p className="text-xs text-[#292039]/70 mt-0.5">
              View outstanding penalty notices and settlement receipts
            </p>
          </div>
          <span className="text-base text-[#D94378]">&rarr;</span>
        </Link>
      </div>
    </div>
  )
}
