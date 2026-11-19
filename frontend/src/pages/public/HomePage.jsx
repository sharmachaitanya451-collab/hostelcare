import { Link } from 'react-router-dom'
import {
  IndianHostelIllustration,
  StudentCommunityIllustration,
} from '../../components/Illustrations'
import { mockFacilities, mockHostelInfo } from '../../lib/mockData'

export function HomePage() {
  return (
    <div className="space-y-24 sm:space-y-32 pb-20">
      {/* 1. HERO SECTION */}
      <section className="relative pt-6 sm:pt-12 overflow-hidden">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-8 items-center">
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

              <div className="pt-2 flex flex-col sm:flex-row items-center justify-center lg:justify-start gap-4">
                <Link
                  to="/register"
                  className="w-full sm:w-auto px-7 py-3.5 rounded-xl text-base font-semibold text-[#FFFCF7] bg-[#D94378] hover:bg-[#C23365] shadow-md shadow-[#D94378]/30 transition-all flex items-center justify-center gap-2"
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
                </Link>

                <Link
                  to="/how-it-works"
                  className="w-full sm:w-auto px-6 py-3.5 rounded-xl text-base font-semibold text-[#292039] bg-[#F7EFE6] hover:bg-[#EFE3D5] border border-[#E2D4C3] transition-colors text-center"
                >
                  How HostelCare Works
                </Link>
              </div>

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

            <div className="lg:col-span-6 relative">
              <div className="relative mx-auto max-w-lg lg:max-w-none rounded-3xl p-3 sm:p-5 bg-gradient-to-tr from-[#F7EFE6] via-[#FFFCF7] to-[#F5ECE1] border-2 border-[#EEDBCA] shadow-xl shadow-[#292039]/5">
                <IndianHostelIllustration className="w-full h-auto drop-shadow-sm rounded-2xl" />

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

      {/* 2. PHILOSOPHY PREVIEW */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="rounded-3xl bg-[#F7EFE6]/80 border border-[#E8DCCF] p-8 sm:p-14">
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
              HostelCare replaces friction with quiet reliability.
            </p>
            <Link
              to="/about"
              className="inline-flex items-center gap-2 text-sm font-semibold text-[#D94378] hover:underline"
            >
              <span>Read the full HostelCare story</span>
              <span>&rarr;</span>
            </Link>
          </div>
        </div>
      </section>

      {/* 3. FACILITIES HIGHLIGHT */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col sm:flex-row sm:items-end justify-between mb-12 gap-4">
          <div>
            <span className="text-xs font-bold text-[#D94378] tracking-widest uppercase">
              Campus Infrastructure
            </span>
            <h2 className="font-serif text-3xl font-bold text-[#292039] mt-1">
              Thoughtful Facilities
            </h2>
          </div>
          <Link to="/facilities" className="text-xs font-semibold text-[#D94378] hover:underline">
            View All Amenities &rarr;
          </Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {mockFacilities.slice(0, 3).map((fac, idx) => (
            <div
              key={idx}
              className="bg-[#FFFCF7] p-6 rounded-2xl border border-[#E8DCCF] space-y-3"
            >
              <span className="text-[11px] font-semibold text-[#368F83] bg-[#368F83]/10 px-2 py-0.5 rounded-full">
                {fac.tag}
              </span>
              <h3 className="font-serif text-lg font-bold text-[#292039]">{fac.title}</h3>
              <p className="text-xs text-[#292039]/70 leading-relaxed">{fac.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* 4. STUDENT COMMUNITY TEASER */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-center">
          <div className="lg:col-span-6">
            <div className="rounded-3xl p-4 bg-[#F7EFE6] border border-[#E0D3C1]">
              <StudentCommunityIllustration className="w-full h-auto rounded-2xl" />
            </div>
          </div>
          <div className="lg:col-span-6 space-y-5">
            <span className="text-xs font-bold text-[#F4AA35] tracking-widest uppercase">
              Hostel Life
            </span>
            <h2 className="font-serif text-3xl font-bold text-[#292039]">
              More than four walls. A culture of shared growth.
            </h2>
            <p className="text-xs sm:text-sm text-[#292039]/75 leading-relaxed">
              From festival celebrations in the central courtyard to exam quiet study hours and
              student-supervised mess menus, life at {mockHostelInfo.name} is shaped by residents.
            </p>
            <Link
              to="/hostel-life"
              className="inline-block px-5 py-2.5 rounded-xl text-xs font-semibold text-white bg-[#292039] hover:bg-[#3D3252]"
            >
              Explore Hostel Community &rarr;
            </Link>
          </div>
        </div>
      </section>
    </div>
  )
}
