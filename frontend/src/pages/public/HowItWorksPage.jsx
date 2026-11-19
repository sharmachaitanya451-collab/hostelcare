import { Link } from 'react-router-dom'

export function HowItWorksPage() {
  const steps = [
    {
      num: '01',
      title: 'Student Self-Registration',
      tag: 'Resident Onboarding',
      desc: 'Fill in your college roll number, full name, registered phone number, and allocated room (e.g. A-203). Create a secure password.',
      note: "Takes under 2 minutes. Account is assigned status 'pending'.",
    },
    {
      num: '02',
      title: 'Warden Verification & Allotment',
      tag: 'Administrative Approval',
      desc: 'The Chief Warden or Administrative Desk cross-checks your registration against the university hostel admission register.',
      note: 'Guards against fake accounts and guarantees verified resident status.',
    },
    {
      num: '03',
      title: 'Dashboard & Room Access',
      tag: 'Live Resident Status',
      desc: 'Once verified, log in anytime to view your assigned bed position, roommate details, hostel notices, and emergency contacts.',
      note: 'Accessible smoothly on mobile phones or campus laptops.',
    },
    {
      num: '04',
      title: '1-Click Maintenance Dispatch',
      tag: 'Rapid Resolution',
      desc: 'Facing water leakage, fan regulator trouble, or broken desk hinges? Submit a complaint with optional photos. Track duty staff assignment in real time.',
      note: 'Complete history log and resolution sign-off.',
    },
  ]

  return (
    <div className="py-12 sm:py-16 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-16">
      <div className="max-w-3xl space-y-4">
        <span className="text-xs font-bold text-[#D94378] tracking-widest uppercase">
          Onboarding &amp; Daily Maintenance
        </span>
        <h1 className="font-serif text-3xl sm:text-5xl font-bold text-[#292039] leading-tight">
          How HostelCare Operates
        </h1>
        <p className="text-sm sm:text-base text-[#292039]/75">
          From the day you move into your room to tracking repair teams, here is how the platform
          keeps your college accommodation running effortlessly.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {steps.map((st) => (
          <div
            key={st.num}
            className="p-8 rounded-3xl bg-[#FFFCF7] border border-[#E8DCCF] space-y-4 relative overflow-hidden"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-[#368F83] bg-[#368F83]/10 px-3 py-1 rounded-full">
                {st.tag}
              </span>
              <span className="font-serif text-3xl font-bold text-[#D94378]">{st.num}</span>
            </div>

            <h3 className="font-serif text-2xl font-bold text-[#292039]">{st.title}</h3>

            <p className="text-xs sm:text-sm text-[#292039]/75 leading-relaxed">{st.desc}</p>

            <div className="pt-2 text-xs text-[#292039]/60 border-t border-[#F0E4D4]">
              💡 {st.note}
            </div>
          </div>
        ))}
      </div>

      <div className="text-center pt-4">
        <Link
          to="/register"
          className="inline-block px-8 py-3.5 rounded-xl text-sm font-semibold bg-[#D94378] text-white hover:bg-[#C23365] shadow-md shadow-[#D94378]/25 transition-all"
        >
          Begin Resident Registration &rarr;
        </Link>
      </div>
    </div>
  )
}
