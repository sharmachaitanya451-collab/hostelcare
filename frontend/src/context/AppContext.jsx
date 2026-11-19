import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import {
  apiDownloadBlob,
  apiRequest,
  clearCsrfToken,
  onAuthForbidden,
  onSessionExpired,
} from '../lib/api'
import { mockHostelInfo } from '../lib/mockData'

const AppContext = createContext(null)

const STATUS_DISPLAY_MAP = {
  submitted: 'Submitted',
  under_review: 'Under Review',
  assigned: 'Assigned',
  accepted: 'Accepted',
  in_progress: 'In Progress',
  completed: 'Resolved',
  resolved: 'Resolved',
  closed: 'Closed',
  rejected: 'Rejected',
}

const PRIORITY_DISPLAY_MAP = {
  low: 'Low',
  medium: 'Medium',
  high: 'High',
}

export function isComplaintOwnedByStudent(complaint, user) {
  if (!complaint || !user) return false
  const cStudentId = complaint.studentId || complaint.student_user_id
  if (cStudentId && user.id) {
    return String(cStudentId) === String(user.id)
  }
  const cRoll = complaint.studentRoll || complaint.student_roll || complaint.reporterRoll
  if (cRoll && user.rollNumber) {
    return String(cRoll).toUpperCase() === String(user.rollNumber).toUpperCase()
  }
  return false
}

const FINE_STATUS_DISPLAY_MAP = {
  pending: 'Pending',
  disputed: 'Disputed',
  paid: 'Paid',
  waived: 'Waived',
  cancelled: 'Cancelled',
}

const DISPUTE_STATUS_DISPLAY_MAP = {
  open: 'Pending Review',
  approved: 'Approved',
  rejected: 'Rejected',
}

export function normalizeFineForUi(raw) {
  if (!raw || typeof raw !== 'object') return raw
  const rawStatus = String(raw.status || 'pending').toLowerCase()
  const displayStatus = FINE_STATUS_DISPLAY_MAP[rawStatus] || raw.status || 'Pending'

  const rawDispute = raw.dispute
    ? {
        ...raw.dispute,
        dbStatus: String(raw.dispute.status || 'open').toLowerCase(),
        status:
          DISPUTE_STATUS_DISPLAY_MAP[String(raw.dispute.status || 'open').toLowerCase()] ||
          raw.dispute.status,
        explanation: raw.dispute.reason || raw.dispute.explanation || '',
        submittedAt: raw.dispute.createdAt
          ? new Date(raw.dispute.createdAt).toLocaleString('en-IN', {
              dateStyle: 'medium',
              timeStyle: 'short',
            })
          : raw.dispute.submittedAt || '',
        reviewNote: raw.dispute.decisionReason || raw.dispute.reviewNote || null,
        reviewedBy: raw.dispute.decidedBy || raw.dispute.reviewedBy || null,
        reviewedAt: raw.dispute.decidedAt
          ? new Date(raw.dispute.decidedAt).toLocaleString('en-IN', {
              dateStyle: 'medium',
              timeStyle: 'short',
            })
          : raw.dispute.reviewedAt || null,
      }
    : null

  const normalizedHistory = Array.isArray(raw.history)
    ? raw.history.map((h) => ({
        ...h,
        actor: h.actorName || h.actor || 'HostelCare',
        timestamp: h.createdAt
          ? new Date(h.createdAt).toLocaleString('en-IN', {
              dateStyle: 'medium',
              timeStyle: 'short',
            })
          : h.timestamp || '',
        note: h.note || '',
      }))
    : []

  const amountNum = Number(raw.amountInr ?? raw.amount ?? 0)
  return {
    ...raw,
    id: raw.referenceNo || raw.id,
    referenceNo: raw.referenceNo || raw.id,
    dbStatus: rawStatus,
    status: displayStatus,
    amount: Number.isFinite(amountNum) ? amountNum : 0,
    amountInr: raw.amountInr || (Number.isFinite(amountNum) ? amountNum.toFixed(2) : '0.00'),
    category: raw.category || 'Disciplinary Penalty',
    dispute: rawDispute,
    history: normalizedHistory,
  }
}

function sanitizeComplaintForStudentUi(complaint) {
  if (!complaint || typeof complaint !== 'object') return complaint
  const sanitized = { ...complaint }
  delete sanitized.internalNotes
  delete sanitized.internal_notes
  delete sanitized.assignmentNotes
  delete sanitized.instructions
  if (Array.isArray(sanitized.history)) {
    sanitized.history = sanitized.history.map((h) => {
      if (!h || typeof h !== 'object') return h
      const actionCode = String(h.actionCode || h.action_code || h.action || '').toLowerCase()
      let safeNote = typeof h.note === 'string' ? h.note : ''
      if (
        actionCode === 'assigned' ||
        actionCode === 'assigned to duty staff' ||
        actionCode === 'reassigned' ||
        actionCode === 'reassigned to duty staff'
      ) {
        const lower = safeNote.toLowerCase()
        const wardenIdx = lower.indexOf(' warden note:')
        const instrIdx = lower.indexOf(' instructions:')
        let cutIdx = -1
        if (wardenIdx !== -1) cutIdx = wardenIdx
        if (instrIdx !== -1 && (cutIdx === -1 || instrIdx < cutIdx)) cutIdx = instrIdx
        if (cutIdx !== -1) {
          safeNote = safeNote.slice(0, cutIdx).trim()
          if (safeNote && !safeNote.endsWith('.')) {
            safeNote += '.'
          }
        }
      }
      return { ...h, note: safeNote }
    })
  }
  return sanitized
}

export function normalizeComplaintForUi(raw) {
  if (!raw || typeof raw !== 'object') return raw
  const rawStatus = String(raw.status || 'submitted')
  const lowerStatus = rawStatus.toLowerCase().replace(/\s+/g, '_')
  const displayStatus = raw.displayStatus || STATUS_DISPLAY_MAP[lowerStatus] || rawStatus

  const rawPriority = String(raw.priority || 'medium')
  const lowerPriority = rawPriority.toLowerCase()
  const displayPriority = raw.displayPriority || PRIORITY_DISPLAY_MAP[lowerPriority] || rawPriority

  const normalizedHistory = Array.isArray(raw.history)
    ? raw.history.map((h) => ({
        ...h,
        action: h.actionLabel || h.action || 'Status Updated',
        actionCode: h.action_code || h.action,
        by: h.by || h.actor_name || h.actor || 'HostelCare',
        role: h.role || h.actor_role || 'Hostel Operations',
        time: h.time || h.timestamp || '',
        note: h.note || '',
      }))
    : []

  const normalizedUpdates = Array.isArray(raw.updates)
    ? raw.updates.map((u) => ({
        ...u,
        authorName: u.authorName || u.author_name || 'Duty Staff',
        authorRole: u.authorRole || u.author_role || 'Maintenance Staff',
        body: u.body || u.note || u.message || '',
        note: u.body || u.note || u.message || '',
        time: u.time || u.timestamp || '',
      }))
    : []

  const normalizedAttachments = Array.isArray(raw.attachments)
    ? raw.attachments.map((att) => ({
        ...att,
        id: att.id || att.public_id || att.publicId,
        publicId: att.publicId || att.public_id || att.id,
        filename: att.filename || att.original_filename || att.originalFilename || 'photo',
        mimeType: att.mimeType || att.mime_type || 'image/jpeg',
        fileSizeBytes: Number(att.fileSizeBytes ?? att.file_size_bytes ?? 0),
        createdAt: att.createdAt || att.created_at || null,
        url: att.url || '',
      }))
    : []

  const each = {
    ...raw,
    id: raw.id || raw.reference_no || raw.referenceNo,
    referenceNo: raw.reference_no || raw.referenceNo || raw.id,
    dbStatus: lowerStatus,
    status: displayStatus,
    dbPriority: lowerPriority,
    priority: displayPriority,
    category: raw.category || 'General / Custom',
    studentId: raw.studentId || raw.student_user_id,
    studentName: raw.studentName || raw.student_name || raw.reporterName || 'Resident Student',
    studentRoll: raw.studentRoll || raw.student_roll || raw.reporterRoll || 'N/A',
    locationType: raw.locationType || raw.location_type || 'room',
    locationDetail: raw.locationDetail || raw.location_detail || null,
    room:
      raw.room ||
      (raw.location_type === 'common_area'
        ? `Common Area (${raw.location_detail || 'Campus'})`
        : 'Assigned Room'),
    block: raw.block || 'Hostel',
    date: raw.date || raw.dateSubmitted || '',
    updatedDate: raw.updatedDate || raw.date || '',
    assignedStaffId: raw.assignedStaffId || raw.assigned_staff_id || null,
    assignedStaff:
      raw.assignedStaff && raw.assignedStaff !== 'Unassigned' ? raw.assignedStaff : null,
    assignedStaffRole: raw.assignedStaffRole || raw.assigned_staff_role || null,
    assignedStaffContact: raw.assignedStaffContact || raw.assigned_staff_contact || null,
    assignmentNotes: raw.assignmentNotes ?? raw.instructions ?? null,
    completionNote: raw.completionNote ?? raw.completion_note ?? null,
    reworkNote: raw.reworkNote ?? raw.rework_note ?? null,
    rejectionReason: raw.rejectionReason ?? raw.rejection_reason ?? null,
    updates: normalizedUpdates,
    history: normalizedHistory,
    attachments: normalizedAttachments,
  }

  if (Array.isArray(raw.internalNotes) || Array.isArray(raw.internal_notes)) {
    const notesSource = raw.internalNotes || raw.internal_notes || []
    each.internalNotes = notesSource.map((n) => ({
      ...n,
      by: n.by || n.author_name || n.author || 'Hostel Warden',
      role: n.role || n.author_role || 'Hostel Warden',
      time: n.time || n.timestamp || '',
      note: n.note || n.body || '',
      body: n.body || n.note || '',
    }))
  }

  return each
}

export function AppProvider({ children }) {
  // Current authenticated user comes strictly from `/api/v1/auth/me` or `/api/v1/auth/login`
  const [user, setUser] = useState(null)
  const userRef = useRef(null)
  const revalidationPromiseRef = useRef(null)
  const [authLoading, setAuthLoading] = useState(true)
  const [sessionExpired, setSessionExpired] = useState(false)

  // Domain Store — initialized to empty arrays (never mock fallbacks)
  const [students, setStudents] = useState([])
  const [studentsLoading, setStudentsLoading] = useState(false)
  const [studentsError, setStudentsError] = useState('')
  const [complaints, setComplaints] = useState([])
  const [complaintsLoading, setComplaintsLoading] = useState(false)
  const [blocks, setBlocks] = useState([])
  const [blocksLoading, setBlocksLoading] = useState(false)
  const [blocksError, setBlocksError] = useState('')
  const [rooms, setRooms] = useState([])
  const [roomsLoading, setRoomsLoading] = useState(false)
  const [roomsError, setRoomsError] = useState('')
  const [allocations, setAllocations] = useState([])
  const [allocationsLoading, setAllocationsLoading] = useState(false)
  const [allocationsError, setAllocationsError] = useState('')
  const [staff, setStaff] = useState([])
  const [staffLoading, setStaffLoading] = useState(false)
  const [staffError, setStaffError] = useState('')
  const [auditLogs, setAuditLogs] = useState([])
  const [auditLogsLoading, setAuditLogsLoading] = useState(false)
  const [auditLogsError, setAuditLogsError] = useState('')
  const [adminOverview, setAdminOverview] = useState(null)
  const [adminOverviewLoading, setAdminOverviewLoading] = useState(false)
  const [adminOverviewError, setAdminOverviewError] = useState('')
  const adminOverviewReqIdRef = useRef(0)
  const adminOverviewAbortRef = useRef(null)
  const [complaintAnalytics, setComplaintAnalytics] = useState(null)
  const [complaintAnalyticsLoading, setComplaintAnalyticsLoading] = useState(false)
  const [complaintAnalyticsError, setComplaintAnalyticsError] = useState('')
  const complaintAnalyticsReqIdRef = useRef(0)
  const complaintAnalyticsAbortRef = useRef(null)
  const [notifications, setNotifications] = useState([])
  const [staffNotifications, setStaffNotifications] = useState([])
  const [fines, setFines] = useState([])
  const [finesLoading, setFinesLoading] = useState(false)
  const [finesError, setFinesError] = useState('')
  const [finesPagination, setFinesPagination] = useState({
    page: 1,
    pageSize: 20,
    total: 0,
    totalPages: 1,
  })

  useEffect(() => {
    userRef.current = user
  }, [user])

  const clearAdminState = useCallback(() => {
    setStudents([])
    setStudentsError('')
    setStaff([])
    setStaffError('')
    setRooms([])
    setRoomsError('')
    setBlocks([])
    setBlocksError('')
    setAllocations([])
    setAllocationsError('')
    setAuditLogs([])
    setAuditLogsError('')
    if (adminOverviewAbortRef.current) {
      adminOverviewAbortRef.current.abort()
      adminOverviewAbortRef.current = null
    }
    adminOverviewReqIdRef.current += 1
    setAdminOverview(null)
    setAdminOverviewLoading(false)
    setAdminOverviewError('')
    if (complaintAnalyticsAbortRef.current) {
      complaintAnalyticsAbortRef.current.abort()
      complaintAnalyticsAbortRef.current = null
    }
    complaintAnalyticsReqIdRef.current += 1
    setComplaintAnalytics(null)
    setComplaintAnalyticsLoading(false)
    setComplaintAnalyticsError('')
    setFinesError('')
  }, [])

  const clearAllSessionData = useCallback(() => {
    userRef.current = null
    setUser(null)
    setComplaints([])
    setFines([])
    setFinesError('')
    setFinesPagination({ page: 1, pageSize: 20, total: 0, totalPages: 1 })
    setNotifications([])
    setStaffNotifications([])
    clearAdminState()
  }, [clearAdminState])

  const upsertComplaintInState = useCallback((rawComplaint) => {
    if (!rawComplaint) return null
    const normalized = normalizeComplaintForUi(rawComplaint)
    setComplaints((prev) => {
      const exists = prev.some((c) => c.id === normalized.id)
      if (exists) {
        return prev.map((c) => (c.id === normalized.id ? normalized : c))
      }
      return [normalized, ...prev]
    })
    return normalized
  }, [])

  const refreshNotifications = useCallback(async (roleHint) => {
    try {
      const res = await apiRequest('/api/v1/notifications')
      if (Array.isArray(res?.notifications)) {
        setNotifications(res.notifications)
        if (roleHint === 'staff') {
          setStaffNotifications(res.notifications)
        }
      }
    } catch {
      // Ignore transient notification fetch error
    }
  }, [])

  const fetchStudents = useCallback(async () => {
    setStudentsLoading(true)
    setStudentsError('')
    try {
      const res = await apiRequest('/api/v1/admin/students')
      const list = Array.isArray(res?.students) ? res.students : []
      setStudents(list)
      return list
    } catch (err) {
      const msg = err?.message || 'Unable to load student directory.'
      setStudentsError(msg)
      throw err
    } finally {
      setStudentsLoading(false)
    }
  }, [])

  const fetchStaff = useCallback(async () => {
    setStaffLoading(true)
    setStaffError('')
    try {
      const res = await apiRequest('/api/v1/admin/staff')
      const list = Array.isArray(res?.staff) ? res.staff : []
      setStaff(list)
      return list
    } catch (err) {
      const msg = err?.message || 'Unable to load maintenance staff records.'
      setStaffError(msg)
      throw err
    } finally {
      setStaffLoading(false)
    }
  }, [])

  const fetchRooms = useCallback(async (filters = {}) => {
    setRoomsLoading(true)
    setRoomsError('')
    try {
      const params = new URLSearchParams()
      if (filters.blockId || filters.block_id)
        params.set('block_id', filters.blockId || filters.block_id)
      if (filters.floor !== undefined && filters.floor !== '') params.set('floor', filters.floor)
      if (filters.isActive !== undefined)
        params.set('is_active', filters.isActive ? 'true' : 'false')
      const queryStr = params.toString() ? `?${params.toString()}` : ''
      const res = await apiRequest(`/api/v1/admin/rooms${queryStr}`)
      const list = Array.isArray(res?.rooms) ? res.rooms : []
      setRooms(list)
      return list
    } catch (err) {
      const msg = err?.message || 'Unable to load hostel room occupancy.'
      setRoomsError(msg)
      throw err
    } finally {
      setRoomsLoading(false)
    }
  }, [])

  const fetchBlocks = useCallback(async () => {
    setBlocksLoading(true)
    setBlocksError('')
    try {
      const res = await apiRequest('/api/v1/admin/blocks')
      const list = Array.isArray(res?.blocks) ? res.blocks : []
      setBlocks(list)
      return list
    } catch (err) {
      const msg = err?.message || 'Unable to load hostel blocks.'
      setBlocksError(msg)
      throw err
    } finally {
      setBlocksLoading(false)
    }
  }, [])

  const addBlock = useCallback(
    async (data) => {
      const res = await apiRequest('/api/v1/admin/blocks', {
        method: 'POST',
        body: data,
      })
      if (res?.block) {
        setBlocks((prev) => [...prev, res.block])
        fetchBlocks().catch(() => {})
        fetchRooms().catch(() => {})
      }
      return res?.block
    },
    [fetchBlocks, fetchRooms],
  )

  const updateBlock = useCallback(
    async (id, data) => {
      const res = await apiRequest(`/api/v1/admin/blocks/${id}`, {
        method: 'PATCH',
        body: data,
      })
      if (res?.block) {
        setBlocks((prev) => prev.map((b) => (b.id === id ? { ...b, ...res.block } : b)))
        fetchBlocks().catch(() => {})
        fetchRooms().catch(() => {})
      }
      return res?.block
    },
    [fetchBlocks, fetchRooms],
  )

  const addRoom = useCallback(
    async (data) => {
      const res = await apiRequest('/api/v1/admin/rooms', {
        method: 'POST',
        body: data,
      })
      if (res?.room) {
        setRooms((prev) => [...prev, res.room])
        fetchBlocks().catch(() => {})
      }
      return res?.room
    },
    [fetchBlocks],
  )

  const updateRoom = useCallback(
    async (identifier, data) => {
      const res = await apiRequest(`/api/v1/admin/rooms/${identifier}`, {
        method: 'PATCH',
        body: data,
      })
      if (res?.room) {
        setRooms((prev) =>
          prev.map((r) =>
            r.room_number === res.room.room_number || r.id === res.room.id ? res.room : r,
          ),
        )
        fetchBlocks().catch(() => {})
      }
      return res?.room
    },
    [fetchBlocks],
  )

  const fetchAllocations = useCallback(async (filters = {}) => {
    setAllocationsLoading(true)
    setAllocationsError('')
    try {
      const params = new URLSearchParams()
      if (filters.roomId || filters.room_id)
        params.set('room_id', filters.roomId || filters.room_id)
      if (filters.studentId || filters.student_id)
        params.set('student_id', filters.studentId || filters.student_id)
      if (filters.activeOnly !== undefined)
        params.set('active_only', filters.activeOnly ? 'true' : 'false')
      const queryStr = params.toString() ? `?${params.toString()}` : ''
      const res = await apiRequest(`/api/v1/admin/room-allocations${queryStr}`)
      const list = Array.isArray(res?.allocations) ? res.allocations : []
      setAllocations(list)
      return list
    } catch (err) {
      const msg = err?.message || 'Unable to load room allocations.'
      setAllocationsError(msg)
      throw err
    } finally {
      setAllocationsLoading(false)
    }
  }, [])

  const allocateRoom = useCallback(
    async (data) => {
      const res = await apiRequest('/api/v1/admin/room-allocations', {
        method: 'POST',
        body: data,
      })
      if (res?.allocation) {
        setAllocations((prev) => [res.allocation, ...prev])
        fetchRooms().catch(() => {})
        fetchBlocks().catch(() => {})
      }
      return res?.allocation
    },
    [fetchBlocks, fetchRooms],
  )

  const endAllocation = useCallback(
    async (id, data) => {
      const res = await apiRequest(`/api/v1/admin/room-allocations/${id}/end`, {
        method: 'POST',
        body: data,
      })
      if (res?.allocation) {
        setAllocations((prev) => prev.map((a) => (a.id === id ? res.allocation : a)))
        fetchRooms().catch(() => {})
        fetchBlocks().catch(() => {})
      }
      return res?.allocation
    },
    [fetchBlocks, fetchRooms],
  )

  const transferAllocation = useCallback(
    async (id, data) => {
      const res = await apiRequest(`/api/v1/admin/room-allocations/${id}/transfer`, {
        method: 'POST',
        body: data,
      })
      if (res?.allocation) {
        setAllocations((prev) => [
          res.allocation,
          ...prev.map((a) => (a.id === id ? res.previous_allocation : a)),
        ])
        fetchRooms().catch(() => {})
        fetchBlocks().catch(() => {})
      }
      return res
    },
    [fetchBlocks, fetchRooms],
  )

  const fetchAuditLogs = useCallback(async () => {
    setAuditLogsLoading(true)
    setAuditLogsError('')
    try {
      const res = await apiRequest('/api/v1/admin/audit-logs')
      const list = Array.isArray(res?.audit_logs) ? res.audit_logs : []
      setAuditLogs(list)
      return list
    } catch (err) {
      const msg = err?.message || 'Unable to load administrative audit logs.'
      setAuditLogsError(msg)
      throw err
    } finally {
      setAuditLogsLoading(false)
    }
  }, [])

  const fetchAdminOverview = useCallback(async (filters = {}) => {
    if (adminOverviewAbortRef.current) {
      adminOverviewAbortRef.current.abort()
    }
    const controller = typeof AbortController !== 'undefined' ? new AbortController() : null
    adminOverviewAbortRef.current = controller
    const reqId = adminOverviewReqIdRef.current + 1
    adminOverviewReqIdRef.current = reqId

    setAdminOverviewLoading(true)
    setAdminOverviewError('')

    try {
      const params = new URLSearchParams()
      if (filters.preset) params.set('preset', filters.preset)
      if (filters.dateFrom || filters.date_from) {
        params.set('date_from', filters.dateFrom || filters.date_from)
      }
      if (filters.dateTo || filters.date_to) {
        params.set('date_to', filters.dateTo || filters.date_to)
      }
      const queryStr = params.toString() ? `?${params.toString()}` : ''
      const res = await apiRequest(`/api/v1/admin/analytics/overview${queryStr}`, {
        signal: controller?.signal,
      })

      if (adminOverviewReqIdRef.current !== reqId) {
        return null
      }
      setAdminOverview(res || null)
      return res
    } catch (err) {
      if (err?.name === 'AbortError' || adminOverviewReqIdRef.current !== reqId) {
        return null
      }
      const msg = err?.message || 'Unable to load administrative dashboard analytics.'
      setAdminOverviewError(msg)
      throw err
    } finally {
      if (adminOverviewReqIdRef.current === reqId) {
        setAdminOverviewLoading(false)
      }
    }
  }, [])

  const fetchComplaintAnalytics = useCallback(async (filters = {}) => {
    if (complaintAnalyticsAbortRef.current) {
      complaintAnalyticsAbortRef.current.abort()
    }
    const controller = typeof AbortController !== 'undefined' ? new AbortController() : null
    complaintAnalyticsAbortRef.current = controller
    const reqId = complaintAnalyticsReqIdRef.current + 1
    complaintAnalyticsReqIdRef.current = reqId

    setComplaintAnalyticsLoading(true)
    setComplaintAnalyticsError('')

    try {
      const params = new URLSearchParams()
      if (filters.preset) params.set('preset', filters.preset)
      if (filters.dateFrom || filters.date_from) {
        params.set('date_from', filters.dateFrom || filters.date_from)
      }
      if (filters.dateTo || filters.date_to) {
        params.set('date_to', filters.dateTo || filters.date_to)
      }
      const queryStr = params.toString() ? `?${params.toString()}` : ''
      const res = await apiRequest(`/api/v1/admin/analytics/complaints${queryStr}`, {
        signal: controller?.signal,
      })

      if (complaintAnalyticsReqIdRef.current !== reqId) {
        return null
      }
      setComplaintAnalytics(res || null)
      return res
    } catch (err) {
      if (err?.name === 'AbortError' || complaintAnalyticsReqIdRef.current !== reqId) {
        return null
      }
      const msg = err?.message || 'Unable to load complaint & SLA analytics.'
      setComplaintAnalyticsError(msg)
      throw err
    } finally {
      if (complaintAnalyticsReqIdRef.current === reqId) {
        setComplaintAnalyticsLoading(false)
      }
    }
  }, [])

  const refreshAdminIdentityData = useCallback(async () => {
    await Promise.allSettled([
      fetchStudents(),
      fetchStaff(),
      fetchAuditLogs(),
      fetchRooms(),
      fetchBlocks(),
      fetchAllocations(),
    ])
  }, [fetchAllocations, fetchAuditLogs, fetchBlocks, fetchRooms, fetchStaff, fetchStudents])

  const refreshRoleData = useCallback(
    async (activeUser) => {
      if (!activeUser) {
        setComplaints([])
        setNotifications([])
        setStaffNotifications([])
        clearAdminState()
        return
      }
      if (activeUser.role !== 'admin') {
        clearAdminState()
      }
      setComplaintsLoading(true)
      try {
        await refreshNotifications(activeUser.role)

        if (activeUser.role === 'student') {
          const [compRes, blocksRes, finesSettled] = await Promise.all([
            apiRequest('/api/v1/student/complaints'),
            apiRequest('/api/v1/blocks').catch(() => ({ blocks: [] })),
            apiRequest('/api/v1/student/fines').catch(() => null),
          ])
          if (Array.isArray(compRes?.complaints)) {
            const studentNormalized = compRes.complaints
              .map((raw) => sanitizeComplaintForStudentUi(normalizeComplaintForUi(raw)))
              .filter((c) => isComplaintOwnedByStudent(c, activeUser))
            setComplaints(studentNormalized)
          }
          if (Array.isArray(blocksRes?.blocks)) {
            setBlocks(blocksRes.blocks)
          }
          if (finesSettled && Array.isArray(finesSettled.fines)) {
            setFines(finesSettled.fines.map(normalizeFineForUi))
          }
        } else if (activeUser.role === 'staff') {
          const taskRes = await apiRequest('/api/v1/staff/tasks')
          const list = taskRes?.tasks || taskRes?.complaints || []
          if (Array.isArray(list)) {
            setComplaints(list.map(normalizeComplaintForUi))
          }
        } else if (activeUser.role === 'admin') {
          const [compSettled, finesSettled] = await Promise.allSettled([
            apiRequest('/api/v1/admin/complaints'),
            apiRequest('/api/v1/admin/fines'),
            refreshAdminIdentityData(),
          ])
          if (compSettled.status === 'fulfilled' && Array.isArray(compSettled.value?.complaints)) {
            setComplaints(compSettled.value.complaints.map(normalizeComplaintForUi))
          }
          if (finesSettled.status === 'fulfilled' && Array.isArray(finesSettled.value?.fines)) {
            setFines(finesSettled.value.fines.map(normalizeFineForUi))
            if (finesSettled.value.pagination) {
              setFinesPagination(finesSettled.value.pagination)
            }
          }
        }
      } catch {
        // Individual fetch handlers manage their own error states
      } finally {
        setComplaintsLoading(false)
      }
    },
    [clearAdminState, refreshAdminIdentityData, refreshNotifications],
  )

  const revalidateSession = useCallback(async () => {
    if (revalidationPromiseRef.current) {
      return revalidationPromiseRef.current
    }

    const promise = (async () => {
      const prevUser = userRef.current
      try {
        const data = await apiRequest('/api/v1/auth/me')
        const nextUser = data?.user || null
        if (!nextUser) {
          clearAllSessionData()
          return null
        }

        const identityOrRoleChanged =
          !prevUser || prevUser.id !== nextUser.id || prevUser.role !== nextUser.role

        userRef.current = nextUser
        setUser((prev) => {
          if (
            prev &&
            prev.id === nextUser.id &&
            prev.role === nextUser.role &&
            prev.status === nextUser.status &&
            prev.email === nextUser.email &&
            prev.fullName === nextUser.fullName &&
            prev.phone === nextUser.phone &&
            prev.room === nextUser.room &&
            prev.bed === nextUser.bed &&
            prev.block === nextUser.block &&
            prev.hasActiveRoom === nextUser.hasActiveRoom
          ) {
            return prev
          }
          return nextUser
        })
        setSessionExpired(false)

        if (identityOrRoleChanged) {
          setComplaints([])
          setNotifications([])
          setStaffNotifications([])
          if (nextUser.role !== 'admin') {
            clearAdminState()
          }
          await refreshRoleData(nextUser)
        }
        return nextUser
      } catch (err) {
        clearAllSessionData()
        if (err?.code === 'session_expired' || prevUser !== null) {
          setSessionExpired(true)
        }
        return null
      } finally {
        revalidationPromiseRef.current = null
      }
    })()

    revalidationPromiseRef.current = promise
    return promise
  }, [clearAdminState, clearAllSessionData, refreshRoleData])

  const fetchComplaintDetail = useCallback(
    async (complaintId) => {
      const activeUser = userRef.current || user
      if (!activeUser || !complaintId) return null
      const encoded = encodeURIComponent(complaintId)
      let endpoint = `/api/v1/student/complaints/${encoded}`
      if (activeUser.role === 'admin') {
        endpoint = `/api/v1/admin/complaints/${encoded}`
      } else if (activeUser.role === 'staff') {
        endpoint = `/api/v1/staff/tasks/${encoded}`
      }
      try {
        const res = await apiRequest(endpoint)
        const raw = res?.complaint || res?.task
        if (raw && typeof raw === 'object' && (raw.id || raw.reference_no)) {
          if (activeUser.role === 'student') {
            const normalizedCheck = sanitizeComplaintForStudentUi(normalizeComplaintForUi(raw))
            if (!isComplaintOwnedByStudent(normalizedCheck, activeUser)) {
              setComplaints((prev) =>
                prev.filter(
                  (c) =>
                    String(c.id) !== String(complaintId) &&
                    String(c.referenceNo || '') !== String(complaintId),
                ),
              )
              const err = new Error(
                "You do not have permission to access another student's complaint.",
              )
              err.status = 403
              err.code = 'forbidden'
              throw err
            }
            return upsertComplaintInState(sanitizeComplaintForStudentUi(raw))
          }
          return upsertComplaintInState(raw)
        }
        return null
      } catch (err) {
        if (
          err?.status === 403 ||
          err?.status === 404 ||
          err?.code === 'forbidden' ||
          err?.code === 'complaint_not_found' ||
          err?.code === 'not_found'
        ) {
          setComplaints((prev) =>
            prev.filter(
              (c) =>
                String(c.id) !== String(complaintId) &&
                String(c.referenceNo || '') !== String(complaintId),
            ),
          )
        }
        throw err
      }
    },
    [upsertComplaintInState, user],
  )

  // Subscribe to 401 session expiration and 403 permission denial events from the API client
  useEffect(() => {
    const unsubExpired = onSessionExpired(() => {
      clearAllSessionData()
      setSessionExpired(true)
    })
    const unsubForbidden = onAuthForbidden(() => {
      revalidateSession().catch(() => {})
    })
    return () => {
      unsubExpired()
      unsubForbidden()
    }
  }, [clearAllSessionData, revalidateSession])

  // Revalidate session when the browser tab becomes visible or receives focus
  useEffect(() => {
    const handleFocus = () => {
      revalidateSession().catch(() => {})
    }
    const handleVisibilityChange = () => {
      if (typeof document !== 'undefined' && document.visibilityState === 'visible') {
        revalidateSession().catch(() => {})
      }
    }

    if (typeof window !== 'undefined') {
      window.addEventListener('focus', handleFocus)
    }
    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', handleVisibilityChange)
    }

    return () => {
      if (typeof window !== 'undefined') {
        window.removeEventListener('focus', handleFocus)
      }
      if (typeof document !== 'undefined') {
        document.removeEventListener('visibilitychange', handleVisibilityChange)
      }
    }
  }, [revalidateSession])

  // Restore session on page refresh via `GET /api/v1/auth/me`
  useEffect(() => {
    let active = true
    async function restoreSession() {
      try {
        const data = await apiRequest('/api/v1/auth/me')
        if (!active) return
        if (data?.user) {
          userRef.current = data.user
          setUser(data.user)
          setSessionExpired(false)
          await refreshRoleData(data.user)
        } else {
          clearAllSessionData()
        }
      } catch (err) {
        if (!active) return
        clearAllSessionData()
        if (err?.code === 'session_expired') {
          setSessionExpired(true)
        }
      } finally {
        if (active) {
          setAuthLoading(false)
        }
      }
    }
    restoreSession()
    return () => {
      active = false
    }
  }, [clearAllSessionData, refreshRoleData])

  // Real Backend Authentication (`POST /api/v1/auth/login`)
  const login = async (identifier, password, role) => {
    const cleanId = (identifier || '').trim()
    const payload = {
      identifier: cleanId,
      email: cleanId,
      password,
    }
    if (role) {
      payload.role = role
    }
    const data = await apiRequest('/api/v1/auth/login', {
      method: 'POST',
      body: payload,
    })
    const authenticatedUser = data.user
    userRef.current = authenticatedUser
    setUser(authenticatedUser)
    setSessionExpired(false)
    await refreshRoleData(authenticatedUser)
    return authenticatedUser
  }

  const logout = async () => {
    try {
      await apiRequest('/api/v1/auth/logout', { method: 'POST' })
    } catch {
      // Even if network/session is already gone, clear local auth state
    } finally {
      clearCsrfToken()
      clearAllSessionData()
    }
  }

  // Student Self-Registration (`POST /api/v1/auth/register` -> creates status='pending')
  const registerStudent = async (formData) => {
    const data = await apiRequest('/api/v1/auth/register', {
      method: 'POST',
      body: {
        fullName: formData.fullName,
        email: formData.email,
        rollNumber: formData.rollNumber,
        phone: formData.phone,
        password: formData.password,
        confirmPassword: formData.confirmPassword ?? formData.password,
      },
    })
    return data.user
  }

  // Password Recovery & Setup (`POST /api/v1/auth/forgot-password` & `/api/v1/auth/reset-password`)
  const requestPasswordReset = async (email) => {
    return apiRequest('/api/v1/auth/forgot-password', {
      method: 'POST',
      body: { email },
    })
  }

  const confirmPasswordReset = async ({ token, password, confirmPassword }) => {
    return apiRequest('/api/v1/auth/reset-password', {
      method: 'POST',
      body: { token, password, confirmPassword },
    })
  }

  // ---------------------------------------------------------------------------
  // Phase 3D: Database-Backed Complaint, Task & Notification Operations
  // ---------------------------------------------------------------------------

  const addComplaint = async (complaintData) => {
    const photos = Array.isArray(complaintData.photos) ? complaintData.photos.filter(Boolean) : []
    const payload = {
      title: complaintData.title,
      category:
        complaintData.category && complaintData.category !== 'Uncategorized (Free-Text)'
          ? complaintData.category
          : null,
      description: complaintData.description,
      priority: String(complaintData.priority || 'Medium').toLowerCase(),
      location_type: complaintData.locationType || complaintData.location_type || 'room',
      location_detail: complaintData.locationDetail || complaintData.location_detail || null,
      block_id: complaintData.blockId || complaintData.block_id || null,
      block_code: complaintData.blockCode || complaintData.block_code || null,
    }

    let requestBody = payload
    if (photos.length > 0) {
      const formData = new FormData()
      formData.append('title', payload.title)
      formData.append('description', payload.description)
      formData.append('priority', payload.priority)
      formData.append('location_type', payload.location_type)
      if (payload.category) {
        formData.append('category', payload.category)
      }
      if (payload.location_detail) {
        formData.append('location_detail', payload.location_detail)
      }
      if (payload.block_id !== null && payload.block_id !== undefined && payload.block_id !== '') {
        formData.append('block_id', String(payload.block_id))
      }
      if (payload.block_code) {
        formData.append('block_code', payload.block_code)
      }
      photos.forEach((file) => {
        formData.append('photos', file)
      })
      requestBody = formData
    }

    const res = await apiRequest('/api/v1/student/complaints', {
      method: 'POST',
      body: requestBody,
    })
    const created = upsertComplaintInState(res?.complaint)
    await refreshNotifications(user?.role)
    return created
  }

  const updateComplaint = async (updated) => {
    if (!updated?.id) return null
    const res = await apiRequest(`/api/v1/admin/complaints/${encodeURIComponent(updated.id)}`, {
      method: 'PATCH',
      body: {
        priority: updated.priority ? String(updated.priority).toLowerCase() : undefined,
        category: updated.category,
      },
    })
    const saved = upsertComplaintInState(res?.complaint)
    await refreshAdminIdentityData()
    return saved
  }

  const reviewComplaint = async (complaintId, { note } = {}) => {
    const res = await apiRequest(`/api/v1/admin/complaints/${encodeURIComponent(complaintId)}`, {
      method: 'PATCH',
      body: {
        status: 'under_review',
        action: 'start_review',
        note,
      },
    })
    const saved = upsertComplaintInState(res?.complaint)
    await refreshAdminIdentityData()
    return saved
  }

  const assignStaffToComplaint = async (
    complaintId,
    { staffId, assignmentNotes, isReassign = false, reason } = {},
  ) => {
    const existing = complaints.find((c) => c.id === complaintId)
    const shouldReassign =
      isReassign ||
      Boolean(
        existing &&
        (existing.dbStatus === 'assigned' ||
          existing.dbStatus === 'accepted' ||
          existing.dbStatus === 'in_progress' ||
          existing.status === 'Assigned' ||
          existing.status === 'Accepted' ||
          existing.status === 'In Progress'),
      )

    const actionSegment = shouldReassign ? 'reassign' : 'assign'
    const res = await apiRequest(
      `/api/v1/admin/complaints/${encodeURIComponent(complaintId)}/${actionSegment}`,
      {
        method: 'POST',
        body: {
          staff_id: staffId,
          instructions: assignmentNotes,
          reason: reason || assignmentNotes,
        },
      },
    )
    const saved = upsertComplaintInState(res?.complaint)
    await refreshAdminIdentityData()
    return saved
  }

  const reassignStaffToComplaint = async (
    complaintId,
    { staffId, assignmentNotes, reason } = {},
  ) => {
    return assignStaffToComplaint(complaintId, {
      staffId,
      assignmentNotes,
      reason,
      isReassign: true,
    })
  }

  const closeComplaint = async (complaintId, { closureNote } = {}) => {
    const res = await apiRequest(
      `/api/v1/admin/complaints/${encodeURIComponent(complaintId)}/close`,
      {
        method: 'POST',
        body: { note: closureNote },
      },
    )
    const saved = upsertComplaintInState(res?.complaint)
    await refreshAdminIdentityData()
    return saved
  }

  const returnTaskForRework = async (complaintId, { reworkNote } = {}) => {
    const res = await apiRequest(
      `/api/v1/admin/complaints/${encodeURIComponent(complaintId)}/return-for-rework`,
      {
        method: 'POST',
        body: { reason: reworkNote },
      },
    )
    const saved = upsertComplaintInState(res?.complaint)
    await refreshAdminIdentityData()
    return saved
  }

  const rejectComplaint = async (complaintId, { reason } = {}) => {
    const res = await apiRequest(
      `/api/v1/admin/complaints/${encodeURIComponent(complaintId)}/reject`,
      {
        method: 'POST',
        body: { reason },
      },
    )
    const saved = upsertComplaintInState(res?.complaint)
    await refreshAdminIdentityData()
    return saved
  }

  const reopenComplaint = async (complaintId, { reason } = {}) => {
    const res = await apiRequest(
      `/api/v1/admin/complaints/${encodeURIComponent(complaintId)}/reopen`,
      {
        method: 'POST',
        body: { reason },
      },
    )
    const saved = upsertComplaintInState(res?.complaint)
    await refreshAdminIdentityData()
    return saved
  }

  const addInternalNote = async (complaintId, noteText) => {
    const res = await apiRequest(
      `/api/v1/admin/complaints/${encodeURIComponent(complaintId)}/internal-notes`,
      {
        method: 'POST',
        body: { body: noteText },
      },
    )
    const saved = upsertComplaintInState(res?.complaint)
    await refreshAdminIdentityData()
    return saved
  }

  // Staff Task Execution Operations (`/api/v1/staff/tasks/{id}/*`)
  const acceptTask = async (taskId) => {
    const res = await apiRequest(`/api/v1/staff/tasks/${encodeURIComponent(taskId)}/accept`, {
      method: 'POST',
    })
    const saved = upsertComplaintInState(res?.task || res?.complaint)
    await refreshNotifications('staff')
    return saved
  }

  const startTaskWork = async (taskId, { note } = {}) => {
    const res = await apiRequest(`/api/v1/staff/tasks/${encodeURIComponent(taskId)}/start`, {
      method: 'POST',
      body: { note },
    })
    const saved = upsertComplaintInState(res?.task || res?.complaint)
    await refreshNotifications('staff')
    return saved
  }

  const updateTaskProgress = async (taskId, { note } = {}) => {
    const res = await apiRequest(`/api/v1/staff/tasks/${encodeURIComponent(taskId)}/updates`, {
      method: 'POST',
      body: { body: note },
    })
    const saved = upsertComplaintInState(res?.task || res?.complaint)
    await refreshNotifications('staff')
    return saved
  }

  const completeTaskWork = async (taskId, { completionNote } = {}) => {
    const res = await apiRequest(`/api/v1/staff/tasks/${encodeURIComponent(taskId)}/complete`, {
      method: 'POST',
      body: { note: completionNote },
    })
    const saved = upsertComplaintInState(res?.task || res?.complaint)
    await refreshNotifications('staff')
    return saved
  }

  const startComplaintWork = startTaskWork
  const resolveComplaint = completeTaskWork

  const updateStaffProfile = async (updatedFields) => {
    const data = await apiRequest('/api/v1/staff/profile', {
      method: 'PATCH',
      body: {
        phone: updatedFields.phone,
        shift: updatedFields.shift,
      },
    })
    if (data?.user) {
      setUser(data.user)
      setStaff((prev) => prev.map((s) => (s.id === data.user.id ? { ...s, ...data.user } : s)))
      return data.user
    }
    return null
  }

  const markNotificationRead = async (id) => {
    setNotifications((prev) => prev.map((n) => (n.id === id ? { ...n, read: true } : n)))
    setStaffNotifications((prev) => prev.map((n) => (n.id === id ? { ...n, read: true } : n)))
    try {
      await apiRequest(`/api/v1/notifications/${encodeURIComponent(id)}/read`, {
        method: 'POST',
      })
    } catch {
      // Optimistically updated
    }
  }

  const markStaffNotificationRead = markNotificationRead

  const markAllNotificationsRead = async () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })))
    setStaffNotifications((prev) => prev.map((n) => ({ ...n, read: true })))
    try {
      await apiRequest('/api/v1/notifications/read-all', { method: 'POST' })
    } catch {
      // Optimistically updated
    }
  }

  // Staff Management Operations (`/api/v1/admin/staff*`)
  const addStaff = async (staffData) => {
    const data = await apiRequest('/api/v1/admin/staff', {
      method: 'POST',
      body: {
        fullName: staffData.name || staffData.fullName,
        email: staffData.email,
        phone: staffData.phone,
        staffCode: staffData.staffCode,
        trade: staffData.trade,
        shift: staffData.shift || 'General (09:00 AM - 05:30 PM)',
        status: staffData.status || 'Active',
      },
    })
    const createdStaff = data.staff
    setStaff((prev) => [createdStaff, ...prev.filter((s) => s.id !== createdStaff.id)])
    await refreshAdminIdentityData()
    return createdStaff
  }

  const updateStaff = async (staffData) => {
    const targetId = staffData.id || staffData.staffCode
    const data = await apiRequest(`/api/v1/admin/staff/${encodeURIComponent(targetId)}`, {
      method: 'PATCH',
      body: {
        fullName: staffData.name || staffData.fullName,
        email: staffData.email,
        phone: staffData.phone,
        trade: staffData.trade,
        shift: staffData.shift,
        status: staffData.status,
      },
    })
    const updated = data.staff
    setStaff((prev) =>
      prev.map((s) => (s.id === staffData.id || s.id === updated.id ? updated : s)),
    )
    await refreshAdminIdentityData()
    return updated
  }

  const deactivateStaff = async (staffId) => {
    const data = await apiRequest(`/api/v1/admin/staff/${encodeURIComponent(staffId)}/deactivate`, {
      method: 'POST',
    })
    const updated = data.staff
    setStaff((prev) => prev.map((s) => (s.id === staffId || s.id === updated.id ? updated : s)))
    await refreshAdminIdentityData()
    return updated
  }

  const toggleStaffStatus = async (staffId) => {
    const current = staff.find((s) => s.id === staffId || s.staffCode === staffId)
    const isCurrentlyActive =
      current &&
      (current.status === 'Active' ||
        current.status === 'On Duty' ||
        current.status === 'active' ||
        current.display_status === 'Active' ||
        current.rawStatus === 'active')
    if (isCurrentlyActive) {
      return deactivateStaff(staffId)
    }
    return updateStaff({ ...current, id: staffId, status: 'Active' })
  }

  const sendUserPasswordReset = async (userId) => {
    const data = await apiRequest(
      `/api/v1/admin/users/${encodeURIComponent(userId)}/send-password-reset`,
      { method: 'POST' },
    )
    await refreshAdminIdentityData()
    return data
  }

  // Admin Student Approval Operations (`/api/v1/admin/students/{id}/approve|reject|reactivate`)
  const approveStudent = async (studentId, note = '') => {
    const data = await apiRequest(
      `/api/v1/admin/students/${encodeURIComponent(studentId)}/approve`,
      {
        method: 'POST',
        body: { note },
      },
    )
    const updated = data.student
    setStudents((prev) =>
      prev.map((s) => (s.id === studentId || s.id === updated.id ? updated : s)),
    )
    await refreshAdminIdentityData()
    return updated
  }

  const rejectStudent = async (studentId, reason) => {
    const data = await apiRequest(
      `/api/v1/admin/students/${encodeURIComponent(studentId)}/reject`,
      {
        method: 'POST',
        body: { reason },
      },
    )
    const updated = data.student
    setStudents((prev) =>
      prev.map((s) => (s.id === studentId || s.id === updated.id ? updated : s)),
    )
    await refreshAdminIdentityData()
    return updated
  }

  const reactivateStudent = async (studentId, reason) => {
    const data = await apiRequest(
      `/api/v1/admin/students/${encodeURIComponent(studentId)}/reactivate`,
      {
        method: 'POST',
        body: { reason },
      },
    )
    const updated = data.student
    setStudents((prev) =>
      prev.map((s) => (s.id === studentId || s.id === updated.id ? updated : s)),
    )
    await refreshAdminIdentityData()
    return updated
  }

  const updateStudentStatus = async (studentId, status, reason = '') => {
    if (status === 'active') {
      return approveStudent(studentId, reason)
    }
    if (status === 'rejected') {
      return rejectStudent(studentId, reason)
    }
    if (status === 'pending') {
      return reactivateStudent(studentId, reason)
    }
    return null
  }

  // Fine & Disciplinary Operations (Phase 3E)
  const upsertFineInState = useCallback((normalizedFine) => {
    if (!normalizedFine) return null
    setFines((prev) => {
      const idx = prev.findIndex(
        (item) =>
          String(item.id) === String(normalizedFine.id) ||
          (item.referenceNo && item.referenceNo === normalizedFine.referenceNo),
      )
      if (idx === -1) {
        return [normalizedFine, ...prev]
      }
      const next = [...prev]
      next[idx] = { ...prev[idx], ...normalizedFine }
      return next
    })
    return normalizedFine
  }, [])

  const fetchAdminFines = useCallback(async (filters = {}) => {
    setFinesLoading(true)
    setFinesError('')
    try {
      const params = new URLSearchParams()
      if (filters.status && filters.status !== 'All') {
        params.set('status', String(filters.status).toLowerCase())
      }
      if (filters.student) {
        params.set('student', String(filters.student).trim())
      }
      if (filters.reference) {
        params.set('reference', String(filters.reference).trim())
      }
      if (filters.dateFrom) {
        params.set('date_from', filters.dateFrom)
      }
      if (filters.dateTo) {
        params.set('date_to', filters.dateTo)
      }
      if (filters.overdue === true || filters.overdue === 'true') {
        params.set('overdue', 'true')
      }
      if (filters.page) {
        params.set('page', String(filters.page))
      }
      if (filters.pageSize) {
        params.set('page_size', String(filters.pageSize))
      }
      const qs = params.toString()
      const data = await apiRequest(`/api/v1/admin/fines${qs ? `?${qs}` : ''}`)
      const normalized = Array.isArray(data.fines) ? data.fines.map(normalizeFineForUi) : []
      setFines(normalized)
      if (data.pagination) {
        setFinesPagination(data.pagination)
      }
      return { fines: normalized, pagination: data.pagination || null }
    } catch (err) {
      setFinesError(err.message || 'Unable to load fines.')
      throw err
    } finally {
      setFinesLoading(false)
    }
  }, [])

  const fetchStudentFines = useCallback(async () => {
    setFinesLoading(true)
    setFinesError('')
    try {
      const data = await apiRequest('/api/v1/student/fines')
      const normalized = Array.isArray(data.fines) ? data.fines.map(normalizeFineForUi) : []
      setFines(normalized)
      return normalized
    } catch (err) {
      setFinesError(err.message || 'Unable to load your fines.')
      throw err
    } finally {
      setFinesLoading(false)
    }
  }, [])

  const fetchFineDetail = useCallback(
    async (fineId, roleOverride) => {
      const targetRole = roleOverride || user?.role
      const endpoint =
        targetRole === 'admin'
          ? `/api/v1/admin/fines/${encodeURIComponent(fineId)}`
          : `/api/v1/student/fines/${encodeURIComponent(fineId)}`
      const data = await apiRequest(endpoint)
      const normalized = normalizeFineForUi(data.fine)
      return upsertFineInState(normalized)
    },
    [user?.role, upsertFineInState],
  )

  const issueFine = async (fineData) => {
    const payload = {
      student_id: fineData.studentId,
      category: fineData.category,
      description: fineData.description,
      amount_inr: fineData.amount,
      issue_date: fineData.issueDate,
      due_date: fineData.dueDate,
    }
    const data = await apiRequest('/api/v1/admin/fines', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
    const normalized = normalizeFineForUi(data.fine)
    return upsertFineInState(normalized)
  }

  const disputeFine = async (fineId, reason) => {
    const data = await apiRequest(`/api/v1/student/fines/${encodeURIComponent(fineId)}/dispute`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    })
    const normalized = normalizeFineForUi(data.fine)
    return upsertFineInState(normalized)
  }

  const fetchAdminDisputes = useCallback(async (filters = {}) => {
    const params = new URLSearchParams()
    if (filters.status && filters.status !== 'all') {
      params.set('status', String(filters.status).toLowerCase())
    }
    if (filters.student) {
      params.set('student', String(filters.student).trim())
    }
    if (filters.reference) {
      params.set('reference', String(filters.reference).trim())
    }
    if (filters.dateFrom) {
      params.set('date_from', filters.dateFrom)
    }
    if (filters.dateTo) {
      params.set('date_to', filters.dateTo)
    }
    if (filters.page) {
      params.set('page', String(filters.page))
    }
    if (filters.pageSize) {
      params.set('page_size', String(filters.pageSize))
    }
    const qs = params.toString()
    return apiRequest(`/api/v1/admin/fines/disputes${qs ? `?${qs}` : ''}`)
  }, [])

  const reviewDispute = async (fineId, { decision, reason }) => {
    const data = await apiRequest(
      `/api/v1/admin/fines/${encodeURIComponent(fineId)}/dispute/review`,
      {
        method: 'POST',
        body: JSON.stringify({ decision, reason }),
      },
    )
    const normalized = normalizeFineForUi(data.fine)
    return upsertFineInState(normalized)
  }

  const waiveFine = async (fineId, reason) => {
    const data = await apiRequest(`/api/v1/admin/fines/${encodeURIComponent(fineId)}/waive`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    })
    const normalized = normalizeFineForUi(data.fine)
    return upsertFineInState(normalized)
  }

  const cancelFine = async (fineId, reason) => {
    const data = await apiRequest(`/api/v1/admin/fines/${encodeURIComponent(fineId)}/cancel`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    })
    const normalized = normalizeFineForUi(data.fine)
    return upsertFineInState(normalized)
  }

  const recordFinePayment = async (fineId, { amountInr, paymentMethod, manualReference }) => {
    const data = await apiRequest(`/api/v1/admin/fines/${encodeURIComponent(fineId)}/payments`, {
      method: 'POST',
      body: JSON.stringify({
        amount_inr: amountInr,
        payment_method: paymentMethod,
        manual_reference: manualReference,
      }),
    })
    const normalized = normalizeFineForUi(data.fine)
    upsertFineInState(normalized)
    return {
      fine: normalized,
      payment: data.payment || null,
      receipt: data.receipt || null,
    }
  }

  const fetchFinePayments = useCallback(
    async (fineId, roleOverride) => {
      const targetRole = roleOverride || user?.role
      const endpoint =
        targetRole === 'admin'
          ? `/api/v1/admin/fines/${encodeURIComponent(fineId)}/payments`
          : `/api/v1/student/fines/${encodeURIComponent(fineId)}/payments`
      return apiRequest(endpoint)
    },
    [user?.role],
  )

  const createRazorpayOrder = useCallback(async (fineId) => {
    const data = await apiRequest(
      `/api/v1/student/fines/${encodeURIComponent(fineId)}/payments/razorpay/order`,
      {
        method: 'POST',
        body: JSON.stringify({}),
      },
    )
    return data.order || null
  }, [])

  const verifyRazorpayPayment = useCallback(
    async (fineId, { razorpay_order_id, razorpay_payment_id, razorpay_signature }) => {
      const data = await apiRequest(
        `/api/v1/student/fines/${encodeURIComponent(fineId)}/payments/razorpay/verify`,
        {
          method: 'POST',
          body: JSON.stringify({
            razorpay_order_id,
            razorpay_payment_id,
            razorpay_signature,
          }),
        },
      )
      const normalized = normalizeFineForUi(data.fine)
      upsertFineInState(normalized)
      return {
        fine: normalized,
        payment: data.payment || null,
        receipt: data.receipt || null,
        alreadySettled: Boolean(data.alreadySettled),
      }
    },
    [upsertFineInState],
  )

  const recordRazorpayAttemptFailure = useCallback(async (fineId, payload) => {
    return apiRequest(
      `/api/v1/student/fines/${encodeURIComponent(fineId)}/payments/razorpay/fail`,
      {
        method: 'POST',
        body: JSON.stringify(payload || {}),
      },
    )
  }, [])

  const fetchReceipt = useCallback(
    async (receiptNumber, roleOverride) => {
      const targetRole = roleOverride || user?.role
      const endpoint =
        targetRole === 'admin'
          ? `/api/v1/admin/receipts/${encodeURIComponent(receiptNumber)}`
          : `/api/v1/student/receipts/${encodeURIComponent(receiptNumber)}`
      const data = await apiRequest(endpoint)
      return data.receipt || null
    },
    [user?.role],
  )

  const downloadReceiptPdf = useCallback(
    async (receiptNumber, roleOverride) => {
      const targetRole = roleOverride || user?.role
      const endpoint =
        targetRole === 'admin'
          ? `/api/v1/admin/receipts/${encodeURIComponent(receiptNumber)}/pdf`
          : `/api/v1/student/receipts/${encodeURIComponent(receiptNumber)}/pdf`
      const { blob, filename } = await apiDownloadBlob(endpoint)
      const resolvedFilename = filename || `HostelCare-${receiptNumber}.pdf`
      const objectUrl = URL.createObjectURL(blob)
      try {
        const anchor = document.createElement('a')
        anchor.href = objectUrl
        anchor.download = resolvedFilename
        anchor.style.display = 'none'
        document.body.appendChild(anchor)
        anchor.click()
        document.body.removeChild(anchor)
      } finally {
        URL.revokeObjectURL(objectUrl)
      }
      return resolvedFilename
    },
    [user?.role],
  )

  return (
    <AppContext.Provider
      value={{
        hostelInfo: mockHostelInfo,
        user,
        setUser,
        authLoading,
        sessionExpired,
        setSessionExpired,
        revalidateSession,
        login,
        logout,
        requestPasswordReset,
        confirmPasswordReset,
        students,
        studentsLoading,
        studentsError,
        fetchStudents,
        registerStudent,
        approveStudent,
        rejectStudent,
        reactivateStudent,
        updateStudentStatus,
        refreshAdminIdentityData,
        refreshRoleData,
        complaints,
        complaintsLoading,
        blocks,
        blocksLoading,
        blocksError,
        fetchBlocks,
        addBlock,
        updateBlock,
        addRoom,
        updateRoom,
        allocations,
        allocationsLoading,
        allocationsError,
        fetchAllocations,
        allocateRoom,
        endAllocation,
        transferAllocation,
        fetchComplaintDetail,
        addComplaint,
        updateComplaint,
        reviewComplaint,
        assignStaffToComplaint,
        reassignStaffToComplaint,
        startComplaintWork,
        resolveComplaint,
        closeComplaint,
        rejectComplaint,
        reopenComplaint,
        addInternalNote,
        acceptTask,
        startTaskWork,
        updateTaskProgress,
        completeTaskWork,
        returnTaskForRework,
        rooms,
        setRooms,
        roomsLoading,
        roomsError,
        fetchRooms,
        staff,
        setStaff,
        staffLoading,
        staffError,
        fetchStaff,
        addStaff,
        updateStaff,
        deactivateStaff,
        toggleStaffStatus,
        sendUserPasswordReset,
        updateStaffProfile,
        auditLogs,
        auditLogsLoading,
        auditLogsError,
        fetchAuditLogs,
        adminOverview,
        adminOverviewLoading,
        adminOverviewError,
        fetchAdminOverview,
        complaintAnalytics,
        complaintAnalyticsLoading,
        complaintAnalyticsError,
        fetchComplaintAnalytics,
        notifications,
        markNotificationRead,
        markAllNotificationsRead,
        staffNotifications,
        markStaffNotificationRead,
        fines,
        finesLoading,
        finesError,
        finesPagination,
        fetchAdminFines,
        fetchStudentFines,
        fetchFineDetail,
        issueFine,
        disputeFine,
        fetchAdminDisputes,
        reviewDispute,
        waiveFine,
        cancelFine,
        recordFinePayment,
        createRazorpayOrder,
        verifyRazorpayPayment,
        recordRazorpayAttemptFailure,
        fetchFinePayments,
        fetchReceipt,
        downloadReceiptPdf,
      }}
    >
      {children}
    </AppContext.Provider>
  )
}

export function useApp() {
  const context = useContext(AppContext)
  if (!context) {
    throw new Error('useApp must be used within an AppProvider')
  }
  return context
}
