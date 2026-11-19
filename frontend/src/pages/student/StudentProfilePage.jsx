import { useApp } from '../../context/AppContext'
import { StatusBadge } from '../../components/Brand'

export function StudentProfilePage() {
  const { user } = useApp()

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="pb-4 border-b border-[#F0E4D4]">
        <h2 className="font-serif text-2xl font-bold text-[#292039]">Student Profile Record</h2>
        <p className="text-xs text-[#292039]/70">
          Official resident credentials verified by hostel administration
        </p>
      </div>

      <div className="bg-[#FFFCF7] p-6 sm:p-8 rounded-3xl border border-[#E8DCCF] space-y-6">
        <div className="flex items-center gap-4 pb-6 border-b border-[#F0E4D4]">
          <div
            className={`h-16 w-16 rounded-2xl ${user?.avatarColor || 'bg-[#D94378]'} text-white font-bold text-2xl flex items-center justify-center`}
          >
            {user?.fullName?.charAt(0) || 'S'}
          </div>
          <div>
            <h3 className="font-serif text-xl font-bold text-[#292039]">{user?.fullName}</h3>
            <p className="text-xs font-mono text-[#D94378] font-bold mt-0.5">{user?.rollNumber}</p>
            <div className="mt-1.5">
              <StatusBadge status={user?.status || 'active'} />
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
          <div className="p-3.5 rounded-xl bg-[#F7EFE6]">
            <span className="text-[#292039]/60">Student Email</span>
            <p className="font-semibold text-[#292039] mt-0.5">{user?.email}</p>
          </div>
          <div className="p-3.5 rounded-xl bg-[#F7EFE6]">
            <span className="text-[#292039]/60">Registered Mobile (Indian)</span>
            <p className="font-semibold text-[#292039] mt-0.5">{user?.phone}</p>
          </div>
          <div className="p-3.5 rounded-xl bg-[#F7EFE6]">
            <span className="text-[#292039]/60">Allotted Room</span>
            <p className="font-semibold text-[#292039] mt-0.5">
              {user?.room && user?.room !== 'Not Assigned'
                ? `${user.room} (${user.block || 'Hostel'})`
                : 'Not Assigned'}
            </p>
          </div>
          <div className="p-3.5 rounded-xl bg-[#F7EFE6]">
            <span className="text-[#292039]/60">Hostel Admission Date</span>
            <p className="font-semibold text-[#292039] mt-0.5">
              {user?.joinDate || user?.join_date || 'Registered'}
            </p>
          </div>
        </div>

        <div className="p-4 rounded-xl bg-amber-50/70 border border-amber-200 text-xs text-amber-900 leading-relaxed">
          <strong>Notice:</strong> To update your registered mobile number or request a room
          exchange, please submit a written application to the Warden Office before the 5th of each
          calendar month.
        </div>
      </div>
    </div>
  )
}
