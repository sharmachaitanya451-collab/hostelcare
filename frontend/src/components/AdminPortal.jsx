import { useState } from 'react'
import { StatusBadge, PriorityBadge } from './Brand'

export function AdminPortal({
  students,
  complaints,
  rooms,
  onUpdateStudentStatus,
  onUpdateComplaint,
  onLogout,
}) {
  const [activeTab, setActiveTab] = useState('overview') // 'overview', 'approvals', 'students', 'rooms', 'complaints'
  const [selectedComplaint, setSelectedComplaint] = useState(null)
  const [statusFilter, setStatusFilter] = useState('all')

  // Stats
  const totalStudents = students.length
  const pendingApprovals = students.filter((s) => s.status === 'pending')
  const openComplaints = complaints.filter((c) => c.status === 'open')
  const inProgressComplaints = complaints.filter((c) => c.status === 'in_progress')
  const resolvedComplaints = complaints.filter(
    (c) => c.status === 'resolved' || c.status === 'closed',
  )

  const filteredComplaints = complaints.filter((c) => {
    if (statusFilter === 'all') return true
    return c.status === statusFilter
  })

  return (
    <div className="min-h-screen bg-[#FBF7F0] flex flex-col md:flex-row">
      {/* --------------------------------------------------------------------- */}
      {/* Admin Sidebar Navigation                                              */}
      {/* --------------------------------------------------------------------- */}
      <aside className="w-full md:w-64 bg-[#1E172B] text-[#FFFCF7] flex flex-col shrink-0 md:sticky md:top-0 md:h-screen md:h-[100dvh] md:max-h-[100dvh] p-5 border-r border-[#342A4A] z-30">
        <div className="shrink-0">
          {/* Header */}
          <div className="pb-6 border-b border-[#342A4A] flex items-center justify-between">
            <div>
              <span className="font-serif text-xl font-bold text-[#FFFCF7]">
                Hostel<span className="text-[#F4AA35]">Care</span>
              </span>
              <p className="text-[11px] font-semibold text-[#D94378] tracking-wider uppercase mt-0.5">
                Administration Console
              </p>
            </div>
            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-[#D94378] text-white">
              Admin
            </span>
          </div>

          {/* Admin badge */}
          <div className="my-5 p-3.5 rounded-xl bg-[#282038] border border-[#3E3356] flex items-center gap-3">
            <div className="h-9 w-9 rounded-lg bg-[#F4AA35] text-[#292039] flex items-center justify-center font-bold text-sm">
              W
            </div>
            <div className="min-w-0">
              <h4 className="text-xs font-semibold text-white">Warden Desk</h4>
              <p className="text-[10px] text-[#D8CEBE]">Hostel Administration Wing A</p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto min-h-0 space-y-1.5 pt-2 pr-1">
          {[
            {
              id: 'overview',
              label: 'Admin Overview',
              icon: 'M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z',
            },
            {
              id: 'approvals',
              label: 'Registration Approvals',
              icon: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
              badge: pendingApprovals.length,
              badgeColor: 'bg-[#F4AA35] text-[#292039]',
            },
            {
              id: 'complaints',
              label: 'Complaint Queue',
              icon: 'M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10',
              badge: openComplaints.length,
              badgeColor: 'bg-[#D94378] text-white',
            },
            {
              id: 'students',
              label: 'Resident Directory',
              icon: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z',
            },
            {
              id: 'rooms',
              label: 'Room Occupancy Map',
              icon: 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4',
            },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => {
                setActiveTab(tab.id)
                setSelectedComplaint(null)
              }}
              className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                activeTab === tab.id
                  ? 'bg-[#D94378] text-[#FFFCF7] shadow-sm'
                  : 'text-[#D8CEBE] hover:bg-[#282038] hover:text-[#FFFCF7]'
              }`}
            >
              <div className="flex items-center gap-3">
                <svg
                  className="w-4 h-4 shrink-0"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d={tab.icon} />
                </svg>
                <span>{tab.label}</span>
              </div>
              {tab.badge !== undefined && tab.badge > 0 && (
                <span
                  className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${tab.badgeColor || 'bg-slate-700 text-white'}`}
                >
                  {tab.badge}
                </span>
              )}
            </button>
          ))}
        </nav>

        {/* Exit link */}
        <div className="mt-auto pt-4 border-t border-[#342A4A] shrink-0">
          <button
            onClick={onLogout}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-xs font-semibold text-[#D8CEBE] hover:text-white hover:bg-[#2E2442] transition-colors cursor-pointer border border-[#44365E]"
          >
            <span>Exit Administration</span>
          </button>
        </div>
      </aside>

      {/* --------------------------------------------------------------------- */}
      {/* Main Admin Screen                                                     */}
      {/* --------------------------------------------------------------------- */}
      <main className="flex-1 min-w-0 p-4 sm:p-8 lg:p-10 max-w-6xl">
        {/* =================================================================== */}
        {/* VIEW 1: OVERVIEW DASHBOARD                                          */}
        {/* =================================================================== */}
        {activeTab === 'overview' && (
          <div className="space-y-8">
            <div>
              <h1 className="font-serif text-3xl font-bold text-[#292039]">
                Hostel Operations Dashboard
              </h1>
              <p className="text-xs text-[#292039]/70 mt-1">
                Real-time snapshot of resident admissions, active maintenance duty roster, and room
                allocations.
              </p>
            </div>

            {/* Metrics cards */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5">
              <div className="bg-[#FFFCF7] p-5 rounded-2xl border border-[#E8DCCF] shadow-xs">
                <span className="text-xs text-[#292039]/60 font-medium">Registered Residents</span>
                <div className="font-serif text-3xl font-bold text-[#292039] mt-2">
                  {totalStudents}
                </div>
                <div className="text-[11px] text-[#368F83] font-semibold mt-1">
                  104 Rooms Active
                </div>
              </div>

              <div className="bg-[#FFFCF7] p-5 rounded-2xl border border-[#E8DCCF] shadow-xs">
                <span className="text-xs text-[#292039]/60 font-medium">Pending Approvals</span>
                <div className="font-serif text-3xl font-bold text-[#F4AA35] mt-2">
                  {pendingApprovals.length}
                </div>
                <div className="text-[11px] text-[#F4AA35] font-semibold mt-1">
                  Requires roll check
                </div>
              </div>

              <div className="bg-[#FFFCF7] p-5 rounded-2xl border border-[#E8DCCF] shadow-xs">
                <span className="text-xs text-[#292039]/60 font-medium">Open Maintenance</span>
                <div className="font-serif text-3xl font-bold text-[#D94378] mt-2">
                  {openComplaints.length + inProgressComplaints.length}
                </div>
                <div className="text-[11px] text-[#D94378] font-semibold mt-1">
                  {openComplaints.length} unassigned
                </div>
              </div>

              <div className="bg-[#FFFCF7] p-5 rounded-2xl border border-[#E8DCCF] shadow-xs">
                <span className="text-xs text-[#292039]/60 font-medium">Resolved (Term)</span>
                <div className="font-serif text-3xl font-bold text-[#368F83] mt-2">
                  {resolvedComplaints.length}
                </div>
                <div className="text-[11px] text-emerald-700 font-semibold mt-1">
                  98% closed within SLA
                </div>
              </div>
            </div>

            {/* Quick Action Alerts: Pending Approvals */}
            {pendingApprovals.length > 0 && (
              <div className="p-5 rounded-3xl bg-amber-50/90 border border-amber-300 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full bg-amber-500 animate-pulse" />
                    <h3 className="text-sm font-bold text-amber-900">
                      {pendingApprovals.length} Student Registration(s) Awaiting Warden Approval
                    </h3>
                  </div>
                  <p className="text-xs text-amber-800">
                    Verify applicant roll numbers against the Dean of Student Affairs allotment
                    register.
                  </p>
                </div>
                <button
                  onClick={() => setActiveTab('approvals')}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-[#292039] text-white hover:bg-[#3D3252] transition-colors shrink-0"
                >
                  Review Approvals &rarr;
                </button>
              </div>
            )}

            {/* Active Complaints Table */}
            <div className="bg-[#FFFCF7] p-6 rounded-3xl border border-[#E8DCCF] space-y-4 shadow-xs">
              <div className="flex items-center justify-between pb-3 border-b border-[#F0E4D4]">
                <div>
                  <h3 className="font-serif text-lg font-bold text-[#292039]">
                    Recent Maintenance Queue
                  </h3>
                  <p className="text-xs text-[#292039]/65">
                    Reviewing electrical, plumbing, and carpentry reports
                  </p>
                </div>
                <button
                  onClick={() => setActiveTab('complaints')}
                  className="text-xs font-semibold text-[#D94378] hover:underline"
                >
                  Manage All Tickets &rarr;
                </button>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-[#F0E4D4] text-[#292039]/60 font-semibold">
                      <th className="pb-2.5">ID</th>
                      <th className="pb-2.5">Room</th>
                      <th className="pb-2.5">Category</th>
                      <th className="pb-2.5">Title</th>
                      <th className="pb-2.5">Priority</th>
                      <th className="pb-2.5">Status</th>
                      <th className="pb-2.5 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#F7EFE6]">
                    {complaints.slice(0, 4).map((c) => (
                      <tr key={c.id} className="hover:bg-[#FDF9F3]">
                        <td className="py-3 font-mono font-bold text-[#292039]">{c.id}</td>
                        <td className="py-3 font-semibold text-[#D94378]">{c.room}</td>
                        <td className="py-3 text-[#368F83] font-medium">{c.category}</td>
                        <td className="py-3 font-medium text-[#292039] max-w-xs truncate">
                          {c.title}
                        </td>
                        <td className="py-3">
                          <PriorityBadge priority={c.priority} />
                        </td>
                        <td className="py-3">
                          <StatusBadge status={c.status} />
                        </td>
                        <td className="py-3 text-right">
                          <button
                            onClick={() => {
                              setSelectedComplaint(c)
                              setActiveTab('complaints')
                            }}
                            className="text-[#D94378] font-semibold hover:underline"
                          >
                            Inspect &rarr;
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* =================================================================== */}
        {/* VIEW 2: REGISTRATION APPROVALS                                      */}
        {/* =================================================================== */}
        {activeTab === 'approvals' && (
          <div className="space-y-6">
            <div className="pb-4 border-b border-[#F0E4D4]">
              <h2 className="font-serif text-2xl font-bold text-[#292039]">
                Pending Student Registrations
              </h2>
              <p className="text-xs text-[#292039]/70">
                Self-registered accounts requiring administrative approval before portal activation.
              </p>
            </div>

            {pendingApprovals.length === 0 ? (
              <div className="bg-[#FFFCF7] p-12 rounded-3xl border border-[#E8DCCF] text-center space-y-2">
                <span className="text-3xl">✓</span>
                <h3 className="font-serif text-lg font-bold text-[#292039]">
                  No Pending Registrations
                </h3>
                <p className="text-xs text-[#292039]/60">
                  All student accounts are verified and up to date.
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {pendingApprovals.map((stu) => (
                  <div
                    key={stu.id}
                    className="bg-[#FFFCF7] p-5 sm:p-6 rounded-3xl border border-[#E8DCCF] flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-bold text-[#D94378]">
                          {stu.rollNumber}
                        </span>
                        <StatusBadge status={stu.status} />
                      </div>
                      <h4 className="font-serif text-lg font-bold text-[#292039]">
                        {stu.fullName}
                      </h4>
                      <p className="text-xs text-[#292039]/70">
                        Requested Room: <strong>{stu.room}</strong> ({stu.block}, {stu.floor}) •
                        Phone: {stu.phone}
                      </p>
                      <p className="text-[11px] text-[#292039]/50">Applied on {stu.joinDate}</p>
                    </div>

                    <div className="flex items-center gap-2.5 self-end sm:self-auto">
                      <button
                        onClick={() => onUpdateStudentStatus(stu.id, 'rejected')}
                        className="px-4 py-2 rounded-xl text-xs font-semibold text-red-700 bg-red-50 hover:bg-red-100 border border-red-200 transition-colors"
                      >
                        Reject
                      </button>
                      <button
                        onClick={() => onUpdateStudentStatus(stu.id, 'active')}
                        className="px-5 py-2 rounded-xl text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 shadow-sm transition-colors"
                      >
                        Approve Student
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* =================================================================== */}
        {/* VIEW 3: COMPLAINT QUEUE MANAGEMENT                                  */}
        {/* =================================================================== */}
        {activeTab === 'complaints' && (
          <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#F0E4D4]">
              <div>
                <h2 className="font-serif text-2xl font-bold text-[#292039]">
                  Hostel Complaint Management
                </h2>
                <p className="text-xs text-[#292039]/70">
                  Assign duty staff, change status, and record technician notes
                </p>
              </div>

              {/* Status filter buttons */}
              <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
                {['all', 'open', 'in_progress', 'resolved', 'closed'].map((f) => (
                  <button
                    key={f}
                    onClick={() => {
                      setStatusFilter(f)
                      setSelectedComplaint(null)
                    }}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold capitalize whitespace-nowrap transition-colors ${
                      statusFilter === f
                        ? 'bg-[#292039] text-[#FFFCF7]'
                        : 'bg-[#F7EFE6] text-[#292039] hover:bg-[#EADBCA]'
                    }`}
                  >
                    {f.replace('_', ' ')}
                  </button>
                ))}
              </div>
            </div>

            {selectedComplaint ? (
              /* Selected Complaint Admin Action Panel */
              <div className="bg-[#FFFCF7] p-6 sm:p-8 rounded-3xl border border-[#E8DCCF] space-y-6">
                <div className="flex items-center justify-between pb-4 border-b border-[#F0E4D4]">
                  <button
                    onClick={() => setSelectedComplaint(null)}
                    className="text-xs font-semibold text-[#D94378] flex items-center gap-1 cursor-pointer"
                  >
                    <span>&larr;</span>
                    <span>Back to queue</span>
                  </button>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-[#292039]">
                      {selectedComplaint.id}
                    </span>
                    <StatusBadge status={selectedComplaint.status} />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <PriorityBadge priority={selectedComplaint.priority} />
                    <span className="text-xs font-semibold text-[#368F83]">
                      {selectedComplaint.category}
                    </span>
                    <span className="text-xs text-[#292039]/50">
                      • Room {selectedComplaint.room}
                    </span>
                  </div>
                  <h3 className="font-serif text-2xl font-bold text-[#292039]">
                    {selectedComplaint.title}
                  </h3>
                  <p className="text-xs text-[#292039]/65">
                    Reported by <strong>{selectedComplaint.reporterName}</strong> (
                    {selectedComplaint.reporterRoll}) on {selectedComplaint.dateSubmitted}
                  </p>
                </div>

                <div className="p-4 rounded-2xl bg-[#F7EFE6] border border-[#EADBCA] text-xs sm:text-sm text-[#292039]/85 leading-relaxed">
                  {selectedComplaint.description}
                </div>

                {/* Admin Actions: Update status & reassign staff */}
                <div className="p-5 rounded-2xl bg-amber-50/70 border border-amber-200/80 space-y-4">
                  <h4 className="font-serif text-base font-bold text-[#292039]">
                    Administrative Actions
                  </h4>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-semibold text-[#292039] mb-1">
                        Update Status
                      </label>
                      <select
                        value={selectedComplaint.status}
                        onChange={(e) => {
                          const updated = { ...selectedComplaint, status: e.target.value }
                          onUpdateComplaint(updated)
                          setSelectedComplaint(updated)
                        }}
                        className="w-full px-3 py-2 rounded-lg border border-amber-300 bg-[#FFFCF7] text-xs font-semibold text-[#292039]"
                      >
                        <option value="open">Open (Unassigned / Pending)</option>
                        <option value="in_progress">In Progress (Technician Assigned)</option>
                        <option value="resolved">Resolved (Work Completed)</option>
                        <option value="closed">Closed (Verified by Warden)</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-xs font-semibold text-[#292039] mb-1">
                        Assign Technician / Roster
                      </label>
                      <select
                        value={selectedComplaint.assignedStaff}
                        onChange={(e) => {
                          const updated = { ...selectedComplaint, assignedStaff: e.target.value }
                          onUpdateComplaint(updated)
                          setSelectedComplaint(updated)
                        }}
                        className="w-full px-3 py-2 rounded-lg border border-amber-300 bg-[#FFFCF7] text-xs font-semibold text-[#292039]"
                      >
                        <option value="Unassigned">Unassigned</option>
                        <option value="Ramesh Babu (Electrician)">
                          Ramesh Babu (Duty Electrician)
                        </option>
                        <option value="Santosh Kumar (Plumber)">
                          Santosh Kumar (Duty Plumber)
                        </option>
                        <option value="Hostel Carpentry & Metal Works">
                          Hostel Carpentry Team
                        </option>
                        <option value="Campus IT & Wi-Fi Cell">Campus IT Network Cell</option>
                        <option value="Sanitation & Housekeeping Staff">
                          Sanitation &amp; Housekeeping
                        </option>
                      </select>
                    </div>
                  </div>
                </div>

                {/* Complaint History Log */}
                <div className="space-y-3 pt-2">
                  <h4 className="font-serif text-base font-bold text-[#292039]">
                    Audit &amp; Dispatch Timeline
                  </h4>
                  <div className="space-y-2.5">
                    {selectedComplaint.history?.map((h, i) => (
                      <div
                        key={i}
                        className="flex items-start gap-3 text-xs border-l-2 border-[#368F83] pl-3 py-1"
                      >
                        <div>
                          <span className="font-bold text-[#292039]">{h.action}</span>
                          <span className="text-[11px] text-[#292039]/50 ml-2">({h.time})</span>
                          <p className="text-[#292039]/70 mt-0.5">
                            {h.note} — <em>{h.by}</em>
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              /* Complaints list */
              <div className="bg-[#FFFCF7] rounded-3xl border border-[#E8DCCF] divide-y divide-[#F0E4D4] overflow-hidden">
                {filteredComplaints.map((c) => (
                  <div
                    key={c.id}
                    onClick={() => setSelectedComplaint(c)}
                    className="p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-[#FDF9F3] transition-colors cursor-pointer"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-bold text-[#292039]">{c.id}</span>
                        <PriorityBadge priority={c.priority} />
                        <span className="text-xs text-[#368F83] font-semibold">{c.category}</span>
                        <span className="text-xs font-bold text-[#D94378] ml-1">Room {c.room}</span>
                      </div>
                      <h4 className="text-sm font-semibold text-[#292039]">{c.title}</h4>
                      <p className="text-xs text-[#292039]/65">
                        Resident: {c.reporterName} ({c.reporterRoll}) • Staff: {c.assignedStaff}
                      </p>
                    </div>

                    <div className="flex items-center gap-3 self-end sm:self-auto">
                      <StatusBadge status={c.status} />
                      <span className="text-xs font-semibold text-[#D94378]">&rarr;</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* =================================================================== */}
        {/* VIEW 4: RESIDENTS DIRECTORY                                         */}
        {/* =================================================================== */}
        {activeTab === 'students' && (
          <div className="space-y-6">
            <div className="pb-4 border-b border-[#F0E4D4]">
              <h2 className="font-serif text-2xl font-bold text-[#292039]">
                Resident Student Directory
              </h2>
              <p className="text-xs text-[#292039]/70">
                All verified and registered hostel boarders
              </p>
            </div>

            <div className="bg-[#FFFCF7] rounded-3xl border border-[#E8DCCF] overflow-hidden">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-[#F0E4D4] text-[#292039]/60 font-semibold bg-[#F7EFE6]/50">
                    <th className="p-4">Roll Number</th>
                    <th className="p-4">Student Name</th>
                    <th className="p-4">Room &amp; Block</th>
                    <th className="p-4">Contact</th>
                    <th className="p-4">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#F7EFE6]">
                  {students.map((stu) => (
                    <tr key={stu.id} className="hover:bg-[#FDF9F3]">
                      <td className="p-4 font-mono font-bold text-[#292039]">{stu.rollNumber}</td>
                      <td className="p-4 font-semibold text-[#292039]">{stu.fullName}</td>
                      <td className="p-4 font-semibold text-[#D94378]">
                        {stu.room} ({stu.block})
                      </td>
                      <td className="p-4 text-[#292039]/80">{stu.phone}</td>
                      <td className="p-4">
                        <StatusBadge status={stu.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* =================================================================== */}
        {/* VIEW 5: ROOM OCCUPANCY MAP                                          */}
        {/* =================================================================== */}
        {activeTab === 'rooms' && (
          <div className="space-y-6">
            <div className="pb-4 border-b border-[#F0E4D4]">
              <h2 className="font-serif text-2xl font-bold text-[#292039]">
                Hostel Room Occupancy Map
              </h2>
              <p className="text-xs text-[#292039]/70">
                Live occupancy count across Block A, Block B, and Block C
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {rooms.map((rm) => (
                <div
                  key={rm.id}
                  className="p-5 rounded-2xl bg-[#FFFCF7] border border-[#E8DCCF] space-y-3"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-serif text-lg font-bold text-[#292039]">{rm.id}</span>
                    <span
                      className={`text-[11px] font-bold px-2 py-0.5 rounded ${
                        rm.occupied === rm.capacity
                          ? 'bg-red-50 text-red-700'
                          : 'bg-emerald-50 text-emerald-700'
                      }`}
                    >
                      {rm.occupied}/{rm.capacity} Beds
                    </span>
                  </div>
                  <div className="text-[11px] text-[#292039]/65">
                    {rm.block} • {rm.floor}
                  </div>
                  <div className="pt-2 border-t border-[#F0E4D4] text-[11px] space-y-1 text-[#292039]/80">
                    <p className="font-medium text-[#292039]/60">Allotted Residents:</p>
                    {rm.students.map((name, i) => (
                      <p key={i} className="truncate">
                        • {name}
                      </p>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
