import { mockFacilities } from '../../lib/mockData'

export function FacilitiesPage() {
  return (
    <div className="py-12 sm:py-16 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-12">
      <div className="max-w-2xl space-y-3">
        <span className="text-xs font-bold text-[#D94378] tracking-widest uppercase">
          Hostel Infrastructure &amp; Amenities
        </span>
        <h1 className="font-serif text-3xl sm:text-5xl font-bold text-[#292039]">
          Campus Facilities
        </h1>
        <p className="text-sm sm:text-base text-[#292039]/75">
          Designed for quiet study, community gatherings, health, and reliable routine utilities
          across all three hostel wings.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
        {mockFacilities.map((fac, idx) => (
          <div
            key={idx}
            className="p-8 rounded-3xl bg-[#FFFCF7] border border-[#E8DCCF] space-y-4 hover:border-[#D94378]/40 hover:shadow-lg hover:shadow-[#D94378]/5 transition-all"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-[#368F83] bg-[#368F83]/10 px-3 py-1 rounded-full">
                {fac.tag}
              </span>
              <span className="font-mono text-xs font-bold text-[#D94378]">REF 0{idx + 1}</span>
            </div>

            <h3 className="font-serif text-2xl font-bold text-[#292039]">{fac.title}</h3>

            <p className="text-xs sm:text-sm text-[#292039]/75 leading-relaxed">{fac.desc}</p>

            <div className="pt-2 text-[11px] text-[#292039]/50 border-t border-[#F0E4D4]">
              Maintained under campus estate &amp; student mess committee protocols.
            </div>
          </div>
        ))}
      </div>

      <div className="p-6 rounded-2xl bg-[#F7EFE6] border border-[#E5D7C5] text-xs text-[#292039]/80 space-y-1">
        <p className="font-semibold text-sm text-[#292039]">Maintenance Reporting Note:</p>
        <p>
          If any facility fixture (such as corridor Wi-Fi repeaters, solar water heating line, or
          water coolers) requires servicing, residents can file a quick ticket through the student
          portal.
        </p>
      </div>
    </div>
  )
}
