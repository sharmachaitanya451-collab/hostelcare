import { useEffect, useState } from 'react'
import { useApp } from '../../context/AppContext'

export function AdminStaffPage() {
  const {
    staff,
    staffLoading,
    staffError,
    fetchStaff,
    addStaff,
    updateStaff,
    toggleStaffStatus,
    sendUserPasswordReset,
    complaints,
  } = useApp()

  const [showAddModal, setShowAddModal] = useState(false)
  const [editingStaff, setEditingStaff] = useState(null)
  const [editFieldErrors, setEditFieldErrors] = useState({})
  const [editSubmitting, setEditSubmitting] = useState(false)
  const [updatedStaffMember, setUpdatedStaffMember] = useState(null)
  const [notice, setNotice] = useState('')
  const [errorMsg, setErrorMsg] = useState('')

  useEffect(() => {
    fetchStaff().catch(() => {})
  }, [fetchStaff])

  const handleRetry = async () => {
    setErrorMsg('')
    try {
      await fetchStaff()
    } catch {
      // staffError is populated by fetchStaff
    }
  }

  // Add form fields
  const [name, setName] = useState('')
  const [staffCode, setStaffCode] = useState('')
  const [trade, setTrade] = useState('Electrician')
  const [customTrade, setCustomTrade] = useState('')
  const [phone, setPhone] = useState('+91 ')
  const [email, setEmail] = useState('')
  const [shift, setShift] = useState('General (09:00 AM - 05:30 PM)')
  const [status, setStatus] = useState('Active')

  const handleAddSubmit = async (e) => {
    e.preventDefault()
    if (!name.trim() || !phone.trim()) return

    setErrorMsg('')
    setNotice('')
    const finalTrade = trade === 'Other' && customTrade.trim() ? customTrade.trim() : trade

    try {
      const created = await addStaff({
        name: name.trim(),
        staffCode: staffCode.trim() || undefined,
        trade: finalTrade,
        phone: phone.trim(),
        email: email.trim() || `${name.toLowerCase().replace(/\s+/g, '.')}@hostelcare.in`,
        status,
        shift,
      })

      setName('')
      setStaffCode('')
      setCustomTrade('')
      setPhone('+91 ')
      setEmail('')
      setShowAddModal(false)
      setNotice(
        `Provisioned staff account for ${created.name} (${created.staffCode || created.id}). A 30-minute single-use password setup link has been emailed.`,
      )
    } catch (err) {
      setErrorMsg(err?.message || 'Unable to create staff account.')
    }
  }

  const handleEditSubmit = async (e) => {
    e.preventDefault()
    if (!editingStaff || editSubmitting) return

    setEditFieldErrors({})
    setErrorMsg('')
    setNotice('')

    const errors = {}
    const trimmedEmail = (editingStaff.email || '').trim().toLowerCase()
    if (!trimmedEmail) {
      errors.email = 'Email address is required.'
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmedEmail)) {
      errors.email = 'Please provide a valid email address.'
    }

    if (!editingStaff.name?.trim()) {
      errors.name = 'Full name is required.'
    }

    if (!editingStaff.trade?.trim()) {
      errors.trade = 'Role / Specialization is required.'
    }

    if (!editingStaff.phone?.trim()) {
      errors.phone = 'Contact phone is required.'
    }

    if (Object.keys(errors).length > 0) {
      setEditFieldErrors(errors)
      return
    }

    setEditSubmitting(true)
    try {
      const updated = await updateStaff({
        ...editingStaff,
        email: trimmedEmail,
        name: editingStaff.name.trim(),
        trade: editingStaff.trade.trim(),
        phone: editingStaff.phone.trim(),
      })
      const staffResult = updated || { ...editingStaff, email: trimmedEmail }
      setUpdatedStaffMember(staffResult)
      setNotice(
        `Updated staff record for ${staffResult.name || editingStaff.name} (${staffResult.email || trimmedEmail}).`,
      )
      setEditingStaff(null)
      setEditFieldErrors({})
    } catch (err) {
      const msg = err?.message || 'Unable to update staff record.'
      const lower = msg.toLowerCase()
      if (
        err?.status === 409 ||
        lower.includes('already in use') ||
        lower.includes('duplicate email')
      ) {
        setEditFieldErrors({ email: 'Email address is already in use by another user.' })
      } else if (lower.includes('email') || lower.includes('valid email')) {
        setEditFieldErrors({ email: msg })
      } else {
        setEditFieldErrors({ general: msg })
      }
    } finally {
      setEditSubmitting(false)
    }
  }

  const handleToggleStatus = async (s) => {
    setErrorMsg('')
    setNotice('')
    try {
      await toggleStaffStatus(s.id)
      setNotice(`Updated active status for ${s.name}.`)
    } catch (err) {
      setErrorMsg(err?.message || 'Unable to update staff status.')
    }
  }

  const handleSendReset = async (s) => {
    setErrorMsg('')
    setNotice('')
    try {
      await sendUserPasswordReset(s.id)
      setNotice(`Dispatched a 30-minute password setup/reset link to ${s.email}.`)
    } catch (err) {
      setErrorMsg(err?.message || 'Unable to dispatch password reset link.')
    }
  }

  // Calculate live active ticket counts for each staff member
  const getActiveTicketCount = (staffMember) => {
    const fromComplaints = complaints.filter(
      (c) =>
        (c.assignedStaff === staffMember.name || c.assignedStaffId === staffMember.id) &&
        (c.status === 'Assigned' ||
          c.status === 'Accepted' ||
          c.status === 'In Progress' ||
          c.status === 'in_progress'),
    ).length
    return Math.max(fromComplaints, Number(staffMember.activeTickets || 0))
  }

  const combinedError = errorMsg || staffError

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#F0E4D4]">
        <div>
          <span className="text-[11px] font-bold text-[#D94378] uppercase tracking-wider">
            Hostel Duty Roster &amp; Personnel
          </span>
          <h1 className="font-serif text-2xl sm:text-3xl font-bold text-[#292039]">
            Maintenance Staff Management
          </h1>
          <p className="text-xs text-[#292039]/70 mt-1">
            Maintain campus duty personnel records, specializations, contact lines, and duty shifts
          </p>
        </div>

        <button
          onClick={() => setShowAddModal(true)}
          className="px-4 py-2.5 rounded-xl text-xs font-semibold bg-[#292039] text-white hover:bg-[#3D3252] transition-colors self-start sm:self-auto cursor-pointer shadow-xs flex items-center gap-1.5"
        >
          <span>+ Add New Staff Record</span>
        </button>
      </div>

      {notice && (
        <div className="p-3.5 rounded-2xl bg-emerald-50 border border-emerald-300 text-emerald-900 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span>✓</span>
            <span className="font-medium">{notice}</span>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {updatedStaffMember && (
              <button
                type="button"
                onClick={() => handleSendReset(updatedStaffMember)}
                className="px-3 py-1.5 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white font-semibold text-xs transition-colors cursor-pointer"
              >
                Send Password Setup Link
              </button>
            )}
            <button
              type="button"
              onClick={() => {
                setNotice('')
                setUpdatedStaffMember(null)
              }}
              className="text-emerald-700 hover:text-emerald-900 font-bold px-1"
            >
              ✕
            </button>
          </div>
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
            onClick={handleRetry}
            className="px-3 py-1.5 rounded-xl bg-rose-700 text-white font-semibold text-xs hover:bg-rose-800 transition-colors cursor-pointer self-start sm:self-auto shrink-0"
          >
            Retry
          </button>
        </div>
      )}

      {staffLoading && staff.length === 0 ? (
        <div className="p-8 rounded-3xl bg-[#FFFCF7] border border-[#E8DCCF] text-center text-xs font-semibold text-[#292039]/70">
          Loading maintenance staff records...
        </div>
      ) : !staffLoading && !combinedError && staff.length === 0 ? (
        <div className="p-8 rounded-3xl bg-[#FFFCF7] border border-[#E8DCCF] text-center space-y-2">
          <p className="font-serif text-base font-bold text-[#292039]">
            No Maintenance Staff Records Found
          </p>
          <p className="text-xs text-[#292039]/65">
            No maintenance staff members have been provisioned yet. Click &ldquo;+ Add New Staff
            Record&rdquo; to create one.
          </p>
        </div>
      ) : (
        /* Staff Grid */
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {staff.map((s) => {
            const liveTickets = getActiveTicketCount(s)
            const isActive =
              s.status === 'Active' ||
              s.status === 'On Duty' ||
              s.status === 'active' ||
              s.display_status === 'Active'

            return (
              <div
                key={s.id}
                className="p-5 rounded-3xl bg-[#FFFCF7] border border-[#E8DCCF] space-y-4 shadow-xs flex flex-col justify-between"
              >
                <div className="space-y-2">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h3 className="font-serif text-lg font-bold text-[#292039]">{s.name}</h3>
                      <span className="text-xs text-[#368F83] font-semibold block">
                        {s.trade} {s.staffCode ? `• ${s.staffCode}` : ''}
                      </span>
                    </div>

                    <button
                      onClick={() => handleToggleStatus(s)}
                      className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full cursor-pointer transition-colors ${
                        isActive
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-300'
                          : 'bg-slate-100 text-slate-500 border border-slate-300'
                      }`}
                    >
                      {isActive ? 'Active' : 'Inactive'} (toggle)
                    </button>
                  </div>

                  <div className="text-xs text-[#292039]/80 space-y-1.5 pt-2 border-t border-[#F0E4D4]">
                    <div className="flex justify-between">
                      <span className="text-slate-500">Contact:</span>
                      <span className="font-mono font-medium">{s.phone}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Email:</span>
                      <span className="text-slate-700 truncate max-w-[170px]">
                        {s.email || 'N/A'}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Duty Shift:</span>
                      <span className="text-slate-700">{s.shift}</span>
                    </div>
                    <div className="flex justify-between items-center pt-1 border-t border-[#F0E4D4]">
                      <span className="text-slate-500">Active Work Orders:</span>
                      <span
                        className={`font-mono font-bold text-xs px-2 py-0.5 rounded-md ${
                          liveTickets > 0
                            ? 'bg-amber-100 text-amber-900'
                            : 'bg-slate-100 text-slate-600'
                        }`}
                      >
                        {liveTickets} in progress
                      </span>
                    </div>
                  </div>
                </div>

                <div className="pt-2 flex justify-between items-center gap-2 border-t border-[#F0E4D4]">
                  <button
                    type="button"
                    onClick={() => handleSendReset(s)}
                    className="px-2.5 py-1.5 rounded-xl border border-[#D8CEBE] text-[11px] font-semibold text-[#368F83] hover:bg-teal-50 transition-colors cursor-pointer"
                  >
                    Send Setup / Reset Link
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setEditingStaff({
                        ...s,
                        name: s.name || s.fullName || '',
                        email: s.email || '',
                        trade: s.trade || '',
                        phone: s.phone || '',
                        shift: s.shift || '',
                        status: isActive ? 'Active' : 'Inactive',
                      })
                      setEditFieldErrors({})
                    }}
                    className="px-3 py-1.5 rounded-xl border border-[#D8CEBE] text-xs font-semibold text-[#292039] hover:bg-[#F7EFE6] transition-colors cursor-pointer"
                  >
                    Edit Profile
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Modal: Add Staff */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#292039]/60 backdrop-blur-xs">
          <div className="bg-[#FFFCF7] p-6 sm:p-7 rounded-3xl border border-[#E8DCCF] max-w-md w-full space-y-4 shadow-2xl">
            <h3 className="font-serif text-xl font-bold text-[#292039]">Add Maintenance Staff</h3>
            <p className="text-xs text-[#292039]/70">
              Provision a staff account. HostelCare never generates temporary passwords; a 30-minute
              single-use password setup link will be emailed to the staff member.
            </p>

            <form onSubmit={handleAddSubmit} className="space-y-3.5">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-[#292039] mb-1">
                    Full Name *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Ramesh Babu"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-[#D8CEBE] text-xs focus:outline-none focus:border-[#D94378] bg-[#FFFDF9]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#292039] mb-1">
                    Staff Code
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. STF-0005"
                    value={staffCode}
                    onChange={(e) => setStaffCode(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-[#D8CEBE] text-xs focus:outline-none focus:border-[#D94378] bg-[#FFFDF9]"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#292039] mb-1">
                  Staff Email Address *
                </label>
                <input
                  type="email"
                  required
                  placeholder="e.g. ramesh.electrician@hostelcare.in"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-[#D8CEBE] text-xs focus:outline-none focus:border-[#D94378] bg-[#FFFDF9]"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#292039] mb-1">
                  Role / Specialization *
                </label>
                <select
                  value={trade}
                  onChange={(e) => setTrade(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-[#D8CEBE] text-xs bg-[#FFFDF9]"
                >
                  <option value="Electrician">Electrician</option>
                  <option value="Plumber">Plumber</option>
                  <option value="Carpenter">Carpenter</option>
                  <option value="Housekeeping">Housekeeping</option>
                  <option value="General maintenance">General maintenance</option>
                  <option value="IT support">IT support</option>
                  <option value="Other">Other Specific Role</option>
                </select>
              </div>

              {trade === 'Other' && (
                <div>
                  <label className="block text-xs font-semibold text-[#292039] mb-1">
                    Custom Specialization Name
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Masonry &amp; Painting"
                    value={customTrade}
                    onChange={(e) => setCustomTrade(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-[#D8CEBE] text-xs bg-[#FFFDF9]"
                  />
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-[#292039] mb-1">
                    Contact Phone *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="+91 98765 43210"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-[#D8CEBE] text-xs bg-[#FFFDF9]"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-[#292039] mb-1">
                    Active Status
                  </label>
                  <select
                    value={status}
                    onChange={(e) => setStatus(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-[#D8CEBE] text-xs bg-[#FFFDF9]"
                  >
                    <option value="Active">Active</option>
                    <option value="Inactive">Inactive</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#292039] mb-1">
                  Duty Shift Timing
                </label>
                <select
                  value={shift}
                  onChange={(e) => setShift(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-[#D8CEBE] text-xs bg-[#FFFDF9]"
                >
                  <option value="Morning (08:00 AM - 04:30 PM)">
                    Morning (08:00 AM - 04:30 PM)
                  </option>
                  <option value="General (09:00 AM - 05:30 PM)">
                    General (09:00 AM - 05:30 PM)
                  </option>
                  <option value="Evening (01:00 PM - 09:30 PM)">
                    Evening (01:00 PM - 09:30 PM)
                  </option>
                  <option value="Night Emergency On-Call">Night Emergency On-Call</option>
                </select>
              </div>

              <div className="flex justify-end gap-2 pt-3">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-[#E8DCCF] text-[#292039]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-xl text-xs font-semibold bg-[#292039] text-[#FFFCF7] hover:bg-[#3D3252]"
                >
                  Save Staff Member
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Edit Staff */}
      {editingStaff && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#292039]/60 backdrop-blur-xs">
          <div className="bg-[#FFFCF7] p-6 sm:p-7 rounded-3xl border border-[#E8DCCF] max-w-md w-full space-y-4 shadow-2xl">
            <h3 className="font-serif text-xl font-bold text-[#292039]">
              Edit Staff: {editingStaff.name}
            </h3>

            {editFieldErrors.general && (
              <div
                role="alert"
                className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 text-xs"
              >
                {editFieldErrors.general}
              </div>
            )}

            <form onSubmit={handleEditSubmit} className="space-y-3.5" noValidate>
              <div>
                <label
                  htmlFor="edit-staff-name"
                  className="block text-xs font-semibold text-[#292039] mb-1"
                >
                  Full Name *
                </label>
                <input
                  id="edit-staff-name"
                  type="text"
                  required
                  value={editingStaff.name}
                  onChange={(e) => {
                    setEditingStaff({ ...editingStaff, name: e.target.value })
                    if (editFieldErrors.name) setEditFieldErrors((p) => ({ ...p, name: undefined }))
                  }}
                  className={`w-full px-3 py-2 rounded-xl border ${
                    editFieldErrors.name
                      ? 'border-rose-400 bg-rose-50/20'
                      : 'border-[#D8CEBE] bg-[#FFFDF9]'
                  } text-xs text-[#292039] focus:outline-none focus:border-[#368F83]`}
                />
                {editFieldErrors.name && (
                  <p className="text-[11px] text-rose-600 font-medium mt-1">
                    {editFieldErrors.name}
                  </p>
                )}
              </div>

              <div>
                <label
                  htmlFor="edit-staff-email"
                  className="block text-xs font-semibold text-[#292039] mb-1"
                >
                  Email Address *
                </label>
                <input
                  id="edit-staff-email"
                  type="email"
                  required
                  value={editingStaff.email || ''}
                  onChange={(e) => {
                    setEditingStaff({ ...editingStaff, email: e.target.value })
                    if (editFieldErrors.email)
                      setEditFieldErrors((p) => ({ ...p, email: undefined }))
                  }}
                  className={`w-full px-3 py-2 rounded-xl border ${
                    editFieldErrors.email
                      ? 'border-rose-400 bg-rose-50/20'
                      : 'border-[#D8CEBE] bg-[#FFFDF9]'
                  } text-xs text-[#292039] focus:outline-none focus:border-[#368F83]`}
                />
                {editFieldErrors.email && (
                  <p className="text-[11px] text-rose-600 font-medium mt-1">
                    {editFieldErrors.email}
                  </p>
                )}
              </div>

              <div>
                <label
                  htmlFor="edit-staff-trade"
                  className="block text-xs font-semibold text-[#292039] mb-1"
                >
                  Role / Specialization *
                </label>
                <input
                  id="edit-staff-trade"
                  type="text"
                  required
                  value={editingStaff.trade}
                  onChange={(e) => {
                    setEditingStaff({ ...editingStaff, trade: e.target.value })
                    if (editFieldErrors.trade)
                      setEditFieldErrors((p) => ({ ...p, trade: undefined }))
                  }}
                  className={`w-full px-3 py-2 rounded-xl border ${
                    editFieldErrors.trade
                      ? 'border-rose-400 bg-rose-50/20'
                      : 'border-[#D8CEBE] bg-[#FFFDF9]'
                  } text-xs text-[#292039] focus:outline-none focus:border-[#368F83]`}
                />
                {editFieldErrors.trade && (
                  <p className="text-[11px] text-rose-600 font-medium mt-1">
                    {editFieldErrors.trade}
                  </p>
                )}
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label
                    htmlFor="edit-staff-phone"
                    className="block text-xs font-semibold text-[#292039] mb-1"
                  >
                    Contact Phone *
                  </label>
                  <input
                    id="edit-staff-phone"
                    type="text"
                    required
                    value={editingStaff.phone}
                    onChange={(e) => {
                      setEditingStaff({ ...editingStaff, phone: e.target.value })
                      if (editFieldErrors.phone)
                        setEditFieldErrors((p) => ({ ...p, phone: undefined }))
                    }}
                    className={`w-full px-3 py-2 rounded-xl border ${
                      editFieldErrors.phone
                        ? 'border-rose-400 bg-rose-50/20'
                        : 'border-[#D8CEBE] bg-[#FFFDF9]'
                    } text-xs text-[#292039] focus:outline-none focus:border-[#368F83]`}
                  />
                  {editFieldErrors.phone && (
                    <p className="text-[11px] text-rose-600 font-medium mt-1">
                      {editFieldErrors.phone}
                    </p>
                  )}
                </div>

                <div>
                  <label
                    htmlFor="edit-staff-status"
                    className="block text-xs font-semibold text-[#292039] mb-1"
                  >
                    Active Status
                  </label>
                  <select
                    id="edit-staff-status"
                    value={editingStaff.status}
                    onChange={(e) => setEditingStaff({ ...editingStaff, status: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl border border-[#D8CEBE] text-xs bg-[#FFFDF9] text-[#292039]"
                  >
                    <option value="Active">Active</option>
                    <option value="Inactive">Inactive</option>
                  </select>
                </div>
              </div>

              <div>
                <label
                  htmlFor="edit-staff-shift"
                  className="block text-xs font-semibold text-[#292039] mb-1"
                >
                  Duty Shift
                </label>
                <input
                  id="edit-staff-shift"
                  type="text"
                  value={editingStaff.shift}
                  onChange={(e) => setEditingStaff({ ...editingStaff, shift: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl border border-[#D8CEBE] text-xs bg-[#FFFDF9] text-[#292039]"
                />
              </div>

              <div className="flex flex-wrap items-center justify-between gap-2 pt-3 border-t border-[#F0E4D4]">
                <button
                  type="button"
                  onClick={() => handleSendReset(editingStaff)}
                  className="px-3.5 py-2 rounded-xl text-xs font-semibold border border-[#D8CEBE] text-[#368F83] hover:bg-teal-50 transition-colors cursor-pointer"
                  title="Generate a fresh single-use password setup link for this staff member"
                >
                  Send Password Setup Link
                </button>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setEditingStaff(null)
                      setEditFieldErrors({})
                    }}
                    className="px-4 py-2 rounded-xl text-xs font-semibold bg-[#E8DCCF] text-[#292039] hover:bg-[#DDD0C2] cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={editSubmitting}
                    className="px-5 py-2 rounded-xl text-xs font-semibold bg-[#368F83] text-white hover:bg-[#2B7369] disabled:opacity-50 cursor-pointer"
                  >
                    {editSubmitting ? 'Updating...' : 'Update Record'}
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
