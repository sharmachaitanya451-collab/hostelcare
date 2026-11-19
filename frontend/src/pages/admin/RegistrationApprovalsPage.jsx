import { useState } from 'react'
import { useApp } from '../../context/AppContext'
import { StatusBadge } from '../../components/Brand'

export function RegistrationApprovalsPage() {
  const { students, approveStudent, rejectStudent, reactivateStudent } = useApp()

  const [reasonDrafts, setReasonDrafts] = useState({})
  const [notice, setNotice] = useState('')
  const [errorMsg, setErrorMsg] = useState('')

  const pendingApprovals = students.filter((s) => s.status === 'pending')
  const rejectedStudents = students.filter((s) => s.status === 'rejected')

  const getDraft = (id) => reasonDrafts[id] || ''
  const setDraft = (id, val) => setReasonDrafts((prev) => ({ ...prev, [id]: val }))

  const handleApprove = async (stu) => {
    setErrorMsg('')
    setNotice('')
    try {
      await approveStudent(stu.id, getDraft(stu.id) || 'Verified and approved by Warden Office.')
      setNotice(`Approved registration for ${stu.fullName} (${stu.rollNumber}).`)
    } catch (err) {
      setErrorMsg(err?.message || 'Unable to approve student registration.')
    }
  }

  const handleReject = async (stu) => {
    setErrorMsg('')
    setNotice('')
    const reason = getDraft(stu.id).trim()
    if (!reason) {
      setErrorMsg(
        `Please enter a mandatory rejection reason before rejecting ${stu.fullName} (${stu.rollNumber}).`,
      )
      return
    }
    try {
      await rejectStudent(stu.id, reason)
      setDraft(stu.id, '')
      setNotice(`Rejected registration for ${stu.fullName} (${stu.rollNumber}).`)
    } catch (err) {
      setErrorMsg(err?.message || 'Unable to reject student registration.')
    }
  }

  const handleReactivate = async (stu) => {
    setErrorMsg('')
    setNotice('')
    const reason = getDraft(stu.id).trim()
    if (!reason) {
      setErrorMsg(
        `Please enter a mandatory reactivation reason before reactivating ${stu.fullName} (${stu.rollNumber}).`,
      )
      return
    }
    try {
      await reactivateStudent(stu.id, reason)
      setDraft(stu.id, '')
      setNotice(
        `Reactivated ${stu.fullName} (${stu.rollNumber}) back to pending review on the existing account.`,
      )
    } catch (err) {
      setErrorMsg(err?.message || 'Unable to reactivate rejected student registration.')
    }
  }

  return (
    <div className="space-y-6">
      <div className="pb-4 border-b border-[#F0E4D4]">
        <h2 className="font-serif text-2xl font-bold text-[#292039]">
          Pending Student Registrations
        </h2>
        <p className="text-xs text-[#292039]/70">
          Self-registered accounts requiring administrative approval before portal activation.
        </p>
      </div>

      {notice && (
        <div className="p-3.5 rounded-2xl bg-emerald-50 border border-emerald-300 text-emerald-900 text-xs">
          ✓ {notice}
        </div>
      )}

      {errorMsg && (
        <div
          role="alert"
          className="p-3.5 rounded-2xl bg-rose-50 border border-rose-300 text-rose-900 text-xs"
        >
          {errorMsg}
        </div>
      )}

      {pendingApprovals.length === 0 ? (
        <div className="bg-[#FFFCF7] p-12 rounded-3xl border border-[#E8DCCF] text-center space-y-2">
          <span className="text-3xl">✓</span>
          <h3 className="font-serif text-lg font-bold text-[#292039]">No Pending Registrations</h3>
          <p className="text-xs text-[#292039]/60">
            All student accounts are verified and up to date.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {pendingApprovals.map((stu) => (
            <div
              key={stu.id}
              className="bg-[#FFFCF7] p-5 sm:p-6 rounded-3xl border border-[#E8DCCF] flex flex-col gap-4"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-[#D94378]">
                      {stu.rollNumber}
                    </span>
                    <StatusBadge status={stu.status} />
                  </div>
                  <h4 className="font-serif text-lg font-bold text-[#292039]">{stu.fullName}</h4>
                  <p className="text-xs text-[#292039]/70">
                    Email: <strong>{stu.email}</strong> • Phone: {stu.phone} • Room:{' '}
                    <strong>{stu.room || 'Unallocated'}</strong>
                  </p>
                  <p className="text-[11px] text-[#292039]/50">Applied on {stu.joinDate}</p>
                </div>

                <div className="flex items-center gap-2.5 self-end sm:self-auto">
                  <button
                    type="button"
                    onClick={() => handleReject(stu)}
                    className="px-4 py-2 rounded-xl text-xs font-semibold text-red-700 bg-red-50 hover:bg-red-100 border border-red-200 transition-colors cursor-pointer"
                  >
                    Reject
                  </button>
                  <button
                    type="button"
                    onClick={() => handleApprove(stu)}
                    className="px-5 py-2 rounded-xl text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 shadow-sm transition-colors cursor-pointer"
                  >
                    Approve Student
                  </button>
                </div>
              </div>

              <div>
                <input
                  type="text"
                  value={getDraft(stu.id)}
                  onChange={(e) => setDraft(stu.id, e.target.value)}
                  placeholder="Review note (required when rejecting registration)..."
                  className="w-full px-3.5 py-2 rounded-xl border border-[#D8CEBE] text-xs bg-white focus:outline-none focus:border-[#D94378]"
                />
              </div>
            </div>
          ))}
        </div>
      )}

      {rejectedStudents.length > 0 && (
        <div className="pt-4 space-y-4">
          <div className="pb-2 border-b border-[#F0E4D4]">
            <h3 className="font-serif text-lg font-bold text-[#292039]">
              Rejected Student Registrations (Controlled Reactivation)
            </h3>
            <p className="text-xs text-[#292039]/70">
              Reactivating a rejected student transitions the existing account back to pending
              review without creating duplicate roll numbers.
            </p>
          </div>

          {rejectedStudents.map((stu) => (
            <div
              key={stu.id}
              className="bg-[#FFFCF7] p-5 rounded-3xl border border-[#E8DCCF] flex flex-col gap-3"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-[#D94378]">
                      {stu.rollNumber}
                    </span>
                    <StatusBadge status={stu.status} />
                  </div>
                  <h4 className="font-serif text-base font-bold text-[#292039]">{stu.fullName}</h4>
                  <p className="text-xs text-[#292039]/70">
                    {stu.email} • {stu.phone}
                  </p>
                  {stu.reviewNote && (
                    <p className="text-[11px] text-rose-800 mt-1">
                      Previous note: {stu.reviewNote}
                    </p>
                  )}
                </div>

                <button
                  type="button"
                  onClick={() => handleReactivate(stu)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-[#292039] bg-[#F4AA35] hover:bg-[#E29822] transition-colors cursor-pointer self-end sm:self-auto"
                >
                  Reactivate to Pending
                </button>
              </div>

              <input
                type="text"
                value={getDraft(stu.id)}
                onChange={(e) => setDraft(stu.id, e.target.value)}
                placeholder="Mandatory reactivation reason (e.g. Original college ID verified at Warden Office)..."
                className="w-full px-3.5 py-2 rounded-xl border border-[#D8CEBE] text-xs bg-white focus:outline-none focus:border-[#D94378]"
              />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
