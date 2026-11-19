import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useApp } from '../context/AppContext'

export function getPortalDashboardForRole(role) {
  if (role === 'admin') return '/admin/dashboard'
  if (role === 'staff') return '/staff/dashboard'
  return '/student/dashboard'
}

export function RequireRole({ allowedRoles = ['student'] }) {
  const { user, authLoading } = useApp()
  const location = useLocation()

  if (authLoading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center p-8">
        <div className="bg-[#FFFCF7] px-6 py-4 rounded-2xl border border-[#E8DCCF] shadow-xs text-xs font-semibold text-[#292039]/75">
          Restoring HostelCare session...
        </div>
      </div>
    )
  }

  // If no authenticated user, redirect to login
  if (!user) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />
  }

  // Non-active accounts (pending, rejected, suspended, deactivated) cannot access protected portals
  const normalizedStatus = (user.status || 'active').toLowerCase()
  if (normalizedStatus !== 'active' && normalizedStatus !== 'on duty') {
    return <Navigate to="/login" state={{ pendingNotice: normalizedStatus === 'pending' }} replace />
  }

  // Enforce strict role isolation
  if (!allowedRoles.includes(user.role)) {
    return <Navigate to={getPortalDashboardForRole(user.role)} replace />
  }

  return <Outlet />
}
