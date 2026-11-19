import { Link } from 'react-router-dom'
import { IndianHostelIllustration } from '../../components/Illustrations'

export function AboutPage() {
  return (
    <div className="py-12 sm:py-16 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-16">
      {/* Header */}
      <div className="max-w-3xl space-y-4">
        <span className="text-xs font-bold text-[#D94378] tracking-widest uppercase">
          About HostelCare &amp; Our Mission
        </span>
        <h1 className="font-serif text-4xl sm:text-5xl font-bold text-[#292039] leading-tight">
          Restoring peace of mind to collegiate hostel living.
        </h1>
        <p className="text-base sm:text-lg text-[#292039]/80 leading-relaxed">
          HostelCare was envisioned not as enterprise software, but as an empathetic bridge between
          students experiencing their first independent home away from home and the collegiate
          administration dedicated to their safety.
        </p>
      </div>

      {/* Visual Break */}
      <div className="bg-[#F7EFE6] p-4 sm:p-8 rounded-3xl border border-[#E8DCCF]">
        <IndianHostelIllustration className="w-full max-h-96 object-contain" />
      </div>

      {/* Core Principles Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        <div className="p-6 rounded-2xl bg-[#FFFCF7] border border-[#E8DCCF] space-y-3">
          <div className="h-10 w-10 rounded-xl bg-[#D94378]/15 text-[#D94378] flex items-center justify-center font-bold text-lg">
            01
          </div>
          <h3 className="font-serif text-xl font-bold text-[#292039]">No Lost Slips</h3>
          <p className="text-xs sm:text-sm text-[#292039]/70 leading-relaxed">
            Eliminating physical paper registers and unassigned verbal requests. Every reported
            dripping tap or flickering tube light receives a trackable ticket ID.
          </p>
        </div>

        <div className="p-6 rounded-2xl bg-[#FFFCF7] border border-[#E8DCCF] space-y-3">
          <div className="h-10 w-10 rounded-xl bg-[#368F83]/15 text-[#368F83] flex items-center justify-center font-bold text-lg">
            02
          </div>
          <h3 className="font-serif text-xl font-bold text-[#292039]">Clear Accountability</h3>
          <p className="text-xs sm:text-sm text-[#292039]/70 leading-relaxed">
            Duty electricians, plumbers, and carpenters have dedicated rosters. Wardens can see
            pending queues at a glance, ensuring no room waits weeks for essential repairs.
          </p>
        </div>

        <div className="p-6 rounded-2xl bg-[#FFFCF7] border border-[#E8DCCF] space-y-3">
          <div className="h-10 w-10 rounded-xl bg-[#F4AA35]/15 text-[#B36E08] flex items-center justify-center font-bold text-lg">
            03
          </div>
          <h3 className="font-serif text-xl font-bold text-[#292039]">Dignified Living</h3>
          <p className="text-xs sm:text-sm text-[#292039]/70 leading-relaxed">
            A functional desk lamp and quiet ceiling fan are not luxuries—they are foundational to
            studying well and feeling secure during university years.
          </p>
        </div>
      </div>

      {/* Institutional Context */}
      <div className="p-8 sm:p-10 rounded-3xl bg-[#292039] text-[#FFFCF7] flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="space-y-2 max-w-xl">
          <h3 className="font-serif text-2xl font-bold text-white">
            Join the HostelCare Resident Portal
          </h3>
          <p className="text-xs sm:text-sm text-[#D8CEBE]">
            Are you a student living in Block A, B, or C? Self-register your room allotment today.
          </p>
        </div>
        <Link
          to="/register"
          className="px-6 py-3 rounded-xl text-sm font-semibold bg-[#D94378] hover:bg-[#C23365] text-white shrink-0"
        >
          Resident Registration &rarr;
        </Link>
      </div>
    </div>
  )
}
