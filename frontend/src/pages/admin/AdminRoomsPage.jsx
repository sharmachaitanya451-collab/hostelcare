import { useEffect, useMemo, useState } from 'react'
import { useApp } from '../../context/AppContext'
import { StatusBadge } from '../../components/Brand'

export function AdminRoomsPage() {
  const {
    rooms,
    roomsLoading,
    roomsError,
    fetchRooms,
    addRoom,
    updateRoom,
    blocks,
    blocksLoading,
    blocksError,
    fetchBlocks,
    addBlock,
    updateBlock,
    allocations,
    allocationsLoading,
    allocationsError,
    fetchAllocations,
    allocateRoom,
    endAllocation,
    transferAllocation,
    students,
    fetchStudents,
  } = useApp()

  const [activeTab, setActiveTab] = useState('rooms') // 'rooms' | 'blocks' | 'allocations'
  const [notice, setNotice] = useState('')
  const [errorMsg, setErrorMsg] = useState('')

  // Search & Filters
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedBlockFilter, setSelectedBlockFilter] = useState('ALL')
  const [selectedFloorFilter, setSelectedFloorFilter] = useState('ALL')
  const [allocationStatusFilter, setAllocationStatusFilter] = useState('active')

  // Modals state
  const [showAddBlockModal, setShowAddBlockModal] = useState(false)
  const [editingBlock, setEditingBlock] = useState(null)
  const [showAddRoomModal, setShowAddRoomModal] = useState(false)
  const [editingRoom, setEditingRoom] = useState(null)
  const [showAllocateModal, setShowAllocateModal] = useState(false)
  const [prefilledAllocate, setPrefilledAllocate] = useState(null)
  const [transferTarget, setTransferTarget] = useState(null) // allocation object
  const [endTarget, setEndTarget] = useState(null) // allocation object

  // Form states - Block
  const [blockName, setBlockName] = useState('')
  const [blockCode, setBlockCode] = useState('')
  const [blockOrder, setBlockOrder] = useState('1')
  const [blockActive, setBlockActive] = useState(true)
  const [blockFieldErrors, setBlockFieldErrors] = useState({})

  // Form states - Room
  const [roomBlockId, setRoomBlockId] = useState('')
  const [roomNumber, setRoomNumber] = useState('')
  const [roomFloor, setRoomFloor] = useState('1')
  const [roomCapacity, setRoomCapacity] = useState('2')
  const [roomType, setRoomType] = useState('double')

  // Form states - Allocate
  const [allocStudentId, setAllocStudentId] = useState('')
  const [allocRoomId, setAllocRoomId] = useState('')
  const [allocBedNumber, setAllocBedNumber] = useState('1')
  const [allocStartDate, setAllocStartDate] = useState(() => new Date().toISOString().split('T')[0])

  // Form states - Transfer
  const [transferTargetRoomId, setTransferTargetRoomId] = useState('')
  const [transferTargetBed, setTransferTargetBed] = useState('1')
  const [transferDate, setTransferDate] = useState(() => new Date().toISOString().split('T')[0])
  const [transferReason, setTransferReason] = useState('')

  // Form states - End Allocation
  const [endDate, setEndDate] = useState(() => new Date().toISOString().split('T')[0])
  const [endReason, setEndReason] = useState('')

  const [submitting, setSubmitting] = useState(false)

  // Load initial data
  useEffect(() => {
    fetchRooms().catch(() => {})
    fetchBlocks().catch(() => {})
    fetchAllocations().catch(() => {})
    fetchStudents().catch(() => {})
  }, [fetchAllocations, fetchBlocks, fetchRooms, fetchStudents])

  const handleRetry = () => {
    setErrorMsg('')
    fetchRooms().catch(() => {})
    fetchBlocks().catch(() => {})
    fetchAllocations().catch(() => {})
  }

  // Active approved students available for room allocation
  const activeStudents = useMemo(() => {
    return (students || []).filter((s) => s.status === 'active')
  }, [students])

  // Filtered rooms
  const filteredRooms = useMemo(() => {
    return (rooms || []).filter((rm) => {
      const q = searchTerm.toLowerCase().trim()
      const matchesSearch =
        !q ||
        (rm.room_number || rm.roomNumber || '').toLowerCase().includes(q) ||
        (rm.block || '').toLowerCase().includes(q) ||
        (Array.isArray(rm.residents) && rm.residents.some((name) => name.toLowerCase().includes(q)))

      const matchesBlock =
        selectedBlockFilter === 'ALL' ||
        String(rm.block_id || rm.blockId) === String(selectedBlockFilter) ||
        String(rm.block_code || rm.blockCode) === String(selectedBlockFilter)

      const matchesFloor =
        selectedFloorFilter === 'ALL' ||
        String(rm.floor_number ?? rm.floorNumber) === String(selectedFloorFilter)

      return matchesSearch && matchesBlock && matchesFloor
    })
  }, [rooms, searchTerm, selectedBlockFilter, selectedFloorFilter])

  // Filtered allocations
  const filteredAllocations = useMemo(() => {
    return (allocations || []).filter((alloc) => {
      const q = searchTerm.toLowerCase().trim()
      const stuName = alloc.student?.fullName || alloc.student?.full_name || ''
      const stuRoll = alloc.student?.rollNumber || alloc.student?.roll_number || ''
      const rmNo = alloc.room_number || alloc.roomNumber || ''

      const matchesSearch =
        !q ||
        stuName.toLowerCase().includes(q) ||
        stuRoll.toLowerCase().includes(q) ||
        rmNo.toLowerCase().includes(q)

      const matchesStatus =
        allocationStatusFilter === 'all' ||
        (allocationStatusFilter === 'active' && alloc.status === 'active') ||
        (allocationStatusFilter === 'ended' && alloc.status === 'ended')

      return matchesSearch && matchesStatus
    })
  }, [allocations, searchTerm, allocationStatusFilter])

  // Vacant beds in selected room for allocation modal
  const targetRoomForAlloc = useMemo(() => {
    if (!allocRoomId) return null
    return (rooms || []).find(
      (r) => String(r.id) === String(allocRoomId) || String(r.room_number) === String(allocRoomId),
    )
  }, [rooms, allocRoomId])

  const vacantBedsForAlloc = useMemo(() => {
    if (!targetRoomForAlloc) return []
    const capacity = Number(targetRoomForAlloc.capacity || 0)
    const occupiedBeds = new Set(
      (targetRoomForAlloc.beds || []).filter((b) => b.occupied).map((b) => Number(b.bed_number)),
    )
    const vacant = []
    for (let i = 1; i <= capacity; i++) {
      if (!occupiedBeds.has(i)) vacant.push(i)
    }
    return vacant
  }, [targetRoomForAlloc])

  // Vacant beds in target room for transfer modal
  const targetRoomForTransfer = useMemo(() => {
    if (!transferTargetRoomId) return null
    return (rooms || []).find(
      (r) =>
        String(r.id) === String(transferTargetRoomId) ||
        String(r.room_number) === String(transferTargetRoomId),
    )
  }, [rooms, transferTargetRoomId])

  const vacantBedsForTransfer = useMemo(() => {
    if (!targetRoomForTransfer) return []
    const capacity = Number(targetRoomForTransfer.capacity || 0)
    const occupiedBeds = new Set(
      (targetRoomForTransfer.beds || []).filter((b) => b.occupied).map((b) => Number(b.bed_number)),
    )
    const vacant = []
    for (let i = 1; i <= capacity; i++) {
      if (!occupiedBeds.has(i)) vacant.push(i)
    }
    return vacant
  }, [targetRoomForTransfer])

  // ---------------------------------------------------------------------------
  // Action Handlers
  // ---------------------------------------------------------------------------

  const handleCreateBlock = async (e) => {
    e.preventDefault()
    if (submitting) return

    setBlockFieldErrors({})
    setErrorMsg('')
    setNotice('')

    const trimmedName = blockName.trim()
    const trimmedCode = blockCode.trim().toUpperCase()
    const parsedOrder = parseInt(blockOrder, 10)

    const clientErrors = {}
    if (!trimmedName) {
      clientErrors.name = 'Block name is required.'
    } else if (trimmedName.length > 80) {
      clientErrors.name = 'Block name must not exceed 80 characters.'
    }

    if (trimmedCode && !/^[A-Z0-9]{1,10}$/.test(trimmedCode)) {
      clientErrors.code =
        'Block code must be 1 to 10 alphanumeric uppercase characters (e.g. "BLKA", "NORTH").'
    }

    if (blockOrder !== '' && (isNaN(parsedOrder) || parsedOrder < 0)) {
      clientErrors.display_order = 'Display order must be a non-negative number.'
    }

    if (Object.keys(clientErrors).length > 0) {
      setBlockFieldErrors(clientErrors)
      return
    }

    setSubmitting(true)
    try {
      const created = await addBlock({
        name: trimmedName,
        code: trimmedCode || undefined,
        display_order: isNaN(parsedOrder) ? 0 : parsedOrder,
      })
      await Promise.allSettled([fetchBlocks(), fetchRooms()])
      setNotice(`Successfully created block "${created.name}" (${created.code}).`)
      setShowAddBlockModal(false)
      setBlockName('')
      setBlockCode('')
      setBlockOrder('1')
      setBlockFieldErrors({})
    } catch (err) {
      const msg = err?.message || 'Unable to create block.'
      const lower = msg.toLowerCase()
      const serverErrors = {}
      if (lower.includes('name')) {
        serverErrors.name = msg
      } else if (lower.includes('code')) {
        serverErrors.code = msg
      } else if (lower.includes('order')) {
        serverErrors.display_order = msg
      } else {
        serverErrors.general = msg
      }
      setBlockFieldErrors(serverErrors)
    } finally {
      setSubmitting(false)
    }
  }

  const handleUpdateBlock = async (e) => {
    e.preventDefault()
    if (!editingBlock) return
    setErrorMsg('')
    setNotice('')
    setSubmitting(true)
    try {
      const updated = await updateBlock(editingBlock.id, {
        name: blockName.trim(),
        code: blockCode.trim().toUpperCase(),
        display_order: parseInt(blockOrder, 10) || 0,
        is_active: blockActive,
      })
      setNotice(`Updated block "${updated.name}".`)
      setEditingBlock(null)
    } catch (err) {
      setErrorMsg(err?.message || 'Unable to update block.')
    } finally {
      setSubmitting(false)
    }
  }

  const handleCreateRoom = async (e) => {
    e.preventDefault()
    setErrorMsg('')
    setNotice('')
    setSubmitting(true)
    try {
      const created = await addRoom({
        block_id: parseInt(roomBlockId, 10),
        room_number: roomNumber.trim().toUpperCase(),
        floor: parseInt(roomFloor, 10) || 0,
        capacity: parseInt(roomCapacity, 10) || 2,
        room_type: roomType,
      })
      setNotice(`Room ${created.room_number} created in ${created.block}.`)
      setShowAddRoomModal(false)
      setRoomNumber('')
      setRoomCapacity('2')
    } catch (err) {
      setErrorMsg(err?.message || 'Unable to create room.')
    } finally {
      setSubmitting(false)
    }
  }

  const handleUpdateRoom = async (e) => {
    e.preventDefault()
    if (!editingRoom) return
    setErrorMsg('')
    setNotice('')
    setSubmitting(true)
    try {
      const updated = await updateRoom(editingRoom.id, {
        capacity: parseInt(roomCapacity, 10),
        room_type: roomType,
        is_active: editingRoom.is_active,
      })
      setNotice(`Room ${updated.room_number} capacity updated to ${updated.capacity}.`)
      setEditingRoom(null)
    } catch (err) {
      setErrorMsg(err?.message || 'Unable to update room.')
    } finally {
      setSubmitting(false)
    }
  }

  const handleAllocateStudent = async (e) => {
    e.preventDefault()
    setErrorMsg('')
    setNotice('')
    if (!allocStudentId || !allocRoomId || !allocBedNumber) {
      setErrorMsg('Please select a student, room, and available bed number.')
      return
    }
    setSubmitting(true)
    try {
      const alloc = await allocateRoom({
        student_id: allocStudentId,
        room_id: parseInt(allocRoomId, 10) || allocRoomId,
        bed_number: parseInt(allocBedNumber, 10),
        start_date: allocStartDate,
      })
      setNotice(
        `Allocated ${alloc.student?.fullName || 'student'} to Room ${alloc.room_number} (Bed ${alloc.bed_number}).`,
      )
      setShowAllocateModal(false)
      setAllocStudentId('')
      setAllocRoomId('')
      setPrefilledAllocate(null)
    } catch (err) {
      setErrorMsg(err?.message || 'Unable to allocate room.')
    } finally {
      setSubmitting(false)
    }
  }

  const handleTransferStudent = async (e) => {
    e.preventDefault()
    if (!transferTarget) return
    setErrorMsg('')
    setNotice('')
    if (!transferTargetRoomId || !transferTargetBed || !transferReason.trim()) {
      setErrorMsg('Target room, target bed, and a mandatory reason are required for transfer.')
      return
    }
    setSubmitting(true)
    try {
      const res = await transferAllocation(transferTarget.id, {
        target_room_id: parseInt(transferTargetRoomId, 10) || transferTargetRoomId,
        target_bed_number: parseInt(transferTargetBed, 10),
        effective_date: transferDate,
        reason: transferReason.trim(),
      })
      const newAlloc = res.allocation
      setNotice(
        `Transferred ${newAlloc.student?.fullName || 'student'} from Room ${transferTarget.room_number} to Room ${newAlloc.room_number} Bed ${newAlloc.bed_number}.`,
      )
      setTransferTarget(null)
      setTransferReason('')
    } catch (err) {
      setErrorMsg(err?.message || 'Unable to transfer student.')
    } finally {
      setSubmitting(false)
    }
  }

  const handleEndAllocation = async (e) => {
    e.preventDefault()
    if (!endTarget) return
    setErrorMsg('')
    setNotice('')
    if (!endReason.trim() || endReason.trim().length < 3) {
      setErrorMsg('A mandatory checkout explanation (at least 3 characters) is required.')
      return
    }
    setSubmitting(true)
    try {
      const ended = await endAllocation(endTarget.id, {
        end_date: endDate,
        reason: endReason.trim(),
      })
      setNotice(
        `Ended room allocation for ${ended.student?.fullName || 'student'} in Room ${ended.room_number}.`,
      )
      setEndTarget(null)
      setEndReason('')
    } catch (err) {
      setErrorMsg(err?.message || 'Unable to end room allocation.')
    } finally {
      setSubmitting(false)
    }
  }

  const openAllocateForRoomBed = (room, bedNo) => {
    setAllocRoomId(String(room.id || room.room_number))
    setAllocBedNumber(String(bedNo))
    setPrefilledAllocate({ room, bedNo })
    setShowAllocateModal(true)
  }

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-[#F0E4D4]">
        <div>
          <span className="text-[11px] font-bold text-[#D94378] uppercase tracking-wider">
            Hostel Operations &amp; Residential Allocation
          </span>
          <h2 className="font-serif text-2xl sm:text-3xl font-bold text-[#292039]">
            Room &amp; Occupancy Management
          </h2>
          <p className="text-xs text-[#292039]/70 mt-1">
            Real-time block capacities, live bed assignments, and resident transfer workflows
          </p>
        </div>

        {/* Global Action Buttons */}
        <div className="flex flex-wrap items-center gap-2.5">
          <button
            type="button"
            onClick={() => {
              setBlockName('')
              setBlockCode('')
              setBlockOrder(String(blocks.length + 1))
              setBlockFieldErrors({})
              setShowAddBlockModal(true)
            }}
            className="px-3.5 py-2 rounded-xl border border-[#D8CEBE] bg-[#FFFCF7] text-xs font-semibold text-[#292039] hover:bg-[#F7EFE6] transition-colors cursor-pointer"
          >
            + Add Block
          </button>
          <button
            type="button"
            onClick={() => {
              if (blocks.length > 0 && !roomBlockId) {
                setRoomBlockId(String(blocks[0].id))
              }
              setShowAddRoomModal(true)
            }}
            className="px-3.5 py-2 rounded-xl border border-[#D8CEBE] bg-[#FFFCF7] text-xs font-semibold text-[#292039] hover:bg-[#F7EFE6] transition-colors cursor-pointer"
          >
            + Add Room
          </button>
          <button
            type="button"
            onClick={() => {
              setPrefilledAllocate(null)
              setShowAllocateModal(true)
            }}
            className="px-4 py-2 rounded-xl bg-[#292039] text-[#FFFDF9] text-xs font-semibold hover:bg-[#3D3052] transition-colors cursor-pointer"
          >
            + Allocate Student
          </button>
        </div>
      </div>

      {/* Notices & Errors */}
      {notice && (
        <div className="p-3.5 rounded-2xl bg-emerald-50 border border-emerald-300 text-emerald-900 text-xs flex items-center justify-between gap-3">
          <span>{notice}</span>
          <button
            type="button"
            onClick={() => setNotice('')}
            className="text-emerald-700 hover:text-emerald-900 font-bold"
          >
            ✕
          </button>
        </div>
      )}

      {(errorMsg || roomsError || blocksError || allocationsError) && (
        <div
          role="alert"
          className="p-3.5 rounded-2xl bg-rose-50 border border-rose-300 text-rose-900 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3"
        >
          <span>{errorMsg || roomsError || blocksError || allocationsError}</span>
          <button
            type="button"
            onClick={handleRetry}
            className="px-3 py-1.5 rounded-xl bg-rose-700 text-white font-semibold text-xs hover:bg-rose-800 transition-colors cursor-pointer shrink-0"
          >
            Retry
          </button>
        </div>
      )}

      {/* Navigation Tabs */}
      <div className="flex border-b border-[#E8DCCF] gap-2">
        <button
          type="button"
          onClick={() => setActiveTab('rooms')}
          className={`px-4 py-2 text-xs font-bold transition-all border-b-2 cursor-pointer ${
            activeTab === 'rooms'
              ? 'border-[#D94378] text-[#D94378]'
              : 'border-transparent text-[#292039]/65 hover:text-[#292039]'
          }`}
        >
          Rooms &amp; Occupancy Map ({rooms.length})
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('blocks')}
          className={`px-4 py-2 text-xs font-bold transition-all border-b-2 cursor-pointer ${
            activeTab === 'blocks'
              ? 'border-[#D94378] text-[#D94378]'
              : 'border-transparent text-[#292039]/65 hover:text-[#292039]'
          }`}
        >
          Hostel Blocks ({blocks.length})
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('allocations')}
          className={`px-4 py-2 text-xs font-bold transition-all border-b-2 cursor-pointer ${
            activeTab === 'allocations'
              ? 'border-[#D94378] text-[#D94378]'
              : 'border-transparent text-[#292039]/65 hover:text-[#292039]'
          }`}
        >
          Resident Allocations ({allocations.length})
        </button>
      </div>

      {/* Filters Bar */}
      <div className="bg-[#FFFCF7] p-4 rounded-2xl border border-[#E8DCCF] flex flex-wrap items-center justify-between gap-4">
        <div className="flex-1 min-w-[220px]">
          <input
            type="text"
            placeholder={
              activeTab === 'blocks'
                ? 'Search blocks by name or code...'
                : activeTab === 'allocations'
                  ? 'Search by student, roll number, or room...'
                  : 'Search rooms by number, block, or resident...'
            }
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full px-3.5 py-2 rounded-xl border border-[#D8CEBE] text-xs bg-[#FFFDF9] text-[#292039] placeholder:text-[#292039]/40 focus:outline-none focus:border-[#D94378]"
          />
        </div>

        {activeTab === 'rooms' && (
          <div className="flex flex-wrap items-center gap-3">
            <select
              value={selectedBlockFilter}
              onChange={(e) => setSelectedBlockFilter(e.target.value)}
              className="px-3 py-2 rounded-xl border border-[#D8CEBE] text-xs bg-[#FFFDF9] text-[#292039]"
            >
              <option value="ALL">All Blocks</option>
              {blocks.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name} ({b.code})
                </option>
              ))}
            </select>

            <select
              value={selectedFloorFilter}
              onChange={(e) => setSelectedFloorFilter(e.target.value)}
              className="px-3 py-2 rounded-xl border border-[#D8CEBE] text-xs bg-[#FFFDF9] text-[#292039]"
            >
              <option value="ALL">All Floors</option>
              <option value="0">Ground Floor</option>
              <option value="1">1st Floor</option>
              <option value="2">2nd Floor</option>
              <option value="3">3rd Floor</option>
              <option value="4">4th Floor</option>
            </select>
          </div>
        )}

        {activeTab === 'allocations' && (
          <div className="flex items-center gap-3">
            <select
              value={allocationStatusFilter}
              onChange={(e) => setAllocationStatusFilter(e.target.value)}
              className="px-3 py-2 rounded-xl border border-[#D8CEBE] text-xs bg-[#FFFDF9] text-[#292039]"
            >
              <option value="active">Active Allocations Only</option>
              <option value="ended">Past / Ended Allocations</option>
              <option value="all">All Allocations</option>
            </select>
          </div>
        )}
      </div>

      {/* ------------------------------------------------------------------- */}
      {/* TAB 1: Rooms & Occupancy Grid */}
      {/* ------------------------------------------------------------------- */}
      {activeTab === 'rooms' && (
        <div>
          {roomsLoading && rooms.length === 0 ? (
            <div className="p-8 rounded-3xl bg-[#FFFCF7] border border-[#E8DCCF] text-center text-xs font-semibold text-[#292039]/70">
              Loading hostel room occupancy...
            </div>
          ) : !roomsLoading && filteredRooms.length === 0 ? (
            <div className="p-8 rounded-3xl bg-[#FFFCF7] border border-[#E8DCCF] text-center space-y-2">
              <p className="font-serif text-base font-bold text-[#292039]">
                {rooms.length === 0 ? 'No Hostel Rooms Configured' : 'No Rooms Match Filters'}
              </p>
              <p className="text-xs text-[#292039]/65">
                {rooms.length === 0
                  ? 'No hostel rooms exist in the database. Use "+ Add Block" and "+ Add Room" to configure hostel wings.'
                  : 'Try clearing your block or floor filter criteria.'}
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {filteredRooms.map((rm) => {
                const roomNumber = rm.room_number || rm.roomNumber || rm.id
                const capacity = Number(rm.capacity || 0)
                const occupied = Number(rm.occupied ?? rm.occupied_beds ?? 0)
                const isFull = occupied >= capacity && capacity > 0

                return (
                  <div
                    key={roomNumber}
                    className="p-5 rounded-2xl bg-[#FFFCF7] border border-[#E8DCCF] space-y-3 shadow-xs hover:border-[#D8CEBE] transition-all flex flex-col justify-between"
                  >
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="font-serif text-xl font-bold text-[#292039]">
                          {roomNumber}
                        </span>
                        <div className="flex items-center gap-1.5">
                          <span
                            className={`text-[11px] font-bold px-2 py-0.5 rounded-md ${
                              isFull
                                ? 'bg-rose-100 text-rose-800'
                                : occupied === 0
                                  ? 'bg-slate-100 text-slate-700'
                                  : 'bg-emerald-100 text-emerald-800'
                            }`}
                          >
                            {occupied}/{capacity} Beds
                          </span>
                          <button
                            type="button"
                            onClick={() => {
                              setEditingRoom(rm)
                              setRoomCapacity(String(rm.capacity))
                              setRoomType(rm.room_type || 'standard')
                            }}
                            className="text-[11px] text-[#292039]/60 hover:text-[#292039] px-1"
                            title="Edit Room Capacity"
                          >
                            ✎
                          </button>
                        </div>
                      </div>

                      <div className="text-[11px] text-[#292039]/65">
                        {rm.block} • {rm.floor}
                      </div>

                      {/* Bed Slots Listing */}
                      <div className="pt-2 border-t border-[#F0E4D4] text-[11px] space-y-2">
                        <span className="font-bold text-[#292039]/60 uppercase tracking-wider text-[10px]">
                          Bed Allocation Slots:
                        </span>

                        {(Array.isArray(rm.beds) && rm.beds.length > 0
                          ? rm.beds
                          : Array.isArray(rm.students) && rm.students.length > 0
                            ? rm.students.map((name, idx) => ({
                                bed_number: idx + 1,
                                occupied: name !== '(Vacant Bed)' && name !== 'Vacant',
                                student_name:
                                  name !== '(Vacant Bed)' && name !== 'Vacant' ? name : null,
                              }))
                            : Array.from({ length: capacity }, (_, idx) => {
                                const resName = Array.isArray(rm.residents)
                                  ? rm.residents[idx]
                                  : null
                                return {
                                  bed_number: idx + 1,
                                  occupied: Boolean(resName),
                                  student_name: resName,
                                }
                              })
                        ).map((bed) => {
                          const resident = (rm.resident_details || rm.residentDetails || []).find(
                            (r) => Number(r.bed_number || r.bedNumber) === bed.bed_number,
                          )

                          return (
                            <div
                              key={bed.bed_number}
                              className={`p-2 rounded-xl border flex items-center justify-between gap-2 ${
                                bed.occupied
                                  ? 'bg-[#FFFDF9] border-[#E8DCCF]'
                                  : 'bg-emerald-50/40 border-dashed border-emerald-300'
                              }`}
                            >
                              <div className="truncate flex-1">
                                <span className="font-mono font-bold text-[#292039] mr-1.5">
                                  Bed {bed.bed_number}:
                                </span>
                                {bed.occupied ? (
                                  <span className="font-semibold text-[#292039]">
                                    • {bed.student_name}
                                    {bed.roll_number && (
                                      <span className="text-[10px] text-[#292039]/60 ml-1 font-mono">
                                        ({bed.roll_number})
                                      </span>
                                    )}
                                  </span>
                                ) : (
                                  <span className="text-emerald-700 italic">• (Vacant Bed)</span>
                                )}
                              </div>

                              <div>
                                {bed.occupied && resident ? (
                                  <div className="flex items-center gap-1">
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setTransferTarget({
                                          id: resident.allocation_id,
                                          room_number: roomNumber,
                                          bed_number: bed.bed_number,
                                          student: { fullName: resident.full_name },
                                        })
                                        setTransferTargetRoomId('')
                                      }}
                                      className="px-1.5 py-0.5 rounded bg-[#F7EFE6] hover:bg-[#E8DCCF] text-[10px] font-semibold text-[#292039] cursor-pointer"
                                      title="Transfer Resident"
                                    >
                                      Transfer
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setEndTarget({
                                          id: resident.allocation_id,
                                          room_number: roomNumber,
                                          bed_number: bed.bed_number,
                                          student: { fullName: resident.full_name },
                                        })
                                      }}
                                      className="px-1.5 py-0.5 rounded bg-rose-50 hover:bg-rose-100 text-[10px] font-semibold text-rose-700 cursor-pointer"
                                      title="Checkout / Vacate"
                                    >
                                      Checkout
                                    </button>
                                  </div>
                                ) : !bed.occupied ? (
                                  <button
                                    type="button"
                                    onClick={() => openAllocateForRoomBed(rm, bed.bed_number)}
                                    className="px-2 py-0.5 rounded bg-emerald-600 hover:bg-emerald-700 text-white text-[10px] font-bold cursor-pointer"
                                  >
                                    Allocate
                                  </button>
                                ) : null}
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* ------------------------------------------------------------------- */}
      {/* TAB 2: Blocks Management View */}
      {/* ------------------------------------------------------------------- */}
      {activeTab === 'blocks' && (
        <div className="bg-[#FFFCF7] rounded-3xl border border-[#E8DCCF] shadow-xs overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#F7EFE6] text-[#292039]/80 font-semibold border-b border-[#E8DCCF]">
                <tr>
                  <th className="py-3 px-4">Code</th>
                  <th className="py-3 px-4">Block Name</th>
                  <th className="py-3 px-4">Rooms</th>
                  <th className="py-3 px-4">Total Capacity</th>
                  <th className="py-3 px-4">Occupied Beds</th>
                  <th className="py-3 px-4">Vacant Beds</th>
                  <th className="py-3 px-4">Display Order</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E8DCCF]/60">
                {blocksLoading && blocks.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="py-12 text-center text-[#292039]/60">
                      Loading hostel blocks...
                    </td>
                  </tr>
                ) : blocks.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="py-12 text-center text-[#292039]/60">
                      No blocks found. Click &quot;+ Add Block&quot; to configure your first hostel
                      wing.
                    </td>
                  </tr>
                ) : (
                  blocks.map((b) => (
                    <tr key={b.id} className="hover:bg-[#FFFDF9] transition-colors">
                      <td className="py-3.5 px-4 font-mono font-bold text-[#292039]">{b.code}</td>
                      <td className="py-3.5 px-4 font-semibold text-[#292039]">{b.name}</td>
                      <td className="py-3.5 px-4 font-mono">
                        {b.totalRooms ?? b.rooms_count ?? 0}
                      </td>
                      <td className="py-3.5 px-4 font-mono">
                        {b.totalCapacity ?? b.total_capacity ?? 0}
                      </td>
                      <td className="py-3.5 px-4 font-mono font-semibold text-[#D94378]">
                        {b.occupiedBeds ?? b.occupied_beds ?? 0}
                      </td>
                      <td className="py-3.5 px-4 font-mono font-semibold text-emerald-700">
                        {b.vacantBeds ?? b.vacant_beds ?? 0}
                      </td>
                      <td className="py-3.5 px-4 font-mono">{b.display_order}</td>
                      <td className="py-3.5 px-4">
                        <StatusBadge status={b.is_active ? 'active' : 'inactive'} />
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <button
                          type="button"
                          onClick={() => {
                            setEditingBlock(b)
                            setBlockName(b.name)
                            setBlockCode(b.code)
                            setBlockOrder(String(b.display_order))
                            setBlockActive(b.is_active)
                          }}
                          className="px-2.5 py-1 rounded-lg border border-[#D8CEBE] font-semibold text-[#292039] hover:bg-[#F7EFE6] transition-colors cursor-pointer"
                        >
                          Edit Block
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------- */}
      {/* TAB 3: Allocations Directory View */}
      {/* ------------------------------------------------------------------- */}
      {activeTab === 'allocations' && (
        <div className="bg-[#FFFCF7] rounded-3xl border border-[#E8DCCF] shadow-xs overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#F7EFE6] text-[#292039]/80 font-semibold border-b border-[#E8DCCF]">
                <tr>
                  <th className="py-3 px-4">Student</th>
                  <th className="py-3 px-4">Roll Number</th>
                  <th className="py-3 px-4">Room &amp; Bed</th>
                  <th className="py-3 px-4">Block</th>
                  <th className="py-3 px-4">Start Date</th>
                  <th className="py-3 px-4">End Date</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E8DCCF]/60">
                {allocationsLoading && allocations.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="py-12 text-center text-[#292039]/60">
                      Loading room allocations...
                    </td>
                  </tr>
                ) : filteredAllocations.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="py-12 text-center text-[#292039]/60">
                      No room allocations match your search criteria.
                    </td>
                  </tr>
                ) : (
                  filteredAllocations.map((alloc) => (
                    <tr key={alloc.id} className="hover:bg-[#FFFDF9] transition-colors">
                      <td className="py-3.5 px-4 font-semibold text-[#292039]">
                        {alloc.student?.fullName || alloc.student?.full_name || 'Resident Student'}
                      </td>
                      <td className="py-3.5 px-4 font-mono font-bold text-[#292039]">
                        {alloc.student?.rollNumber || alloc.student?.roll_number || 'N/A'}
                      </td>
                      <td className="py-3.5 px-4 font-semibold text-[#D94378]">
                        Room {alloc.room_number || alloc.roomNumber} (Bed{' '}
                        {alloc.bed_number || alloc.bedNumber})
                      </td>
                      <td className="py-3.5 px-4 text-[#292039]/80">
                        {alloc.block_name || alloc.blockName}
                      </td>
                      <td className="py-3.5 px-4 text-[#292039]/80">
                        {alloc.startDate || alloc.start_date}
                      </td>
                      <td className="py-3.5 px-4 text-[#292039]/70">
                        {alloc.endDate || alloc.end_date || 'Current Active'}
                      </td>
                      <td className="py-3.5 px-4">
                        <StatusBadge status={alloc.status === 'active' ? 'active' : 'inactive'} />
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        {alloc.status === 'active' ? (
                          <div className="flex items-center justify-end gap-1.5">
                            <button
                              type="button"
                              onClick={() => {
                                setTransferTarget(alloc)
                                setTransferTargetRoomId('')
                              }}
                              className="px-2.5 py-1 rounded-lg border border-[#D8CEBE] font-semibold text-[#292039] hover:bg-[#F7EFE6] transition-colors cursor-pointer"
                            >
                              Transfer
                            </button>
                            <button
                              type="button"
                              onClick={() => setEndTarget(alloc)}
                              className="px-2.5 py-1 rounded-lg border border-rose-200 text-rose-700 bg-rose-50 hover:bg-rose-100 font-semibold transition-colors cursor-pointer"
                            >
                              Checkout
                            </button>
                          </div>
                        ) : (
                          <span
                            className="text-[11px] text-[#292039]/50 truncate max-w-[120px] inline-block"
                            title={alloc.end_reason || 'Checkout completed'}
                          >
                            {alloc.end_reason || 'Vacated'}
                          </span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------- */}
      {/* MODAL: Add Block */}
      {/* ------------------------------------------------------------------- */}
      {showAddBlockModal && (
        <div className="fixed inset-0 bg-[#292039]/40 z-50 flex items-center justify-center p-4 backdrop-blur-xs">
          <div className="bg-[#FFFCF7] border border-[#E8DCCF] rounded-3xl p-6 sm:p-8 max-w-md w-full space-y-5 shadow-2xl">
            <div className="flex justify-between items-center pb-3 border-b border-[#F0E4D4]">
              <h3 className="font-serif text-lg font-bold text-[#292039]">Add New Hostel Block</h3>
              <button
                type="button"
                onClick={() => setShowAddBlockModal(false)}
                className="text-[#292039]/60 hover:text-[#292039] font-bold"
              >
                ✕
              </button>
            </div>

            {blockFieldErrors.general && (
              <div
                role="alert"
                className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 text-xs"
              >
                {blockFieldErrors.general}
              </div>
            )}

            <form onSubmit={handleCreateBlock} className="space-y-4 text-xs" noValidate>
              <div>
                <label htmlFor="add-block-name" className="font-semibold text-[#292039] block mb-1">
                  Block Name <span className="text-[#D94378]">*</span>
                </label>
                <input
                  id="add-block-name"
                  type="text"
                  placeholder="e.g. Block D (Aryabhata Wing)"
                  value={blockName}
                  onChange={(e) => {
                    setBlockName(e.target.value)
                    if (blockFieldErrors.name) {
                      setBlockFieldErrors((prev) => ({ ...prev, name: undefined }))
                    }
                  }}
                  className={`w-full px-3.5 py-2 rounded-xl border ${
                    blockFieldErrors.name
                      ? 'border-rose-400 bg-rose-50/20'
                      : 'border-[#D8CEBE] bg-[#FFFDF9]'
                  } text-[#292039] focus:outline-none focus:border-[#D94378]`}
                />
                {blockFieldErrors.name && (
                  <p className="text-[11px] text-rose-600 font-medium mt-1">
                    {blockFieldErrors.name}
                  </p>
                )}
              </div>

              <div>
                <label htmlFor="add-block-code" className="font-semibold text-[#292039] block mb-1">
                  Block Code (1-10 uppercase alphanumeric)
                </label>
                <input
                  id="add-block-code"
                  type="text"
                  placeholder="e.g. BLKD"
                  value={blockCode}
                  onChange={(e) => {
                    setBlockCode(e.target.value.toUpperCase())
                    if (blockFieldErrors.code) {
                      setBlockFieldErrors((prev) => ({ ...prev, code: undefined }))
                    }
                  }}
                  className={`w-full px-3.5 py-2 rounded-xl border ${
                    blockFieldErrors.code
                      ? 'border-rose-400 bg-rose-50/20'
                      : 'border-[#D8CEBE] bg-[#FFFDF9]'
                  } font-mono text-[#292039] focus:outline-none focus:border-[#D94378]`}
                />
                {blockFieldErrors.code && (
                  <p className="text-[11px] text-rose-600 font-medium mt-1">
                    {blockFieldErrors.code}
                  </p>
                )}
              </div>

              <div>
                <label
                  htmlFor="add-block-order"
                  className="font-semibold text-[#292039] block mb-1"
                >
                  Display Order
                </label>
                <input
                  id="add-block-order"
                  type="number"
                  min="0"
                  value={blockOrder}
                  onChange={(e) => {
                    setBlockOrder(e.target.value)
                    if (blockFieldErrors.display_order) {
                      setBlockFieldErrors((prev) => ({ ...prev, display_order: undefined }))
                    }
                  }}
                  className={`w-full px-3.5 py-2 rounded-xl border ${
                    blockFieldErrors.display_order
                      ? 'border-rose-400 bg-rose-50/20'
                      : 'border-[#D8CEBE] bg-[#FFFDF9]'
                  } text-[#292039] focus:outline-none focus:border-[#D94378]`}
                />
                {blockFieldErrors.display_order && (
                  <p className="text-[11px] text-rose-600 font-medium mt-1">
                    {blockFieldErrors.display_order}
                  </p>
                )}
              </div>

              <div className="flex justify-end gap-3 pt-3">
                <button
                  type="button"
                  onClick={() => setShowAddBlockModal(false)}
                  className="px-4 py-2 rounded-xl border border-[#D8CEBE] text-[#292039] font-semibold hover:bg-[#F7EFE6] cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-5 py-2 rounded-xl bg-[#292039] text-white font-semibold hover:bg-[#3D3052] disabled:opacity-50 cursor-pointer"
                >
                  {submitting ? 'Creating...' : 'Create Block'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------- */}
      {/* MODAL: Edit Block */}
      {/* ------------------------------------------------------------------- */}
      {editingBlock && (
        <div className="fixed inset-0 bg-[#292039]/40 z-50 flex items-center justify-center p-4 backdrop-blur-xs">
          <div className="bg-[#FFFCF7] border border-[#E8DCCF] rounded-3xl p-6 sm:p-8 max-w-md w-full space-y-5 shadow-2xl">
            <div className="flex justify-between items-center pb-3 border-b border-[#F0E4D4]">
              <h3 className="font-serif text-lg font-bold text-[#292039]">
                Edit Block: {editingBlock.code}
              </h3>
              <button
                type="button"
                onClick={() => setEditingBlock(null)}
                className="text-[#292039]/60 hover:text-[#292039] font-bold"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleUpdateBlock} className="space-y-4 text-xs">
              <div>
                <label className="font-semibold text-[#292039] block mb-1">Block Name</label>
                <input
                  type="text"
                  required
                  value={blockName}
                  onChange={(e) => setBlockName(e.target.value)}
                  className="w-full px-3.5 py-2 rounded-xl border border-[#D8CEBE] bg-[#FFFDF9] text-[#292039] focus:outline-none focus:border-[#D94378]"
                />
              </div>

              <div>
                <label className="font-semibold text-[#292039] block mb-1">Block Code</label>
                <input
                  type="text"
                  required
                  value={blockCode}
                  onChange={(e) => setBlockCode(e.target.value.toUpperCase())}
                  className="w-full px-3.5 py-2 rounded-xl border border-[#D8CEBE] bg-[#FFFDF9] font-mono text-[#292039] focus:outline-none focus:border-[#D94378]"
                />
              </div>

              <div>
                <label className="font-semibold text-[#292039] block mb-1">Display Order</label>
                <input
                  type="number"
                  min="0"
                  value={blockOrder}
                  onChange={(e) => setBlockOrder(e.target.value)}
                  className="w-full px-3.5 py-2 rounded-xl border border-[#D8CEBE] bg-[#FFFDF9] text-[#292039] focus:outline-none focus:border-[#D94378]"
                />
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="blockActiveCheck"
                  checked={blockActive}
                  onChange={(e) => setBlockActive(e.target.checked)}
                  className="rounded text-[#D94378] focus:ring-0"
                />
                <label htmlFor="blockActiveCheck" className="font-semibold text-[#292039]">
                  Active Block (Deactivation blocked if active resident allocations exist)
                </label>
              </div>

              <div className="flex justify-end gap-3 pt-3">
                <button
                  type="button"
                  onClick={() => setEditingBlock(null)}
                  className="px-4 py-2 rounded-xl border border-[#D8CEBE] text-[#292039] font-semibold hover:bg-[#F7EFE6] cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-5 py-2 rounded-xl bg-[#292039] text-white font-semibold hover:bg-[#3D3052] disabled:opacity-50 cursor-pointer"
                >
                  {submitting ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------- */}
      {/* MODAL: Add Room */}
      {/* ------------------------------------------------------------------- */}
      {showAddRoomModal && (
        <div className="fixed inset-0 bg-[#292039]/40 z-50 flex items-center justify-center p-4 backdrop-blur-xs">
          <div className="bg-[#FFFCF7] border border-[#E8DCCF] rounded-3xl p-6 sm:p-8 max-w-md w-full space-y-5 shadow-2xl">
            <div className="flex justify-between items-center pb-3 border-b border-[#F0E4D4]">
              <h3 className="font-serif text-lg font-bold text-[#292039]">Add Hostel Room</h3>
              <button
                type="button"
                onClick={() => setShowAddRoomModal(false)}
                className="text-[#292039]/60 hover:text-[#292039] font-bold"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateRoom} className="space-y-4 text-xs">
              <div>
                <label className="font-semibold text-[#292039] block mb-1">Hostel Block</label>
                <select
                  required
                  value={roomBlockId}
                  onChange={(e) => setRoomBlockId(e.target.value)}
                  className="w-full px-3.5 py-2 rounded-xl border border-[#D8CEBE] bg-[#FFFDF9] text-[#292039]"
                >
                  <option value="">Select a block</option>
                  {blocks.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name} ({b.code})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="font-semibold text-[#292039] block mb-1">
                  Room Number (e.g. A-101, B-204)
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. A-101"
                  value={roomNumber}
                  onChange={(e) => setRoomNumber(e.target.value.toUpperCase())}
                  className="w-full px-3.5 py-2 rounded-xl border border-[#D8CEBE] bg-[#FFFDF9] font-mono text-[#292039] focus:outline-none focus:border-[#D94378]"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold text-[#292039] block mb-1">Floor (0-50)</label>
                  <input
                    type="number"
                    min="0"
                    max="50"
                    required
                    value={roomFloor}
                    onChange={(e) => setRoomFloor(e.target.value)}
                    className="w-full px-3.5 py-2 rounded-xl border border-[#D8CEBE] bg-[#FFFDF9] text-[#292039]"
                  />
                </div>

                <div>
                  <label className="font-semibold text-[#292039] block mb-1">
                    Capacity (1-8 Beds)
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="8"
                    required
                    value={roomCapacity}
                    onChange={(e) => setRoomCapacity(e.target.value)}
                    className="w-full px-3.5 py-2 rounded-xl border border-[#D8CEBE] bg-[#FFFDF9] text-[#292039]"
                  />
                </div>
              </div>

              <div>
                <label className="font-semibold text-[#292039] block mb-1">Room Type</label>
                <select
                  value={roomType}
                  onChange={(e) => setRoomType(e.target.value)}
                  className="w-full px-3.5 py-2 rounded-xl border border-[#D8CEBE] bg-[#FFFDF9] text-[#292039]"
                >
                  <option value="single">Single Occupancy</option>
                  <option value="double">Double Occupancy</option>
                  <option value="triple">Triple Occupancy</option>
                  <option value="standard">Standard Dorm</option>
                </select>
              </div>

              <div className="flex justify-end gap-3 pt-3">
                <button
                  type="button"
                  onClick={() => setShowAddRoomModal(false)}
                  className="px-4 py-2 rounded-xl border border-[#D8CEBE] text-[#292039] font-semibold hover:bg-[#F7EFE6] cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-5 py-2 rounded-xl bg-[#292039] text-white font-semibold hover:bg-[#3D3052] disabled:opacity-50 cursor-pointer"
                >
                  {submitting ? 'Creating...' : 'Create Room'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------- */}
      {/* MODAL: Edit Room Capacity */}
      {/* ------------------------------------------------------------------- */}
      {editingRoom && (
        <div className="fixed inset-0 bg-[#292039]/40 z-50 flex items-center justify-center p-4 backdrop-blur-xs">
          <div className="bg-[#FFFCF7] border border-[#E8DCCF] rounded-3xl p-6 sm:p-8 max-w-md w-full space-y-5 shadow-2xl">
            <div className="flex justify-between items-center pb-3 border-b border-[#F0E4D4]">
              <h3 className="font-serif text-lg font-bold text-[#292039]">
                Configure Room: {editingRoom.room_number || editingRoom.roomNumber}
              </h3>
              <button
                type="button"
                onClick={() => setEditingRoom(null)}
                className="text-[#292039]/60 hover:text-[#292039] font-bold"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleUpdateRoom} className="space-y-4 text-xs">
              <div>
                <label className="font-semibold text-[#292039] block mb-1">
                  Bed Capacity (1-8)
                </label>
                <input
                  type="number"
                  min="1"
                  max="8"
                  required
                  value={roomCapacity}
                  onChange={(e) => setRoomCapacity(e.target.value)}
                  className="w-full px-3.5 py-2 rounded-xl border border-[#D8CEBE] bg-[#FFFDF9] text-[#292039]"
                />
                <p className="text-[11px] text-[#292039]/60 mt-1">
                  Protection: Cannot reduce capacity below current resident bed numbers (currently{' '}
                  {editingRoom.occupied ?? 0} occupied).
                </p>
              </div>

              <div>
                <label className="font-semibold text-[#292039] block mb-1">Room Type</label>
                <select
                  value={roomType}
                  onChange={(e) => setRoomType(e.target.value)}
                  className="w-full px-3.5 py-2 rounded-xl border border-[#D8CEBE] bg-[#FFFDF9] text-[#292039]"
                >
                  <option value="single">Single Occupancy</option>
                  <option value="double">Double Occupancy</option>
                  <option value="triple">Triple Occupancy</option>
                  <option value="standard">Standard Dorm</option>
                </select>
              </div>

              <div className="flex justify-end gap-3 pt-3">
                <button
                  type="button"
                  onClick={() => setEditingRoom(null)}
                  className="px-4 py-2 rounded-xl border border-[#D8CEBE] text-[#292039] font-semibold hover:bg-[#F7EFE6] cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-5 py-2 rounded-xl bg-[#292039] text-white font-semibold hover:bg-[#3D3052] disabled:opacity-50 cursor-pointer"
                >
                  {submitting ? 'Saving...' : 'Update Room'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------- */}
      {/* MODAL: Allocate Student */}
      {/* ------------------------------------------------------------------- */}
      {showAllocateModal && (
        <div className="fixed inset-0 bg-[#292039]/40 z-50 flex items-center justify-center p-4 backdrop-blur-xs">
          <div className="bg-[#FFFCF7] border border-[#E8DCCF] rounded-3xl p-6 sm:p-8 max-w-md w-full space-y-5 shadow-2xl">
            <div className="flex justify-between items-center pb-3 border-b border-[#F0E4D4]">
              <h3 className="font-serif text-lg font-bold text-[#292039]">
                {prefilledAllocate
                  ? `Allocate Bed ${prefilledAllocate.bedNo} (${prefilledAllocate.room.room_number || prefilledAllocate.room.roomNumber})`
                  : 'Allocate Student to Room Bed'}
              </h3>
              <button
                type="button"
                onClick={() => {
                  setShowAllocateModal(false)
                  setPrefilledAllocate(null)
                }}
                className="text-[#292039]/60 hover:text-[#292039] font-bold"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleAllocateStudent} className="space-y-4 text-xs">
              <div>
                <label className="font-semibold text-[#292039] block mb-1">
                  Active Student (Approved Roster)
                </label>
                <select
                  required
                  value={allocStudentId}
                  onChange={(e) => setAllocStudentId(e.target.value)}
                  className="w-full px-3.5 py-2 rounded-xl border border-[#D8CEBE] bg-[#FFFDF9] text-[#292039]"
                >
                  <option value="">Select a student resident</option>
                  {activeStudents.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.fullName} ({s.rollNumber}){' '}
                      {s.room && s.room !== 'Not Assigned'
                        ? `• Currently ${s.room}`
                        : '• Not Allocated'}
                    </option>
                  ))}
                </select>
              </div>

              {!prefilledAllocate && (
                <div>
                  <label className="font-semibold text-[#292039] block mb-1">Target Room</label>
                  <select
                    required
                    value={allocRoomId}
                    onChange={(e) => setAllocRoomId(e.target.value)}
                    className="w-full px-3.5 py-2 rounded-xl border border-[#D8CEBE] bg-[#FFFDF9] text-[#292039]"
                  >
                    <option value="">Select a room</option>
                    {rooms.map((r) => (
                      <option key={r.id || r.room_number} value={r.id || r.room_number}>
                        {r.room_number || r.roomNumber} ({r.block}) —{' '}
                        {r.vacantBeds ?? r.vacant_beds ?? r.capacity - (r.occupied ?? 0)} vacant
                        beds
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div>
                <label className="font-semibold text-[#292039] block mb-1">Bed Number</label>
                {vacantBedsForAlloc.length > 0 ? (
                  <select
                    required
                    value={allocBedNumber}
                    onChange={(e) => setAllocBedNumber(e.target.value)}
                    className="w-full px-3.5 py-2 rounded-xl border border-[#D8CEBE] bg-[#FFFDF9] text-[#292039]"
                  >
                    {vacantBedsForAlloc.map((b) => (
                      <option key={b} value={b}>
                        Bed {b} (Available)
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    type="number"
                    min="1"
                    max="8"
                    required
                    value={allocBedNumber}
                    onChange={(e) => setAllocBedNumber(e.target.value)}
                    className="w-full px-3.5 py-2 rounded-xl border border-[#D8CEBE] bg-[#FFFDF9] text-[#292039]"
                  />
                )}
              </div>

              <div>
                <label className="font-semibold text-[#292039] block mb-1">
                  Allocation Start Date
                </label>
                <input
                  type="date"
                  required
                  value={allocStartDate}
                  onChange={(e) => setAllocStartDate(e.target.value)}
                  className="w-full px-3.5 py-2 rounded-xl border border-[#D8CEBE] bg-[#FFFDF9] text-[#292039]"
                />
              </div>

              <div className="flex justify-end gap-3 pt-3">
                <button
                  type="button"
                  onClick={() => {
                    setShowAllocateModal(false)
                    setPrefilledAllocate(null)
                  }}
                  className="px-4 py-2 rounded-xl border border-[#D8CEBE] text-[#292039] font-semibold hover:bg-[#F7EFE6] cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-5 py-2 rounded-xl bg-[#292039] text-white font-semibold hover:bg-[#3D3052] disabled:opacity-50 cursor-pointer"
                >
                  {submitting ? 'Allocating...' : 'Confirm Allocation'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------- */}
      {/* MODAL: Transfer Student */}
      {/* ------------------------------------------------------------------- */}
      {transferTarget && (
        <div className="fixed inset-0 bg-[#292039]/40 z-50 flex items-center justify-center p-4 backdrop-blur-xs">
          <div className="bg-[#FFFCF7] border border-[#E8DCCF] rounded-3xl p-6 sm:p-8 max-w-md w-full space-y-5 shadow-2xl">
            <div className="flex justify-between items-center pb-3 border-b border-[#F0E4D4]">
              <h3 className="font-serif text-lg font-bold text-[#292039]">
                Transfer Resident: {transferTarget.student?.fullName || 'Resident'}
              </h3>
              <button
                type="button"
                onClick={() => setTransferTarget(null)}
                className="text-[#292039]/60 hover:text-[#292039] font-bold"
              >
                ✕
              </button>
            </div>

            <div className="p-3 bg-[#F7EFE6] rounded-xl text-xs text-[#292039]/80">
              Current Location:{' '}
              <strong>Room {transferTarget.room_number || transferTarget.roomNumber}</strong> (Bed{' '}
              {transferTarget.bed_number || transferTarget.bedNumber})
            </div>

            <form onSubmit={handleTransferStudent} className="space-y-4 text-xs">
              <div>
                <label className="font-semibold text-[#292039] block mb-1">Target Room</label>
                <select
                  required
                  value={transferTargetRoomId}
                  onChange={(e) => setTransferTargetRoomId(e.target.value)}
                  className="w-full px-3.5 py-2 rounded-xl border border-[#D8CEBE] bg-[#FFFDF9] text-[#292039]"
                >
                  <option value="">Select target room</option>
                  {rooms.map((r) => (
                    <option key={r.id || r.room_number} value={r.id || r.room_number}>
                      {r.room_number || r.roomNumber} ({r.block}) —{' '}
                      {r.vacantBeds ?? r.vacant_beds ?? r.capacity - (r.occupied ?? 0)} vacant beds
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="font-semibold text-[#292039] block mb-1">Target Bed Number</label>
                {vacantBedsForTransfer.length > 0 ? (
                  <select
                    required
                    value={transferTargetBed}
                    onChange={(e) => setTransferTargetBed(e.target.value)}
                    className="w-full px-3.5 py-2 rounded-xl border border-[#D8CEBE] bg-[#FFFDF9] text-[#292039]"
                  >
                    {vacantBedsForTransfer.map((b) => (
                      <option key={b} value={b}>
                        Bed {b} (Available)
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    type="number"
                    min="1"
                    max="8"
                    required
                    value={transferTargetBed}
                    onChange={(e) => setTransferTargetBed(e.target.value)}
                    className="w-full px-3.5 py-2 rounded-xl border border-[#D8CEBE] bg-[#FFFDF9] text-[#292039]"
                  />
                )}
              </div>

              <div>
                <label className="font-semibold text-[#292039] block mb-1">
                  Effective Transfer Date
                </label>
                <input
                  type="date"
                  required
                  value={transferDate}
                  onChange={(e) => setTransferDate(e.target.value)}
                  className="w-full px-3.5 py-2 rounded-xl border border-[#D8CEBE] bg-[#FFFDF9] text-[#292039]"
                />
              </div>

              <div>
                <label className="font-semibold text-[#292039] block mb-1">
                  Reason for Transfer (Mandatory)
                </label>
                <textarea
                  required
                  rows={3}
                  placeholder="e.g. Wing maintenance / request approved by Warden"
                  value={transferReason}
                  onChange={(e) => setTransferReason(e.target.value)}
                  className="w-full px-3.5 py-2 rounded-xl border border-[#D8CEBE] bg-[#FFFDF9] text-[#292039] focus:outline-none focus:border-[#D94378]"
                />
              </div>

              <div className="flex justify-end gap-3 pt-3">
                <button
                  type="button"
                  onClick={() => setTransferTarget(null)}
                  className="px-4 py-2 rounded-xl border border-[#D8CEBE] text-[#292039] font-semibold hover:bg-[#F7EFE6] cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-5 py-2 rounded-xl bg-[#292039] text-white font-semibold hover:bg-[#3D3052] disabled:opacity-50 cursor-pointer"
                >
                  {submitting ? 'Transferring...' : 'Execute Transfer'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------- */}
      {/* MODAL: End Allocation (Checkout) */}
      {/* ------------------------------------------------------------------- */}
      {endTarget && (
        <div className="fixed inset-0 bg-[#292039]/40 z-50 flex items-center justify-center p-4 backdrop-blur-xs">
          <div className="bg-[#FFFCF7] border border-[#E8DCCF] rounded-3xl p-6 sm:p-8 max-w-md w-full space-y-5 shadow-2xl">
            <div className="flex justify-between items-center pb-3 border-b border-[#F0E4D4]">
              <h3 className="font-serif text-lg font-bold text-[#292039]">
                Checkout Resident: {endTarget.student?.fullName || 'Resident'}
              </h3>
              <button
                type="button"
                onClick={() => setEndTarget(null)}
                className="text-[#292039]/60 hover:text-[#292039] font-bold"
              >
                ✕
              </button>
            </div>

            <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-900">
              Ending bed allocation for{' '}
              <strong>Room {endTarget.room_number || endTarget.roomNumber}</strong> (Bed{' '}
              {endTarget.bed_number || endTarget.bedNumber}). This frees the bed slot for new
              admissions.
            </div>

            <form onSubmit={handleEndAllocation} className="space-y-4 text-xs">
              <div>
                <label className="font-semibold text-[#292039] block mb-1">
                  Vacate / Checkout Date
                </label>
                <input
                  type="date"
                  required
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="w-full px-3.5 py-2 rounded-xl border border-[#D8CEBE] bg-[#FFFDF9] text-[#292039]"
                />
              </div>

              <div>
                <label className="font-semibold text-[#292039] block mb-1">
                  Checkout Reason (Mandatory, at least 3 characters)
                </label>
                <textarea
                  required
                  rows={3}
                  placeholder="e.g. Semester checkout / graduated / moved off campus"
                  value={endReason}
                  onChange={(e) => setEndReason(e.target.value)}
                  className="w-full px-3.5 py-2 rounded-xl border border-[#D8CEBE] bg-[#FFFDF9] text-[#292039] focus:outline-none focus:border-[#D94378]"
                />
              </div>

              <div className="flex justify-end gap-3 pt-3">
                <button
                  type="button"
                  onClick={() => setEndTarget(null)}
                  className="px-4 py-2 rounded-xl border border-[#D8CEBE] text-[#292039] font-semibold hover:bg-[#F7EFE6] cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-5 py-2 rounded-xl bg-rose-700 text-white font-semibold hover:bg-rose-800 disabled:opacity-50 cursor-pointer"
                >
                  {submitting ? 'Processing...' : 'Confirm Checkout'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
