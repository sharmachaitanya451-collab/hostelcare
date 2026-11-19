import { useState } from 'react'
import { isComplaintOwnedByStudent } from '../context/AppContext'
import { StatusBadge, PriorityBadge } from './Brand'

export function StudentPortal({ student, complaints, onAddComplaint, onLogout }) {
  const [activeTab, setActiveTab] = useState('dashboard') // 'dashboard', 'my-room', 'complaints', 'submit-complaint', 'profile'
  const [selectedComplaint, setSelectedComplaint] = useState(null)

  // Form state for new complaint
  const [newTitle, setNewTitle] = useState('')
  const [newCategory, setNewCategory] = useState('Electrical')
  const [newPriority, setNewPriority] = useState('Medium')
  const [newDesc, setNewDesc] = useState('')
  const [photoCount, setPhotoCount] = useState(0)
  const [submitSuccess, setSubmitSuccess] = useState(false)

  // Complaints submitted strictly by this student
  const studentComplaints = complaints.filter((c) => isComplaintOwnedByStudent(c, student))

  const openComplaintsCount = studentComplaints.filter(
    (c) => c.status === 'open' || c.status === 'in_progress',
  ).length
  const resolvedCount = studentComplaints.filter(
    (c) => c.status === 'resolved' || c.status === 'closed',
  ).length

  const handleComplaintSubmit = (e) => {
    e.preventDefault()
    if (!newTitle.trim() || !newDesc.trim()) return

    const newObj = {
      id: `CMP-2026-0${Math.floor(100 + Math.random() * 900)}`,
      title: newTitle.trim(),
      category: newCategory,
      priority: newPriority,
      status: 'open',
      reporterName: student.fullName,
      reporterRoll: student.rollNumber,
      room: student.room,
      dateSubmitted: '14/11/2026',
      description: newDesc.trim(),
      assignedStaff: 'Unassigned',
      assignedDate: null,
      attachments: photoCount,
      history: [
        {
          action: 'Submitted',
          by: student.fullName,
          time: '14/11/2026, Just now',
          note: 'Submitted by student resident through portal',
        },
      ],
    }

    onAddComplaint(newObj)
    setSubmitSuccess(true)
    setNewTitle('')
    setNewDesc('')
    setPhotoCount(0)
    setTimeout(() => {
      setSubmitSuccess(false)
      setActiveTab('complaints')
    }, 1200)
  }

  return (
    <div className="min-h-screen bg-[#FDF9F3] flex flex-col md:flex-row">
      {/* --------------------------------------------------------------------- */}
      {/* Sidebar Navigation                                                    */}
      {/* --------------------------------------------------------------------- */}
      <aside className="w-full md:w-64 bg-[#292039] text-[#FFFCF7] flex flex-col shrink-0 md:sticky md:top-0 md:h-screen md:h-[100dvh] md:max-h-[100dvh] p-5 border-r border-[#44375A] z-30">
        <div className="shrink-0">
          {/* Brand header */}
          <div className="pb-6 border-b border-[#3D3252] flex items-center justify-between">
            <div>
              <span className="font-serif text-xl font-bold text-[#FFFCF7]">
                Hostel<span className="text-[#D94378]">Care</span>
              </span>
              <p className="text-[11px] font-medium text-[#F4AA35] tracking-wider uppercase mt-0.5">
                Resident Portal
              </p>
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#3D3252] text-[#D8CEBE]">
              v0.1
            </span>
          </div>

          {/* Student Quick Card */}
          <div className="my-5 p-3.5 rounded-xl bg-[#372B4D] border border-[#52416F] flex items-center gap-3">
            <div
              className={`h-10 w-10 rounded-lg ${student.avatarColor} text-white flex items-center justify-center font-bold text-sm shrink-0`}
            >
              {student.fullName.charAt(0)}
            </div>
            <div className="min-w-0">
              <h4 className="text-xs font-semibold text-white truncate">{student.fullName}</h4>
              <p className="text-[11px] font-mono text-[#D8CEBE]">
                {student.room} • {student.rollNumber}
              </p>
            </div>
          </div>
        </div>

        {/* Navigation Links */}
        <nav className="flex-1 overflow-y-auto min-h-0 space-y-1.5 pt-2 pr-1">
          {[
            {
              id: 'dashboard',
              label: 'Dashboard',
              icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6',
            },
            {
              id: 'my-room',
              label: 'My Room & Allotment',
              icon: 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4',
            },
            {
              id: 'submit-complaint',
              label: 'Submit Maintenance',
              icon: 'M12 9v3m0 0v3m0-3h3m-3 0H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z',
            },
            {
              id: 'complaints',
              label: 'My Complaints',
              icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4',
              badge: openComplaintsCount,
            },
            {
              id: 'profile',
              label: 'Student Profile',
              icon: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z',
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
                  : 'text-[#D8CEBE] hover:bg-[#372B4D] hover:text-[#FFFCF7]'
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
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#F4AA35] text-[#292039]">
                  {tab.badge}
                </span>
              )}
            </button>
          ))}
        </nav>

        {/* Logout and Footer */}
        <div className="mt-auto pt-4 border-t border-[#3D3252] space-y-3 shrink-0">
          <div className="px-3 py-2 rounded-lg bg-[#372B4D]/60 text-[11px] text-[#A89CBF]">
            <p className="font-semibold text-[#F4AA35]">Warden Helpdesk:</p>
            <p>Admin Wing A, Ext: 204</p>
          </div>
          <button
            onClick={onLogout}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-xs font-semibold text-[#D8CEBE] hover:text-white hover:bg-[#3D3252] transition-colors cursor-pointer border border-[#4E3F68]"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
              />
            </svg>
            <span>Exit Portal</span>
          </button>
        </div>
      </aside>

      {/* --------------------------------------------------------------------- */}
      {/* Main Content Area                                                     */}
      {/* --------------------------------------------------------------------- */}
      <main className="flex-1 min-w-0 p-4 sm:p-8 lg:p-10 max-w-6xl">
        {/* =================================================================== */}
        {/* VIEW 1: DASHBOARD                                                   */}
        {/* =================================================================== */}
        {activeTab === 'dashboard' && (
          <div className="space-y-8">
            {/* Top Welcome Banner */}
            <div className="bg-gradient-to-r from-[#292039] to-[#3B2C52] text-[#FFFCF7] p-6 sm:p-8 rounded-3xl shadow-sm border border-[#4F3E6B] flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
              <div className="space-y-2">
                <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-[#368F83]/30 text-emerald-300 text-xs font-semibold">
                  <span className="h-2 w-2 rounded-full bg-emerald-400" />
                  Resident Status: Verified &amp; Active
                </div>
                <h1 className="font-serif text-2xl sm:text-3xl font-bold">
                  Namaste, {student.fullName}
                </h1>
                <p className="text-xs sm:text-sm text-[#D8CEBE] max-w-xl">
                  Room {student.room} • {student.block}, {student.floor}. You have{' '}
                  <strong>{openComplaintsCount} active</strong> maintenance ticket(s) in progress.
                </p>
              </div>

              <div className="flex gap-3">
                <button
                  onClick={() => setActiveTab('submit-complaint')}
                  className="px-4 py-2.5 rounded-xl text-xs sm:text-sm font-semibold bg-[#D94378] hover:bg-[#C23365] text-white shadow-md shadow-[#D94378]/25 transition-all cursor-pointer flex items-center gap-1.5"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2"
                      d="M12 4v16m8-8H4"
                    />
                  </svg>
                  <span>New Complaint</span>
                </button>
              </div>
            </div>

            {/* Quick Metrics Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
              <div className="bg-[#FFFCF7] p-5 rounded-2xl border border-[#E8DCCF] shadow-xs">
                <span className="text-xs text-[#292039]/70 font-medium">
                  Assigned Accommodation
                </span>
                <div className="font-serif text-2xl font-bold text-[#292039] mt-1">
                  {student.room}
                </div>
                <div className="text-xs text-[#368F83] font-medium mt-1">
                  Double Occupancy • {student.bed}
                </div>
              </div>

              <div className="bg-[#FFFCF7] p-5 rounded-2xl border border-[#E8DCCF] shadow-xs">
                <span className="text-xs text-[#292039]/70 font-medium">Active Maintenance</span>
                <div className="font-serif text-2xl font-bold text-[#F4AA35] mt-1">
                  {openComplaintsCount}
                </div>
                <div className="text-xs text-[#292039]/60 font-medium mt-1">
                  {openComplaintsCount > 0
                    ? 'Under technician review'
                    : 'No pending issues in room'}
                </div>
              </div>

              <div className="bg-[#FFFCF7] p-5 rounded-2xl border border-[#E8DCCF] shadow-xs">
                <span className="text-xs text-[#292039]/70 font-medium">Resolved This Term</span>
                <div className="font-serif text-2xl font-bold text-[#368F83] mt-1">
                  {resolvedCount}
                </div>
                <div className="text-xs text-emerald-700 font-medium mt-1">
                  Logged &amp; verified fixed
                </div>
              </div>
            </div>

            {/* Recent Complaints Section */}
            <div className="bg-[#FFFCF7] p-6 rounded-3xl border border-[#E8DCCF] shadow-xs space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-[#F0E4D4]">
                <div>
                  <h3 className="font-serif text-lg font-bold text-[#292039]">
                    Recent Room Maintenance
                  </h3>
                  <p className="text-xs text-[#292039]/70">Track repair stages for your room</p>
                </div>
                <button
                  onClick={() => setActiveTab('complaints')}
                  className="text-xs font-semibold text-[#D94378] hover:underline"
                >
                  View All &rarr;
                </button>
              </div>

              {studentComplaints.length === 0 ? (
                <div className="text-center py-8 text-xs text-[#292039]/60">
                  No complaints logged yet. Everything in {student.room} is running smoothly!
                </div>
              ) : (
                <div className="divide-y divide-[#F7EFE6]">
                  {studentComplaints.slice(0, 3).map((item) => (
                    <div
                      key={item.id}
                      onClick={() => {
                        setSelectedComplaint(item)
                        setActiveTab('complaints')
                      }}
                      className="py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-[#FDF9F3] px-2 rounded-xl transition-colors cursor-pointer"
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-mono font-bold text-[#292039]">
                            {item.id}
                          </span>
                          <PriorityBadge priority={item.priority} />
                          <span className="text-xs text-[#292039]/60 font-medium">
                            ({item.category})
                          </span>
                        </div>
                        <h4 className="text-sm font-semibold text-[#292039]">{item.title}</h4>
                        <p className="text-xs text-[#292039]/65">
                          Submitted: {item.dateSubmitted} • Assigned: {item.assignedStaff}
                        </p>
                      </div>

                      <div className="flex items-center gap-3">
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

            {/* Quick Actions Row */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div
                onClick={() => setActiveTab('my-room')}
                className="p-5 rounded-2xl bg-[#F7EFE6] border border-[#E5D7C5] hover:border-[#D94378]/40 transition-colors cursor-pointer flex items-center justify-between"
              >
                <div>
                  <h4 className="font-semibold text-sm text-[#292039]">
                    View Roommate &amp; Bed Details
                  </h4>
                  <p className="text-xs text-[#292039]/70 mt-0.5">
                    Check inventory checklist and room allotment record
                  </p>
                </div>
                <span className="text-base text-[#D94378]">&rarr;</span>
              </div>

              <div
                onClick={() => setActiveTab('submit-complaint')}
                className="p-5 rounded-2xl bg-[#F7EFE6] border border-[#E5D7C5] hover:border-[#D94378]/40 transition-colors cursor-pointer flex items-center justify-between"
              >
                <div>
                  <h4 className="font-semibold text-sm text-[#292039]">
                    Report Urgent Electrical / Water Issue
                  </h4>
                  <p className="text-xs text-[#292039]/70 mt-0.5">
                    Dispatches to morning hostel repair duty roster
                  </p>
                </div>
                <span className="text-base text-[#D94378]">&rarr;</span>
              </div>
            </div>
          </div>
        )}

        {/* =================================================================== */}
        {/* VIEW 2: MY ROOM & ALLOTMENT                                         */}
        {/* =================================================================== */}
        {activeTab === 'my-room' && (
          <div className="space-y-6">
            <div className="pb-4 border-b border-[#F0E4D4]">
              <h2 className="font-serif text-2xl font-bold text-[#292039]">
                My Room &amp; Allotment
              </h2>
              <p className="text-xs text-[#292039]/70">
                Room details, inventory checklist &amp; co-resident information
              </p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Room Badge Card */}
              <div className="bg-[#FFFCF7] p-6 rounded-3xl border border-[#E8DCCF] space-y-4">
                <span className="text-xs font-bold text-[#368F83] uppercase tracking-wider">
                  Allotment Token
                </span>
                <div className="font-serif text-4xl font-bold text-[#292039]">{student.room}</div>
                <div className="space-y-2 text-xs text-[#292039]/80 pt-2 border-t border-[#F0E4D4]">
                  <p>
                    <strong>Hostel Block:</strong> {student.block} (Nalanda)
                  </p>
                  <p>
                    <strong>Floor:</strong> {student.floor}
                  </p>
                  <p>
                    <strong>Bed Position:</strong> {student.bed}
                  </p>
                  <p>
                    <strong>Tenure Start:</strong> {student.joinDate}
                  </p>
                </div>
              </div>

              {/* Roommate details */}
              <div className="bg-[#FFFCF7] p-6 rounded-3xl border border-[#E8DCCF] space-y-4">
                <span className="text-xs font-bold text-[#D94378] uppercase tracking-wider">
                  Co-Resident / Roommate
                </span>
                <div className="flex items-center gap-3 pt-1">
                  <div className="h-10 w-10 rounded-xl bg-[#368F83] text-white font-bold flex items-center justify-center">
                    R
                  </div>
                  <div>
                    <h4 className="font-semibold text-sm text-[#292039]">Rohan Kulkarni</h4>
                    <p className="text-xs font-mono text-[#292039]/60">2023CSB1058</p>
                  </div>
                </div>
                <div className="space-y-1.5 text-xs text-[#292039]/75 pt-3 border-t border-[#F0E4D4]">
                  <p>
                    <strong>Bed Position:</strong> Bed 2 (Door side)
                  </p>
                  <p>
                    <strong>Contact:</strong> +91 98112 33445
                  </p>
                  <p>
                    <strong>Emergency:</strong> Parent Contact on file
                  </p>
                </div>
              </div>

              {/* Standard Room Inventory Checklist */}
              <div className="bg-[#FFFCF7] p-6 rounded-3xl border border-[#E8DCCF] space-y-4">
                <span className="text-xs font-bold text-[#F4AA35] uppercase tracking-wider">
                  Furniture &amp; Fixtures
                </span>
                <ul className="text-xs space-y-2 text-[#292039]/80">
                  <li className="flex items-center justify-between">
                    <span>Wooden Single Beds</span>
                    <span className="font-semibold">02 nos.</span>
                  </li>
                  <li className="flex items-center justify-between">
                    <span>Steel Study Tables &amp; Chairs</span>
                    <span className="font-semibold">02 pairs</span>
                  </li>
                  <li className="flex items-center justify-between">
                    <span>Steel Built-in Almirah</span>
                    <span className="font-semibold">02 bays</span>
                  </li>
                  <li className="flex items-center justify-between">
                    <span>Ceiling Fan (Orient 1200mm)</span>
                    <span className="font-semibold">01 no.</span>
                  </li>
                  <li className="flex items-center justify-between">
                    <span>LED Tube Light Fixtures</span>
                    <span className="font-semibold">02 nos.</span>
                  </li>
                </ul>
              </div>
            </div>

            {/* Room Maintenance Policy Box */}
            <div className="p-5 rounded-2xl bg-[#F7EFE6] border border-[#E5D7C5] text-xs text-[#292039]/80 space-y-2">
              <h4 className="font-semibold text-sm text-[#292039]">
                Room Inspection &amp; Maintenance Policy:
              </h4>
              <p>
                Hostel wardens and authorized maintenance staff conduct scheduled safety checks on
                electrical outlets once each quarter. Heavy appliances such as room immersion
                heaters, induction cooktops, and electric kettles above 1000W are strictly
                prohibited under college hostel rules to prevent electrical overloading.
              </p>
            </div>
          </div>
        )}

        {/* =================================================================== */}
        {/* VIEW 3: SUBMIT COMPLAINT                                            */}
        {/* =================================================================== */}
        {activeTab === 'submit-complaint' && (
          <div className="space-y-6 max-w-2xl">
            <div className="pb-4 border-b border-[#F0E4D4]">
              <h2 className="font-serif text-2xl font-bold text-[#292039]">
                Submit Maintenance Complaint
              </h2>
              <p className="text-xs text-[#292039]/70">
                Log a repair request for Room {student.room}. Our warden desk will assign the duty
                technician.
              </p>
            </div>

            {submitSuccess && (
              <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-300 text-emerald-800 text-xs font-semibold flex items-center gap-2">
                <span className="text-base">✓</span>
                <span>Complaint submitted successfully! Redirecting to tracking...</span>
              </div>
            )}

            <form
              onSubmit={handleComplaintSubmit}
              className="bg-[#FFFCF7] p-6 sm:p-8 rounded-3xl border border-[#E8DCCF] shadow-xs space-y-5"
            >
              <div>
                <label className="block text-xs font-semibold text-[#292039] mb-1.5">
                  Complaint Title *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Washbasin cold water tap dripping continuously"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#D94378] bg-[#FFFCF7]"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-[#292039] mb-1.5">
                    Category *
                  </label>
                  <select
                    value={newCategory}
                    onChange={(e) => setNewCategory(e.target.value)}
                    className="w-full px-3.5 py-2.5 rounded-xl border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#D94378] bg-[#FFFCF7]"
                  >
                    <option value="Electrical">Electrical (Fan, Light, Switchboard)</option>
                    <option value="Plumbing">Plumbing (Tap, Pipe, Washroom)</option>
                    <option value="Furniture">Furniture (Bed, Table, Almirah)</option>
                    <option value="Carpentry & Glass">Carpentry &amp; Glass (Door, Window)</option>
                    <option value="Internet & Wi-Fi">Internet &amp; Campus Wi-Fi</option>
                    <option value="Housekeeping">Housekeeping &amp; Pest Control</option>
                    <option value="Other">Other / General Maintenance</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-[#292039] mb-1.5">
                    Suggested Priority *
                  </label>
                  <select
                    value={newPriority}
                    onChange={(e) => setNewPriority(e.target.value)}
                    className="w-full px-3.5 py-2.5 rounded-xl border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#D94378] bg-[#FFFCF7]"
                  >
                    <option value="Low">Low (Routine, non-disruptive)</option>
                    <option value="Medium">Medium (Impacting daily study)</option>
                    <option value="High">High (Urgent: water leak, sparks, no light)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#292039] mb-1.5">
                  Detailed Description *
                </label>
                <textarea
                  rows={4}
                  required
                  placeholder="Describe the issue clearly, including when it started and exact symptoms..."
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#D94378] bg-[#FFFCF7]"
                />
              </div>

              {/* Photos Attachment Mock (Max 3) */}
              <div>
                <label className="block text-xs font-semibold text-[#292039] mb-1">
                  Photo Attachments (Optional, max 3 photos)
                </label>
                <p className="text-[11px] text-[#292039]/60 mb-2">
                  Clear pictures of damaged hinges, water leak points, or burnt switches help
                  technicians bring the correct spare parts.
                </p>

                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={() => setPhotoCount(Math.min(3, photoCount + 1))}
                    className="px-4 py-2 rounded-xl text-xs font-semibold text-[#292039] bg-[#F7EFE6] border border-[#D8CEBE] hover:bg-[#EFE3D5] cursor-pointer flex items-center gap-1.5"
                  >
                    <span>📷</span>
                    <span>Attach Photo ({photoCount}/3)</span>
                  </button>
                  {photoCount > 0 && (
                    <button
                      type="button"
                      onClick={() => setPhotoCount(0)}
                      className="text-xs text-red-600 hover:underline"
                    >
                      Clear attachments
                    </button>
                  )}
                </div>
              </div>

              <div className="pt-2 flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setActiveTab('dashboard')}
                  className="px-5 py-2.5 rounded-xl text-xs font-semibold text-[#292039] hover:bg-[#F7EFE6] transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-6 py-2.5 rounded-xl text-xs font-semibold text-white bg-[#D94378] hover:bg-[#C23365] shadow-md shadow-[#D94378]/25 transition-all cursor-pointer"
                >
                  Submit Complaint
                </button>
              </div>
            </form>
          </div>
        )}

        {/* =================================================================== */}
        {/* VIEW 4: MY COMPLAINTS LIST & DETAIL                                 */}
        {/* =================================================================== */}
        {activeTab === 'complaints' && (
          <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#F0E4D4]">
              <div>
                <h2 className="font-serif text-2xl font-bold text-[#292039]">
                  My Maintenance Complaints
                </h2>
                <p className="text-xs text-[#292039]/70">
                  Historical and active maintenance tickets for Room {student.room}
                </p>
              </div>
              <button
                onClick={() => setActiveTab('submit-complaint')}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-[#D94378] text-white hover:bg-[#C23365] transition-colors self-start sm:self-auto cursor-pointer"
              >
                + New Complaint
              </button>
            </div>

            {selectedComplaint ? (
              /* Complaint Details View */
              <div className="bg-[#FFFCF7] p-6 sm:p-8 rounded-3xl border border-[#E8DCCF] space-y-6">
                <div className="flex items-center justify-between pb-4 border-b border-[#F0E4D4]">
                  <button
                    onClick={() => setSelectedComplaint(null)}
                    className="text-xs font-semibold text-[#D94378] flex items-center gap-1 cursor-pointer"
                  >
                    <span>&larr;</span>
                    <span>Back to all complaints</span>
                  </button>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono font-bold text-[#292039]">
                      {selectedComplaint.id}
                    </span>
                    <StatusBadge status={selectedComplaint.status} />
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <PriorityBadge priority={selectedComplaint.priority} />
                    <span className="text-xs font-semibold text-[#368F83]">
                      {selectedComplaint.category}
                    </span>
                  </div>
                  <h3 className="font-serif text-2xl font-bold text-[#292039]">
                    {selectedComplaint.title}
                  </h3>
                  <p className="text-xs text-[#292039]/60">
                    Logged on {selectedComplaint.dateSubmitted} for {selectedComplaint.room}
                  </p>
                </div>

                <div className="p-4 rounded-2xl bg-[#F7EFE6] border border-[#EADBCA] text-xs sm:text-sm text-[#292039]/85 leading-relaxed">
                  {selectedComplaint.description}
                </div>

                {/* Technician Assignment Card */}
                <div className="p-4 rounded-2xl border border-[#E8DCCF] bg-[#FFFCF7] grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                  <div>
                    <span className="text-[#292039]/60">Assigned Technician:</span>
                    <p className="font-semibold text-[#292039] text-sm mt-0.5">
                      {selectedComplaint.assignedStaff}
                    </p>
                  </div>
                  <div>
                    <span className="text-[#292039]/60">Resolution Status:</span>
                    <p className="font-semibold text-[#368F83] text-sm mt-0.5">
                      {selectedComplaint.status === 'resolved' ||
                      selectedComplaint.status === 'closed'
                        ? `Resolved on ${selectedComplaint.resolvedDate}`
                        : 'Repair in progress'}
                    </p>
                  </div>
                </div>

                {/* Audit Trail / History */}
                <div className="space-y-3 pt-2">
                  <h4 className="font-serif text-base font-bold text-[#292039]">
                    Complaint Activity Log
                  </h4>
                  <div className="space-y-3">
                    {selectedComplaint.history?.map((h, i) => (
                      <div
                        key={i}
                        className="flex items-start gap-3 text-xs border-l-2 border-[#D94378] pl-3 py-1"
                      >
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-[#292039]">{h.action}</span>
                            <span className="text-[11px] text-[#292039]/50">({h.time})</span>
                          </div>
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
              /* Complaints Table / List */
              <div className="bg-[#FFFCF7] rounded-3xl border border-[#E8DCCF] overflow-hidden">
                <div className="divide-y divide-[#F0E4D4]">
                  {studentComplaints.map((c) => (
                    <div
                      key={c.id}
                      onClick={() => setSelectedComplaint(c)}
                      className="p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-[#FDF9F3] transition-colors cursor-pointer"
                    >
                      <div className="space-y-1.5">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs font-bold text-[#292039]">{c.id}</span>
                          <PriorityBadge priority={c.priority} />
                          <span className="text-xs text-[#368F83] font-medium">{c.category}</span>
                        </div>
                        <h4 className="text-sm font-semibold text-[#292039]">{c.title}</h4>
                        <p className="text-xs text-[#292039]/65">
                          Submitted {c.dateSubmitted} • Assigned to {c.assignedStaff}
                        </p>
                      </div>

                      <div className="flex items-center gap-3 self-end sm:self-auto">
                        <StatusBadge status={c.status} />
                        <span className="text-xs font-semibold text-[#D94378]">&rarr;</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* =================================================================== */}
        {/* VIEW 5: STUDENT PROFILE                                             */}
        {/* =================================================================== */}
        {activeTab === 'profile' && (
          <div className="space-y-6 max-w-2xl">
            <div className="pb-4 border-b border-[#F0E4D4]">
              <h2 className="font-serif text-2xl font-bold text-[#292039]">
                Student Profile Record
              </h2>
              <p className="text-xs text-[#292039]/70">
                Official resident credentials verified by hostel administration
              </p>
            </div>

            <div className="bg-[#FFFCF7] p-6 sm:p-8 rounded-3xl border border-[#E8DCCF] space-y-6">
              <div className="flex items-center gap-4 pb-6 border-b border-[#F0E4D4]">
                <div
                  className={`h-16 w-16 rounded-2xl ${student.avatarColor} text-white font-bold text-2xl flex items-center justify-center`}
                >
                  {student.fullName.charAt(0)}
                </div>
                <div>
                  <h3 className="font-serif text-xl font-bold text-[#292039]">
                    {student.fullName}
                  </h3>
                  <p className="text-xs font-mono text-[#D94378] font-bold mt-0.5">
                    {student.rollNumber}
                  </p>
                  <div className="mt-1.5">
                    <StatusBadge status={student.status} />
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                <div className="p-3.5 rounded-xl bg-[#F7EFE6]">
                  <span className="text-[#292039]/60">Student Email</span>
                  <p className="font-semibold text-[#292039] mt-0.5">{student.email}</p>
                </div>
                <div className="p-3.5 rounded-xl bg-[#F7EFE6]">
                  <span className="text-[#292039]/60">Registered Mobile (Indian)</span>
                  <p className="font-semibold text-[#292039] mt-0.5">{student.phone}</p>
                </div>
                <div className="p-3.5 rounded-xl bg-[#F7EFE6]">
                  <span className="text-[#292039]/60">Allotted Room</span>
                  <p className="font-semibold text-[#292039] mt-0.5">
                    {student.room} ({student.block})
                  </p>
                </div>
                <div className="p-3.5 rounded-xl bg-[#F7EFE6]">
                  <span className="text-[#292039]/60">Hostel Admission Date</span>
                  <p className="font-semibold text-[#292039] mt-0.5">{student.joinDate}</p>
                </div>
              </div>

              <div className="p-4 rounded-xl bg-amber-50/70 border border-amber-200 text-xs text-amber-900 leading-relaxed">
                <strong>Notice:</strong> To update your registered mobile number or request a room
                exchange, please submit a written application to the Warden Office before the 5th of
                each calendar month.
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
