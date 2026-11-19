import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useApp } from '../../context/AppContext'
import { HostelCareLogo } from '../../components/Brand'

export function ForgotPasswordPage() {
  const { requestPasswordReset } = useApp()

  const [email, setEmail] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorMsg, setErrorMsg] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setErrorMsg('')
    setIsSubmitting(true)

    try {
      await requestPasswordReset(email)
      setSubmitted(true)
    } catch (err) {
      setErrorMsg(
        err?.message || 'Unable to process password reset request right now. Please try again.',
      )
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
            Reset Password
          </h1>
          <p className="text-xs text-[#292039]/70">
            Enter your registered hostel or college email to receive recovery instructions
          </p>
        </div>

        {submitted ? (
          <div className="space-y-5">
            <div className="p-4 rounded-2xl bg-teal-50 border border-teal-200 text-teal-900 text-sm space-y-2">
              <div className="flex items-center gap-2 font-bold text-[#368F83]">
                <svg
                  className="w-5 h-5 shrink-0"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                  />
                </svg>
                <span>Instructions Dispatched</span>
              </div>
              <p className="text-xs text-teal-800 leading-relaxed">
                If an account exists with this email address, password reset instructions have been
                sent. Please check your inbox and spam folder.
              </p>
            </div>

            <div className="pt-2 text-center">
              <Link
                to="/login"
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#D94378] hover:underline"
              >
                &larr; Return to Sign In
              </Link>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            {errorMsg && (
              <div
                role="alert"
                className="p-3.5 rounded-xl bg-rose-50 border border-rose-300 text-rose-900 text-xs"
              >
                {errorMsg}
              </div>
            )}

            <div>
              <label
                htmlFor="forgot-email"
                className="block text-xs font-semibold text-[#292039] mb-1"
              >
                Registered Email Address *
              </label>
              <input
                id="forgot-email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="e.g. aarav.sharma@hostelcare.in"
                className="w-full px-3.5 py-2.5 rounded-xl border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#D94378] bg-[#FFFCF7]"
              />
            </div>

            <div className="p-3 rounded-xl bg-[#F7EFE6] text-[11px] text-[#292039]/75 border border-[#E8DCCF]">
              🔒 <strong>Security Note:</strong> Reset links are cryptographically generated,
              single-use, and expire within 30 minutes.
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full py-3 rounded-xl text-sm font-semibold text-white bg-[#D94378] hover:bg-[#C23365] shadow-md shadow-[#D94378]/25 transition-all cursor-pointer disabled:opacity-50"
            >
              {isSubmitting ? 'Sending Instructions...' : 'Send Password Reset Link'}
            </button>

            <div className="pt-2 text-center text-xs text-[#292039]/70">
              Remembered your credentials?{' '}
              <Link to="/login" className="font-semibold text-[#D94378] hover:underline">
                Sign In
              </Link>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
