import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useApp } from '../../context/AppContext'
import { HostelCareLogo } from '../../components/Brand'
import { getPortalDashboardForRole } from '../../components/RequireRole'

export function LoginPage() {
  const { login, sessionExpired, setSessionExpired } = useApp()
  const navigate = useNavigate()
  const location = useLocation()

  const [roleMode, setRoleMode] = useState('student') // 'student' | 'staff' | 'admin'
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [errorMsg, setErrorMsg] = useState('')
  const [errorCode, setErrorCode] = useState(
    location.state?.pendingNotice ? 'account_pending' : '',
  )
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setErrorMsg('')
    setErrorCode('')
    if (sessionExpired) {
      setSessionExpired(false)
    }

    setIsSubmitting(true)
    try {
      const authenticatedUser = await login(identifier, password, roleMode)
      navigate(getPortalDashboardForRole(authenticatedUser.role), { replace: true })
    } catch (err) {
      setErrorCode(err?.code || 'login_failed')
      setErrorMsg(err?.message || 'Unable to sign in. Please check your credentials.')
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
            Sign In to HostelCare
          </h1>
          <p className="text-xs text-[#292039]/70">
            Access your room maintenance requests, duty tasks, or administrative console
          </p>
        </div>

        {/* Portal Role Selector */}
        <div className="flex p-1 bg-[#F7EFE6] rounded-xl border border-[#E8DCCF]">
          <button
            type="button"
            onClick={() => {
              setRoleMode('student')
              setErrorMsg('')
              setErrorCode('')
            }}
            className={`flex-1 py-2 text-xs font-semibold rounded-lg transition-all ${
              roleMode === 'student'
                ? 'bg-white text-[#D94378] shadow-xs'
                : 'text-[#292039]/70 hover:text-[#292039]'
            }`}
          >
            Resident
          </button>
          <button
            type="button"
            onClick={() => {
              setRoleMode('staff')
              setErrorMsg('')
              setErrorCode('')
            }}
            className={`flex-1 py-2 text-xs font-semibold rounded-lg transition-all ${
              roleMode === 'staff'
                ? 'bg-[#368F83] text-white shadow-xs'
                : 'text-[#292039]/70 hover:text-[#292039]'
            }`}
          >
            Duty Staff
          </button>
          <button
            type="button"
            onClick={() => {
              setRoleMode('admin')
              setErrorMsg('')
              setErrorCode('')
            }}
            className={`flex-1 py-2 text-xs font-semibold rounded-lg transition-all ${
              roleMode === 'admin'
                ? 'bg-[#292039] text-[#FFFCF7] shadow-xs'
                : 'text-[#292039]/70 hover:text-[#292039]'
            }`}
          >
            Warden / Admin
          </button>
        </div>

        {sessionExpired && !errorMsg && (
          <div
            role="alert"
            className="p-3.5 rounded-xl bg-amber-50 border border-amber-300 text-amber-900 text-xs"
          >
            <strong>Session Expired:</strong> Your previous session has expired or was invalidated
            after a security update. Please sign in again.
          </div>
        )}

        {errorCode === 'account_pending' ? (
          <div
            role="alert"
            className="p-4 rounded-2xl bg-amber-50 border border-amber-300 text-amber-950 text-xs space-y-1"
          >
            <div className="font-bold text-[#B36E08]">
              ⏳ Registration Pending Warden Approval
            </div>
            <p className="leading-relaxed">
              {errorMsg ||
                'Your registration is pending warden approval. Please check back after verification.'}
            </p>
          </div>
        ) : (
          errorMsg && (
            <div
              role="alert"
              className="p-3.5 rounded-xl bg-rose-50 border border-rose-300 text-rose-900 text-xs"
            >
              {errorMsg}
            </div>
          )
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="login-identifier"
              className="block text-xs font-semibold text-[#292039] mb-1"
            >
              {roleMode === 'student'
                ? 'Hostel Email or Roll Number *'
                : roleMode === 'staff'
                  ? 'Technician / Staff Email *'
                  : 'Warden Admin Email *'}
            </label>
            <input
              id="login-identifier"
              type="text"
              required
              autoComplete="username"
              placeholder={
                roleMode === 'student'
                  ? 'e.g. aarav.sharma@hostelcare.in or 2023CSB1042'
                  : roleMode === 'staff'
                    ? 'e.g. ramesh.electrician@hostelcare.in'
                    : 'e.g. warden@hostelcare.in'
              }
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-xl border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#D94378] bg-[#FFFCF7]"
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-1">
              <label
                htmlFor="login-password"
                className="block text-xs font-semibold text-[#292039]"
              >
                Password *
              </label>
              <Link
                to="/forgot-password"
                className="text-xs text-[#D94378] hover:underline font-medium"
              >
                Forgot Password?
              </Link>
            </div>
            <input
              id="login-password"
              type="password"
              required
              autoComplete="current-password"
              placeholder="Enter your account password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-xl border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#D94378] bg-[#FFFCF7]"
            />
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className={`w-full py-3 rounded-xl text-sm font-semibold text-white shadow-md transition-all cursor-pointer disabled:opacity-60 ${
              roleMode === 'student'
                ? 'bg-[#D94378] hover:bg-[#C23365] shadow-[#D94378]/25'
                : roleMode === 'staff'
                  ? 'bg-[#368F83] hover:bg-[#2B7369] shadow-[#368F83]/25'
                  : 'bg-[#292039] hover:bg-[#3D3252]'
            }`}
          >
            {isSubmitting
              ? 'Verifying Credentials...'
              : roleMode === 'student'
                ? 'Sign In To Resident Portal'
                : roleMode === 'staff'
                  ? 'Access Staff Maintenance Tasks'
                  : 'Access Administration Console'}
          </button>
        </form>

        <div className="pt-2 text-center text-xs text-[#292039]/70 space-y-2">
          <div>
            New student resident?{' '}
            <Link to="/register" className="font-semibold text-[#D94378] hover:underline">
              Self-register your account
            </Link>
          </div>
          <div>
            <Link to="/staff/login" className="text-[#368F83] font-medium hover:underline">
              Go to dedicated Staff Login page &rarr;
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
