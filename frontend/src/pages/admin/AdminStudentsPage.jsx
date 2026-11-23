import { useEffect, useState } from 'react'
import { useApp } from '../../context/AppContext'
import { StatusBadge } from '../../components/Brand'

export function AdminStudentsPage() {
  const { students, studentsLoading, studentsError, fetchStudents, sendUserPasswordReset } =
    useApp()
  const [notice, setNotice] = useState('')
  const [errorMsg, setErrorMsg] = useState('')

  useEffect(() => {
    fetchStudents().catch(() => {})
  }, [fetchStudents])

  const handleSendReset = async (stu) => {
    setNotice('')
    setErrorMsg('')
    try {
      await sendUserPasswordReset(stu.id)
      setNotice(`Dispatched password reset link to ${stu.fullName} (${stu.email}).`)
    } catch (err) {
      setErrorMsg(err?.message || 'Unable to send password reset email.')
    }
  }

  const combinedError = errorMsg || studentsError

  return (
    <div className="space-y-6">
      <div className="pb-4 border-b border-[#F0E4D4]">
        <h2 className="font-serif text-2xl font-bold text-[#292039]">Resident Student Directory</h2>
        <p className="text-xs text-[#292039]/70">
          Verified boarders and pending applicants across all hostel blocks
        </p>
      </div>

      {notice && (
        <div className="p-3.5 rounded-2xl bg-emerald-50 border border-emerald-300 text-emerald-900 text-xs">
          ✓ {notice}
        </div>
      )}
      {combinedError && (
        <div
          role="alert"
          className="p-3.5 rounded-2xl bg-rose-50 border border-rose-300 text-rose-900 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3"
        >
          <span>{combinedError}</span>
          <button
            type="button"
            onClick={() => {
              setErrorMsg('')
              fetchStudents().catch(() => {})
            }}
            className="px-3 py-1.5 rounded-xl bg-rose-700 text-white font-semibold text-xs hover:bg-rose-800 transition-colors cursor-pointer self-start sm:self-auto shrink-0"
          >
            Retry
          </button>
        </div>
      )}

      {studentsLoading && students.length === 0 ? (
        <div className="p-8 rounded-3xl bg-[#FFFCF7] border border-[#E8DCCF] text-center text-xs font-semibold text-[#292039]/70">
          Loading student directory...
        </div>
      ) : (
        <div className="bg-[#FFFCF7] rounded-3xl border border-[#E8DCCF] overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-[#F0E4D4] text-[#292039]/60 font-semibold bg-[#F7EFE6]/50">
                  <th className="p-4">Roll Number</th>
                  <th className="p-4">Student Name</th>
                  <th className="p-4">Room &amp; Block</th>
                  <th className="p-4">Registered Contact</th>
                  <th className="p-4">Admission Date</th>
                  <th className="p-4">Account Status</th>
                  <th className="p-4">Security Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#F7EFE6]">
                {students.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="p-6 text-center text-[#292039]/60">
                      No registered student records found.
                    </td>
                  </tr>
                ) : (
                  students.map((stu) => (
                    <tr key={stu.id} className="hover:bg-[#FDF9F3]">
                      <td className="p-4 font-mono font-bold text-[#292039]">{stu.rollNumber}</td>
                      <td className="p-4 font-semibold text-[#292039]">
                        <div>{stu.fullName}</div>
                        <div className="text-[11px] font-normal text-[#292039]/60">{stu.email}</div>
                      </td>
                      <td className="p-4 font-semibold text-[#D94378]">
                        {stu.room && stu.room !== 'Not Assigned'
                          ? `${stu.room} (${stu.block || 'No Block'})`
                          : 'Not Assigned'}
                      </td>
                      <td className="p-4 text-[#292039]/80">{stu.phone}</td>
                      <td className="p-4 text-[#292039]/60">{stu.joinDate}</td>
                      <td className="p-4">
                        <StatusBadge status={stu.status} />
                      </td>
                      <td className="p-4">
                        {stu.status === 'active' && (
                          <button
                            type="button"
                            onClick={() => handleSendReset(stu)}
                            className="px-2.5 py-1 rounded-lg border border-[#D8CEBE] text-[11px] font-semibold text-[#292039] hover:bg-[#F7EFE6] cursor-pointer"
                          >
                            Send Password Reset
                          </button>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
