import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useApp } from '../../context/AppContext'
import { HostelCareLogo } from '../../components/Brand'
import { getPortalDashboardForRole } from '../../components/RequireRole'

export function StaffLoginPage() {
  const { login } = useApp()
  const navigate = useNavigate()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errorMsg, setErrorMsg] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setErrorMsg('')
    setIsSubmitting(true)
    try {
      const authenticatedUser = await login(email, password, 'staff')
      navigate(getPortalDashboardForRole(authenticatedUser.role), { replace: true })
    } catch (err) {
      setErrorMsg(err?.message || 'Invalid staff email or password.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="py-12 sm:py-20 max-w-md mx-auto px-4">
      <div className="bg-[#FFFCF7] p-8 rounded-3xl border border-[#E8DCCF] shadow-xl space-y-6">
        <div className="text-center space-y-2">
          <div className="inline-block">
            <HostelCareLogo showTagline={false} />
          </div>
          <h1 className="font-serif text-2xl sm:text-3xl font-bold text-[#292039] pt-2">
            Technician &amp; Staff Login
          </h1>
          <p className="text-xs text-[#292039]/70">
            Sign in to view assigned work orders, accept maintenance tasks, and submit repair logs
          </p>
        </div>

        <div className="p-3.5 rounded-2xl bg-teal-50 border border-teal-200 text-teal-900 text-xs space-y-1">
          <div className="font-semibold flex items-center gap-1.5 text-[#368F83]">
            <span>👷</span>
            <span>Duty Staff Authentication:</span>
          </div>
          <p className="text-[11px] leading-relaxed">
            Staff accounts are provisioned by the hostel administration. First-time staff should set
            their password using the single-use setup link sent to their email.
          </p>
        </div>

        {errorMsg && (
          <div
            role="alert"
            className="p-3.5 rounded-xl bg-rose-50 border border-rose-300 text-rose-900 text-xs"
          >
            {errorMsg}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="staff-login-email"
              className="block text-xs font-semibold text-[#292039] mb-1"
            >
              Staff Email or Staff Code *
            </label>
            <input
              id="staff-login-email"
              type="text"
              required
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="e.g. ramesh.electrician@hostelcare.in"
              className="w-full px-3.5 py-2.5 rounded-xl border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#368F83] bg-[#FFFCF7]"
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-1">
              <label
                htmlFor="staff-login-password"
                className="block text-xs font-semibold text-[#292039]"
              >
                Account Password *
              </label>
              <Link
                to="/forgot-password"
                className="text-xs text-[#368F83] hover:underline font-medium"
              >
                Set / Reset Password?
              </Link>
            </div>
            <input
              id="staff-login-password"
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your staff password"
              className="w-full px-3.5 py-2.5 rounded-xl border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#368F83] bg-[#FFFCF7]"
            />
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full py-3 rounded-xl text-sm font-semibold text-white bg-[#368F83] hover:bg-[#2B7369] shadow-md shadow-[#368F83]/25 transition-all cursor-pointer disabled:opacity-60"
          >
            {isSubmitting
              ? 'Signing In...'
              : 'Access Staff Maintenance Console →'}
          </button>
        </form>

        <div className="pt-2 text-center text-xs text-[#292039]/70 space-y-2">
          <div>
            Resident Student or Warden?{' '}
            <Link to="/login" className="font-semibold text-[#D94378] hover:underline">
              Standard Sign In
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
