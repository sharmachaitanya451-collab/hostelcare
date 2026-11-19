import { useState } from 'react'
import { NavLink, Link, Outlet, useNavigate } from 'react-router-dom'
import { useApp } from '../context/AppContext'

export function AdminLayout() {
  const { logout, students, complaints, fines } = useApp()
  const navigate = useNavigate()
  const [mobileNavOpen, setMobileNavOpen] = useState(false)

  const pendingCount = students.filter((s) => s.status === 'pending').length
  const openCount = complaints.filter(
    (c) =>
      c.status === 'Submitted' ||
      c.status === 'open' ||
      c.status === 'Under Review' ||
      c.status === 'Assigned' ||
      c.status === 'In Progress' ||
      c.status === 'in_progress',
  ).length
  const disputedCount = (fines || []).filter((f) => f.status === 'Disputed').length

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const navItems = [
    {
      to: '/admin/dashboard',
      label: 'Admin Overview',
      icon: 'M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z',
    },
    {
      to: '/admin/students',
      label: 'Resident Directory',
      icon: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z',
    },
    {
      to: '/admin/approvals',
      label: 'Registration Approvals',
      icon: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
      badge: pendingCount,
      badgeColor: 'bg-[#F4AA35] text-[#292039]',
    },
    {
      to: '/admin/rooms',
      label: 'Room Occupancy Map',
      icon: 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4',
    },
    {
      to: '/admin/complaints',
      label: 'Complaint Queue',
      icon: 'M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10',
      badge: openCount,
      badgeColor: 'bg-[#D94378] text-white',
    },
    {
      to: '/admin/fines',
      label: 'Fines & Disciplinary',
      icon: 'M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z',
      badge: disputedCount,
      badgeColor: 'bg-purple-600 text-white',
    },
    {
      to: '/admin/staff',
      label: 'Maintenance Staff',
      icon: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z',
    },
    {
      to: '/admin/audit-logs',
      label: 'Audit & Access Logs',
      icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z',
    },
  ]

  return (
    <div className="min-h-screen bg-[#FBF7F0] flex flex-col md:flex-row font-sans">
      {/* ------------------------------------------------------------------- */}
      {/* Desktop Sidebar                                                     */}
      {/* ------------------------------------------------------------------- */}
      <aside className="hidden md:flex md:w-64 bg-[#1E172B] text-[#FFFCF7] flex-col shrink-0 md:sticky md:top-0 h-screen h-[100dvh] max-h-[100dvh] p-5 border-r border-[#342A4A] z-30">
        <div className="shrink-0">
          {/* Header */}
          <div className="pb-6 border-b border-[#342A4A] flex items-center justify-between">
            <Link to="/" className="flex items-center gap-2">
              <div className="h-8 w-8 rounded-lg bg-[#F4AA35] text-[#1E172B] flex items-center justify-center font-bold text-sm">
                HC
              </div>
              <div className="flex flex-col">
                <span className="font-serif text-lg font-bold text-[#FFFCF7] leading-none">
                  Hostel<span className="text-[#F4AA35]">Care</span>
                </span>
                <span className="text-[10px] font-semibold text-[#D94378] uppercase tracking-wider mt-1">
                  Administration
                </span>
              </div>
            </Link>
            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-[#D94378] text-white">
              Warden
            </span>
          </div>

          {/* Warden Badge */}
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
                    : 'text-[#D8CEBE] hover:bg-[#282038] hover:text-[#FFFCF7]'
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
                  className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${item.badgeColor || 'bg-slate-700 text-white'}`}
                >
                  {item.badge}
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Exit link */}
        <div className="mt-auto pt-4 border-t border-[#342A4A] space-y-2 shrink-0">
          <Link to="/" className="block text-center text-xs text-[#A89CBF] hover:text-white py-1">
            ← Public Website
          </Link>
          <button
            onClick={handleLogout}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-xs font-semibold text-[#D8CEBE] hover:text-white hover:bg-[#2E2442] transition-colors cursor-pointer border border-[#44365E]"
          >
            <span>Exit Console</span>
          </button>
        </div>
      </aside>

      {/* ------------------------------------------------------------------- */}
      {/* Mobile Top Header                                                   */}
      {/* ------------------------------------------------------------------- */}
      <div className="md:hidden bg-[#1E172B] text-[#FFFCF7] p-4 flex items-center justify-between border-b border-[#342A4A]">
        <div className="flex items-center gap-2">
          <span className="font-serif font-bold text-base">HostelCare</span>
          <span className="text-xs text-[#D94378] font-semibold">(Admin)</span>
        </div>
        <button
          onClick={() => setMobileNavOpen(!mobileNavOpen)}
          className="p-1.5 rounded-lg bg-[#282038] text-[#D8CEBE]"
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

      {mobileNavOpen && (
        <div className="md:hidden bg-[#1E172B] text-[#FFFCF7] p-4 space-y-2 border-b border-[#342A4A]">
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
            Exit Console
          </button>
        </div>
      )}

      {/* ------------------------------------------------------------------- */}
      {/* Route Content Outlet                                                */}
      {/* ------------------------------------------------------------------- */}
      <main className="flex-1 min-w-0 p-4 sm:p-8 lg:p-10 max-w-6xl">
        <Outlet />
      </main>
    </div>
  )
}
