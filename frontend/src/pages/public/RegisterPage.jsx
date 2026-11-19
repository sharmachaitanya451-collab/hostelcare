import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useApp } from '../../context/AppContext'
import { HostelCareLogo } from '../../components/Brand'

export function RegisterPage() {
  const { registerStudent } = useApp()

  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [rollNumber, setRollNumber] = useState('')
  const [phone, setPhone] = useState('+91 ')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [errorMsg, setErrorMsg] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [successData, setSuccessData] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setErrorMsg('')

    if (password !== confirmPassword) {
      setErrorMsg('Password and confirmation password do not match.')
      return
    }

    setIsSubmitting(true)
    try {
      const registered = await registerStudent({
        fullName,
        email,
        rollNumber,
        phone,
        password,
        confirmPassword,
      })
      setSuccessData(registered)
    } catch (err) {
      setErrorMsg(err?.message || 'Unable to complete registration. Please check your details.')
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
            Student Registration
          </h1>
          <p className="text-xs text-[#292039]/70">
            Create your collegiate resident profile for hostel room services
          </p>
        </div>

        {successData ? (
          <div className="space-y-4 py-4 text-center">
            <div className="h-12 w-12 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center text-2xl mx-auto">
              ✓
            </div>
            <h3 className="font-serif text-xl font-bold text-[#292039]">
              Registration Awaiting Approval
            </h3>

            <div className="p-4 rounded-2xl bg-[#F7EFE6] border border-[#E8DCCF] text-xs text-[#292039]/80 text-left space-y-1.5">
              <p>
                <strong>Status:</strong>{' '}
                <span className="text-[#B36E08] font-bold">
                  Pending Administrative Verification
                </span>
              </p>
              <p>
                <strong>Student:</strong> {successData.fullName} ({successData.rollNumber})
              </p>
              <p>
                <strong>Email:</strong> {successData.email}
              </p>
              <p>
                <strong>Room Allotment:</strong> Assigned after warden verification
              </p>
              <p className="text-[11px] text-[#292039]/60 pt-2 border-t border-[#E5D7C5]">
                Your application has been forwarded to the Chief Warden review queue. Protected
                resident features will unlock once your registration is approved.
              </p>
            </div>

            <Link
              to="/login"
              className="block w-full py-2.5 rounded-xl text-xs font-semibold text-white bg-[#292039] hover:bg-[#3D3252]"
            >
              Return to Login Page
            </Link>
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
                htmlFor="reg-fullname"
                className="block text-xs font-semibold text-[#292039] mb-1"
              >
                Full Name (As per College ID Card) *
              </label>
              <input
                id="reg-fullname"
                type="text"
                required
                placeholder="e.g. Vikram Malhotra"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-xl border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#D94378] bg-[#FFFCF7]"
              />
            </div>

            <div>
              <label
                htmlFor="reg-email"
                className="block text-xs font-semibold text-[#292039] mb-1"
              >
                College / Hostel Email Address *
              </label>
              <input
                id="reg-email"
                type="email"
                required
                placeholder="e.g. vikram.malhotra@hostelcare.in"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-xl border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#D94378] bg-[#FFFCF7]"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label
                  htmlFor="reg-roll"
                  className="block text-xs font-semibold text-[#292039] mb-1"
                >
                  Roll Number *
                </label>
                <input
                  id="reg-roll"
                  type="text"
                  required
                  placeholder="2024MEB1015"
                  value={rollNumber}
                  onChange={(e) => setRollNumber(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#D94378] bg-[#FFFCF7]"
                />
              </div>

              <div>
                <label
                  htmlFor="reg-phone"
                  className="block text-xs font-semibold text-[#292039] mb-1"
                >
                  Indian Mobile Number *
                </label>
                <input
                  id="reg-phone"
                  type="tel"
                  required
                  placeholder="+91 98765 43210"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#D94378] bg-[#FFFCF7]"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label
                  htmlFor="reg-password"
                  className="block text-xs font-semibold text-[#292039] mb-1"
                >
                  Create Password *
                </label>
                <input
                  id="reg-password"
                  type="password"
                  required
                  minLength={8}
                  placeholder="Min 8 chars, letter + digit"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#D94378] bg-[#FFFCF7]"
                />
              </div>

              <div>
                <label
                  htmlFor="reg-confirm-password"
                  className="block text-xs font-semibold text-[#292039] mb-1"
                >
                  Confirm Password *
                </label>
                <input
                  id="reg-confirm-password"
                  type="password"
                  required
                  minLength={8}
                  placeholder="Re-enter password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#D94378] bg-[#FFFCF7]"
                />
              </div>
            </div>

            <div className="p-3 rounded-xl bg-amber-50 text-[11px] text-amber-900 border border-amber-200">
              ⚠️ <strong>Approval Requirement:</strong> All accounts require warden approval before
              protected student features become accessible.
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full py-3 rounded-xl text-sm font-semibold text-white bg-[#D94378] hover:bg-[#C23365] shadow-md shadow-[#D94378]/25 transition-all cursor-pointer disabled:opacity-60"
            >
              {isSubmitting ? 'Submitting Registration...' : 'Submit Registration for Approval'}
            </button>
          </form>
        )}

        <div className="pt-2 text-center text-xs text-[#292039]/70">
          Already registered?{' '}
          <Link to="/login" className="font-semibold text-[#D94378] hover:underline">
            Sign In Here
          </Link>
        </div>
      </div>
    </div>
  )
}
