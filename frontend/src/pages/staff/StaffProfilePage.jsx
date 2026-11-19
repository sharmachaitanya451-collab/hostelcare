import { useState } from 'react'
import { useApp } from '../../context/AppContext'

export function StaffProfilePage() {
  const { user, complaints, updateStaffProfile } = useApp()

  const [phone, setPhone] = useState(user?.phone || '')
  const [email, setEmail] = useState(user?.email || '')
  const [shift, setShift] = useState(user?.shift || 'Morning (08:00 - 16:00)')
  const [isEditing, setIsEditing] = useState(false)
  const [notice, setNotice] = useState(null)

  // Metrics for current technician
  const myTasks = complaints.filter(
    (c) =>
      c.assignedStaff === user?.name ||
      (user?.name && c.assignedStaff && c.assignedStaff.includes(user.name)),
  )

  const activeCount = myTasks.filter((c) =>
    ['Assigned', 'Accepted', 'In Progress'].includes(c.status),
  ).length
  const completedCount = myTasks.filter((c) =>
    ['Completed', 'Resolved', 'Closed'].includes(c.status),
  ).length

  const handleSubmit = async (e) => {
    e.preventDefault()
    try {
      await updateStaffProfile({
        phone: phone.trim(),
        shift: shift.trim(),
      })
      setIsEditing(false)
      setNotice('Profile contact details updated successfully.')
    } catch (err) {
      setNotice(err?.message || 'Unable to update staff profile.')
    }
  }

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#F0E4D4]">
        <div>
          <h1 className="font-serif text-2xl sm:text-3xl font-bold text-[#292039]">
            Duty Staff Profile
          </h1>
          <p className="text-xs text-[#292039]/60">
            Personal maintenance credentials and duty contact details
          </p>
        </div>
        {!isEditing && (
          <button
            type="button"
            onClick={() => setIsEditing(true)}
            className="px-4 py-2 rounded-xl bg-[#292039] text-[#FFFCF7] text-xs font-semibold hover:bg-[#3D3252] transition-colors cursor-pointer self-start sm:self-auto"
          >
            ✏️ Edit Contact Info
          </button>
        )}
      </div>

      {notice && (
        <div className="p-4 rounded-2xl bg-emerald-50 border border-emerald-300 text-emerald-900 text-xs flex items-center justify-between">
          <span>✓ {notice}</span>
          <button onClick={() => setNotice(null)} className="font-bold text-emerald-900">
            ✕
          </button>
        </div>
      )}

      {/* Main Profile Info Card */}
      <div className="bg-[#FFFCF7] p-6 sm:p-8 rounded-3xl border border-[#E8DCCF] shadow-xs space-y-6">
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-5 pb-6 border-b border-[#E8DCCF]">
          <div className="w-16 h-16 rounded-2xl bg-[#D94378] text-[#FFFCF7] flex items-center justify-center font-serif text-2xl font-bold shadow-md">
            {user?.name
              ?.split(' ')
              .map((n) => n[0])
              .slice(0, 2)
              .join('') || 'ST'}
          </div>
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-xl font-bold text-[#292039]">{user?.name}</h2>
              <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-[#368F83]/15 text-[#368F83] border border-[#368F83]/30">
                {user?.trade || 'Maintenance Technician'}
              </span>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-emerald-100 text-emerald-800">
                ACTIVE ON DUTY
              </span>
            </div>
            <p className="text-xs text-[#292039]/70 font-mono">
              Staff ID: <span className="font-bold text-[#292039]">{user?.id || 'STF-DEMO'}</span>
            </p>
          </div>
        </div>

        {/* Task Performance Snapshot */}
        <div className="grid grid-cols-3 gap-3 sm:gap-4 p-4 rounded-2xl bg-[#FBF7F0] border border-[#E8DCCF]">
          <div className="text-center">
            <span className="text-[10px] sm:text-xs font-semibold text-[#292039]/60 uppercase tracking-wider block">
              Total Assigned
            </span>
            <span className="font-serif text-2xl font-bold text-[#292039]">{myTasks.length}</span>
          </div>
          <div className="text-center border-x border-[#E8DCCF]">
            <span className="text-[10px] sm:text-xs font-semibold text-[#292039]/60 uppercase tracking-wider block">
              In Progress
            </span>
            <span className="font-serif text-2xl font-bold text-[#F4AA35]">{activeCount}</span>
          </div>
          <div className="text-center">
            <span className="text-[10px] sm:text-xs font-semibold text-[#292039]/60 uppercase tracking-wider block">
              Completed
            </span>
            <span className="font-serif text-2xl font-bold text-[#368F83]">{completedCount}</span>
          </div>
        </div>

        {/* Profile Details or Edit Form */}
        {isEditing ? (
          <form onSubmit={handleSubmit} className="space-y-5 pt-2">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-[#292039] mb-1">
                  Full Name (Administrative Field)
                </label>
                <input
                  type="text"
                  value={user?.name || ''}
                  disabled
                  className="w-full px-3 py-2 rounded-xl border border-[#D8CEBE] bg-[#F5F2EC] text-xs text-[#292039]/60 cursor-not-allowed"
                />
                <span className="text-[10px] text-[#292039]/50 block mt-1">
                  Name and Trade can only be altered by Hostel Administration.
                </span>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#292039] mb-1">
                  Trade / Specialization
                </label>
                <input
                  type="text"
                  value={user?.trade || ''}
                  disabled
                  className="w-full px-3 py-2 rounded-xl border border-[#D8CEBE] bg-[#F5F2EC] text-xs text-[#292039]/60 cursor-not-allowed"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#292039] mb-1">
                  Contact Phone Number <span className="text-rose-600">*</span>
                </label>
                <input
                  type="tel"
                  required
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="+91 98765 43210"
                  className="w-full px-3 py-2 rounded-xl border border-[#D8CEBE] bg-white text-xs text-[#292039] focus:outline-none focus:border-[#D94378]"
                />
                <span className="text-[10px] text-[#292039]/50 block mt-1">
                  Visible to residents on assigned work order receipts.
                </span>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#292039] mb-1">
                  Email Address
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="ramesh.babu@hostelcare.local"
                  className="w-full px-3 py-2 rounded-xl border border-[#D8CEBE] bg-white text-xs text-[#292039] focus:outline-none focus:border-[#D94378]"
                />
              </div>

              <div className="sm:col-span-2">
                <label className="block text-xs font-semibold text-[#292039] mb-1">
                  Assigned Duty Shift
                </label>
                <select
                  value={shift}
                  onChange={(e) => setShift(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-[#D8CEBE] bg-white text-xs text-[#292039] focus:outline-none focus:border-[#D94378]"
                >
                  <option value="Morning (08:00 - 16:00)">Morning (08:00 - 16:00)</option>
                  <option value="General (09:00 - 17:00)">General (09:00 - 17:00)</option>
                  <option value="Evening (14:00 - 22:00)">Evening (14:00 - 22:00)</option>
                  <option value="Night Emergency (22:00 - 06:00)">
                    Night Emergency (22:00 - 06:00)
                  </option>
                </select>
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-3 border-t border-[#E8DCCF]">
              <button
                type="button"
                onClick={() => {
                  setPhone(user?.phone || '')
                  setEmail(user?.email || '')
                  setShift(user?.shift || 'Morning (08:00 - 16:00)')
                  setIsEditing(false)
                }}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-[#E8DCCF] text-[#292039] hover:bg-[#D8CEBE]"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-5 py-2 rounded-xl text-xs font-semibold bg-[#D94378] text-white hover:bg-[#B83262]"
              >
                Save Changes
              </button>
            </div>
          </form>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 pt-2">
            <div>
              <span className="text-[10px] text-[#292039]/60 uppercase tracking-wider block font-semibold">
                Official Trade
              </span>
              <span className="text-sm font-bold text-[#292039]">
                {user?.trade || 'Electrical Maintenance'}
              </span>
            </div>

            <div>
              <span className="text-[10px] text-[#292039]/60 uppercase tracking-wider block font-semibold">
                Access Authorization
              </span>
              <span className="text-sm font-bold text-[#292039]">Hostel Duty Staff (Level 1)</span>
              <span className="text-[11px] text-[#292039]/60 block">
                Restricted to assigned tasks
              </span>
            </div>

            <div>
              <span className="text-[10px] text-[#292039]/60 uppercase tracking-wider block font-semibold">
                Contact Phone
              </span>
              <span className="text-sm font-bold text-[#292039] font-mono">
                {user?.phone || '+91 98765 43210'}
              </span>
            </div>

            <div>
              <span className="text-[10px] text-[#292039]/60 uppercase tracking-wider block font-semibold">
                Hostel Work Email
              </span>
              <span className="text-sm font-bold text-[#292039]">
                {user?.email || 'ramesh.babu@hostelcare.local'}
              </span>
            </div>

            <div className="sm:col-span-2">
              <span className="text-[10px] text-[#292039]/60 uppercase tracking-wider block font-semibold">
                Duty Shift
              </span>
              <span className="text-sm font-bold text-[#292039]">
                {user?.shift || 'Morning (08:00 - 16:00)'}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Security & Access Notice */}
      <div className="p-4 sm:p-5 rounded-2xl bg-white border border-[#E8DCCF] text-xs text-[#292039]/70 space-y-1">
        <span className="font-bold text-[#292039] block text-[11px] uppercase tracking-wider">
          🔒 System Access Notice
        </span>
        <p>
          Staff login accounts are provisioned exclusively by authorized Chief Wardens. For security
          and audit compliance, duty personnel are strictly limited to their own assigned tasks and
          cannot alter system role classifications or administrative parameters.
        </p>
      </div>
    </div>
  )
}
