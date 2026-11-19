import { useState } from 'react'
import { mockHostelInfo } from '../../lib/mockData'

export function ContactPage() {
  const [submitted, setSubmitted] = useState(false)

  const handleSubmit = (e) => {
    e.preventDefault()
    setSubmitted(true)
  }

  return (
    <div className="py-12 sm:py-16 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-12">
      <div className="max-w-2xl space-y-3">
        <span className="text-xs font-bold text-[#D94378] tracking-widest uppercase">
          Administrative &amp; Maintenance Helpdesk
        </span>
        <h1 className="font-serif text-3xl sm:text-5xl font-bold text-[#292039]">
          Contact The Warden Desk
        </h1>
        <p className="text-sm sm:text-base text-[#292039]/75">
          Have queries regarding room allotments, vacation luggage storage, or visitor passes? Reach
          the hostel caretakers.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-stretch">
        {/* Info Column */}
        <div className="lg:col-span-5 bg-[#F7EFE6] p-8 sm:p-10 rounded-3xl border border-[#E8DCCF] flex flex-col justify-between space-y-6">
          <div>
            <h2 className="font-serif text-2xl font-bold text-[#292039] mb-4">
              Hostel Administrative Wing
            </h2>
            <p className="text-xs sm:text-sm text-[#292039]/75 leading-relaxed">
              Resident welfare and facilities maintenance are managed in coordination with the
              college Dean of Student Affairs.
            </p>
          </div>

          <div className="space-y-4 text-xs sm:text-sm text-[#292039]/80">
            <div className="flex items-center gap-3">
              <span className="font-bold text-[#D94378]">Location:</span>
              <span>{mockHostelInfo.wardenOffice}</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="font-bold text-[#D94378]">Visiting:</span>
              <span>{mockHostelInfo.visitingHours}</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="font-bold text-[#D94378]">Emergency:</span>
              <span className="font-mono font-bold text-[#292039]">
                {mockHostelInfo.emergencyContact}
              </span>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-[#FFFCF7] border border-[#E2D4C3] text-xs text-[#292039]/70">
            *Routine room repair tickets must be logged through the Student Portal for technician
            tracking.
          </div>
        </div>

        {/* Form Column */}
        <div className="lg:col-span-7 bg-[#FFFCF7] p-8 sm:p-10 rounded-3xl border border-[#E8DCCF] space-y-6">
          <h3 className="font-serif text-2xl font-bold text-[#292039]">
            Send a message to the Warden Desk
          </h3>

          {submitted ? (
            <div className="p-6 rounded-2xl bg-emerald-50 border border-emerald-300 text-emerald-800 space-y-2">
              <div className="flex items-center gap-2">
                <span className="text-xl">✓</span>
                <h4 className="font-semibold text-sm">Inquiry Received</h4>
              </div>
              <p className="text-xs">
                Your message has been forwarded to the hostel caretaker desk. A notification will be
                shared during office visiting hours.
              </p>
              <button
                onClick={() => setSubmitted(false)}
                className="text-xs font-semibold text-emerald-700 underline pt-2 block"
              >
                Send another inquiry
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-[#292039] mb-1">
                    Your Full Name *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Aarav Sharma"
                    className="w-full px-3.5 py-2.5 rounded-xl border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#D94378] bg-[#FFFCF7]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#292039] mb-1">
                    Roll No. or Contact Relation *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. 2023CSB1042 / Parent"
                    className="w-full px-3.5 py-2.5 rounded-xl border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#D94378] bg-[#FFFCF7]"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#292039] mb-1">Subject *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Clarification regarding upcoming semester room renewal"
                  className="w-full px-3.5 py-2.5 rounded-xl border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#D94378] bg-[#FFFCF7]"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#292039] mb-1">Message *</label>
                <textarea
                  rows={4}
                  required
                  placeholder="Provide your query details..."
                  className="w-full px-3.5 py-2.5 rounded-xl border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#D94378] bg-[#FFFCF7]"
                />
              </div>

              <button
                type="submit"
                className="px-6 py-3 rounded-xl text-sm font-semibold text-white bg-[#292039] hover:bg-[#3D3252] transition-colors cursor-pointer"
              >
                Submit Inquiry
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}
