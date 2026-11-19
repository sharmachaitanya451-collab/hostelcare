import { useEffect } from 'react'
import { useApp } from '../../context/AppContext'

export function AdminAuditLogsPage() {
  const { auditLogs, auditLogsLoading, auditLogsError, fetchAuditLogs } = useApp()

  useEffect(() => {
    fetchAuditLogs().catch(() => {})
  }, [fetchAuditLogs])

  return (
    <div className="space-y-6">
      <div className="pb-4 border-b border-[#F0E4D4]">
        <h2 className="font-serif text-2xl font-bold text-[#292039]">
          Hostel Caretaker Audit &amp; Event Logs
        </h2>
        <p className="text-xs text-[#292039]/70">
          Immutable record of student approvals, complaint updates, and administrative events
        </p>
      </div>

      {auditLogsError && (
        <div
          role="alert"
          className="p-3.5 rounded-2xl bg-rose-50 border border-rose-300 text-rose-900 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3"
        >
          <span>{auditLogsError}</span>
          <button
            type="button"
            onClick={() => fetchAuditLogs().catch(() => {})}
            className="px-3 py-1.5 rounded-xl bg-rose-700 text-white font-semibold text-xs hover:bg-rose-800 transition-colors cursor-pointer self-start sm:self-auto shrink-0"
          >
            Retry
          </button>
        </div>
      )}

      {auditLogsLoading && auditLogs.length === 0 ? (
        <div className="p-8 rounded-3xl bg-[#FFFCF7] border border-[#E8DCCF] text-center text-xs font-semibold text-[#292039]/70">
          Loading administrative audit logs...
        </div>
      ) : (
        <div className="bg-[#FFFCF7] rounded-3xl border border-[#E8DCCF] overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-[#F0E4D4] text-[#292039]/60 font-semibold bg-[#F7EFE6]/50">
                  <th className="p-4">Event ID</th>
                  <th className="p-4">Timestamp (IST)</th>
                  <th className="p-4">Actor</th>
                  <th className="p-4">Action</th>
                  <th className="p-4">Target</th>
                  <th className="p-4">Audit Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#F7EFE6]">
                {auditLogs.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="p-6 text-center text-[#292039]/60">
                      No audit events recorded yet.
                    </td>
                  </tr>
                ) : (
                  auditLogs.map((log) => (
                    <tr key={log.id} className="hover:bg-[#FDF9F3]">
                      <td className="p-4 font-mono font-bold text-[#292039]">{log.id}</td>
                      <td className="p-4 text-[#292039]/70 whitespace-nowrap">{log.timestamp}</td>
                      <td className="p-4 font-semibold text-[#292039]">{log.actor}</td>
                      <td className="p-4">
                        <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-bold">
                          {log.action}
                        </span>
                      </td>
                      <td className="p-4 font-semibold text-[#D94378]">{log.target}</td>
                      <td className="p-4 text-[#292039]/80 max-w-sm">{log.details}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
