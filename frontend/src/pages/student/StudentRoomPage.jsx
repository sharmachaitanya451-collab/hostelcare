import { useApp } from '../../context/AppContext'

export function StudentRoomPage() {
  const { user } = useApp()

  const hasActiveAllocation = Boolean(
    user?.hasActiveRoom &&
    user?.room &&
    user.room !== 'Unassigned' &&
    user.room !== 'Unallocated' &&
    user.room !== 'Not Assigned',
  )

  const roomDisplay = hasActiveAllocation ? user.room : 'Not Assigned'
  const blockDisplay =
    hasActiveAllocation && user?.block && user.block !== 'Not Assigned'
      ? user.block
      : 'Not Assigned'
  const floorDisplay =
    hasActiveAllocation && user?.floor && user.floor !== 'Not Assigned'
      ? user.floor
      : 'Not Assigned'
  const bedDisplay =
    hasActiveAllocation && user?.bed && user.bed !== 'Not Assigned' ? user.bed : 'Not Assigned'
  const tenureStartDisplay = hasActiveAllocation
    ? user?.allocationStartDate || user?.joinDate || 'Not Assigned'
    : 'Not Assigned'

  const rawRoommate = user?.roommate
  const hasAssignedRoommate = Boolean(
    hasActiveAllocation &&
    rawRoommate &&
    rawRoommate !== 'No Roommate Assigned' &&
    rawRoommate !== '(Allotment pending)' &&
    rawRoommate !== 'Assigned Hostel Room',
  )
  const roommateName = hasAssignedRoommate ? rawRoommate : 'No Roommate Assigned'

  return (
    <div className="space-y-6">
      <div className="pb-4 border-b border-[#F0E4D4]">
        <h2 className="font-serif text-2xl font-bold text-[#292039]">My Room &amp; Allotment</h2>
        <p className="text-xs text-[#292039]/70">
          Room details, inventory checklist &amp; co-resident information
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Room Badge Card */}
        <div className="bg-[#FFFCF7] p-6 rounded-3xl border border-[#E8DCCF] space-y-4">
          <span className="text-xs font-bold text-[#368F83] uppercase tracking-wider">
            Allotment Token
          </span>
          <div className="font-serif text-4xl font-bold text-[#292039]">{roomDisplay}</div>
          <div className="space-y-2 text-xs text-[#292039]/80 pt-2 border-t border-[#F0E4D4]">
            <p>
              <strong>Hostel Block:</strong> {blockDisplay}
            </p>
            <p>
              <strong>Floor:</strong> {floorDisplay}
            </p>
            <p>
              <strong>Bed Position:</strong> {bedDisplay}
            </p>
            <p>
              <strong>Tenure Start:</strong> {tenureStartDisplay}
            </p>
          </div>
        </div>

        {/* Roommate details */}
        <div className="bg-[#FFFCF7] p-6 rounded-3xl border border-[#E8DCCF] space-y-4">
          <span className="text-xs font-bold text-[#D94378] uppercase tracking-wider">
            Co-Resident / Roommate
          </span>
          <div className="flex items-center gap-3 pt-1">
            <div className="h-10 w-10 rounded-xl bg-[#368F83] text-white font-bold flex items-center justify-center">
              {hasAssignedRoommate ? roommateName.charAt(0).toUpperCase() : '—'}
            </div>
            <div>
              <h4 className="font-semibold text-sm text-[#292039]">{roommateName}</h4>
              {hasAssignedRoommate && user?.roommateRoll && (
                <p className="text-xs font-mono text-[#292039]/60">{user.roommateRoll}</p>
              )}
            </div>
          </div>
          <div className="space-y-1.5 text-xs text-[#292039]/75 pt-3 border-t border-[#F0E4D4]">
            <p>
              <strong>Bed Position:</strong>{' '}
              {hasAssignedRoommate ? user?.roommateBed || 'Assigned Bed' : 'Not Assigned'}
            </p>
            <p>
              <strong>Contact:</strong>{' '}
              {hasAssignedRoommate ? user?.roommatePhone || 'On file with Warden Office' : 'N/A'}
            </p>
          </div>
        </div>

        {/* Standard Room Inventory Checklist */}
        <div className="bg-[#FFFCF7] p-6 rounded-3xl border border-[#E8DCCF] space-y-4">
          <span className="text-xs font-bold text-[#F4AA35] uppercase tracking-wider">
            Furniture &amp; Fixtures
          </span>
          <ul className="text-xs space-y-2 text-[#292039]/80">
            <li className="flex items-center justify-between">
              <span>Wooden Single Beds</span>
              <span className="font-semibold">02 nos.</span>
            </li>
            <li className="flex items-center justify-between">
              <span>Steel Study Tables &amp; Chairs</span>
              <span className="font-semibold">02 pairs</span>
            </li>
            <li className="flex items-center justify-between">
              <span>Steel Built-in Almirah</span>
              <span className="font-semibold">02 bays</span>
            </li>
            <li className="flex items-center justify-between">
              <span>Ceiling Fan (Orient 1200mm)</span>
              <span className="font-semibold">01 no.</span>
            </li>
            <li className="flex items-center justify-between">
              <span>LED Tube Light Fixtures</span>
              <span className="font-semibold">02 nos.</span>
            </li>
          </ul>
        </div>
      </div>

      <div className="p-5 rounded-2xl bg-[#F7EFE6] border border-[#E5D7C5] text-xs text-[#292039]/80 space-y-2">
        <h4 className="font-semibold text-sm text-[#292039]">
          Room Inspection &amp; Maintenance Policy:
        </h4>
        <p>
          Hostel wardens and authorized maintenance staff conduct scheduled safety checks on
          electrical outlets once each quarter. Heavy appliances such as room immersion heaters,
          induction cooktops, and electric kettles above 1000W are strictly prohibited under college
          hostel rules to prevent electrical overloading.
        </p>
      </div>
    </div>
  )
}
