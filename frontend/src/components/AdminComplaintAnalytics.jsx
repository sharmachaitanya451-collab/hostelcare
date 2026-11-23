const CATEGORY_BAR_COLORS = ['#D94378', '#368F83', '#F4AA35', '#292039', '#7C3AED', '#C95337']

function formatDuration(hours, seconds) {
  if (hours === null || hours === undefined || Number.isNaN(Number(hours))) {
    return '—'
  }
  const numHours = Number(hours)
  if (seconds !== null && seconds !== undefined && Number(seconds) < 3600) {
    const mins = Math.max(0, Math.round(Number(seconds) / 60))
    return `${mins} min`
  }
  return `${numHours.toFixed(1)} hrs`
}

function formatDayBreakdown(hours) {
  if (hours === null || hours === undefined || Number(hours) < 24) return null
  const total = Math.round(Number(hours))
  const days = Math.floor(total / 24)
  const rem = total % 24
  return `${days}d ${rem}h`
}

function workloadBadgeClasses(indicator) {
  if (indicator === 'Heavy') return 'bg-rose-100 text-rose-800 border-rose-200'
  if (indicator === 'Busy') return 'bg-amber-100 text-amber-800 border-amber-200'
  if (indicator === 'Normal') return 'bg-teal-100 text-teal-800 border-teal-200'
  return 'bg-[#F7EFE6] text-[#292039]/75 border-[#E8DCCF]'
}

function TrendSvgChart({ series }) {
  const width = 600
  const height = 180
  const padLeft = 34
  const padRight = 14
  const padTop = 14
  const padBottom = 28
  const plotW = width - padLeft - padRight
  const plotH = height - padTop - padBottom

  const maxVal = Math.max(1, ...series.flatMap((pt) => [pt.submitted || 0, pt.completed || 0]))
  const stepX = plotW / Math.max(1, series.length)
  const pairWidth = Math.min(26, Math.max(6, stepX * 0.68))
  const barWidth = Math.max(2.5, (pairWidth - 2) / 2)
  const labelStride = series.length <= 10 ? 1 : Math.ceil(series.length / 8)

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="w-full h-44"
      role="img"
      aria-label="Complaint submission and completion trends chart"
    >
      {[0, 0.5, 1].map((frac) => {
        const y = padTop + plotH * (1 - frac)
        const tickVal = Math.round(maxVal * frac)
        return (
          <g key={frac}>
            <line
              x1={padLeft}
              y1={y}
              x2={width - padRight}
              y2={y}
              stroke="#E8DCCF"
              strokeDasharray={frac === 0 ? undefined : '3 3'}
              strokeWidth="1"
            />
            <text
              x={padLeft - 6}
              y={y + 3}
              textAnchor="end"
              fontSize="9"
              fill="#292039"
              opacity="0.6"
            >
              {tickVal}
            </text>
          </g>
        )
      })}

      {series.map((pt, idx) => {
        const centerX = padLeft + stepX * idx + stepX / 2
        const subVal = pt.submitted || 0
        const cmpVal = pt.completed || 0
        const subH = (subVal / maxVal) * plotH
        const cmpH = (cmpVal / maxVal) * plotH
        const subX = centerX - barWidth - 1
        const cmpX = centerX + 1
        const showLabel = idx % labelStride === 0 || idx === series.length - 1

        return (
          <g key={pt.period}>
            <title>{`${pt.label}: ${subVal} submitted, ${cmpVal} completed`}</title>
            <rect
              x={subX}
              y={padTop + plotH - subH}
              width={barWidth}
              height={Math.max(subVal > 0 ? 2 : 0, subH)}
              rx="1.5"
              fill="#D94378"
            />
            <rect
              x={cmpX}
              y={padTop + plotH - cmpH}
              width={barWidth}
              height={Math.max(cmpVal > 0 ? 2 : 0, cmpH)}
              rx="1.5"
              fill="#368F83"
            />
            {showLabel && (
              <text
                x={centerX}
                y={height - 8}
                textAnchor="middle"
                fontSize="9"
                fill="#292039"
                opacity="0.65"
              >
                {pt.label}
              </text>
            )}
          </g>
        )
      })}
    </svg>
  )
}

export function AdminComplaintAnalytics({ data, loading, error, onRetry }) {
  if (error) {
    return (
      <div
        role="alert"
        className="p-4 rounded-2xl bg-rose-50 border border-rose-300 text-rose-900 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3"
      >
        <div>
          <p className="font-bold">Unable to load complaint &amp; SLA analytics</p>
          <p className="mt-0.5 text-rose-800">{error}</p>
        </div>
        <button
          type="button"
          onClick={onRetry}
          className="px-3.5 py-1.5 rounded-xl bg-rose-700 text-white font-semibold text-xs hover:bg-rose-800 transition-colors cursor-pointer self-start sm:self-auto shrink-0"
        >
          Retry
        </button>
      </div>
    )
  }

  if (loading && !data) {
    return (
      <div className="p-8 rounded-3xl bg-[#FFFCF7] border border-[#E8DCCF] text-center space-y-1.5 shadow-xs">
        <p className="text-sm font-semibold text-[#292039]">
          Loading complaint telemetry, SLA compliance, and staff workload...
        </p>
        <p className="text-xs text-[#292039]/65">
          Computing category distributions, MTTR, and priority SLA deadlines.
        </p>
      </div>
    )
  }

  if (!data) return null

  const categories = Array.isArray(data.categories) ? data.categories : []
  const trends = data.trends || { interval: 'daily', series: [] }
  const series = Array.isArray(trends.series) ? trends.series : []
  const resolution = data.resolution || {}
  const sla = data.sla || {}
  const byPriority = Array.isArray(sla.byPriority) ? sla.byPriority : []
  const staff = Array.isArray(data.staff) ? data.staff : []

  const totalSubmittedInTrends = series.reduce((acc, pt) => acc + (pt.submitted || 0), 0)
  const totalCompletedInTrends = series.reduce((acc, pt) => acc + (pt.completed || 0), 0)
  const hasTrendActivity = totalSubmittedInTrends > 0 || totalCompletedInTrends > 0

  const avgDayNote = formatDayBreakdown(resolution.averageHours)
  const medDayNote = formatDayBreakdown(resolution.medianHours)

  return (
    <div className="space-y-6">
      {/* Row 1: Category Distribution & Complaint Trends */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Section A — Category Distribution */}
        <div className="bg-[#FFFCF7] p-6 rounded-3xl border border-[#E8DCCF] space-y-4 shadow-xs">
          <div className="flex items-start justify-between gap-3 pb-3 border-b border-[#F0E4D4]">
            <div>
              <h2 className="font-serif text-lg font-bold text-[#292039]">
                Complaint Category Distribution
              </h2>
              <p className="text-xs text-[#292039]/65">
                Share of submitted maintenance tickets across facility categories
              </p>
            </div>
            {loading && (
              <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 text-[10px] font-semibold">
                Updating...
              </span>
            )}
          </div>

          {categories.length === 0 ? (
            <p className="text-xs text-[#292039]/60 italic py-6 text-center">
              No complaints recorded during the selected reporting window.
            </p>
          ) : (
            <div className="space-y-3">
              {categories.map((cat, idx) => {
                const color = CATEGORY_BAR_COLORS[idx % CATEGORY_BAR_COLORS.length]
                return (
                  <div key={cat.category} className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-semibold text-[#292039]">{cat.category}</span>
                      <span className="text-[#292039]/80 font-medium">
                        {cat.count} <span className="text-[#292039]/60">({cat.percentage}%)</span>
                      </span>
                    </div>
                    <div className="w-full h-2 rounded-full bg-[#F0E4D4] overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all"
                        style={{
                          width: `${Math.min(100, Math.max(2, cat.percentage || 0))}%`,
                          backgroundColor: color,
                        }}
                      />
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Section B — Complaint Trends */}
        <div className="bg-[#FFFCF7] p-6 rounded-3xl border border-[#E8DCCF] space-y-4 shadow-xs">
          <div className="flex items-start justify-between gap-3 pb-3 border-b border-[#F0E4D4]">
            <div>
              <h2 className="font-serif text-lg font-bold text-[#292039]">
                Complaint Volume Trends
              </h2>
              <p className="text-xs text-[#292039]/65">
                Submitted vs completed tickets ({trends.interval} IST buckets)
              </p>
            </div>
            <div className="flex items-center gap-3 text-[11px] font-semibold shrink-0">
              <span className="inline-flex items-center gap-1.5 text-[#292039]">
                <span className="h-2.5 w-2.5 rounded-xs bg-[#D94378]" />
                Submitted ({totalSubmittedInTrends})
              </span>
              <span className="inline-flex items-center gap-1.5 text-[#292039]">
                <span className="h-2.5 w-2.5 rounded-xs bg-[#368F83]" />
                Completed ({totalCompletedInTrends})
              </span>
            </div>
          </div>

          {!hasTrendActivity ? (
            <p className="text-xs text-[#292039]/60 italic py-10 text-center">
              No complaint submissions or completions occurred during this period.
            </p>
          ) : (
            <TrendSvgChart series={series} />
          )}
        </div>
      </div>

      {/* Row 2: MTTR Resolution Performance & SLA Health */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Section C — Resolution Performance (MTTR) */}
        <div className="lg:col-span-4 bg-[#FFFCF7] p-6 rounded-3xl border border-[#E8DCCF] space-y-4 shadow-xs flex flex-col justify-between">
          <div>
            <div className="pb-3 border-b border-[#F0E4D4]">
              <h2 className="font-serif text-lg font-bold text-[#292039]">
                Resolution Performance
              </h2>
              <p className="text-xs text-[#292039]/65">
                Mean Time to Resolution (MTTR) for completed repairs
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-1 gap-3 mt-4">
              <div className="p-3.5 rounded-2xl bg-[#FBF7F0] border border-[#F0E4D4]">
                <span className="text-[10px] text-[#D94378] uppercase font-semibold block">
                  Average MTTR
                </span>
                <div className="font-serif text-2xl font-bold text-[#292039] mt-0.5">
                  {formatDuration(resolution.averageHours, resolution.averageSeconds)}
                </div>
                {avgDayNote && (
                  <span className="text-[10px] text-[#292039]/65">{avgDayNote} avg turnaround</span>
                )}
              </div>

              <div className="p-3.5 rounded-2xl bg-[#FBF7F0] border border-[#F0E4D4]">
                <span className="text-[10px] text-teal-700 uppercase font-semibold block">
                  Median Resolution
                </span>
                <div className="font-serif text-2xl font-bold text-[#368F83] mt-0.5">
                  {formatDuration(resolution.medianHours, resolution.medianSeconds)}
                </div>
                {medDayNote && (
                  <span className="text-[10px] text-[#292039]/65">{medDayNote} median</span>
                )}
              </div>

              <div className="p-3.5 rounded-2xl bg-[#FBF7F0] border border-[#F0E4D4]">
                <span className="text-[10px] text-emerald-700 uppercase font-semibold block">
                  Completed in Period
                </span>
                <div className="font-serif text-2xl font-bold text-emerald-600 mt-0.5">
                  {resolution.completedCount ?? 0}
                </div>
                <span className="text-[10px] text-[#292039]/65">
                  excluding rejected &amp; open tickets
                </span>
              </div>
            </div>
          </div>

          <p className="text-[10px] text-[#292039]/60 pt-2 border-t border-[#F0E4D4]">
            Measures elapsed time from submission (`created_at`) to repair completion
            (`completed_at`), not administrative closure.
          </p>
        </div>

        {/* Section D — SLA Health & Priority Breakdown */}
        <div className="lg:col-span-8 bg-[#FFFCF7] p-6 rounded-3xl border border-[#E8DCCF] space-y-4 shadow-xs">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-[#F0E4D4]">
            <div>
              <h2 className="font-serif text-lg font-bold text-[#292039]">
                SLA Compliance &amp; Breach Monitoring
              </h2>
              <p className="text-xs text-[#292039]/65">
                Priority targets: High (24h), Medium (72h), Low (168h) &middot;{' '}
                {sla.eligibleCount ?? 0} eligible ticket(s)
              </p>
            </div>
            <div className="px-3.5 py-2 rounded-2xl bg-[#FBF7F0] border border-[#E8DCCF] text-right shrink-0">
              <span className="text-[10px] uppercase tracking-wider font-semibold text-[#292039]/60 block">
                SLA Compliance Rate
              </span>
              <span className="font-serif text-xl font-bold text-[#292039]">
                {sla.complianceRate !== null && sla.complianceRate !== undefined
                  ? `${sla.complianceRate}%`
                  : 'N/A'}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-3 rounded-2xl bg-[#FBF7F0] border border-[#F0E4D4]">
              <span className="text-[10px] text-rose-700 uppercase font-semibold block">
                Active Overdue
              </span>
              <div
                className={`font-serif text-xl font-bold mt-0.5 ${
                  (sla.activeOverdue || 0) > 0 ? 'text-rose-600' : 'text-emerald-600'
                }`}
              >
                {sla.activeOverdue ?? 0}
              </div>
              <span className="text-[10px] text-[#292039]/60">past deadline</span>
            </div>

            <div className="p-3 rounded-2xl bg-[#FBF7F0] border border-[#F0E4D4]">
              <span className="text-[10px] text-teal-700 uppercase font-semibold block">
                Active Within SLA
              </span>
              <div className="font-serif text-xl font-bold text-[#368F83] mt-0.5">
                {sla.activeWithinSla ?? 0}
              </div>
              <span className="text-[10px] text-[#292039]/60">on track</span>
            </div>

            <div className="p-3 rounded-2xl bg-[#FBF7F0] border border-[#F0E4D4]">
              <span className="text-[10px] text-emerald-700 uppercase font-semibold block">
                Completed Within SLA
              </span>
              <div className="font-serif text-xl font-bold text-emerald-600 mt-0.5">
                {sla.completedWithinSla ?? 0}
              </div>
              <span className="text-[10px] text-[#292039]/60">on time</span>
            </div>

            <div className="p-3 rounded-2xl bg-[#FBF7F0] border border-[#F0E4D4]">
              <span className="text-[10px] text-amber-700 uppercase font-semibold block">
                Completed After SLA
              </span>
              <div className="font-serif text-xl font-bold text-amber-600 mt-0.5">
                {sla.completedAfterSla ?? 0}
              </div>
              <span className="text-[10px] text-[#292039]/60">SLA breached</span>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-[#F0E4D4] text-[#292039]/60 font-semibold">
                  <th className="py-2">Priority (Target)</th>
                  <th className="py-2 text-right">Eligible</th>
                  <th className="py-2 text-right">Active Overdue</th>
                  <th className="py-2 text-right">Active On Track</th>
                  <th className="py-2 text-right">Completed On Time</th>
                  <th className="py-2 text-right">Breached</th>
                  <th className="py-2 text-right">Compliance</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#F7EFE6]">
                {byPriority.map((row) => (
                  <tr key={row.priority}>
                    <td className="py-2.5 font-semibold text-[#292039]">
                      {row.label}{' '}
                      <span className="text-[10px] font-mono text-[#292039]/60">
                        ({row.targetHours}h)
                      </span>
                    </td>
                    <td className="py-2.5 text-right">{row.total}</td>
                    <td
                      className={`py-2.5 text-right font-semibold ${
                        row.activeOverdue > 0 ? 'text-rose-600' : 'text-[#292039]/70'
                      }`}
                    >
                      {row.activeOverdue}
                    </td>
                    <td className="py-2.5 text-right text-[#368F83] font-medium">
                      {row.activeWithinSla}
                    </td>
                    <td className="py-2.5 text-right text-emerald-700 font-medium">
                      {row.completedWithinSla}
                    </td>
                    <td className="py-2.5 text-right text-amber-700 font-medium">
                      {row.completedAfterSla}
                    </td>
                    <td className="py-2.5 text-right font-semibold text-[#292039]">
                      {row.complianceRate !== null && row.complianceRate !== undefined
                        ? `${row.complianceRate}%`
                        : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Row 3: Section E — Maintenance Staff Workload & Operational Performance */}
      <div className="bg-[#FFFCF7] p-6 rounded-3xl border border-[#E8DCCF] space-y-4 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-[#F0E4D4]">
          <div>
            <h2 className="font-serif text-lg font-bold text-[#292039]">
              Maintenance Staff Workload &amp; Turnaround
            </h2>
            <p className="text-xs text-[#292039]/65">
              Live open ticket load and period completion turnaround across duty technicians
            </p>
          </div>
          <span className="text-[11px] text-[#292039]/65">
            {staff.length} active staff member(s)
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-[#F0E4D4] text-[#292039]/60 font-semibold">
                <th className="pb-2.5">Technician</th>
                <th className="pb-2.5">Trade</th>
                <th className="pb-2.5 text-right">Active Tasks</th>
                <th className="pb-2.5 text-right">In Progress</th>
                <th className="pb-2.5 text-right">Completed (Period)</th>
                <th className="pb-2.5 text-right">Avg Accept</th>
                <th className="pb-2.5 text-right">Avg Complete</th>
                <th className="pb-2.5 text-right">Workload</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#F7EFE6]">
              {staff.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-6 text-center text-[#292039]/60 italic">
                    No active maintenance staff members configured.
                  </td>
                </tr>
              ) : (
                staff.map((st) => (
                  <tr key={st.staffId || st.staffCode}>
                    <td className="py-3 font-semibold text-[#292039]">
                      {st.name}{' '}
                      <span className="text-[10px] font-mono text-[#292039]/55">
                        ({st.staffCode})
                      </span>
                    </td>
                    <td className="py-3 text-[#368F83] font-medium">{st.trade}</td>
                    <td className="py-3 text-right font-bold text-[#292039]">
                      {st.activeAssigned}
                    </td>
                    <td className="py-3 text-right text-[#292039]/80">{st.inProgressTasks}</td>
                    <td className="py-3 text-right font-semibold text-emerald-700">
                      {st.completedCount}
                    </td>
                    <td className="py-3 text-right text-[#292039]/75">
                      {formatDuration(st.avgAcceptanceHours, st.avgAcceptanceSeconds)}
                    </td>
                    <td className="py-3 text-right text-[#292039]/75">
                      {formatDuration(st.avgCompletionHours, st.avgCompletionSeconds)}
                    </td>
                    <td className="py-3 text-right">
                      <span
                        className={`inline-block px-2.5 py-0.5 rounded-full text-[10px] font-bold border ${workloadBadgeClasses(
                          st.workloadIndicator,
                        )}`}
                      >
                        {st.workloadIndicator}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
