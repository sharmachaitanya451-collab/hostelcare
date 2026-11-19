import { IndianHostelIllustration, StudentCommunityIllustration } from './Illustrations'
import { mockFacilities, mockHostelInfo } from '../lib/mockData'

export function HomePage({ onOpenRegister, onOpenAdmin }) {
  return (
    <div className="space-y-24 sm:space-y-32 pb-20">
      {/* ========================================================================= */}
      {/* 1. HERO SECTION                                                          */}
      {/* ========================================================================= */}
      <section id="home" className="relative pt-6 sm:pt-12 overflow-hidden">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-8 items-center">
            {/* Left Column: Heading and Story */}
            <div className="lg:col-span-6 space-y-6 text-center lg:text-left">
              <div className="inline-flex items-center gap-2.5 px-3.5 py-1.5 rounded-full bg-[#D94378]/10 text-[#D94378] border border-[#D94378]/25 text-xs font-semibold tracking-wide">
                <span className="h-1.5 w-1.5 rounded-full bg-[#D94378]" />
                CAMPUS LIVING REDESIGNED
              </div>

              <h1 className="font-serif text-4xl sm:text-5xl lg:text-6xl font-bold text-[#292039] leading-[1.12] tracking-tight">
                Your campus life, <br />
                <span className="italic font-normal text-[#D94378] underline decoration-[#F4AA35] decoration-wavy decoration-2">
                  your second home.
                </span>
              </h1>

              <p className="text-base sm:text-lg text-[#292039]/80 max-w-xl mx-auto lg:mx-0 leading-relaxed">
                HostelCare brings college hostel residents, wardens, and repair teams together on a
                single, responsive platform. Fast maintenance resolutions, room allocation clarity,
                and reliable administration without running between noticeboards.
              </p>

              {/* Action Buttons */}
              <div className="pt-2 flex flex-col sm:flex-row items-center justify-center lg:justify-start gap-4">
                <button
                  onClick={onOpenRegister}
                  className="w-full sm:w-auto px-7 py-3.5 rounded-xl text-base font-semibold text-[#FFFCF7] bg-[#D94378] hover:bg-[#C23365] shadow-md shadow-[#D94378]/30 transition-all cursor-pointer flex items-center justify-center gap-2"
                >
                  <span>Student Registration</span>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2"
                      d="M14 5l7 7m0 0l-7 7m7-7H3"
                    />
                  </svg>
                </button>

                <a
                  href="#how-it-works"
                  className="w-full sm:w-auto px-6 py-3.5 rounded-xl text-base font-semibold text-[#292039] bg-[#F7EFE6] hover:bg-[#EFE3D5] border border-[#E2D4C3] transition-colors text-center"
                >
                  How HostelCare Works
                </a>
              </div>

              {/* Fast stats ribbon */}
              <div className="pt-6 grid grid-cols-3 gap-4 border-t border-[#F0E4D4] max-w-lg mx-auto lg:mx-0 text-left">
                <div>
                  <div className="font-serif text-2xl font-bold text-[#292039]">100%</div>
                  <div className="text-xs text-[#292039]/70 font-medium mt-0.5">
                    Trackable Complaints
                  </div>
                </div>
                <div>
                  <div className="font-serif text-2xl font-bold text-[#368F83]">24-48h</div>
                  <div className="text-xs text-[#292039]/70 font-medium mt-0.5">
                    Average Repair SLA
                  </div>
                </div>
                <div>
                  <div className="font-serif text-2xl font-bold text-[#D94378]">Zero</div>
                  <div className="text-xs text-[#292039]/70 font-medium mt-0.5">
                    Physical Paper Forms
                  </div>
                </div>
              </div>
            </div>

            {/* Right Column: Custom Indian Hostel Architectural Illustration */}
            <div className="lg:col-span-6 relative">
              <div className="relative mx-auto max-w-lg lg:max-w-none rounded-3xl p-3 sm:p-5 bg-gradient-to-tr from-[#F7EFE6] via-[#FFFCF7] to-[#F5ECE1] border-2 border-[#EEDBCA] shadow-xl shadow-[#292039]/5">
                <IndianHostelIllustration className="w-full h-auto drop-shadow-sm rounded-2xl" />

                {/* Floating Badge on Illustration */}
                <div className="absolute -bottom-4 -left-3 sm:left-4 bg-[#FFFCF7] p-3 rounded-2xl border border-[#E8DCCF] shadow-lg flex items-center gap-3">
                  <div className="h-10 w-10 rounded-xl bg-[#368F83] text-[#FFFCF7] flex items-center justify-center font-bold text-lg">
                    ₹0
                  </div>
                  <div className="text-left text-xs">
                    <p className="font-semibold text-[#292039]">No In-App Repair Charges</p>
                    <p className="text-[#368F83]">Covered under term hostel maintenance</p>
                  </div>
                </div>

                <div className="absolute -top-3 -right-2 sm:right-4 bg-[#FFFCF7] px-3.5 py-1.5 rounded-full border border-[#F4AA35]/40 shadow-md text-xs font-semibold text-[#9E5F05] flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-[#F4AA35] animate-ping" />
                  Warden Office Online
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* 2. INTRODUCTION & PHILOSOPHY                                             */}
      {/* ========================================================================= */}
      <section id="about" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="rounded-3xl bg-[#F7EFE6]/80 border border-[#E8DCCF] p-8 sm:p-14 relative overflow-hidden">
          <div className="max-w-3xl space-y-6">
            <span className="text-xs font-bold text-[#368F83] tracking-widest uppercase">
              Hostel Philosophy &amp; Purpose
            </span>
            <h2 className="font-serif text-3xl sm:text-4xl font-bold text-[#292039] leading-snug">
              Hostel life is the crucible of student independence, late-night tea, exam marathons,
              and lifelong friendships.
            </h2>
            <p className="text-base text-[#292039]/80 leading-relaxed">
              Yet too often, students lose valuable study hours chasing electricians, filling paper
              slips for broken taps, or wondering if the warden office received their complaint.
              HostelCare replaces friction with quiet reliability—treating every student room not as
              an inventory unit, but as a home.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 pt-4">
              <div className="bg-[#FFFCF7] p-5 rounded-2xl border border-[#E8DCCF]">
                <div className="h-8 w-8 rounded-lg bg-[#D94378]/15 text-[#D94378] flex items-center justify-center font-bold mb-3">
                  01
                </div>
                <h3 className="font-semibold text-base text-[#292039] mb-1">
                  Transparent Governance
                </h3>
                <p className="text-xs text-[#292039]/70 leading-normal">
                  Every status change—from technician dispatch to parts replacement—is recorded with
                  timestamps and accountable names.
                </p>
              </div>

              <div className="bg-[#FFFCF7] p-5 rounded-2xl border border-[#E8DCCF]">
                <div className="h-8 w-8 rounded-lg bg-[#368F83]/15 text-[#368F83] flex items-center justify-center font-bold mb-3">
                  02
                </div>
                <h3 className="font-semibold text-base text-[#292039] mb-1">
                  Student-First Dignity
                </h3>
                <p className="text-xs text-[#292039]/70 leading-normal">
                  Rooms remain functional so academic focus stays unbroken. Simple photo attachments
                  mean no miscommunication about what is broken.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* 3. HOSTEL FACILITIES & AMENITIES                                         */}
      {/* ========================================================================= */}
      <section id="facilities" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-2xl mx-auto mb-16 space-y-3">
          <span className="text-xs font-bold text-[#D94378] tracking-widest uppercase">
            Campus Infrastructure
          </span>
          <h2 className="font-serif text-3xl sm:text-4xl font-bold text-[#292039]">
            Thoughtfully Built For Collegiate Living
          </h2>
          <p className="text-sm text-[#292039]/75">
            Illustrative amenities provided across our hostel blocks, designed to foster health,
            peace of mind, and peer collaboration.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {mockFacilities.map((fac, idx) => (
            <div
              key={idx}
              className="bg-[#FFFCF7] p-7 rounded-2xl border border-[#E8DCCF] hover:border-[#D94378]/40 hover:shadow-lg hover:shadow-[#D94378]/5 transition-all space-y-4 group"
            >
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold text-[#368F83] bg-[#368F83]/10 px-2.5 py-1 rounded-full border border-[#368F83]/20">
                  {fac.tag}
                </span>
                <span className="text-xs font-mono text-[#D94378] font-bold">0{idx + 1}</span>
              </div>

              <h3 className="font-serif text-xl font-bold text-[#292039] group-hover:text-[#D94378] transition-colors">
                {fac.title}
              </h3>

              <p className="text-xs sm:text-sm text-[#292039]/70 leading-relaxed">{fac.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ========================================================================= */}
      {/* 4. HOSTEL LIFE & COMMUNITY                                               */}
      {/* ========================================================================= */}
      <section id="hostel-life" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
          <div className="lg:col-span-6 order-2 lg:order-1">
            <div className="rounded-3xl p-4 bg-[#F7EFE6] border border-[#E0D3C1] shadow-md">
              <StudentCommunityIllustration className="w-full h-auto rounded-2xl" />
            </div>
          </div>

          <div className="lg:col-span-6 space-y-6 order-1 lg:order-2">
            <span className="text-xs font-bold text-[#F4AA35] tracking-widest uppercase">
              Beyond Just A Room
            </span>
            <h2 className="font-serif text-3xl sm:text-4xl font-bold text-[#292039] leading-tight">
              Community traditions, festive dinners &amp; quiet corners.
            </h2>
            <p className="text-sm text-[#292039]/80 leading-relaxed">
              HostelCare recognizes that hostels are dynamic micro-cities. From Diwali lighting in
              the verandas to annual badminton tournaments and midnight birthday chai runs at the
              gate, we uphold the environment that makes college memories unrepeatable.
            </p>

            <div className="space-y-3.5 pt-2">
              <div className="flex items-start gap-3">
                <div className="h-6 w-6 rounded-full bg-[#368F83]/20 text-[#368F83] flex items-center justify-center shrink-0 mt-0.5 font-bold text-xs">
                  ✓
                </div>
                <div className="text-xs sm:text-sm text-[#292039]/80">
                  <strong>Student Mess Committee:</strong> Monthly rotating menus ensuring dietary
                  variety and fresh seasonal sourcing.
                </div>
              </div>

              <div className="flex items-start gap-3">
                <div className="h-6 w-6 rounded-full bg-[#368F83]/20 text-[#368F83] flex items-center justify-center shrink-0 mt-0.5 font-bold text-xs">
                  ✓
                </div>
                <div className="text-xs sm:text-sm text-[#292039]/80">
                  <strong>Quiet Hours &amp; Study Floor Harmony:</strong> Designated silent hours
                  after 11:00 PM during mid-semester and university examinations.
                </div>
              </div>

              <div className="flex items-start gap-3">
                <div className="h-6 w-6 rounded-full bg-[#368F83]/20 text-[#368F83] flex items-center justify-center shrink-0 mt-0.5 font-bold text-xs">
                  ✓
                </div>
                <div className="text-xs sm:text-sm text-[#292039]/80">
                  <strong>Safe &amp; Respectful Culture:</strong> Strict zero-tolerance anti-ragging
                  protocols verified directly by student welfare wardens.
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* 5. HOW HOSTELCARE WORKS (4 STEPS)                                        */}
      {/* ========================================================================= */}
      <section id="how-it-works" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="rounded-3xl bg-[#292039] text-[#FFFCF7] p-8 sm:p-14 border border-[#44375A]">
          <div className="max-w-2xl mb-12 space-y-3">
            <span className="text-xs font-bold text-[#F4AA35] tracking-widest uppercase">
              Step-by-Step Flow
            </span>
            <h2 className="font-serif text-3xl sm:text-4xl font-bold text-[#FFFCF7]">
              How HostelCare Works
            </h2>
            <p className="text-sm text-[#D8CEBE]">
              Four seamless steps connecting students to administrative action.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {/* Step 1 */}
            <div className="p-6 rounded-2xl bg-[#372B4D] border border-[#52416F] space-y-4">
              <span className="inline-block px-3 py-1 rounded-md bg-[#F4AA35]/20 text-[#F4AA35] text-xs font-mono font-bold">
                STEP 01
              </span>
              <h3 className="font-serif text-lg font-bold text-[#FFFCF7]">Self Registration</h3>
              <p className="text-xs text-[#D8CEBE] leading-relaxed">
                Students register using college roll number, phone number, room assignment, and a
                secure password.
              </p>
            </div>

            {/* Step 2 */}
            <div className="p-6 rounded-2xl bg-[#372B4D] border border-[#52416F] space-y-4">
              <span className="inline-block px-3 py-1 rounded-md bg-[#D94378]/20 text-[#D94378] text-xs font-mono font-bold">
                STEP 02
              </span>
              <h3 className="font-serif text-lg font-bold text-[#FFFCF7]">Warden Verification</h3>
              <p className="text-xs text-[#D8CEBE] leading-relaxed">
                The administration verifies roll details against the institutional hostel allotment
                register before approving access.
              </p>
            </div>

            {/* Step 3 */}
            <div className="p-6 rounded-2xl bg-[#372B4D] border border-[#52416F] space-y-4">
              <span className="inline-block px-3 py-1 rounded-md bg-[#368F83]/20 text-[#368F83] text-xs font-mono font-bold">
                STEP 03
              </span>
              <h3 className="font-serif text-lg font-bold text-[#FFFCF7]">Dashboard Access</h3>
              <p className="text-xs text-[#D8CEBE] leading-relaxed">
                Once approved, students log in to view their allocated room, roommate information,
                and emergency contacts.
              </p>
            </div>

            {/* Step 4 */}
            <div className="p-6 rounded-2xl bg-[#372B4D] border border-[#52416F] space-y-4">
              <span className="inline-block px-3 py-1 rounded-md bg-emerald-400/20 text-emerald-300 text-xs font-mono font-bold">
                STEP 04
              </span>
              <h3 className="font-serif text-lg font-bold text-[#FFFCF7]">1-Click Complaints</h3>
              <p className="text-xs text-[#D8CEBE] leading-relaxed">
                Submit maintenance issues with optional photos. Track assignment to campus
                electricians and plumbers until resolved.
              </p>
            </div>
          </div>

          <div className="mt-12 pt-8 border-t border-[#473B5E] flex flex-col sm:flex-row items-center justify-between gap-4">
            <span className="text-xs text-[#D8CEBE]">
              Are you an institutional staff member or caretaker?
            </span>
            <button
              onClick={onOpenAdmin}
              className="text-xs font-semibold text-[#F4AA35] hover:text-[#FFFCF7] flex items-center gap-1.5 transition-colors"
            >
              <span>Access Administration Console</span>
              <span>&rarr;</span>
            </button>
          </div>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* 6. CONTACT & HELPDESK                                                    */}
      {/* ========================================================================= */}
      <section id="contact" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-stretch">
          <div className="lg:col-span-5 bg-[#F7EFE6] p-8 sm:p-10 rounded-3xl border border-[#E8DCCF] flex flex-col justify-between space-y-6">
            <div>
              <span className="text-xs font-bold text-[#D94378] tracking-widest uppercase">
                Reach The Caretaker
              </span>
              <h2 className="font-serif text-3xl font-bold text-[#292039] mt-2 mb-4">
                Hostel Administrative Office
              </h2>
              <p className="text-xs sm:text-sm text-[#292039]/75 leading-relaxed">
                For routine hostel queries, gate pass inquiries, or room key replacement, drop by
                during designated resident hours.
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
              *Notice: All complaints relating to electrical fixtures, water supply, or furniture
              must be logged through the HostelCare portal for tracking.
            </div>
          </div>

          <div className="lg:col-span-7 bg-[#FFFCF7] p-8 sm:p-10 rounded-3xl border border-[#E8DCCF] space-y-6">
            <h3 className="font-serif text-2xl font-bold text-[#292039]">
              Send an inquiry to the Warden Desk
            </h3>

            <form
              onSubmit={(e) => {
                e.preventDefault()
                alert(
                  'Mock inquiry received! A confirmation note has been noted for the caretaker.',
                )
              }}
              className="space-y-4"
            >
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-[#292039] mb-1">
                    Your Full Name
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Aarav Sharma"
                    required
                    className="w-full px-3.5 py-2.5 rounded-lg border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#D94378] bg-[#FFFCF7]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#292039] mb-1">
                    Student Roll No. or Relation
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. 2023CSB1042 / Parent"
                    required
                    className="w-full px-3.5 py-2.5 rounded-lg border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#D94378] bg-[#FFFCF7]"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#292039] mb-1">Subject</label>
                <input
                  type="text"
                  placeholder="e.g. Clarification regarding upcoming semester room renewal"
                  required
                  className="w-full px-3.5 py-2.5 rounded-lg border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#D94378] bg-[#FFFCF7]"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#292039] mb-1">Message</label>
                <textarea
                  rows={4}
                  placeholder="Provide your query details..."
                  required
                  className="w-full px-3.5 py-2.5 rounded-lg border border-[#D8CEBE] text-sm focus:outline-none focus:border-[#D94378] bg-[#FFFCF7]"
                />
              </div>

              <button
                type="submit"
                className="px-6 py-3 rounded-xl text-sm font-semibold text-[#FFFCF7] bg-[#292039] hover:bg-[#3D3252] transition-colors cursor-pointer"
              >
                Submit Message
              </button>
            </form>
          </div>
        </div>
      </section>
    </div>
  )
}
