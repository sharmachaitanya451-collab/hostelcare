import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useApp } from '../../../context/AppContext'

export function StudentFineDisputePage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user, fines, fetchFineDetail, disputeFine } = useApp()

  const cachedFine = fines.find(
    (f) => String(f.id) === String(id) || (f.referenceNo && f.referenceNo === id),
  )
  const [fineDetail, setFineDetail] = useState(cachedFine || null)
  const [loading, setLoading] = useState(!cachedFine)
  const [loadError, setLoadError] = useState({ status: null, message: '' })

  const [explanation, setExplanation] = useState('')
  const [errorMsg, setErrorMsg] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    let active = true
    fetchFineDetail(id, 'student')
      .then((detail) => {
        if (!active) return
        setFineDetail(detail)
        setLoadError({ status: null, message: '' })
      })
      .catch((err) => {
        if (!active) return
        setLoadError({
          status: err.status || null,
          message: err.message || 'Unable to load fine notice.',
        })
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [id, fetchFineDetail])

  const fine = fineDetail || cachedFine

  if (loading && !fine) {
    return (
      <div className="py-16 text-center space-y-2">
        <h2 className="font-serif text-xl font-bold text-[#292039]">Loading Fine Notice...</h2>
        <p className="text-xs text-[#292039]/65">Checking fine eligibility for dispute.</p>
      </div>
    )
  }

  if (loadError.status === 403) {
    return (
      <div className="py-16 text-center space-y-4">
        <h2 className="font-serif text-2xl font-bold text-[#292039]">Access Restricted</h2>
        <p className="text-xs text-[#292039]/70">{loadError.message}</p>
        <Link
          to="/student/fines"
          className="inline-block px-4 py-2 rounded-xl bg-[#D94378] text-white text-xs font-semibold"
        >
          &larr; Return to My Fines
        </Link>
      </div>
    )
  }

  if (!fine) {
    return (
      <div className="py-16 text-center space-y-4">
        <h2 className="font-serif text-2xl font-bold text-[#292039]">Fine Notice Not Found</h2>
        {loadError.message && <p className="text-xs text-red-700">{loadError.message}</p>}
        <Link
          to="/student/fines"
          className="inline-block px-4 py-2 rounded-xl bg-[#D94378] text-white text-xs font-semibold"
        >
          &larr; Back to Fines
        </Link>
      </div>
    )
  }

  const isOwner =
    !fine.studentId ||
    fine.studentRoll === user?.rollNumber ||
    String(fine.studentId) === String(user?.id)
  if (!isOwner) {
    return (
      <div className="py-16 text-center space-y-4">
        <h2 className="font-serif text-2xl font-bold text-[#292039]">Access Restricted</h2>
        <Link
          to="/student/fines"
          className="inline-block px-4 py-2 rounded-xl bg-[#D94378] text-white text-xs font-semibold"
        >
          &larr; Return to My Fines
        </Link>
      </div>
    )
  }

  if (fine.status === 'Paid' || fine.status === 'Waived' || fine.status === 'Cancelled') {
    return (
      <div className="py-16 text-center space-y-4 max-w-md mx-auto">
        <h2 className="font-serif text-2xl font-bold text-[#292039]">Dispute Not Applicable</h2>
        <p className="text-xs text-[#292039]/70">
          This fine notice is already marked as {fine.status}. Formal disputes may only be submitted
          for pending or overdue notices.
        </p>
        <Link
          to={`/student/fines/${fine.id}`}
          className="inline-block px-4 py-2 rounded-xl bg-[#D94378] text-white text-xs font-semibold"
        >
          View Fine Details
        </Link>
      </div>
    )
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (isSubmitting) return
    setErrorMsg('')

    if (explanation.trim().length < 20) {
      setErrorMsg(
        'Please provide a substantive written explanation (at least 20 characters) explaining why this fine should be reviewed or waived.',
      )
      return
    }

    setIsSubmitting(true)
    try {
      await disputeFine(fine.id, explanation.trim())
      navigate(`/student/fines/${fine.id}`)
    } catch (err) {
      setErrorMsg(err.message || 'Unable to submit dispute. Please try again.')
      setIsSubmitting(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="space-y-1">
        <Link
          to={`/student/fines/${fine.id}`}
          className="text-xs text-[#D94378] font-semibold hover:underline inline-flex items-center gap-1"
        >
          &larr; Back to Fine Notice
        </Link>
        <h1 className="font-serif text-2xl sm:text-3xl font-bold text-[#292039]">
          File Disciplinary Fine Dispute
        </h1>
        <p className="text-xs text-[#292039]/70">
          Submit your formal clarification or mitigating circumstances to the Chief Warden Office
        </p>
      </div>

      {/* Fine Summary Card */}
      <div className="p-5 rounded-2xl bg-[#FFFCF7] border border-[#E8DCCF] shadow-xs space-y-3">
        <div className="flex items-center justify-between text-xs pb-2 border-b border-[#E8DCCF]">
          <span className="font-mono font-bold text-[#292039]">
            Notice: {fine.referenceNo || fine.id}
          </span>
          <span className="font-serif font-bold text-[#D94378] text-base">₹{fine.amount}</span>
        </div>
        <div className="text-xs space-y-1">
          <span className="font-semibold text-[#292039] block">Issuing Allegation:</span>
          <p className="text-[#292039]/80 bg-[#F7EFE6] p-3 rounded-xl">{fine.description}</p>
        </div>
        <div className="flex items-center justify-between text-[11px] text-[#292039]/60">
          <span>Issued By: {fine.issuedBy}</span>
          <span>Payment Due Date: {fine.dueDate}</span>
        </div>
      </div>

      {errorMsg && (
        <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-300 text-amber-900 text-xs">
          {errorMsg}
        </div>
      )}

      {/* Dispute Form */}
      <form
        onSubmit={handleSubmit}
        className="bg-[#FFFCF7] p-6 rounded-3xl border border-[#E8DCCF] shadow-xs space-y-5"
      >
        <div className="space-y-2">
          <label className="block text-xs font-semibold text-[#292039]">
            Detailed Written Explanation &amp; Mitigating Facts *
          </label>
          <textarea
            required
            rows={5}
            value={explanation}
            onChange={(e) => setExplanation(e.target.value)}
            placeholder="Explain clearly what occurred, why this fine should be reconsidered, and reference any relevant gate slips, medical certificates, or maintenance logs..."
            className="w-full px-3.5 py-2.5 rounded-xl border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#D94378] bg-[#FFFDF9]"
          />
          <p className="text-[11px] text-[#292039]/60">
            Be factual and specific. State names, approximate times, or previous complaint numbers
            if applicable.
          </p>
        </div>

        <div className="p-4 rounded-2xl bg-amber-50/70 border border-amber-200 text-amber-950 text-xs space-y-1.5">
          <div className="font-semibold flex items-center gap-1.5 text-amber-900">
            <span>⚖️</span>
            <span>Warden Office Disciplinary Procedure:</span>
          </div>
          <p className="text-[11px] leading-relaxed">
            Upon submission, the fine status will change to <strong>Under Dispute</strong> and
            payment deadlines will be held. The Chief Warden or designated wing warden will review
            your explanation within 3 working days. Submitting fraudulent claims is itself a
            punishable breach of the hostel code.
          </p>
        </div>

        <div className="flex items-center justify-end gap-3 pt-2">
          <Link
            to={`/student/fines/${fine.id}`}
            className="px-4 py-2.5 rounded-xl border border-[#D8CEBE] text-xs font-semibold text-[#292039] hover:bg-[#F7EFE6]"
          >
            Cancel
          </Link>
          <button
            type="submit"
            disabled={isSubmitting}
            className="px-6 py-2.5 rounded-xl bg-[#D94378] text-white text-xs font-semibold hover:bg-[#C23365] shadow-xs cursor-pointer disabled:opacity-50"
          >
            {isSubmitting ? 'Submitting Dispute...' : 'Submit Formal Dispute'}
          </button>
        </div>
      </form>
    </div>
  )
}
