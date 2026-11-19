import { useState } from 'react'
import { HostelCareLogo } from './Brand'

export function AuthModals({
  isOpen,
  mode, // 'student-login', 'student-register', 'admin-login'
  onClose,
  onSwitchMode,
  onStudentLoginSuccess,
  onStudentRegisterSuccess,
  onAdminLoginSuccess,
}) {
  // Login form state
  const [loginEmail, setLoginEmail] = useState('aarav.sharma@hostelcare.in')
  const [loginPass, setLoginPass] = useState('hostel1234')
  const [adminUser, setAdminUser] = useState('warden@hostelcare.in')
  const [adminPass, setAdminPass] = useState('admin1234')

  // Register form state
  const [regFullName, setRegFullName] = useState('')
  const [regRoll, setRegRoll] = useState('')
  const [regPhone, setRegPhone] = useState('')
  const [regRoom, setRegRoom] = useState('A-203')
  const [regPass, setRegPass] = useState('')
  const [regSuccessNotice, setRegSuccessNotice] = useState(false)

  if (!isOpen) return null

  const handleStudentLogin = (e) => {
    e.preventDefault()
    onStudentLoginSuccess(loginEmail)
  }

  const handleAdminLogin = (e) => {
    e.preventDefault()
    onAdminLoginSuccess(adminUser)
  }

  const handleStudentRegister = (e) => {
    e.preventDefault()
    if (!regFullName || !regRoll || !regPhone || !regPass) return

    onStudentRegisterSuccess({
      fullName: regFullName,
      rollNumber: regRoll,
      phone: regPhone,
      room: regRoom,
      password: regPass,
    })
    setRegSuccessNotice(true)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#292039]/70 backdrop-blur-xs overflow-y-auto">
      <div className="relative w-full max-w-md bg-[#FFFCF7] rounded-3xl border border-[#E8DCCF] shadow-2xl p-6 sm:p-8 my-8 text-left">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-5 right-5 text-[#292039]/50 hover:text-[#292039] p-1.5 rounded-full hover:bg-[#F7EFE6] transition-colors"
          aria-label="Close dialog"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>

        {/* Modal Brand Header */}
        <div className="mb-6">
          <HostelCareLogo showTagline={false} />

          {mode === 'student-login' && (
            <div className="mt-4">
              <h3 className="font-serif text-2xl font-bold text-[#292039]">
                Resident Student Login
              </h3>
              <p className="text-xs text-[#292039]/70 mt-1">
                Enter your registered college email or roll number to access your room maintenance
                portal.
              </p>
            </div>
          )}

          {mode === 'student-register' && (
            <div className="mt-4">
              <h3 className="font-serif text-2xl font-bold text-[#292039]">
                Student Self-Registration
              </h3>
              <p className="text-xs text-[#292039]/70 mt-1">
                Create your resident profile. All accounts require warden approval before protected
                features activate.
              </p>
            </div>
          )}

          {mode === 'admin-login' && (
            <div className="mt-4">
              <h3 className="font-serif text-2xl font-bold text-[#292039]">
                Administration &amp; Warden Access
              </h3>
              <p className="text-xs text-[#292039]/70 mt-1">
                Restricted portal for wardens, caretakers, and college administrative staff.
              </p>
            </div>
          )}
        </div>

        {/* ----------------------------------------------------------------- */}
        {/* FORM 1: STUDENT LOGIN                                             */}
        {/* ----------------------------------------------------------------- */}
        {mode === 'student-login' && (
          <form onSubmit={handleStudentLogin} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-[#292039] mb-1">
                Hostel Email or Roll Number *
              </label>
              <input
                type="text"
                required
                value={loginEmail}
                onChange={(e) => setLoginEmail(e.target.value)}
                placeholder="e.g. aarav.sharma@hostelcare.in"
                className="w-full px-3.5 py-2.5 rounded-xl border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#D94378] bg-[#FFFCF7]"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#292039] mb-1">Password *</label>
              <input
                type="password"
                required
                value={loginPass}
                onChange={(e) => setLoginPass(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-xl border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#D94378] bg-[#FFFCF7]"
              />
            </div>

            <div className="p-3 rounded-xl bg-[#F7EFE6] text-[11px] text-[#292039]/80 border border-[#E8DCCF]">
              <strong>Quick Demo Resident:</strong> Use pre-filled{' '}
              <em>aarav.sharma@hostelcare.in</em> or switch to registration.
            </div>

            <button
              type="submit"
              className="w-full py-3 rounded-xl text-sm font-semibold text-white bg-[#D94378] hover:bg-[#C23365] shadow-md shadow-[#D94378]/25 transition-all cursor-pointer"
            >
              Sign In To Resident Portal
            </button>

            <div className="pt-2 text-center text-xs text-[#292039]/70">
              Not registered yet?{' '}
              <button
                type="button"
                onClick={() => onSwitchMode('student-register')}
                className="font-semibold text-[#D94378] hover:underline"
              >
                Register as a student resident
              </button>
            </div>
          </form>
        )}

        {/* ----------------------------------------------------------------- */}
        {/* FORM 2: STUDENT REGISTRATION                                      */}
        {/* ----------------------------------------------------------------- */}
        {mode === 'student-register' && (
          <div>
            {regSuccessNotice ? (
              <div className="space-y-4 py-4 text-center">
                <div className="h-12 w-12 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center text-2xl mx-auto">
                  ✓
                </div>
                <h4 className="font-serif text-xl font-bold text-[#292039]">
                  Registration Received!
                </h4>
                <div className="p-4 rounded-2xl bg-[#F7EFE6] border border-[#E8DCCF] text-xs text-[#292039]/80 text-left space-y-1.5">
                  <p>
                    <strong>Status:</strong> Pending Administrative Approval
                  </p>
                  <p>
                    <strong>Applicant:</strong> {regFullName} ({regRoll})
                  </p>
                  <p>
                    <strong>Allocated Room:</strong> {regRoom}
                  </p>
                  <p className="text-[11px] text-[#292039]/60 pt-1">
                    Your registration has been logged in the pending approval queue. Once the Warden
                    Desk verifies your admission register, you will be able to log in.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setRegSuccessNotice(false)
                    onSwitchMode('student-login')
                  }}
                  className="w-full py-2.5 rounded-xl text-xs font-semibold text-white bg-[#292039] hover:bg-[#3D3252]"
                >
                  Return to Login
                </button>
              </div>
            ) : (
              <form onSubmit={handleStudentRegister} className="space-y-3.5">
                <div>
                  <label className="block text-xs font-semibold text-[#292039] mb-1">
                    Full Name (As per College ID) *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Vikram Malhotra"
                    value={regFullName}
                    onChange={(e) => setRegFullName(e.target.value)}
                    className="w-full px-3.5 py-2.5 rounded-xl border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#D94378] bg-[#FFFCF7]"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-semibold text-[#292039] mb-1">
                      Roll Number *
                    </label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. 2024MEB1015"
                      value={regRoll}
                      onChange={(e) => setRegRoll(e.target.value)}
                      className="w-full px-3.5 py-2.5 rounded-xl border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#D94378] bg-[#FFFCF7]"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-[#292039] mb-1">
                      Allotted Room *
                    </label>
                    <select
                      value={regRoom}
                      onChange={(e) => setRegRoom(e.target.value)}
                      className="w-full px-3 py-2.5 rounded-xl border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#D94378] bg-[#FFFCF7]"
                    >
                      <option value="A-203">A-203 (Block A)</option>
                      <option value="A-312">A-312 (Block A)</option>
                      <option value="B-105">B-105 (Block B)</option>
                      <option value="B-208">B-208 (Block B)</option>
                      <option value="C-102">C-102 (Block C)</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-[#292039] mb-1">
                    Indian Mobile Number *
                  </label>
                  <input
                    type="tel"
                    required
                    placeholder="+91 98765 43210"
                    value={regPhone}
                    onChange={(e) => setRegPhone(e.target.value)}
                    className="w-full px-3.5 py-2.5 rounded-xl border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#D94378] bg-[#FFFCF7]"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-[#292039] mb-1">
                    Create Password (min 10 characters) *
                  </label>
                  <input
                    type="password"
                    required
                    minLength={8}
                    placeholder="••••••••••••"
                    value={regPass}
                    onChange={(e) => setRegPass(e.target.value)}
                    className="w-full px-3.5 py-2.5 rounded-xl border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#D94378] bg-[#FFFCF7]"
                  />
                </div>

                <div className="p-2.5 rounded-xl bg-amber-50 text-[11px] text-amber-900 border border-amber-200">
                  ⚠️ <strong>Notice:</strong> Accounts undergo verification before protected
                  features become accessible.
                </div>

                <button
                  type="submit"
                  className="w-full py-3 rounded-xl text-sm font-semibold text-white bg-[#D94378] hover:bg-[#C23365] shadow-md shadow-[#D94378]/25 transition-all cursor-pointer"
                >
                  Submit Registration for Approval
                </button>

                <div className="pt-2 text-center text-xs text-[#292039]/70">
                  Already registered?{' '}
                  <button
                    type="button"
                    onClick={() => onSwitchMode('student-login')}
                    className="font-semibold text-[#D94378] hover:underline"
                  >
                    Resident Sign In
                  </button>
                </div>
              </form>
            )}
          </div>
        )}

        {/* ----------------------------------------------------------------- */}
        {/* FORM 3: ADMIN LOGIN                                               */}
        {/* ----------------------------------------------------------------- */}
        {mode === 'admin-login' && (
          <form onSubmit={handleAdminLogin} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-[#292039] mb-1">
                Warden / Administrative Username *
              </label>
              <input
                type="text"
                required
                value={adminUser}
                onChange={(e) => setAdminUser(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-xl border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#292039] bg-[#FFFCF7]"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#292039] mb-1">
                Security Password *
              </label>
              <input
                type="password"
                required
                value={adminPass}
                onChange={(e) => setAdminPass(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-xl border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#292039] bg-[#FFFCF7]"
              />
            </div>

            <div className="p-3 rounded-xl bg-[#292039]/5 text-[11px] text-[#292039]/80 border border-[#D8CEBE]">
              <strong>Demo Administrator:</strong> Pre-filled for instant testing. Grants access to
              student approval and complaint dispatch queues.
            </div>

            <button
              type="submit"
              className="w-full py-3 rounded-xl text-sm font-semibold text-white bg-[#292039] hover:bg-[#3D3252] shadow-md transition-all cursor-pointer"
            >
              Access Administration Dashboard
            </button>

            <div className="pt-2 text-center text-xs text-[#292039]/70">
              Resident student?{' '}
              <button
                type="button"
                onClick={() => onSwitchMode('student-login')}
                className="font-semibold text-[#D94378] hover:underline"
              >
                Resident portal sign in
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
