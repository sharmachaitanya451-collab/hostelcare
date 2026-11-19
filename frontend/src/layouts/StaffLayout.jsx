import { useState } from 'react'
import { NavLink, Link, Outlet, useNavigate } from 'react-router-dom'
import { useApp } from '../context/AppContext'

export function StaffLayout() {
  const { user, logout, complaints, staffNotifications } = useApp()
  const navigate = useNavigate()
  const [mobileNavOpen, setMobileNavOpen] = useState(false)

  // Filter tasks assigned to this staff member
  const staffTasks = complaints.filter(
    (c) =>
      c.assignedStaff === user?.name ||
      (c.assignedStaff && user?.name && c.assignedStaff.includes(user.name)),
  )

  const activeTaskCount = staffTasks.filter(
    (c) =>
      c.status === 'Assigned' ||
      c.status === 'Accepted' ||
      c.status === 'In Progress' ||
      c.status === 'in_progress',
  ).length

  const unreadNotifsCount = (staffNotifications || []).filter(
    (n) => !n.read && (n.staffId === user?.id || !n.staffId),
  ).length

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const navItems = [
    {
      to: '/staff/dashboard',
      label: 'Staff Dashboard',
      icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6',
    },
    {
      to: '/staff/tasks',
      label: 'My Assigned Tasks',
      icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4',
      badge: activeTaskCount,
      badgeColor: 'bg-[#F4AA35] text-[#292039]',
    },
    {
      to: '/staff/notifications',
      label: 'Duty Notifications',
      icon: 'M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9',
      badge: unreadNotifsCount,
      badgeColor: 'bg-[#368F83] text-white',
    },
    {
      to: '/staff/profile',
      label: 'Technician Profile',
      icon: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z',
    },
  ]

  return (
    <div className="min-h-screen bg-[#FDF9F3] flex flex-col md:flex-row font-sans">
      {/* ------------------------------------------------------------------- */}
      {/* Desktop Sidebar                                                     */}
      {/* ------------------------------------------------------------------- */}
      <aside className="hidden md:flex md:w-64 bg-[#231E2F] text-[#FFFCF7] flex-col shrink-0 md:sticky md:top-0 h-screen h-[100dvh] max-h-[100dvh] p-5 border-r border-[#3D334E] z-30">
        <div className="shrink-0">
          {/* Header Brand */}
          <div className="pb-6 border-b border-[#352B47] flex items-center justify-between">
            <Link to="/" className="flex items-center gap-2">
              <div className="h-8 w-8 rounded-lg bg-[#368F83] flex items-center justify-center font-bold text-white text-sm">
                HC
              </div>
              <div className="flex flex-col">
                <span className="font-serif text-lg font-bold text-[#FFFCF7] leading-none">
                  Hostel<span className="text-[#368F83]">Care</span>
                </span>
                <span className="text-[10px] font-medium text-[#F4AA35] uppercase tracking-wider mt-1">
                  Staff Portal
                </span>
              </div>
            </Link>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#352B47] text-[#D8CEBE]">
              Technician
            </span>
          </div>

          {/* Staff Badge Card */}
          <div className="my-5 p-3.5 rounded-2xl bg-[#2D243D] border border-[#483B5E] flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-[#368F83] text-white flex items-center justify-center font-bold text-base shrink-0">
              {user?.name?.charAt(0) || 'T'}
            </div>
            <div className="min-w-0">
              <h4 className="text-xs font-semibold text-white truncate">
                {user?.name || 'Maintenance Staff'}
              </h4>
              <p className="text-[11px] text-[#F4AA35] font-medium truncate">
                {user?.trade || 'Duty Technician'}
              </p>
              <span className="text-[10px] text-emerald-400 font-mono">
                ● {user?.status || 'Active'}
              </span>
            </div>
          </div>
        </div>

        {/* Navigation Links */}
        <nav className="flex-1 overflow-y-auto min-h-0 space-y-1.5 pt-2 pr-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `w-full flex items-center justify-between px-3.5 py-3 rounded-xl text-xs font-semibold transition-all ${
                  isActive
                    ? 'bg-[#368F83] text-white shadow-sm'
                    : 'text-[#D8CEBE] hover:bg-[#2D243D] hover:text-white'
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
                  className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                    item.badgeColor || 'bg-[#F4AA35] text-[#292039]'
                  }`}
                >
                  {item.badge}
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Footer controls */}
        <div className="mt-auto pt-4 border-t border-[#352B47] space-y-3 shrink-0">
          <div className="px-3 py-2 rounded-xl bg-[#2D243D]/60 text-[11px] text-[#A89CBF]">
            <p className="font-semibold text-[#F4AA35]">Shift Roster:</p>
            <p className="truncate">{user?.shift || 'General Shift'}</p>
          </div>
          <Link to="/" className="block text-center text-xs text-[#A89CBF] hover:text-white py-1">
            ← Public Website
          </Link>
          <button
            onClick={handleLogout}
            className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl text-xs font-semibold text-[#D8CEBE] hover:text-white hover:bg-[#352B47] transition-colors cursor-pointer border border-[#483B5E]"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
              />
            </svg>
            <span>Sign Out</span>
          </button>
        </div>
      </aside>

      {/* ------------------------------------------------------------------- */}
      {/* Mobile Top Navbar with large touch targets                          */}
      {/* ------------------------------------------------------------------- */}
      <div className="md:hidden bg-[#231E2F] text-white p-4 flex items-center justify-between border-b border-[#3D334E] sticky top-0 z-40">
        <div className="flex items-center gap-2">
          <div className="h-8 w-8 rounded-lg bg-[#368F83] flex items-center justify-center font-bold text-white text-xs">
            HC
          </div>
          <div>
            <span className="font-serif text-base font-bold">
              Hostel<span className="text-[#368F83]">Care</span>
            </span>
            <span className="text-[10px] text-[#F4AA35] font-semibold block leading-none">
              Staff Portal
            </span>
          </div>
        </div>

        <button
          onClick={() => setMobileNavOpen(!mobileNavOpen)}
          className="p-2 rounded-xl bg-[#2D243D] text-[#D8CEBE] hover:text-white"
        >
          {mobileNavOpen ? (
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          ) : (
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M4 6h16M4 12h16M4 18h16"
              />
            </svg>
          )}
        </button>
      </div>

      {/* Mobile Menu Dropdown */}
      {mobileNavOpen && (
        <div className="md:hidden bg-[#231E2F] border-b border-[#3D334E] px-4 py-4 space-y-2 z-40 animate-in slide-in-from-top-2">
          <div className="p-3 rounded-xl bg-[#2D243D] mb-3">
            <h4 className="text-xs font-bold text-white">{user?.name}</h4>
            <p className="text-[11px] text-[#F4AA35]">
              {user?.trade} • {user?.shift}
            </p>
          </div>
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={() => setMobileNavOpen(false)}
              className={({ isActive }) =>
                `w-full flex items-center justify-between px-4 py-3 rounded-xl text-sm font-semibold transition-all ${
                  isActive ? 'bg-[#368F83] text-white' : 'text-[#D8CEBE] hover:bg-[#2D243D]'
                }`
              }
            >
              <span>{item.label}</span>
              {item.badge !== undefined && item.badge > 0 && (
                <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-[#F4AA35] text-[#292039]">
                  {item.badge}
                </span>
              )}
            </NavLink>
          ))}
          <button
            onClick={handleLogout}
            className="w-full text-left px-4 py-3 text-sm font-semibold text-rose-400 hover:bg-[#2D243D] rounded-xl"
          >
            Sign Out
          </button>
        </div>
      )}

      {/* ------------------------------------------------------------------- */}
      {/* Main Content Pane                                                   */}
      {/* ------------------------------------------------------------------- */}
      <main className="flex-1 min-w-0 p-4 sm:p-6 md:p-8 max-w-7xl mx-auto w-full">
        <Outlet />
      </main>
    </div>
  )
}
