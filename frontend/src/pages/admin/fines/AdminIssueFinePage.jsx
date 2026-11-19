import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useApp } from '../../../context/AppContext'

export function AdminIssueFinePage() {
  const navigate = useNavigate()
  const { students, issueFine, user } = useApp()

  // Student selection state
  const [selectedStudentId, setSelectedStudentId] = useState('')
  const [studentSearch, setStudentSearch] = useState('')

  // Form fields
  const [category, setCategory] = useState('Prohibited Electrical Appliance')
  const [customCategory, setCustomCategory] = useState('')
  const [description, setDescription] = useState('')
  const [amount, setAmount] = useState('500')
  const [issueDate, setIssueDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [dueDate, setDueDate] = useState(() =>
    new Date(Date.now() + 14 * 86400000).toISOString().slice(0, 10),
  )
  const [issuedBy, setIssuedBy] = useState(user?.fullName || 'Chief Warden Desk')
  const [errorMsg, setErrorMsg] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Filtered students for search dropdown
  const filteredStudents = students.filter(
    (s) =>
      (s.fullName || '').toLowerCase().includes(studentSearch.toLowerCase()) ||
      (s.rollNumber || '').toLowerCase().includes(studentSearch.toLowerCase()) ||
      (s.room || '').toLowerCase().includes(studentSearch.toLowerCase()),
  )

  const selectedStudent = students.find((s) => s.id === selectedStudentId)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (isSubmitting) return
    setErrorMsg('')

    if (!selectedStudentId) {
      setErrorMsg('Please select a student resident from the roster.')
      return
    }

    if (!description.trim() || description.trim().length < 10) {
      setErrorMsg(
        'Mandatory violation description must be detailed and specific (at least 10 characters).',
      )
      return
    }

    if (!amount || Number(amount) <= 0) {
      setErrorMsg('Fine amount must be a positive INR sum.')
      return
    }

    if (!issueDate || !dueDate || dueDate < issueDate) {
      setErrorMsg('Payment due date must be on or after the notice issue date.')
      return
    }

    setIsSubmitting(true)

    try {
      const finalCategory =
        category === 'Other' && customCategory.trim() ? customCategory.trim() : category

      const created = await issueFine({
        studentId: selectedStudentId,
        category: finalCategory,
        description: description.trim(),
        amount: Number(amount),
        issueDate,
        dueDate,
        issuedBy,
      })

      navigate(`/admin/fines/${created.id}`)
    } catch (err) {
      setErrorMsg(err.message || 'Unable to issue disciplinary fine. Please try again.')
      setIsSubmitting(false)
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="space-y-1">
        <Link
          to="/admin/fines"
          className="text-xs text-[#D94378] font-semibold hover:underline inline-flex items-center gap-1"
        >
          &larr; Back to Fines Directory
        </Link>
        <h1 className="font-serif text-2xl sm:text-3xl font-bold text-[#292039]">
          Issue Disciplinary Fine Notice
        </h1>
        <p className="text-xs text-[#292039]/70">
          Record a hostel rule violation and levy penalty dues for an individual resident
        </p>
      </div>

      {errorMsg && (
        <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-300 text-amber-900 text-xs">
          {errorMsg}
        </div>
      )}

      <form
        onSubmit={handleSubmit}
        className="bg-[#FFFCF7] p-6 sm:p-8 rounded-3xl border border-[#E8DCCF] shadow-xs space-y-6"
      >
        {/* Step 1: Student Selection */}
        <div className="space-y-3 pb-6 border-b border-[#E8DCCF]">
          <h2 className="text-xs font-bold text-[#292039] uppercase tracking-wider">
            1. Select Resident Student
          </h2>

          <div className="space-y-2">
            <label className="block text-xs font-semibold text-[#292039]">
              Search by Student Name, Roll Number, or Room *
            </label>
            <input
              type="text"
              value={studentSearch}
              onChange={(e) => setStudentSearch(e.target.value)}
              placeholder="Type e.g. Aarav, 2023CSB1042, or A-203..."
              className="w-full px-3.5 py-2.5 rounded-xl border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#D94378] bg-[#FFFDF9]"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-48 overflow-y-auto p-1 border border-[#E8DCCF] rounded-2xl bg-[#FFFDF9]">
            {filteredStudents.length === 0 ? (
              <div className="col-span-full p-4 text-center text-xs text-[#292039]/60">
                No matching student residents found.
              </div>
            ) : (
              filteredStudents.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => {
                    setSelectedStudentId(s.id)
                    setStudentSearch(`${s.fullName} (${s.rollNumber})`)
                  }}
                  className={`p-3 rounded-xl text-left text-xs transition-all flex items-center justify-between ${
                    selectedStudentId === s.id
                      ? 'bg-[#292039] text-[#FFFCF7] shadow-xs'
                      : 'hover:bg-[#F7EFE6] text-[#292039]'
                  }`}
                >
                  <div>
                    <div className="font-semibold">{s.fullName}</div>
                    <div className="text-[10px] opacity-75 font-mono">
                      {s.rollNumber} • Room {s.room} ({s.block})
                    </div>
                  </div>
                  {selectedStudentId === s.id && (
                    <span className="text-[#F4AA35] font-bold">✓</span>
                  )}
                </button>
              ))
            )}
          </div>

          {selectedStudent && (
            <div className="p-3.5 rounded-xl bg-teal-50 border border-teal-200 text-teal-900 text-xs flex items-center justify-between">
              <div>
                <span className="font-bold">Target Resident:</span> {selectedStudent.fullName} (
                {selectedStudent.rollNumber}) — Room {selectedStudent.room}, {selectedStudent.block}
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-teal-100 font-semibold">
                ID: {selectedStudent.id}
              </span>
            </div>
          )}
        </div>

        {/* Step 2: Category & Mandatory Free-Text Description */}
        <div className="space-y-4 pb-6 border-b border-[#E8DCCF]">
          <h2 className="text-xs font-bold text-[#292039] uppercase tracking-wider">
            2. Violation Particulars
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-[#292039] mb-1">
                General Violation Category (Optional classification)
              </label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-xl border border-[#D8CEBE] text-xs bg-[#FFFDF9] text-[#292039]"
              >
                <option value="Prohibited Electrical Appliance">
                  Prohibited Electrical Appliance
                </option>
                <option value="Hostel Curfew & Gate Entry">Hostel Curfew & Gate Entry</option>
                <option value="Noise & Silent Hours">Noise & Silent Hours</option>
                <option value="Common Property Damage">Common Property Damage</option>
                <option value="Mess Discipline">Mess Discipline</option>
                <option value="Unauthorized Guest & Wing Entry">
                  Unauthorized Guest & Wing Entry
                </option>
                <option value="Sanitation & Cleanliness">Sanitation & Cleanliness</option>
                <option value="Other">Other Specific Infraction</option>
              </select>
            </div>

            {category === 'Other' && (
              <div>
                <label className="block text-xs font-semibold text-[#292039] mb-1">
                  Custom Category Name
                </label>
                <input
                  type="text"
                  value={customCategory}
                  onChange={(e) => setCustomCategory(e.target.value)}
                  placeholder="e.g. Rooftop Access Violation"
                  className="w-full px-3.5 py-2.5 rounded-xl border border-[#D8CEBE] text-xs bg-[#FFFDF9]"
                />
              </div>
            )}
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="block text-xs font-semibold text-[#292039]">
                Mandatory Incident Description (Free-Text) *
              </label>
              <span className="text-[10px] text-[#D94378] font-semibold uppercase">
                Unrestricted Free Text
              </span>
            </div>
            <textarea
              required
              rows={4}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe in exact factual detail what the student did (e.g. Found operating an unapproved 1500W open-coil immersion water heater inside room A-203 during safety check, causing wing circuit breaker trip...)"
              className="w-full px-3.5 py-2.5 rounded-xl border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#D94378] bg-[#FFFDF9]"
            />
            <p className="text-[11px] text-[#292039]/65">
              Hostel rule violations vary considerably. Administrators are not restricted to
              predefined templates and must state the specific evidence or circumstances observed.
            </p>
          </div>
        </div>

        {/* Step 3: Financial & Timeline Terms */}
        <div className="space-y-4 pb-6 border-b border-[#E8DCCF]">
          <h2 className="text-xs font-bold text-[#292039] uppercase tracking-wider">
            3. Financial &amp; Authority Terms
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-semibold text-[#292039] mb-1">
                Fine Amount (INR ₹) *
              </label>
              <div className="relative">
                <span className="absolute left-3.5 top-2.5 font-bold text-slate-500">₹</span>
                <input
                  type="number"
                  min="50"
                  step="50"
                  required
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  className="w-full pl-8 pr-3 py-2 rounded-xl border border-[#D8CEBE] text-sm font-semibold text-[#292039] bg-[#FFFDF9]"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#292039] mb-1">
                Notice Issue Date
              </label>
              <input
                type="date"
                required
                value={issueDate}
                onChange={(e) => setIssueDate(e.target.value)}
                className="w-full px-3.5 py-2 rounded-xl border border-[#D8CEBE] text-xs bg-[#FFFDF9]"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#292039] mb-1">
                Payment Due Date *
              </label>
              <input
                type="date"
                required
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                className="w-full px-3.5 py-2 rounded-xl border border-[#D8CEBE] text-xs bg-[#FFFDF9]"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-[#292039] mb-1">
              Issuing Administrator *
            </label>
            <input
              type="text"
              required
              value={issuedBy}
              onChange={(e) => setIssuedBy(e.target.value)}
              className="w-full px-3.5 py-2 rounded-xl border border-[#D8CEBE] text-xs bg-[#FFFDF9]"
            />
          </div>
        </div>

        {/* Submit */}
        <div className="flex items-center justify-end gap-3 pt-2">
          <Link
            to="/admin/fines"
            className="px-4 py-2.5 rounded-xl border border-[#D8CEBE] text-xs font-semibold text-[#292039] hover:bg-[#F7EFE6]"
          >
            Cancel
          </Link>
          <button
            type="submit"
            disabled={isSubmitting}
            className="px-6 py-2.5 rounded-xl bg-[#D94378] text-white text-xs font-semibold hover:bg-[#C23365] shadow-xs cursor-pointer disabled:opacity-50"
          >
            {isSubmitting ? 'Issuing Notice...' : 'Issue Disciplinary Notice'}
          </button>
        </div>
      </form>
    </div>
  )
}
