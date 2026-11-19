import { Link } from 'react-router-dom'
import { useApp } from '../../../context/AppContext'

export function AdminViolationsPage() {
  const { fines } = useApp()

  // Aggregate by category
  const categoryMap = {}
  const blockMap = { 'Block A': 0, 'Block B': 0, 'Block C': 0 }

  fines.forEach((fine) => {
    categoryMap[fine.category] = (categoryMap[fine.category] || 0) + 1
    if (fine.block && blockMap[fine.block] !== undefined) {
      blockMap[fine.block] += 1
    } else if (fine.room) {
      if (fine.room.startsWith('A')) blockMap['Block A'] += 1
      else if (fine.room.startsWith('B')) blockMap['Block B'] += 1
      else if (fine.room.startsWith('C')) blockMap['Block C'] += 1
    }
  })

  const categoryList = Object.entries(categoryMap).sort((a, b) => b[1] - a[1])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <span className="text-[11px] font-bold text-[#D94378] uppercase tracking-wider">
            Hostel Safety &amp; Disciplinary Oversight
          </span>
          <h1 className="font-serif text-2xl sm:text-3xl font-bold text-[#292039]">
            Violation Trends &amp; Safety Insights
          </h1>
          <p className="text-xs text-[#292039]/70 mt-1">
            Data-informed analysis of residential rule infractions, high-risk items, and wing-level
            trends
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            to="/admin/fines"
            className="px-4 py-2 rounded-xl border border-[#D8CEBE] bg-[#FFFCF7] text-xs font-semibold text-[#292039] hover:bg-[#F7EFE6]"
          >
            &larr; Back to Fines Directory
          </Link>
        </div>
      </div>

      {/* Grid: Category Breakdown & Block Distribution */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Categories */}
        <div className="bg-[#FFFCF7] p-6 rounded-3xl border border-[#E8DCCF] shadow-xs space-y-4">
          <h2 className="font-serif text-base font-bold text-[#292039]">
            Violation Frequency by Category
          </h2>
          <div className="space-y-3">
            {categoryList.length === 0 ? (
              <p className="text-xs text-[#292039]/60">No violation records logged.</p>
            ) : (
              categoryList.map(([cat, count]) => {
                const pct = Math.round((count / fines.length) * 100) || 0
                return (
                  <div key={cat} className="space-y-1">
                    <div className="flex justify-between text-xs">
                      <span className="font-semibold text-[#292039]">{cat}</span>
                      <span className="text-[#292039]/70 font-mono">
                        {count} ({pct}%)
                      </span>
                    </div>
                    <div className="h-2 w-full bg-[#F7EFE6] rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-[#D94378] to-[#F4AA35] rounded-full"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>

        {/* Wing / Block Distribution */}
        <div className="bg-[#FFFCF7] p-6 rounded-3xl border border-[#E8DCCF] shadow-xs space-y-4">
          <h2 className="font-serif text-base font-bold text-[#292039]">
            Infraction Distribution by Hostel Wing
          </h2>
          <div className="space-y-3">
            {fines.length === 0 ? (
              <p className="text-xs text-[#292039]/60">No block-level infractions logged.</p>
            ) : (
              Object.entries(blockMap).map(([block, count]) => {
                const pct = fines.length ? Math.round((count / fines.length) * 100) : 0
                return (
                  <div
                    key={block}
                    className="p-4 rounded-2xl bg-[#FFFDF9] border border-[#E8DCCF] space-y-2"
                  >
                    <div className="flex justify-between items-center text-xs">
                      <span className="font-bold text-[#292039]">{block}</span>
                      <span className="font-mono text-[#D94378] font-bold">{count} Notices</span>
                    </div>
                    <div className="h-1.5 w-full bg-[#F7EFE6] rounded-full overflow-hidden">
                      <div
                        className="h-full bg-[#368F83] rounded-full"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                )
              })
            )}
          </div>

          <div className="p-4 rounded-2xl bg-[#F7EFE6] border border-[#E8DCCF] text-xs text-[#292039]/80 space-y-1">
            <p className="font-semibold text-[#292039]">Welfare Committee Advisory:</p>
            <p>
              Electrical appliance infractions represent the largest hazard category. Wing
              inspection schedules should prioritize circuit safety checks and room heater warnings
              ahead of winter months.
            </p>
          </div>
        </div>
      </div>

      {/* Recent Disciplinary Cases */}
      <div className="bg-[#FFFCF7] p-6 rounded-3xl border border-[#E8DCCF] shadow-xs space-y-4">
        <h2 className="font-serif text-base font-bold text-[#292039]">
          Recent Disciplinary Cases on Record
        </h2>
        <div className="divide-y divide-[#E8DCCF]">
          {fines.slice(0, 5).map((f) => (
            <div key={f.id} className="py-3 flex items-center justify-between gap-4 text-xs">
              <div className="space-y-0.5">
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold">{f.id}</span>
                  <span className="font-semibold text-[#292039]">{f.studentName}</span>
                  <span className="text-[10px] px-2 py-0.5 rounded bg-[#F7EFE6]">{f.category}</span>
                </div>
                <p className="text-[#292039]/70 truncate max-w-lg">{f.description}</p>
              </div>
              <div className="text-right shrink-0">
                <span className="font-bold text-[#D94378]">₹{f.amount}</span>
                <span className="block text-[10px] text-[#292039]/60">{f.status}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
