import { StudentCommunityIllustration } from '../../components/Illustrations'

export function HostelLifePage() {
  return (
    <div className="py-12 sm:py-16 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-16">
      <div className="max-w-3xl space-y-4">
        <span className="text-xs font-bold text-[#F4AA35] tracking-widest uppercase">
          Culture &amp; Everyday Rhythm
        </span>
        <h1 className="font-serif text-3xl sm:text-5xl font-bold text-[#292039] leading-tight">
          Hostel Life: Stories, shared chai &amp; night study.
        </h1>
        <p className="text-sm sm:text-base text-[#292039]/75 leading-relaxed">
          The collegiate hostel experience is where strangers turn into lifelong confidants. We
          maintain an atmosphere where discipline and academic focus balance naturally with
          spontaneous laughter and festive joy.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-center">
        <div className="lg:col-span-6">
          <div className="rounded-3xl p-4 bg-[#F7EFE6] border border-[#E0D3C1]">
            <StudentCommunityIllustration className="w-full h-auto rounded-2xl" />
          </div>
        </div>

        <div className="lg:col-span-6 space-y-6">
          <div className="space-y-4">
            <div className="p-4 rounded-xl bg-[#FFFCF7] border border-[#E8DCCF]">
              <h3 className="font-serif text-lg font-bold text-[#292039]">
                Student Mess Committee
              </h3>
              <p className="text-xs text-[#292039]/70 mt-1">
                Elected monthly by residents. Formulates breakfast, lunch, high tea, and dinner
                menus respecting diverse Indian regional cuisines and seasonal nutrition.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-[#FFFCF7] border border-[#E8DCCF]">
              <h3 className="font-serif text-lg font-bold text-[#292039]">Silent Study Windows</h3>
              <p className="text-xs text-[#292039]/70 mt-1">
                Hostel verandas and corridors maintain strict quiet hours between 11:00 PM and 06:00
                AM during mid-term and university finals, with the silent reference room open until
                01:00 AM.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-[#FFFCF7] border border-[#E8DCCF]">
              <h3 className="font-serif text-lg font-bold text-[#292039]">Festive Traditions</h3>
              <p className="text-xs text-[#292039]/70 mt-1">
                Rangoli competitions during Diwali, hostel sports leagues (cricket &amp; badminton),
                and farewell dinners organized jointly with the warden council.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
