import { Link } from 'react-router-dom'
import { useApp } from '../../context/AppContext'

export function StudentNotificationsPage() {
  const { notifications, markNotificationRead, markAllNotificationsRead } = useApp()

  const unreadCount = notifications.filter((n) => !n.read).length

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#F0E4D4]">
        <div>
          <div className="flex items-center gap-2.5">
            <h2 className="font-serif text-2xl font-bold text-[#292039]">
              Hostel Notices &amp; Updates
            </h2>
            {unreadCount > 0 && (
              <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#D94378] text-white">
                {unreadCount} unread
              </span>
            )}
          </div>
          <p className="text-xs text-[#292039]/70">
            Complaint lifecycle alerts, technician updates, and warden announcements
          </p>
        </div>

        {unreadCount > 0 && (
          <button
            type="button"
            onClick={() => markAllNotificationsRead()}
            className="px-4 py-2 rounded-xl border border-[#292039]/20 bg-white text-[#292039] text-xs font-semibold hover:bg-[#E8DCCF]/30 transition-colors cursor-pointer self-start sm:self-auto"
          >
            ✓ Mark all as read
          </button>
        )}
      </div>

      <div className="space-y-4">
        {notifications.length === 0 ? (
          <div className="bg-[#FFFCF7] p-12 rounded-3xl border border-[#E8DCCF] text-center space-y-2">
            <span className="text-3xl block">🔔</span>
            <h3 className="font-serif text-lg font-bold text-[#292039]">No Notifications</h3>
            <p className="text-xs text-[#292039]/60">
              You have no unread hostel notices or complaint updates right now.
            </p>
          </div>
        ) : (
          notifications.map((n) => (
            <div
              key={n.id}
              onClick={() => markNotificationRead(n.id)}
              className={`p-6 rounded-3xl border transition-all cursor-pointer ${
                n.read
                  ? 'bg-[#FFFCF7] border-[#E8DCCF]'
                  : 'bg-amber-50/70 border-amber-300 shadow-xs'
              }`}
            >
              <div className="flex items-center justify-between pb-2">
                <span
                  className={`text-[11px] font-bold px-2.5 py-0.5 rounded-full uppercase tracking-wider ${
                    n.read ? 'bg-[#F7EFE6] text-[#292039]/70' : 'bg-[#F4AA35] text-[#292039]'
                  }`}
                >
                  {n.category}
                </span>
                <span className="text-xs text-[#292039]/50">{n.time}</span>
              </div>

              <h3 className="font-serif text-lg font-bold text-[#292039]">{n.title}</h3>

              <p className="text-xs text-[#292039]/80 mt-1.5 leading-relaxed">{n.message}</p>

              <div className="mt-3 flex items-center justify-between">
                {!n.read ? (
                  <span className="text-[11px] font-semibold text-[#D94378]">
                    • Click to mark as read
                  </span>
                ) : (
                  <span />
                )}
                {n.entityType === 'complaint' && n.entityRef && (
                  <Link
                    to={`/student/complaints/${n.entityRef}`}
                    onClick={(e) => e.stopPropagation()}
                    className="text-xs font-semibold text-[#368F83] hover:underline"
                  >
                    View Complaint {n.entityRef} &rarr;
                  </Link>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
