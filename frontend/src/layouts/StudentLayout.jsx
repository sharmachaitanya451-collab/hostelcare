import { useState } from 'react'
import { NavLink, Link, Outlet, useNavigate } from 'react-router-dom'
import { isComplaintOwnedByStudent, useApp } from '../context/AppContext'

export function StudentLayout() {
  const { user, logout, complaints, notifications, fines } = useApp()
  const navigate = useNavigate()
  const [mobileNavOpen, setMobileNavOpen] = useState(false)

  // Filter complaints belonging strictly to this student
  const studentComplaints = complaints.filter((c) => isComplaintOwnedByStudent(c, user))
  const openCount = studentComplaints.filter(
    (c) =>
      c.status === 'Submitted' ||
      c.status === 'Under Review' ||
      c.status === 'Assigned' ||
      c.status === 'In Progress' ||
      c.status === 'open' ||
      c.status === 'in_progress',
  ).length
  const unreadNotifs = notifications.filter((n) => !n.read).length

  // Filter fines related to this student
  const studentFines = (fines || []).filter(
    (f) => f.studentRoll === user?.rollNumber || f.studentId === user?.id,
  )
  const pendingFinesCount = studentFines.filter(
    (f) => f.status === 'Pending' || f.status === 'Overdue',
  ).length

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const navItems = [
    {
      to: '/student/dashboard',
      label: 'Dashboard',
      icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6',
    },
    {
      to: '/student/room',
      label: 'My Room & Allotment',
      icon: 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4',
    },
    {
      to: '/student/complaints/new',
      label: 'Submit Maintenance',
      icon: 'M12 9v3m0 0v3m0-3h3m-3 0H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z',
    },
    {
      to: '/student/complaints',
      label: 'My Complaints',
      icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4',
      badge: openCount,
    },
    {
      to: '/student/fines',
      label: 'My Fines & Dues',
      icon: 'M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z',
      badge: pendingFinesCount,
      badgeColor: 'bg-[#D94378] text-white',
    },
    {
      to: '/student/notifications',
      label: 'Hostel Notices',
      icon: 'M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9',
      badge: unreadNotifs,
      badgeColor: 'bg-[#368F83] text-white',
    },
    {
      to: '/student/profile',
      label: 'Student Profile',
      icon: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z',
    },
  ]

  return (
    <div className="min-h-screen bg-[#FDF9F3] flex flex-col md:flex-row font-sans">
      {/* ------------------------------------------------------------------- */}
      {/* Desktop Sidebar                                                     */}
      {/* ------------------------------------------------------------------- */}
      <aside className="hidden md:flex md:w-64 bg-[#292039] text-[#FFFCF7] flex-col shrink-0 md:sticky md:top-0 h-screen h-[100dvh] max-h-[100dvh] p-5 border-r border-[#44375A] z-30">
        <div className="shrink-0">
          {/* Header Brand */}
          <div className="pb-6 border-b border-[#3D3252] flex items-center justify-between">
            <Link to="/" className="flex items-center gap-2">
              <div className="h-8 w-8 rounded-lg bg-[#D94378] flex items-center justify-center font-bold text-white text-sm">
                HC
              </div>
              <div className="flex flex-col">
                <span className="font-serif text-lg font-bold text-[#FFFCF7] leading-none">
                  Hostel<span className="text-[#D94378]">Care</span>
                </span>
                <span className="text-[10px] font-medium text-[#F4AA35] uppercase tracking-wider mt-1">
                  Resident Portal
                </span>
              </div>
            </Link>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#3D3252] text-[#D8CEBE]">
              Student
            </span>
          </div>

          {/* Student Badge Card */}
          <div className="my-5 p-3.5 rounded-xl bg-[#372B4D] border border-[#52416F] flex items-center gap-3">
            <div
              className={`h-10 w-10 rounded-lg ${user?.avatarColor || 'bg-[#D94378]'} text-white flex items-center justify-center font-bold text-sm shrink-0`}
            >
              {user?.fullName?.charAt(0) || 'S'}
            </div>
            <div className="min-w-0">
              <h4 className="text-xs font-semibold text-white truncate">
                {user?.fullName || 'Resident Student'}
              </h4>
              <p className="text-[11px] font-mono text-[#D8CEBE]">
                {user?.room || 'Room'} • {user?.rollNumber}
              </p>
            </div>
          </div>
        </div>

        {/* Nav Items */}
        <nav className="flex-1 overflow-y-auto min-h-0 space-y-1.5 pt-2 pr-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-semibold transition-all ${
                  isActive
                    ? 'bg-[#D94378] text-[#FFFCF7] shadow-sm'
                    : 'text-[#D8CEBE] hover:bg-[#372B4D] hover:text-[#FFFCF7]'
                }`
              }
            >
              <div className="flex items-center gap-3">
                <svg
                  className="w-4 h-4 shrink-0"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d={item.icon}
                  />
                </svg>
                <span>{item.label}</span>
              </div>
              {item.badge !== undefined && item.badge > 0 && (
                <span
                  className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${item.badgeColor || 'bg-[#F4AA35] text-[#292039]'}`}
                >
                  {item.badge}
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Footer controls */}
        <div className="mt-auto pt-4 border-t border-[#3D3252] space-y-3 shrink-0">
          <div className="px-3 py-2 rounded-lg bg-[#372B4D]/60 text-[11px] text-[#A89CBF]">
            <p className="font-semibold text-[#F4AA35]">Warden Helpdesk:</p>
            <p>Admin Wing A, Ext: 204</p>
          </div>
          <Link to="/" className="block text-center text-xs text-[#A89CBF] hover:text-white py-1">
            ← Public Website
          </Link>
          <button
            onClick={handleLogout}
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

      {/* ------------------------------------------------------------------- */}
      {/* Mobile Header Bar                                                   */}
      {/* ------------------------------------------------------------------- */}
      <div className="md:hidden bg-[#292039] text-[#FFFCF7] p-4 flex items-center justify-between border-b border-[#44375A]">
        <div className="flex items-center gap-2">
          <span className="font-serif font-bold text-base">HostelCare</span>
          <span className="text-xs text-[#F4AA35] font-semibold">({user?.room})</span>
        </div>
        <button
          onClick={() => setMobileNavOpen(!mobileNavOpen)}
          className="p-1.5 rounded-lg bg-[#372B4D] text-[#D8CEBE]"
          aria-label="Toggle Navigation"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M4 6h16M4 12h16M4 18h16"
            />
          </svg>
        </button>
      </div>

      {/* Mobile Drawer */}
      {mobileNavOpen && (
        <div className="md:hidden bg-[#292039] text-[#FFFCF7] p-4 space-y-2 border-b border-[#44375A]">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={() => setMobileNavOpen(false)}
              className={({ isActive }) =>
                `block px-3 py-2 rounded-lg text-xs font-semibold ${
                  isActive ? 'bg-[#D94378] text-white' : 'text-[#D8CEBE]'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
          <button
            onClick={() => {
              setMobileNavOpen(false)
              handleLogout()
            }}
            className="block w-full text-left px-3 py-2 rounded-lg text-xs font-semibold text-red-300"
          >
            Sign Out
          </button>
        </div>
      )}

      {/* ------------------------------------------------------------------- */}
      {/* Outlet                                                              */}
      {/* ------------------------------------------------------------------- */}
      <main className="flex-1 min-w-0 p-4 sm:p-8 lg:p-10 max-w-6xl">
        <Outlet />
      </main>
    </div>
  )
}
