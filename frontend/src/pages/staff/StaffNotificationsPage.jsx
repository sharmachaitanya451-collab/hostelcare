import { Link } from 'react-router-dom'
import { useApp } from '../../context/AppContext'

export function StaffNotificationsPage() {
  const { user, staffNotifications, markStaffNotificationRead, markAllNotificationsRead } = useApp()

  // Filter notifications for this staff member (or global broadcasts)
  const myNotifications = staffNotifications.filter((n) => !n.staffId || n.staffId === user?.id)

  const unreadCount = myNotifications.filter((n) => !n.read).length

  const handleMarkAllRead = () => {
    markAllNotificationsRead()
  }

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#F0E4D4]">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="font-serif text-2xl sm:text-3xl font-bold text-[#292039]">
              Duty Notifications
            </h1>
            {unreadCount > 0 && (
              <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#D94378] text-white">
                {unreadCount} unread
              </span>
            )}
          </div>
          <p className="text-xs text-[#292039]/60">
            Work order assignments, reworks, and warden instructions
          </p>
        </div>

        {unreadCount > 0 && (
          <button
            type="button"
            onClick={handleMarkAllRead}
            className="px-4 py-2 rounded-xl border border-[#292039]/20 bg-white text-[#292039] text-xs font-semibold hover:bg-[#E8DCCF]/30 transition-colors cursor-pointer self-start sm:self-auto"
          >
            ✓ Mark all as read
          </button>
        )}
      </div>

      {/* Notifications List */}
      <div className="space-y-3">
        {myNotifications.length > 0 ? (
          myNotifications.map((n) => (
            <div
              key={n.id}
              className={`p-5 rounded-2xl border transition-all ${
                n.read
                  ? 'bg-[#FFFCF7] border-[#E8DCCF] opacity-80'
                  : 'bg-white border-[#D94378]/30 shadow-xs ring-1 ring-[#D94378]/10'
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-1.5 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                        n.category === 'Work Order'
                          ? 'bg-purple-100 text-purple-800'
                          : n.category === 'Rework'
                            ? 'bg-amber-100 text-amber-900'
                            : 'bg-[#368F83]/15 text-[#368F83]'
                      }`}
                    >
                      {n.category || 'Duty Alert'}
                    </span>
                    {!n.read && (
                      <span className="w-2 h-2 rounded-full bg-[#D94378]" title="Unread" />
                    )}
                    <span className="text-[11px] text-[#292039]/50 font-mono">{n.time}</span>
                  </div>

                  <h3 className="text-sm font-bold text-[#292039]">{n.title}</h3>
                  <p className="text-xs text-[#292039]/80 leading-relaxed">{n.message}</p>
                </div>

                <div className="flex flex-col items-end gap-2 shrink-0">
                  {!n.read && (
                    <button
                      type="button"
                      onClick={() => markStaffNotificationRead(n.id)}
                      className="text-[11px] font-bold text-[#D94378] hover:underline cursor-pointer"
                    >
                      Mark read
                    </button>
                  )}
                  {(n.entityRef || n.title.includes('CMP-')) && (
                    <Link
                      to={`/staff/tasks/${n.entityRef || n.title.match(/CMP-[\w-]+/)?.[0] || ''}`}
                      className="px-3 py-1.5 rounded-lg bg-[#292039] text-[#FFFCF7] text-[11px] font-semibold hover:bg-[#3D3252] transition-colors"
                    >
                      View Task &rarr;
                    </Link>
                  )}
                </div>
              </div>
            </div>
          ))
        ) : (
          <div className="bg-[#FFFCF7] p-12 rounded-3xl border border-[#E8DCCF] text-center space-y-2">
            <span className="text-3xl block">🔔</span>
            <h3 className="font-serif text-lg font-bold text-[#292039]">No Notifications</h3>
            <p className="text-xs text-[#292039]/60">
              You are completely caught up with all work order alerts.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
