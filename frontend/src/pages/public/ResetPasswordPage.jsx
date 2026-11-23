import { useState, useMemo } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useApp } from '../../context/AppContext'
import { HostelCareLogo } from '../../components/Brand'

export function ResetPasswordPage() {
  const { token } = useParams()
  const { confirmPasswordReset } = useApp()

  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorMsg, setErrorMsg] = useState('')
  const [tokenRejected, setTokenRejected] = useState(false)

  const cleanToken = useMemo(() => (token || '').trim().replace(/^["']|["']$/g, ''), [token])

  // Explicit URL states or server rejection
  const isRedactedToken = cleanToken === '[REDACTED-TOKEN]' || cleanToken === '%5BREDACTED-TOKEN%5D'
  const isInvalid = cleanToken === 'invalid' || tokenRejected || isRedactedToken
  const isExpired = cleanToken === 'expired'

  // Password strength calculation
  const strength = useMemo(() => {
    if (!password) return { score: 0, label: 'Too short', color: 'bg-slate-200' }
    let score = 0
    if (password.length >= 8) score += 1
    if (password.length >= 10) score += 1
    if (/[A-Z]/.test(password) && /[a-z]/.test(password)) score += 1
    if (/[0-9]/.test(password)) score += 1
    if (/[^A-Za-z0-9]/.test(password)) score += 1

    if (score <= 2) return { score: 1, label: 'Weak', color: 'bg-rose-500' }
    if (score === 3 || score === 4) return { score: 2, label: 'Moderate', color: 'bg-[#F4AA35]' }
    return { score: 3, label: 'Strong', color: 'bg-emerald-600' }
  }, [password])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setErrorMsg('')

    if (password.length < 8) {
      setErrorMsg('Password must be at least 8 characters long.')
      return
    }

    if (password !== confirmPassword) {
      setErrorMsg('New password and confirmation password do not match.')
      return
    }

    setIsSubmitting(true)
    try {
      await confirmPasswordReset({
        token: cleanToken,
        password,
        confirmPassword,
      })
      setSubmitted(true)
    } catch (err) {
      if (err?.code === 'invalid_or_expired_token') {
        setTokenRejected(true)
      } else {
        setErrorMsg(err?.message || 'Unable to reset password. Please try again.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  // Handle Invalid or Expired Token
  if (isInvalid || isExpired) {
    return (
      <div className="py-12 sm:py-20 max-w-md mx-auto px-4">
        <div className="bg-[#FFFCF7] p-8 rounded-3xl border border-[#E8DCCF] shadow-xl space-y-6 text-center">
          <div className="inline-block">
            <HostelCareLogo showTagline={false} />
          </div>

          <div className="w-14 h-14 rounded-full bg-rose-100 text-rose-600 mx-auto flex items-center justify-center">
            <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>

          <div className="space-y-2">
            <h1 className="font-serif text-2xl font-bold text-[#292039]">
              {isExpired ? 'Reset Link Expired' : 'Invalid Reset Token'}
            </h1>
            <p className="text-xs text-[#292039]/70 leading-relaxed">
              {isExpired
                ? 'This password reset link has passed its 30-minute validity window. Please request a fresh reset link.'
                : isRedactedToken
                  ? 'This password reset link contains a redacted placeholder token. Please use the complete link printed in your local development console.'
                  : 'The token provided in the URL is unrecognized, expired, or has already been used.'}
            </p>
          </div>

          <div className="pt-2 space-y-3">
            <Link
              to="/forgot-password"
              className="block w-full py-3 rounded-xl text-sm font-semibold text-white bg-[#D94378] hover:bg-[#C23365] shadow-md shadow-[#D94378]/25 transition-all text-center"
            >
              Request New Reset Link
            </Link>
            <Link
              to="/login"
              className="block text-xs font-semibold text-[#292039]/75 hover:text-[#292039]"
            >
              Back to Sign In
            </Link>
          </div>
        </div>
      </div>
    )
  }

  // Handle Success State
  if (submitted) {
    return (
      <div className="py-12 sm:py-20 max-w-md mx-auto px-4">
        <div className="bg-[#FFFCF7] p-8 rounded-3xl border border-[#E8DCCF] shadow-xl space-y-6 text-center">
          <div className="inline-block">
            <HostelCareLogo showTagline={false} />
          </div>

          <div className="w-14 h-14 rounded-full bg-emerald-100 text-emerald-600 mx-auto flex items-center justify-center">
            <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M5 13l4 4L19 7"
              />
            </svg>
          </div>

          <div className="space-y-2">
            <h1 className="font-serif text-2xl font-bold text-[#292039]">
              Password Updated Successfully
            </h1>
            <p className="text-xs text-[#292039]/70 leading-relaxed">
              Your account password has been updated and any previous sessions have been signed out.
              You can now use your new credentials to log in.
            </p>
          </div>

          <div className="pt-2">
            <Link
              to="/login"
              className="block w-full py-3 rounded-xl text-sm font-semibold text-white bg-[#D94378] hover:bg-[#C23365] shadow-md shadow-[#D94378]/25 transition-all text-center"
            >
              Proceed to Sign In
            </Link>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="py-12 sm:py-20 max-w-md mx-auto px-4">
      <div className="bg-[#FFFCF7] p-8 rounded-3xl border border-[#E8DCCF] shadow-xl space-y-6">
        <div className="text-center space-y-2">
          <div className="inline-block">
            <HostelCareLogo showTagline={false} />
          </div>
          <h1 className="font-serif text-2xl sm:text-3xl font-bold text-[#292039] pt-2">
            Create New Password
          </h1>
          <p className="text-xs text-[#292039]/70">
            Choose a strong password to protect your HostelCare portal access
          </p>
        </div>

        {errorMsg && (
          <div
            role="alert"
            className="p-3.5 rounded-xl bg-amber-50 border border-amber-300 text-amber-900 text-xs"
          >
            {errorMsg}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="new-password"
              className="block text-xs font-semibold text-[#292039] mb-1"
            >
              New Password *
            </label>
            <input
              id="new-password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 8 characters"
              className="w-full px-3.5 py-2.5 rounded-xl border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#D94378] bg-[#FFFCF7]"
            />

            {/* Strength meter */}
            {password && (
              <div className="mt-2 space-y-1">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-[#292039]/70">Strength:</span>
                  <span className="font-semibold text-[#292039]">{strength.label}</span>
                </div>
                <div className="h-1.5 w-full bg-slate-200 rounded-full overflow-hidden flex">
                  <div
                    className={`h-full transition-all duration-300 ${strength.color} ${
                      strength.score === 1 ? 'w-1/3' : strength.score === 2 ? 'w-2/3' : 'w-full'
                    }`}
                  />
                </div>
              </div>
            )}
          </div>

          <div>
            <label
              htmlFor="confirm-password"
              className="block text-xs font-semibold text-[#292039] mb-1"
            >
              Confirm New Password *
            </label>
            <input
              id="confirm-password"
              type="password"
              required
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Re-type your new password"
              className="w-full px-3.5 py-2.5 rounded-xl border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#D94378] bg-[#FFFCF7]"
            />
          </div>

          <div className="p-3 rounded-xl bg-[#F7EFE6] text-[11px] text-[#292039]/75 border border-[#E8DCCF]">
            🛡️ <strong>Security Tip:</strong> Include uppercase letters, numbers, and symbols to
            ensure your room allotment and maintenance data remains secure.
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full py-3 rounded-xl text-sm font-semibold text-white bg-[#D94378] hover:bg-[#C23365] shadow-md shadow-[#D94378]/25 transition-all cursor-pointer disabled:opacity-60"
          >
            {isSubmitting ? 'Updating Password...' : 'Update Password & Sign In'}
          </button>
        </form>

        <div className="pt-2 text-center text-xs text-[#292039]/70">
          <Link to="/login" className="font-semibold text-[#D94378] hover:underline">
            &larr; Cancel and Return to Sign In
          </Link>
        </div>
      </div>
    </div>
  )
}
