import { StrictMode } from 'react'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import App from './App.jsx'
import {
  initialAuditLogs,
  initialComplaints,
  initialNotifications,
  initialStaff,
  initialStaffNotifications,
  initialStudents,
} from './lib/mockData.js'

const defaultStudentUser = {
  id: 'stu-1',
  role: 'student',
  status: 'active',
  hasActiveRoom: true,
  ...initialStudents[0],
}

const defaultAdminUser = {
  id: 'adm-1',
  role: 'admin',
  status: 'active',
  fullName: 'Dr. K. S. Verma',
  email: 'warden@hostelcare.in',
  designation: 'Chief Hostel Warden',
}

const defaultStaffUser = {
  id: 'stf-1',
  role: 'staff',
  status: 'active',
  ...initialStaff[0],
}

let mockSessionUser = defaultStudentUser
let mockMeErrorCode = null
let mockLoginError = null
let mockComplaintsState = []
let mockNotificationsState = []
let mockStaffState = []
let mockStaffError = null
let mockRoomsState = []
let mockRoomsError = null
let mockBlocksState = []
let mockAllocationsState = []
let mockComplaintDetailError = null
let mockFinesState = []
let mockFinesError = null
let mockFinePaymentsState = {}
let mockReceiptsState = {}
let mockReceiptPdfError = null
let mockStudentsState = []

function jsonResponse(body, status = 200, headers = { 'X-CSRF-Token': 'test-csrf-token' }) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    headers: {
      get: (key) => {
        const lower = key.toLowerCase()
        if (lower === 'content-type') return 'application/json'
        if (lower === 'x-csrf-token') return headers['X-CSRF-Token'] || 'test-csrf-token'
        return null
      },
    },
    json: () => Promise.resolve(body),
  })
}

beforeEach(() => {
  mockSessionUser = defaultStudentUser
  mockMeErrorCode = null
  mockLoginError = null
  mockComplaintsState = JSON.parse(JSON.stringify(initialComplaints))
  mockNotificationsState = JSON.parse(
    JSON.stringify([...initialNotifications, ...initialStaffNotifications]),
  )
  mockStaffState = JSON.parse(JSON.stringify(initialStaff))
  mockStaffError = null
  mockRoomsState = []
  mockRoomsError = null
  mockBlocksState = []
  mockAllocationsState = []
  mockComplaintDetailError = null
  mockFinesState = []
  mockFinesError = null
  mockFinePaymentsState = {}
  mockReceiptsState = {}
  mockReceiptPdfError = null
  mockStudentsState = [
    {
      id: defaultStudentUser.id,
      fullName: defaultStudentUser.fullName,
      rollNumber: defaultStudentUser.rollNumber,
      room: defaultStudentUser.room,
      block: defaultStudentUser.block,
    },
  ]

  vi.spyOn(globalThis, 'fetch').mockImplementation((url, options = {}) => {
    const path = typeof url === 'string' ? url : url.toString()
    const method = (options.method || 'GET').toUpperCase()
    const body = options.body ? JSON.parse(options.body) : {}

    if (path === '/api/v1/auth/me' && method === 'GET') {
      if (mockMeErrorCode) {
        return jsonResponse(
          { error: { code: mockMeErrorCode, message: 'Session expired or unauthenticated.' } },
          401,
        )
      }
      if (!mockSessionUser) {
        return jsonResponse(
          { error: { code: 'unauthenticated', message: 'Authentication is required.' } },
          401,
        )
      }
      return jsonResponse({ user: mockSessionUser, csrf_token: 'test-csrf-token' }, 200)
    }

    if (path === '/api/v1/auth/login' && method === 'POST') {
      if (mockLoginError) {
        return jsonResponse(
          { error: { code: mockLoginError.code, message: mockLoginError.message } },
          mockLoginError.status || 403,
        )
      }
      const id = (body.identifier || body.email || '').toLowerCase()
      let userRole = 'student'
      if (id.includes('warden') || id.includes('admin')) {
        userRole = 'admin'
      } else if (id.includes('ramesh') || id.includes('staff') || id.includes('stf')) {
        userRole = 'staff'
      }

      if (body.role && body.role !== userRole) {
        return jsonResponse(
          {
            error: {
              code: 'role_mismatch',
              message:
                "The selected role does not match this account's credentials. Please select the correct portal.",
            },
          },
          403,
        )
      }

      if (userRole === 'admin') {
        mockSessionUser = defaultAdminUser
      } else if (userRole === 'staff') {
        mockSessionUser = defaultStaffUser
      } else {
        mockSessionUser = defaultStudentUser
      }
      return jsonResponse({ user: mockSessionUser, csrf_token: 'test-csrf-token' }, 200)
    }

    if (path === '/api/v1/auth/logout' && method === 'POST') {
      mockSessionUser = null
      return jsonResponse({ message: 'Signed out successfully.' }, 200)
    }

    if (path === '/api/v1/auth/register' && method === 'POST') {
      return jsonResponse(
        {
          message: 'Registration submitted. Your account is pending warden approval.',
          user: {
            id: 'stu-new-1',
            role: 'student',
            status: 'pending',
            fullName: body.fullName,
            email: body.email,
            rollNumber: body.rollNumber,
            phone: body.phone,
            room: 'Unallocated',
          },
        },
        201,
      )
    }

    if (path === '/api/v1/auth/forgot-password' && method === 'POST') {
      return jsonResponse(
        {
          message:
            'If an account exists with this email address, password reset instructions have been sent.',
        },
        200,
      )
    }

    if (path === '/api/v1/auth/reset-password' && method === 'POST') {
      if (body.token === 'server-expired-token') {
        return jsonResponse(
          {
            error: {
              code: 'invalid_or_expired_token',
              message: 'This password reset link is invalid, expired, or has already been used.',
            },
          },
          400,
        )
      }
      return jsonResponse({ message: 'Password has been updated successfully.' }, 200)
    }

    if (path.startsWith('/api/v1/admin/analytics/overview') && method === 'GET') {
      return jsonResponse(
        {
          dateRange: {
            preset: '30d',
            dateFrom: '2026-10-20',
            dateTo: '2026-11-18',
            timezone: 'Asia/Kolkata',
          },
          complaints: {
            total: mockComplaintsState.length,
            newSubmissions: mockComplaintsState.filter(
              (c) => c.status === 'Submitted' || c.status === 'open',
            ).length,
            underReview: 0,
            assigned: 0,
            accepted: 0,
            inProgress: mockComplaintsState.filter(
              (c) => c.status === 'In Progress' || c.status === 'in_progress',
            ).length,
            completed: 0,
            closed: 0,
            rejected: 0,
            unassigned: mockComplaintsState.filter(
              (c) => !c.assignedStaff || c.assignedStaff === 'Unassigned',
            ).length,
            resolved: mockComplaintsState.filter(
              (c) => c.status === 'Resolved' || c.status === 'Closed',
            ).length,
            byStatus: {
              submitted: 0,
              under_review: 0,
              assigned: 0,
              accepted: 0,
              in_progress: 0,
              completed: 0,
              closed: 0,
              rejected: 0,
            },
          },
          approvals: {
            pendingCount: initialStudents.filter((s) => s.status === 'pending').length,
            approvedCount: initialStudents.filter((s) => s.status === 'active').length,
            rejectedCount: 0,
            totalStudents: initialStudents.length,
          },
          occupancy: {
            referenceDate: '2026-11-18',
            totalCapacity: 40,
            occupiedBeds: 28,
            vacantBeds: 12,
            occupancyRate: 70.0,
            activeRoomsCount: 20,
            blocks: [
              {
                blockId: 1,
                code: 'A',
                name: 'Block A',
                activeRoomsCount: 20,
                totalCapacity: 40,
                occupiedBeds: 28,
                vacantBeds: 12,
                occupancyRate: 70.0,
              },
            ],
          },
          residents: {
            activeCount: 28,
          },
          finances: {
            leviedAmount: 1500,
            leviedAmountInr: '1500.00',
            leviedCount: 2,
            collectedAmount: 1000,
            collectedAmountInr: '1000.00',
            collectedCount: 1,
            outstandingAmount: 500,
            outstandingAmountInr: '500.00',
            outstandingCount: 1,
            waivedAmount: 0,
            waivedAmountInr: '0.00',
            waivedCount: 0,
            cancelledAmount: 0,
            cancelledAmountInr: '0.00',
            cancelledCount: 0,
            pendingDisputesCount: 0,
          },
          recentActivity: mockComplaintsState.slice(0, 5),
        },
        200,
      )
    }

    if (path.startsWith('/api/v1/admin/analytics/complaints') && method === 'GET') {
      return jsonResponse(
        {
          dateRange: {
            preset: '30d',
            dateFrom: '2026-10-20',
            dateTo: '2026-11-18',
            timezone: 'Asia/Kolkata',
          },
          categories: [{ category: 'Electrical', count: 2, percentage: 100.0 }],
          trends: {
            interval: 'daily',
            series: [{ period: '2026-11-18', label: '18 Nov', submitted: 2, completed: 1 }],
          },
          resolution: {
            completedCount: 1,
            averageSeconds: 14400,
            averageHours: 4.0,
            medianSeconds: 14400,
            medianHours: 4.0,
          },
          sla: {
            eligibleCount: 2,
            activeOverdue: 0,
            activeWithinSla: 1,
            completedWithinSla: 1,
            completedAfterSla: 0,
            complianceRate: 100.0,
            byPriority: [
              {
                priority: 'high',
                label: 'High',
                targetHours: 24,
                total: 1,
                activeOverdue: 0,
                activeWithinSla: 0,
                completedWithinSla: 1,
                completedAfterSla: 0,
                complianceRate: 100.0,
              },
              {
                priority: 'medium',
                label: 'Medium',
                targetHours: 72,
                total: 1,
                activeOverdue: 0,
                activeWithinSla: 1,
                completedWithinSla: 0,
                completedAfterSla: 0,
                complianceRate: null,
              },
              {
                priority: 'low',
                label: 'Low',
                targetHours: 168,
                total: 0,
                activeOverdue: 0,
                activeWithinSla: 0,
                completedWithinSla: 0,
                completedAfterSla: 0,
                complianceRate: null,
              },
            ],
          },
          staff: [],
        },
        200,
      )
    }

    if (path.startsWith('/api/v1/admin/students') && method === 'GET') {
      return jsonResponse({ students: initialStudents }, 200)
    }

    if (path.startsWith('/api/v1/admin/staff') && method === 'GET') {
      if (mockStaffError) {
        return jsonResponse(
          { error: { code: mockStaffError.code, message: mockStaffError.message } },
          mockStaffError.status || 500,
        )
      }
      return jsonResponse({ staff: mockStaffState }, 200)
    }

    if (path === '/api/v1/admin/staff' && method === 'POST') {
      if (!mockSessionUser || mockSessionUser.role !== 'admin') {
        return jsonResponse(
          {
            error: {
              code: 'forbidden',
              message: 'You do not have permission to perform this action.',
            },
          },
          403,
        )
      }
      if (mockStaffError) {
        return jsonResponse(
          { error: { code: mockStaffError.code, message: mockStaffError.message } },
          mockStaffError.status || 403,
        )
      }
      const createdStaff = {
        id: 'stf-created-1',
        name: body.fullName,
        fullName: body.fullName,
        email: body.email,
        phone: body.phone,
        staffCode: body.staffCode || 'STF-0001',
        trade: body.trade,
        shift: body.shift || 'General (09:00 AM - 05:30 PM)',
        status: 'active',
        display_status: 'Active',
        activeTickets: 0,
      }
      mockStaffState = [createdStaff, ...mockStaffState]
      return jsonResponse({ staff: createdStaff }, 201)
    }

    if (path.startsWith('/api/v1/admin/staff/') && method === 'PATCH') {
      const staffId = decodeURIComponent(path.split('/').pop())
      const normEmail = (body.email || '').trim().toLowerCase()
      if (
        normEmail &&
        mockStaffState.some(
          (s) =>
            s.email?.toLowerCase() === normEmail && s.id !== staffId && s.staffCode !== staffId,
        )
      ) {
        return jsonResponse(
          { error: { code: 'conflict', message: 'Email address is already in use.' } },
          409,
        )
      }
      const idx = mockStaffState.findIndex((s) => s.id === staffId || s.staffCode === staffId)
      if (idx !== -1) {
        mockStaffState[idx] = {
          ...mockStaffState[idx],
          name: body.fullName || mockStaffState[idx].name,
          fullName: body.fullName || mockStaffState[idx].fullName,
          email: normEmail || mockStaffState[idx].email,
          phone: body.phone || mockStaffState[idx].phone,
          trade: body.trade || mockStaffState[idx].trade,
          shift: body.shift || mockStaffState[idx].shift,
          status: body.status || mockStaffState[idx].status,
        }
        return jsonResponse({ staff: mockStaffState[idx] }, 200)
      }
      return jsonResponse({ error: { code: 'not_found', message: 'Staff member not found.' } }, 404)
    }

    if (path.includes('/send-password-reset') && method === 'POST') {
      return jsonResponse(
        { message: 'A 30-minute password setup/reset link has been emailed to the user.' },
        200,
      )
    }

    if (path.startsWith('/api/v1/admin/rooms') && method === 'GET') {
      if (mockRoomsError) {
        return jsonResponse(
          { error: { code: mockRoomsError.code, message: mockRoomsError.message } },
          mockRoomsError.status || 500,
        )
      }
      return jsonResponse({ rooms: mockRoomsState }, 200)
    }

    if (path.startsWith('/api/v1/admin/blocks') && method === 'GET') {
      return jsonResponse({ blocks: mockBlocksState }, 200)
    }

    if (path === '/api/v1/admin/blocks' && method === 'POST') {
      const name = (body.name || body.block_name || body.blockName || '').trim()
      if (!name) {
        return jsonResponse(
          { error: { code: 'validation_error', message: 'Block name is required.' } },
          400,
        )
      }
      const rawCode = (body.code || body.block_code || body.blockCode || 'BLKA')
        .trim()
        .toUpperCase()
      const createdBlock = {
        id: `blk-${Date.now()}`,
        code: rawCode,
        name: name,
        display_order: body.display_order ?? 0,
        is_active: body.is_active ?? true,
        total_rooms: 0,
        total_capacity: 0,
        occupied_beds: 0,
        vacant_beds: 0,
      }
      mockBlocksState = [...mockBlocksState, createdBlock]
      return jsonResponse({ block: createdBlock }, 201)
    }

    if (path.startsWith('/api/v1/admin/blocks/') && method === 'PATCH') {
      const blockId = path.split('/').pop()
      const idx = mockBlocksState.findIndex(
        (b) => String(b.id) === String(blockId) || b.code === blockId,
      )
      if (idx !== -1) {
        mockBlocksState[idx] = { ...mockBlocksState[idx], ...body }
        return jsonResponse({ block: mockBlocksState[idx] }, 200)
      }
      return jsonResponse({ error: { code: 'not_found', message: 'Block not found' } }, 404)
    }

    if (path.startsWith('/api/v1/admin/room-allocations') && method === 'GET') {
      return jsonResponse({ allocations: mockAllocationsState }, 200)
    }

    if (path.startsWith('/api/v1/admin/audit-logs') && method === 'GET') {
      return jsonResponse({ audit_logs: initialAuditLogs }, 200)
    }

    if (path === '/api/v1/staff/profile' && method === 'PATCH') {
      mockSessionUser = { ...defaultStaffUser, ...body }
      return jsonResponse({ user: mockSessionUser }, 200)
    }

    if (path === '/api/v1/blocks' && method === 'GET') {
      return jsonResponse(
        {
          blocks: [
            { id: 'BLKA', code: 'BLKA', name: 'Block A (Aryabhatta Wing)' },
            { id: 'BLKB', code: 'BLKB', name: 'Block B (Bhaskara Wing)' },
          ],
        },
        200,
      )
    }

    if (path === '/api/v1/notifications' && method === 'GET') {
      return jsonResponse({ notifications: mockNotificationsState }, 200)
    }

    if (path === '/api/v1/notifications/read-all' && method === 'POST') {
      mockNotificationsState = mockNotificationsState.map((n) => ({ ...n, read: true }))
      return jsonResponse({ updated_count: mockNotificationsState.length }, 200)
    }

    if (path.startsWith('/api/v1/notifications/') && path.endsWith('/read') && method === 'POST') {
      const id = path.split('/')[4]
      mockNotificationsState = mockNotificationsState.map((n) =>
        n.id === id ? { ...n, read: true } : n,
      )
      return jsonResponse({ notification: { id, read: true } }, 200)
    }

    if (path === '/api/v1/student/complaints' && method === 'GET') {
      const items = mockComplaintsState
        .filter((c) => {
          const cid = c.studentId || c.student_user_id
          if (cid && mockSessionUser?.id) {
            return String(cid) === String(mockSessionUser.id)
          }
          const cRoll = c.studentRoll || c.reporterRoll
          return Boolean(
            cRoll &&
            mockSessionUser?.rollNumber &&
            String(cRoll).toUpperCase() === String(mockSessionUser.rollNumber).toUpperCase(),
          )
        })
        .map((c) => {
          const copy = { ...c }
          delete copy.internalNotes
          delete copy.internal_notes
          delete copy.assignmentNotes
          delete copy.instructions
          return copy
        })
      return jsonResponse({ complaints: items }, 200)
    }

    if (path === '/api/v1/student/complaints' && method === 'POST') {
      const created = {
        id: 'CMP-2026-00099',
        referenceNo: 'CMP-2026-00099',
        studentId: mockSessionUser?.id,
        title: body.title,
        category: body.category || 'General Maintenance',
        description: body.description,
        priority: body.priority || 'Medium',
        locationType: body.locationType || 'room',
        locationDetail: body.locationDetail || null,
        room: body.locationType === 'common_area' ? 'Common Area' : 'A-204',
        block: 'Block A (Aryabhatta Wing)',
        reporterName: mockSessionUser?.fullName || 'Aarav Sharma',
        reporterRoll: mockSessionUser?.rollNumber || '2026CSB1042',
        status: 'Submitted',
        dateSubmitted: '2026-11-14',
        lastUpdated: '2026-11-14',
        assignedStaff: 'Unassigned',
        assignedStaffRole: '',
        updates: [],
        history: [
          {
            timestamp: '2026-11-14 10:00',
            actor: `${mockSessionUser?.fullName || 'Aarav Sharma'} (Student)`,
            action: 'Complaint Submitted',
            note: 'Submitted maintenance request.',
          },
        ],
      }
      mockComplaintsState = [created, ...mockComplaintsState]
      return jsonResponse({ complaint: created }, 201)
    }

    if (path.startsWith('/api/v1/student/complaints/') && method === 'GET') {
      if (mockComplaintDetailError) {
        if (mockComplaintDetailError.networkError) {
          return Promise.reject(new TypeError('Failed to fetch'))
        }
        return jsonResponse(
          {
            error: {
              code: mockComplaintDetailError.code || 'internal_error',
              message: mockComplaintDetailError.message || 'Server error',
            },
          },
          mockComplaintDetailError.status || 500,
        )
      }
      const cid = decodeURIComponent(path.split('/').pop())
      const found = mockComplaintsState.find((c) => c.id === cid)
      if (!found) {
        return jsonResponse({ error: { code: 'complaint_not_found', message: 'Not found' } }, 404)
      }
      const ownerId = found.studentId || found.student_user_id
      const ownerRoll = found.studentRoll || found.reporterRoll
      const isOwned = ownerId
        ? String(ownerId) === String(mockSessionUser?.id || '')
        : Boolean(
            ownerRoll &&
            mockSessionUser?.rollNumber &&
            String(ownerRoll).toUpperCase() === String(mockSessionUser.rollNumber).toUpperCase(),
          )
      if (!isOwned) {
        return jsonResponse(
          {
            error: {
              code: 'forbidden',
              message: "You do not have permission to access another student's complaint.",
            },
          },
          403,
        )
      }
      const copy = { ...found }
      delete copy.internalNotes
      delete copy.internal_notes
      delete copy.assignmentNotes
      delete copy.instructions
      return jsonResponse({ complaint: copy }, 200)
    }

    if (path.startsWith('/api/v1/admin/complaints') && method === 'GET') {
      const cleanPath = path.split('?')[0]
      if (cleanPath === '/api/v1/admin/complaints') {
        return jsonResponse({ complaints: mockComplaintsState }, 200)
      }
      const cid = decodeURIComponent(cleanPath.split('/').pop())
      const found = mockComplaintsState.find((c) => c.id === cid)
      if (!found) {
        return jsonResponse({ error: { code: 'not_found', message: 'Not found' } }, 404)
      }
      return jsonResponse({ complaint: found }, 200)
    }

    if (path.startsWith('/api/v1/admin/complaints/') && method !== 'GET') {
      const parts = path.split('/')
      const cid = decodeURIComponent(parts[5])
      const action = parts[6] || 'patch'
      const idx = mockComplaintsState.findIndex((c) => c.id === cid)
      if (idx === -1) {
        return jsonResponse({ error: { code: 'not_found', message: 'Not found' } }, 404)
      }
      const current = { ...mockComplaintsState[idx] }
      if (method === 'PATCH') {
        if (body.status === 'under_review' || body.status === 'Under Review') {
          current.status = 'Under Review'
        }
        if (body.priority) current.priority = body.priority
        if (body.category) current.category = body.category
      } else if (action === 'assign' || action === 'reassign') {
        const staffMember =
          initialStaff.find((s) => s.id === body.staffId || s.name === body.staffName) ||
          initialStaff[0]
        current.status = 'Assigned'
        current.assignedStaff = staffMember.name
        current.assignedStaffId = staffMember.id
        current.assignedStaffRole = staffMember.trade
        current.assignmentNotes = body.note || ''
      } else if (action === 'internal-notes') {
        current.internalNotes = [
          ...(current.internalNotes || []),
          {
            id: `NOTE-${Date.now()}`,
            by: 'Dr. K. S. Verma (Chief Warden)',
            time: '2026-11-14 11:00',
            note: body.body || body.note,
          },
        ]
      } else if (action === 'close') {
        current.status = 'Closed'
      } else if (action === 'return-for-rework') {
        current.status = 'In Progress'
        current.reworkNote = body.reason
      } else if (action === 'reject') {
        current.status = 'Rejected'
        current.rejectionReason = body.reason
      } else if (action === 'reopen') {
        current.status = 'Under Review'
      }
      mockComplaintsState[idx] = current
      return jsonResponse({ complaint: current }, 200)
    }

    if (path === '/api/v1/staff/tasks' && method === 'GET') {
      const items = mockComplaintsState
        .filter((c) => c.assignedStaff && c.assignedStaff.includes('Ramesh'))
        .map((c) => {
          const copy = { ...c }
          delete copy.internalNotes
          return copy
        })
      return jsonResponse({ tasks: items }, 200)
    }

    if (path.startsWith('/api/v1/staff/tasks/') && method === 'GET') {
      const cid = decodeURIComponent(path.split('/').pop())
      const found = mockComplaintsState.find((c) => c.id === cid)
      if (!found) {
        return jsonResponse({ error: { code: 'not_found', message: 'Not found' } }, 404)
      }
      const copy = { ...found }
      delete copy.internalNotes
      return jsonResponse({ task: copy }, 200)
    }

    if (path.startsWith('/api/v1/staff/tasks/') && method === 'POST') {
      const parts = path.split('/')
      const cid = decodeURIComponent(parts[5])
      const action = parts[6]
      const idx = mockComplaintsState.findIndex((c) => c.id === cid)
      const current = { ...mockComplaintsState[idx] }
      if (action === 'accept') {
        current.status = 'Accepted'
      } else if (action === 'start') {
        current.status = 'In Progress'
      } else if (action === 'updates') {
        current.updates = [
          ...(current.updates || []),
          {
            id: `UPD-${Date.now()}`,
            updateType: 'progress',
            body: body.note,
            author: 'Ramesh Babu',
            timestamp: '2026-11-14 12:00',
          },
        ]
      } else if (action === 'complete') {
        current.status = 'Completed'
        current.completionNote = body.completionNote
      }
      const copy = { ...current }
      delete copy.internalNotes
      mockComplaintsState[idx] = current
      return jsonResponse({ task: copy }, 200)
    }

    if (path.startsWith('/api/v1/admin/students') && method === 'GET') {
      return jsonResponse({ students: mockStudentsState }, 200)
    }

    if (path.startsWith('/api/v1/admin/fines/disputes') && method === 'GET') {
      if (mockFinesError) {
        return jsonResponse(
          {
            error: { code: mockFinesError.code || 'server_error', message: mockFinesError.message },
          },
          mockFinesError.status || 500,
        )
      }
      const query = path.includes('?')
        ? new URLSearchParams(path.split('?')[1])
        : new URLSearchParams()
      const statusFilter = query.get('status')
      const disputes = mockFinesState
        .filter((f) => f.dispute)
        .map((f) => ({
          id: f.dispute.id || `DSP-${f.id}`,
          fineId: f.id,
          fineReference: f.referenceNo || f.id,
          fineStatus: f.status,
          amountInr: f.amountInr || String(f.amount || 0),
          category: f.category,
          description: f.description,
          issueDate: f.issueDate,
          dueDate: f.dueDate,
          studentName: f.studentName,
          studentRoll: f.studentRoll,
          room: f.room,
          status: f.dispute.status,
          reason: f.dispute.reason,
          decisionReason: f.dispute.decisionReason || null,
          createdAt: f.dispute.createdAt,
          decidedAt: f.dispute.decidedAt || null,
        }))
        .filter((d) => !statusFilter || d.status === statusFilter)
      return jsonResponse(
        {
          disputes,
          pagination: { page: 1, pageSize: 20, total: disputes.length, totalPages: 1 },
        },
        200,
      )
    }

    if (path.startsWith('/api/v1/admin/fines') && method === 'GET') {
      if (mockFinesError) {
        return jsonResponse(
          {
            error: { code: mockFinesError.code || 'server_error', message: mockFinesError.message },
          },
          mockFinesError.status || 500,
        )
      }
      const cleanPath = path.split('?')[0]
      if (cleanPath === '/api/v1/admin/fines') {
        const query = path.includes('?')
          ? new URLSearchParams(path.split('?')[1])
          : new URLSearchParams()
        const statusFilter = query.get('status')
        const items = statusFilter
          ? mockFinesState.filter(
              (f) => String(f.status).toLowerCase() === statusFilter.toLowerCase(),
            )
          : mockFinesState
        return jsonResponse(
          {
            fines: items,
            pagination: { page: 1, pageSize: 20, total: items.length, totalPages: 1 },
          },
          200,
        )
      }
      const parts = cleanPath.split('/')
      if (parts[parts.length - 1] === 'payments') {
        const fineId = decodeURIComponent(parts[parts.length - 2])
        const found = mockFinesState.find(
          (f) => String(f.id) === fineId || f.referenceNo === fineId,
        )
        const payments = mockFinePaymentsState[fineId] || []
        return jsonResponse(
          {
            payments,
            outstandingInr: found?.status === 'paid' ? '0.00' : found?.amountInr || '500.00',
            attempts: [],
          },
          200,
        )
      }
      const fineId = decodeURIComponent(parts.pop())
      const found = mockFinesState.find((f) => String(f.id) === fineId || f.referenceNo === fineId)
      if (!found) {
        return jsonResponse({ error: { code: 'not_found', message: 'Fine not found.' } }, 404)
      }
      return jsonResponse({ fine: found }, 200)
    }

    if (path === '/api/v1/admin/fines' && method === 'POST') {
      const student = mockStudentsState.find((s) => String(s.id) === String(body.student_id)) || {
        id: body.student_id,
        fullName: 'Aarav Sharma',
        rollNumber: '2026CSB1042',
        room: 'A-204',
        block: 'Block A',
      }
      const newFine = {
        id: `fine-${mockFinesState.length + 1}`,
        referenceNo: `FIN-2026-0000${mockFinesState.length + 1}`,
        studentId: student.id,
        studentName: student.fullName,
        studentRoll: student.rollNumber,
        room: student.room,
        block: student.block,
        category: body.category,
        description: body.description,
        amountInr: Number(body.amount_inr).toFixed(2),
        amount: Number(body.amount_inr),
        issueDate: body.issue_date,
        dueDate: body.due_date,
        issuedBy: mockSessionUser?.fullName || 'Chief Warden',
        status: 'pending',
        dispute: null,
        history: [
          {
            action: 'FINE_ISSUED',
            actor: mockSessionUser?.fullName || 'Chief Warden',
            timestamp: '2026-11-15 10:00',
            note: body.description,
          },
        ],
      }
      mockFinesState = [newFine, ...mockFinesState]
      return jsonResponse({ fine: newFine }, 201)
    }

    if (path.startsWith('/api/v1/admin/fines/') && method === 'POST') {
      const parts = path.split('/')
      const action = parts[parts.length - 1]
      const isDisputeReview = parts[parts.length - 2] === 'dispute' && action === 'review'
      const fineId = decodeURIComponent(
        isDisputeReview ? parts[parts.length - 3] : parts[parts.length - 2],
      )
      const idx = mockFinesState.findIndex(
        (f) => String(f.id) === fineId || f.referenceNo === fineId,
      )
      if (idx === -1) {
        return jsonResponse({ error: { code: 'not_found', message: 'Fine not found.' } }, 404)
      }
      const current = { ...mockFinesState[idx] }
      if (action === 'waive') {
        current.status = 'waived'
        current.history = [
          {
            action: 'FINE_WAIVED',
            actor: 'Chief Warden',
            timestamp: '2026-11-15 11:00',
            note: body.reason,
          },
          ...(current.history || []),
        ]
        mockFinesState[idx] = current
        return jsonResponse({ fine: current }, 200)
      }
      if (action === 'cancel') {
        current.status = 'cancelled'
        current.history = [
          {
            action: 'FINE_CANCELLED',
            actor: 'Chief Warden',
            timestamp: '2026-11-15 11:00',
            note: body.reason,
          },
          ...(current.history || []),
        ]
        mockFinesState[idx] = current
        return jsonResponse({ fine: current }, 200)
      }
      if (isDisputeReview) {
        const approved = body.decision === 'approve'
        current.status = approved ? 'waived' : 'pending'
        current.dispute = {
          ...(current.dispute || {}),
          status: approved ? 'approved' : 'rejected',
          decisionReason: body.reason,
          decidedAt: '2026-11-15 12:00',
        }
        mockFinesState[idx] = current
        return jsonResponse({ fine: current }, 200)
      }
      if (action === 'payments') {
        const receiptNumber = `RCP-2026-0000${Object.keys(mockReceiptsState).length + 1}`
        const payment = {
          id: `pay-${Date.now()}`,
          amountInr: String(body.amount_inr || current.amountInr),
          paymentMethod: body.payment_method,
          manualReference: body.manual_reference,
          receiptNumber,
          verifiedAt: '2026-11-15T12:30:00Z',
        }
        const receipt = {
          institution: 'HostelCare',
          receiptNumber,
          fineReference: current.referenceNo || current.id,
          studentName: current.studentName,
          studentRoll: current.studentRoll,
          fineCategory: current.category,
          fineDescription: current.description,
          amountInr: payment.amountInr,
          paymentMethod: payment.paymentMethod,
          transactionReference: payment.manualReference,
          paidAt: payment.paidAt,
          paymentStatus: 'completed',
        }
        current.status = 'paid'
        current.payment = payment
        mockFinesState[idx] = current
        mockFinePaymentsState[current.id] = [payment]
        mockReceiptsState[receiptNumber] = receipt
        return jsonResponse({ fine: current, payment, receipt }, 201)
      }
    }

    if (path === '/api/v1/student/fines' && method === 'GET') {
      if (mockFinesError) {
        return jsonResponse(
          {
            error: { code: mockFinesError.code || 'server_error', message: mockFinesError.message },
          },
          mockFinesError.status || 500,
        )
      }
      const items = mockFinesState.filter(
        (f) =>
          String(f.studentId) === String(mockSessionUser?.id) ||
          f.studentRoll === mockSessionUser?.rollNumber,
      )
      return jsonResponse({ fines: items }, 200)
    }

    if (path.startsWith('/api/v1/student/fines/') && method === 'GET') {
      if (mockFinesError) {
        return jsonResponse(
          {
            error: { code: mockFinesError.code || 'server_error', message: mockFinesError.message },
          },
          mockFinesError.status || 500,
        )
      }
      const parts = path.split('?')[0].split('/')
      if (parts[parts.length - 1] === 'payments') {
        const fineId = decodeURIComponent(parts[parts.length - 2])
        const found = mockFinesState.find(
          (f) => String(f.id) === fineId || f.referenceNo === fineId,
        )
        if (!found) {
          return jsonResponse({ error: { code: 'not_found', message: 'Fine not found.' } }, 404)
        }
        if (String(found.studentId) !== String(mockSessionUser?.id)) {
          return jsonResponse({ error: { code: 'forbidden', message: 'Access denied.' } }, 403)
        }
        const payments = mockFinePaymentsState[found.id] || (found.payment ? [found.payment] : [])
        return jsonResponse(
          {
            fineReference: found.referenceNo || found.id,
            fineStatus: found.status,
            outstandingInr: found.status === 'paid' ? '0.00' : found.amountInr || '500.00',
            payments,
          },
          200,
        )
      }
      const fineId = decodeURIComponent(parts.pop())
      const found = mockFinesState.find((f) => String(f.id) === fineId || f.referenceNo === fineId)
      if (!found) {
        return jsonResponse({ error: { code: 'not_found', message: 'Fine not found.' } }, 404)
      }
      if (String(found.studentId) !== String(mockSessionUser?.id)) {
        return jsonResponse(
          {
            error: {
              code: 'forbidden',
              message: "You do not have permission to access another student's fine.",
            },
          },
          403,
        )
      }
      return jsonResponse({ fine: found }, 200)
    }

    if (
      path.startsWith('/api/v1/student/fines/') &&
      path.endsWith('/dispute') &&
      method === 'POST'
    ) {
      const parts = path.split('/')
      const fineId = decodeURIComponent(parts[parts.length - 2])
      const idx = mockFinesState.findIndex(
        (f) => String(f.id) === fineId || f.referenceNo === fineId,
      )
      if (idx === -1) {
        return jsonResponse({ error: { code: 'not_found', message: 'Fine not found.' } }, 404)
      }
      const current = { ...mockFinesState[idx] }
      if (String(current.studentId) !== String(mockSessionUser?.id)) {
        return jsonResponse({ error: { code: 'forbidden', message: 'Forbidden' } }, 403)
      }
      current.status = 'disputed'
      current.dispute = {
        id: `DSP-${current.id}`,
        status: 'open',
        reason: body.reason,
        createdAt: '2026-11-15 11:30',
      }
      mockFinesState[idx] = current
      return jsonResponse({ fine: current }, 201)
    }

    if (
      path.startsWith('/api/v1/student/fines/') &&
      path.includes('/payments/razorpay/') &&
      method === 'POST'
    ) {
      const parts = path.split('/')
      const action = parts[parts.length - 1]
      const fineId = decodeURIComponent(parts[parts.length - 4])
      const idx = mockFinesState.findIndex(
        (f) => String(f.id) === fineId || f.referenceNo === fineId,
      )
      if (idx === -1) {
        return jsonResponse({ error: { code: 'not_found', message: 'Fine not found.' } }, 404)
      }
      const current = { ...mockFinesState[idx] }
      if (action === 'order') {
        if (current.status !== 'pending') {
          return jsonResponse(
            { error: { code: 'conflict', message: `Cannot pay fine in ${current.status} state.` } },
            409,
          )
        }
        return jsonResponse(
          {
            reused: false,
            order: {
              attemptId: 'att-001',
              orderId: 'order_TestRzp123',
              keyId: 'rzp_test_mock_key',
              amountPaise: Math.round(Number(current.amountInr || current.amount || 500) * 100),
              amountInr: current.amountInr || '500.00',
              currency: 'INR',
              fineReference: current.referenceNo || current.id,
              name: 'HostelCare',
              description: `Fine Settlement — ${current.referenceNo || current.id}`,
              prefill: {
                name: mockSessionUser?.fullName || 'Student',
                email: mockSessionUser?.email || 'student@hostelcare.test',
              },
              notes: { fineReference: current.referenceNo || current.id },
            },
          },
          201,
        )
      }
      if (action === 'verify') {
        if (body.razorpay_signature === 'bad_sig') {
          return jsonResponse(
            {
              error: {
                code: 'invalid_signature',
                message: 'Payment signature verification failed.',
              },
            },
            400,
          )
        }
        const receiptNumber = `RCP-2026-0000${Object.keys(mockReceiptsState).length + 1}`
        const payment = {
          id: 'pay-rzp-1',
          channel: 'razorpay',
          paymentMethod: 'upi',
          verificationMethod: 'api_fetch',
          gatewayOrderId: body.razorpay_order_id,
          gatewayPaymentId: body.razorpay_payment_id,
          transactionReference: body.razorpay_payment_id,
          receiptNumber,
          amountInr: current.amountInr || '500.00',
          status: 'paid',
          paidAt: '2026-11-16T03:00:00Z',
          verifiedAt: '2026-11-16T03:00:00Z',
        }
        const receipt = {
          institution: 'HostelCare',
          receiptNumber,
          fineReference: current.referenceNo || current.id,
          fineCategory: current.category || 'Disciplinary Violation',
          fineDescription: current.description || 'Violation',
          amountInr: current.amountInr || '500.00',
          paymentMethod: 'upi',
          channel: 'razorpay',
          transactionReference: body.razorpay_payment_id,
          paymentStatus: 'paid',
          paidAt: '2026-11-16T03:00:00Z',
          studentName: current.studentName || mockSessionUser?.fullName,
          studentRoll: current.studentRoll || mockSessionUser?.rollNumber,
        }
        current.status = 'paid'
        current.paidAt = '2026-11-16T03:00:00Z'
        mockFinesState[idx] = current
        mockFinePaymentsState[current.referenceNo || current.id] = [payment]
        mockReceiptsState[receiptNumber] = receipt
        return jsonResponse({ fine: current, payment, receipt, alreadySettled: false }, 200)
      }
      if (action === 'fail') {
        return jsonResponse(
          { recorded: true, attemptStatus: 'cancelled', fineStatus: current.status },
          200,
        )
      }
    }

    if (
      (path.startsWith('/api/v1/admin/receipts/') ||
        path.startsWith('/api/v1/student/receipts/')) &&
      method === 'GET'
    ) {
      if (path.endsWith('/pdf')) {
        if (mockReceiptPdfError) {
          return jsonResponse(
            {
              error: {
                code: mockReceiptPdfError.code || 'server_error',
                message: mockReceiptPdfError.message || 'Unable to generate PDF receipt.',
              },
            },
            mockReceiptPdfError.status || 500,
          )
        }
        const parts = path.split('/')
        const receiptNumber = decodeURIComponent(parts[parts.length - 2])
        const receipt = mockReceiptsState[receiptNumber]
        if (!receipt) {
          return jsonResponse({ error: { code: 'not_found', message: 'Receipt not found.' } }, 404)
        }
        const pdfBlob = new Blob(['%PDF-1.4\n%%EOF\n'], { type: 'application/pdf' })
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: {
            get: (key) => {
              const lower = key.toLowerCase()
              if (lower === 'content-type') return 'application/pdf'
              if (lower === 'content-disposition') {
                return `attachment; filename="HostelCare-${receiptNumber}.pdf"`
              }
              return null
            },
          },
          blob: () => Promise.resolve(pdfBlob),
        })
      }
      const receiptNumber = decodeURIComponent(path.split('/').pop())
      const receipt = mockReceiptsState[receiptNumber]
      if (!receipt) {
        return jsonResponse({ error: { code: 'not_found', message: 'Receipt not found.' } }, 404)
      }
      return jsonResponse({ receipt }, 200)
    }

    return jsonResponse({ ok: true }, 200)
  })
})

describe('HostelCare Multi-Page Application & Phase 3C Authentication', () => {
  it('renders public home route and navigation links', async () => {
    mockSessionUser = null
    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText(/Your campus life,/i)).toBeInTheDocument()
    })
    expect(screen.getByText(/your second home/i)).toBeInTheDocument()
    expect(screen.getAllByText(/A place to belong/i).length).toBeGreaterThan(0)
  })

  it('navigates directly to /about route', async () => {
    mockSessionUser = null
    render(
      <MemoryRouter initialEntries={['/about']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText(/About HostelCare & Our Mission/i)).toBeInTheDocument()
    })
    expect(
      screen.getByText(/Restoring peace of mind to collegiate hostel living/i),
    ).toBeInTheDocument()
  })

  it('navigates directly to /facilities route', async () => {
    mockSessionUser = null
    render(
      <MemoryRouter initialEntries={['/facilities']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText(/Hostel Infrastructure & Amenities/i)).toBeInTheDocument()
    })
    expect(screen.getByText(/Campus Facilities/i)).toBeInTheDocument()
    expect(screen.getByText(/Sunlit Courtyard & Study Verandas/i)).toBeInTheDocument()
  })

  it('renders login route and handles student sign in via backend API', async () => {
    mockSessionUser = null
    render(
      <MemoryRouter initialEntries={['/login']}>
        <App />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: /Sign In to HostelCare/i })).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText(/Hostel Email or Roll Number/i), {
      target: { value: 'aarav.sharma@hostelcare.in' },
    })
    fireEvent.change(screen.getByLabelText(/Password \*/i), {
      target: { value: 'StudentPass123!' },
    })

    const submitBtn = screen.getByRole('button', { name: /Sign In To Resident Portal/i })
    fireEvent.click(submitBtn)

    await waitFor(() => {
      expect(screen.getByText(/Namaste, Aarav Sharma/i)).toBeInTheDocument()
    })
  })

  it('enforces selected role on login and rejects role mismatch with clear error', async () => {
    mockSessionUser = null
    render(
      <MemoryRouter initialEntries={['/login']}>
        <App />
      </MemoryRouter>,
    )

    // 1. Role tab is default "Resident" (student), but user enters Admin credentials
    fireEvent.change(screen.getByLabelText(/Hostel Email or Roll Number/i), {
      target: { value: 'warden@hostelcare.in' },
    })
    fireEvent.change(screen.getByLabelText(/Password \*/i), {
      target: { value: 'AdminPass123!' },
    })

    const submitBtn = screen.getByRole('button', { name: /Sign In To Resident Portal/i })
    fireEvent.click(submitBtn)

    // 2. Verify 403 role mismatch error is shown and user is NOT navigated away
    await waitFor(() => {
      expect(
        screen.getByText(/The selected role does not match this account's credentials/i),
      ).toBeInTheDocument()
    })
    expect(screen.getByRole('heading', { name: /Sign In to HostelCare/i })).toBeInTheDocument()
    expect(screen.queryByText(/Hostel Operations/i)).not.toBeInTheDocument()

    // 3. User switches to "Warden / Admin" tab
    const adminTab = screen.getByRole('button', { name: /Warden \/ Admin/i })
    fireEvent.click(adminTab)

    // Error is cleared upon tab switch
    expect(
      screen.queryByText(/The selected role does not match this account's credentials/i),
    ).not.toBeInTheDocument()

    // 4. Submit with the correct tab selected
    fireEvent.change(screen.getByLabelText(/Warden Admin Email/i), {
      target: { value: 'warden@hostelcare.in' },
    })
    fireEvent.change(screen.getByLabelText(/Password \*/i), {
      target: { value: 'AdminPass123!' },
    })

    const submitAdminBtn = screen.getByRole('button', {
      name: /Access Administration Console/i,
    })
    fireEvent.click(submitAdminBtn)

    // 5. Successful login navigates to Admin portal
    await waitFor(() => {
      expect(screen.getByText(/Hostel Operations/i)).toBeInTheDocument()
      expect(screen.getAllByText(/Administration/i).length).toBeGreaterThan(0)
    })
  })

  it('shows pending-approval banner when a pending student attempts to sign in', async () => {
    mockSessionUser = null
    mockLoginError = {
      status: 403,
      code: 'account_pending',
      message:
        'Your registration is pending warden approval. Please check back after verification.',
    }

    render(
      <MemoryRouter initialEntries={['/login']}>
        <App />
      </MemoryRouter>,
    )

    fireEvent.change(screen.getByLabelText(/Hostel Email or Roll Number/i), {
      target: { value: 'pending.student@hostelcare.in' },
    })
    fireEvent.change(screen.getByLabelText(/Password \*/i), {
      target: { value: 'StudentPass123!' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Sign In To Resident Portal/i }))

    await waitFor(() => {
      expect(screen.getByText(/Registration Pending Warden Approval/i)).toBeInTheDocument()
    })
  })

  it('submits student registration to /api/v1/auth/register and shows pending verification card', async () => {
    mockSessionUser = null
    render(
      <MemoryRouter initialEntries={['/register']}>
        <App />
      </MemoryRouter>,
    )

    fireEvent.change(screen.getByLabelText(/Full Name/i), {
      target: { value: 'Vikram Malhotra' },
    })
    fireEvent.change(screen.getByLabelText(/College \/ Hostel Email Address/i), {
      target: { value: 'vikram.malhotra@hostelcare.in' },
    })
    fireEvent.change(screen.getByLabelText(/Roll Number/i), {
      target: { value: '2026MEB1015' },
    })
    fireEvent.change(screen.getByLabelText(/Indian Mobile Number/i), {
      target: { value: '+91 98765 43210' },
    })
    fireEvent.change(screen.getByLabelText(/^Create Password/i), {
      target: { value: 'VikramPass123!' },
    })
    fireEvent.change(screen.getByLabelText(/Confirm Password/i), {
      target: { value: 'VikramPass123!' },
    })

    fireEvent.click(screen.getByRole('button', { name: /Submit Registration for Approval/i }))

    await waitFor(() => {
      expect(screen.getByText(/Registration Awaiting Approval/i)).toBeInTheDocument()
      expect(screen.getByText(/Pending Administrative Verification/i)).toBeInTheDocument()
    })
  })

  it('restores student session via /api/v1/auth/me and renders student room route', async () => {
    render(
      <MemoryRouter initialEntries={['/student/room']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /My Room & Allotment/i })).toBeInTheDocument()
    })
    expect(screen.getByText(/Co-Resident \/ Roommate/i)).toBeInTheDocument()
    expect(screen.getByText(/Rohan Kulkarni/i)).toBeInTheDocument()
  })

  it('enforces role-based redirects when a student navigates to an admin route', async () => {
    mockSessionUser = defaultStudentUser
    render(
      <MemoryRouter initialEntries={['/admin/dashboard']}>
        <App />
      </MemoryRouter>,
    )

    // Student attempting to visit /admin/dashboard is redirected to /student/dashboard
    await waitFor(() => {
      expect(screen.getByText(/Namaste, Aarav Sharma/i)).toBeInTheDocument()
    })
  })

  it('enforces selected role on login and rejects role mismatch with clear error', async () => {
    mockSessionUser = null
    render(
      <MemoryRouter initialEntries={['/login']}>
        <App />
      </MemoryRouter>,
    )

    // 1. Role tab is default "Resident" (student), but user enters Admin credentials
    fireEvent.change(screen.getByLabelText(/Hostel Email or Roll Number/i), {
      target: { value: 'warden@hostelcare.in' },
    })
    fireEvent.change(screen.getByLabelText(/Password \*/i), {
      target: { value: 'AdminPass123!' },
    })

    const submitBtn = screen.getByRole('button', { name: /Sign In To Resident Portal/i })
    fireEvent.click(submitBtn)

    // 2. Verify 403 role mismatch error is shown and user is NOT navigated away
    await waitFor(() => {
      expect(
        screen.getByText(/The selected role does not match this account's credentials/i),
      ).toBeInTheDocument()
    })
    expect(screen.getByRole('heading', { name: /Sign In to HostelCare/i })).toBeInTheDocument()
    expect(screen.queryByText(/Hostel Operations/i)).not.toBeInTheDocument()

    // 3. User switches to "Warden / Admin" tab
    const adminTab = screen.getByRole('button', { name: /Warden \/ Admin/i })
    fireEvent.click(adminTab)

    // Error is cleared upon tab switch
    expect(
      screen.queryByText(/The selected role does not match this account's credentials/i),
    ).not.toBeInTheDocument()

    // 4. Submit with the correct tab selected
    fireEvent.change(screen.getByLabelText(/Warden Admin Email/i), {
      target: { value: 'warden@hostelcare.in' },
    })
    fireEvent.change(screen.getByLabelText(/Password \*/i), {
      target: { value: 'AdminPass123!' },
    })

    const submitAdminBtn = screen.getByRole('button', {
      name: /Access Administration Console/i,
    })
    fireEvent.click(submitAdminBtn)

    // 5. Successful login navigates to Admin portal
    await waitFor(() => {
      expect(screen.getByText(/Hostel Operations/i)).toBeInTheDocument()
      expect(screen.getAllByText(/Administration/i).length).toBeGreaterThan(0)
    })
  })

  it('handles expired session gracefully by redirecting to /login with Session Expired notice', async () => {
    mockSessionUser = null
    mockMeErrorCode = 'session_expired'

    render(
      <MemoryRouter initialEntries={['/student/dashboard']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Sign In to HostelCare/i })).toBeInTheDocument()
      expect(screen.getByText(/Session Expired:/i)).toBeInTheDocument()
    })
  })

  it('handles logout and clears authenticated session', async () => {
    mockSessionUser = defaultStudentUser
    render(
      <MemoryRouter initialEntries={['/student/dashboard']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText(/Namaste, Aarav Sharma/i)).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: /Exit Portal/i }))

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Sign In to HostelCare/i })).toBeInTheDocument()
    })
  })

  it('handles admin login and renders admin routes', async () => {
    mockSessionUser = null
    render(
      <MemoryRouter initialEntries={['/login']}>
        <App />
      </MemoryRouter>,
    )

    const adminTab = screen.getByRole('button', { name: /Warden \/ Admin/i })
    fireEvent.click(adminTab)

    fireEvent.change(screen.getByLabelText(/Warden Admin Email/i), {
      target: { value: 'warden@hostelcare.in' },
    })
    fireEvent.change(screen.getByLabelText(/Password \*/i), {
      target: { value: 'AdminPass123!' },
    })

    const submitAdmin = screen.getByRole('button', { name: /Access Administration Console/i })
    fireEvent.click(submitAdmin)

    await waitFor(() => {
      expect(screen.getByText(/Hostel Operations/i)).toBeInTheDocument()
      expect(screen.getAllByText(/Administration/i).length).toBeGreaterThan(0)
    })
  })

  it('renders 404 page for unknown routes', async () => {
    mockSessionUser = null
    render(
      <MemoryRouter initialEntries={['/some/unknown/route']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText(/Page Not Found/i)).toBeInTheDocument()
    })
    expect(screen.getByText(/Return to Homepage/i)).toBeInTheDocument()
  })

  it('renders forgot password page and shows neutral confirmation on submit', async () => {
    mockSessionUser = null
    render(
      <MemoryRouter initialEntries={['/forgot-password']}>
        <App />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: /Reset Password/i })).toBeInTheDocument()
    const emailInput = screen.getByPlaceholderText(/aarav.sharma@hostelcare.in/i)
    fireEvent.change(emailInput, { target: { value: 'student@hostelcare.in' } })

    const sendBtn = screen.getByRole('button', { name: /Send Password Reset Link/i })
    fireEvent.click(sendBtn)

    await waitFor(() => {
      expect(screen.getByText(/Instructions Dispatched/i)).toBeInTheDocument()
    })
  })

  it('renders reset password page for valid and invalid tokens', async () => {
    mockSessionUser = null
    // Valid token view
    const { unmount } = render(
      <MemoryRouter initialEntries={['/reset-password/sample-valid-token']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Create New Password/i })).toBeInTheDocument()
    })
    unmount()

    // Invalid token view
    const { unmount: unmountInvalid } = render(
      <MemoryRouter initialEntries={['/reset-password/invalid']}>
        <App />
      </MemoryRouter>,
    )
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Invalid Reset Token/i })).toBeInTheDocument()
    })
    unmountInvalid()

    // Expired token view
    const { unmount: unmountExpired } = render(
      <MemoryRouter initialEntries={['/reset-password/expired']}>
        <App />
      </MemoryRouter>,
    )
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Reset Link Expired/i })).toBeInTheDocument()
    })
    unmountExpired()

    // Redacted placeholder token view
    render(
      <MemoryRouter initialEntries={['/reset-password/[REDACTED-TOKEN]']}>
        <App />
      </MemoryRouter>,
    )
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Invalid Reset Token/i })).toBeInTheDocument()
      expect(screen.getByText(/contains a redacted placeholder token/i)).toBeInTheDocument()
    })
  })

  it('submits valid reset token and handles server rejection', async () => {
    mockSessionUser = null
    const { unmount } = render(
      <MemoryRouter initialEntries={['/reset-password/my-clean-token']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Create New Password/i })).toBeInTheDocument()
    })

    const passwordInput = screen.getByLabelText(/^New Password/i)
    const confirmInput = screen.getByLabelText(/^Confirm New Password/i)
    const submitBtn = screen.getByRole('button', { name: /Update Password/i })

    fireEvent.change(passwordInput, { target: { value: 'NewSecurePass123!' } })
    fireEvent.change(confirmInput, { target: { value: 'NewSecurePass123!' } })
    fireEvent.click(submitBtn)

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /Password Updated Successfully/i }),
      ).toBeInTheDocument()
    })
    unmount()

    // Test server rejection flow
    render(
      <MemoryRouter initialEntries={['/reset-password/server-expired-token']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Create New Password/i })).toBeInTheDocument()
    })

    const pwInput2 = screen.getByLabelText(/^New Password/i)
    const confInput2 = screen.getByLabelText(/^Confirm New Password/i)
    const submitBtn2 = screen.getByRole('button', { name: /Update Password/i })

    fireEvent.change(pwInput2, { target: { value: 'NewSecurePass123!' } })
    fireEvent.change(confInput2, { target: { value: 'NewSecurePass123!' } })
    fireEvent.click(submitBtn2)

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Invalid Reset Token/i })).toBeInTheDocument()
      expect(
        screen.getByText(
          /The token provided in the URL is unrecognized, expired, or has already been used/i,
        ),
      ).toBeInTheDocument()
    })
  })

  it('renders student fines page with empty state without mock records', async () => {
    render(
      <MemoryRouter initialEntries={['/student/fines']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /My Fines & Penalties/i })).toBeInTheDocument()
    })
    expect(screen.getByText(/No Outstanding Fines/i)).toBeInTheDocument()
    expect(
      screen.getByText(/Your hostel disciplinary and dues account is clean/i),
    ).toBeInTheDocument()
    expect(screen.getByText(/₹0/i)).toBeInTheDocument()
    expect(screen.queryByText(/FIN-2026-012/i)).not.toBeInTheDocument()
  })

  it('renders admin fines directory and dispute queue', async () => {
    mockSessionUser = defaultAdminUser
    render(
      <MemoryRouter initialEntries={['/admin/fines']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText(/Fines & Disciplinary Records/i)).toBeInTheDocument()
    })
    expect(screen.getByText(/Issue New Fine/i)).toBeInTheDocument()
  })

  it('renders student complaint submission with free-text and optional category', async () => {
    render(
      <MemoryRouter initialEntries={['/student/complaints/new']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /Submit Maintenance Complaint/i }),
      ).toBeInTheDocument()
    })
    expect(screen.getByText(/Free-Text in your own words/i)).toBeInTheDocument()

    // Title input
    const titleInput = screen.getByPlaceholderText(/Broken bed frame/i)
    fireEvent.change(titleInput, { target: { value: 'Study table leg cracked' } })

    // Free text description
    const descInput = screen.getByPlaceholderText(/Explain any hostel-related issue/i)
    fireEvent.change(descInput, {
      target: { value: 'The wooden table right front leg has a deep crack and wobbles.' },
    })

    const submitBtn = screen.getByRole('button', { name: /Submit Maintenance Complaint/i })
    fireEvent.click(submitBtn)

    await waitFor(() => {
      expect(screen.getByText(/Complaint submitted successfully!/i)).toBeInTheDocument()
    })
  })

  it('renders student complaint detail with assigned technician visibility', async () => {
    render(
      <MemoryRouter initialEntries={['/student/complaints/CMP-2026-089']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText(/CMP-2026-089/i)).toBeInTheDocument()
    })
    expect(screen.getAllByText(/Ramesh Babu/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Electrician/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/Official Complaint History & Audit Trail/i)).toBeInTheDocument()
    // Ensure internal notes are NOT visible to the student
    expect(screen.queryByText(/Internal Administrative Notes/i)).not.toBeInTheDocument()
  })

  it('renders admin complaint queue and detail with private notes and lifecycle actions', async () => {
    mockSessionUser = defaultAdminUser
    render(
      <MemoryRouter initialEntries={['/admin/complaints']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText(/Hostel Complaint Management/i)).toBeInTheDocument()
    })
    expect(screen.getByText(/New Submissions/i)).toBeInTheDocument()
  })

  it('renders admin staff management roster', async () => {
    mockSessionUser = defaultAdminUser
    render(
      <MemoryRouter initialEntries={['/admin/staff']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText(/Maintenance Staff Management/i)).toBeInTheDocument()
    })
    expect(screen.getByText(/Ramesh Babu/i)).toBeInTheDocument()
    expect(screen.getByText(/Santosh Kumar/i)).toBeInTheDocument()
  })

  it('handles dedicated staff login and dashboard access', async () => {
    mockSessionUser = null
    render(
      <MemoryRouter initialEntries={['/staff/login']}>
        <App />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: /Technician & Staff Login/i })).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText(/Staff Email or Staff Code/i), {
      target: { value: 'ramesh.electrician@hostelcare.in' },
    })
    fireEvent.change(screen.getByLabelText(/Account Password/i), {
      target: { value: 'StaffPass123!' },
    })

    const submitBtn = screen.getByRole('button', { name: /Access Staff Maintenance Console/i })
    fireEvent.click(submitBtn)

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Namaste, Ramesh Babu/i })).toBeInTheDocument()
    })
    expect(screen.getByText(/Total Work Orders/i)).toBeInTheDocument()
    expect(screen.getByText(/Completed Tasks/i)).toBeInTheDocument()
  })

  it('renders staff assigned tasks and enforces strict task ownership', async () => {
    mockSessionUser = defaultStaffUser
    render(
      <MemoryRouter initialEntries={['/staff/tasks']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /My Assigned Work Orders/i })).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: /All \(/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /In Progress \(/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Completed \(/i })).toBeInTheDocument()
  })

  it('renders staff profile with read-only trade and editable contact details', async () => {
    mockSessionUser = defaultStaffUser
    render(
      <MemoryRouter initialEntries={['/staff/profile']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Duty Staff Profile/i })).toBeInTheDocument()
    })
    expect(screen.getAllByText(/Ramesh Babu/i).length).toBeGreaterThan(0)
    expect(screen.getByRole('button', { name: /Edit Contact Info/i })).toBeInTheDocument()
  })

  it('renders staff notifications and mark read action', async () => {
    mockSessionUser = defaultStaffUser
    render(
      <MemoryRouter initialEntries={['/staff/notifications']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Duty Notifications/i })).toBeInTheDocument()
    })
    expect(screen.getAllByText(/Work Order/i).length).toBeGreaterThan(0)
  })

  it('renders staff task detail view and allows completing work with mandatory note', async () => {
    mockSessionUser = defaultStaffUser
    render(
      <MemoryRouter initialEntries={['/staff/tasks']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /My Assigned Work Orders/i })).toBeInTheDocument()
    })

    // Open first task
    const viewDetailsBtn = screen.getAllByRole('button', { name: /Open Task/i })[0]
    fireEvent.click(viewDetailsBtn)

    // Verify task detail elements
    await waitFor(() => {
      expect(screen.getByText(/Student Problem Description/i)).toBeInTheDocument()
    })
    expect(screen.getByText(/Action Control Panel/i)).toBeInTheDocument()
    expect(screen.getByText(/Work Order Audit History/i)).toBeInTheDocument()
  })

  it('allows an approved student without a room allocation to submit a common-area complaint', async () => {
    mockSessionUser = {
      ...defaultStudentUser,
      room: 'Unallocated',
      hasActiveRoom: false,
    }
    render(
      <MemoryRouter initialEntries={['/student/complaints/new']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /Submit Maintenance Complaint/i }),
      ).toBeInTheDocument()
    })

    const locationDetailInput = screen.getByPlaceholderText(/2nd Floor Corridor near Water Cooler/i)
    fireEvent.change(locationDetailInput, {
      target: { value: '2nd Floor Common Washroom near Staircase B' },
    })
    fireEvent.change(screen.getByPlaceholderText(/Broken bed frame/i), {
      target: { value: 'Exhaust fan rattling loudly' },
    })
    fireEvent.change(screen.getByPlaceholderText(/Explain any hostel-related issue/i), {
      target: { value: 'The exhaust fan in the 2nd floor washroom makes a loud metallic noise.' },
    })

    fireEvent.click(screen.getByRole('button', { name: /Submit Maintenance Complaint/i }))

    await waitFor(() => {
      expect(screen.getByText(/Complaint submitted successfully!/i)).toBeInTheDocument()
    })
  })

  it('renders admin complaint detail with internal notes and pre-acceptance rejection', async () => {
    mockSessionUser = defaultAdminUser
    render(
      <MemoryRouter initialEntries={['/admin/complaints/CMP-2026-089']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText(/Internal Administrative Notes/i)).toBeInTheDocument()
    })

    const noteTextarea = screen.getByPlaceholderText(/Add private note for warden team/i)
    fireEvent.change(noteTextarea, {
      target: { value: 'Verified voltage drop at main distribution panel.' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Add Private Note/i }))

    await waitFor(() => {
      expect(
        screen.getByText(/Verified voltage drop at main distribution panel\./i),
      ).toBeInTheDocument()
    })
  })

  it('detects session change on window focus when another tab logs in as student and removes stale admin UI', async () => {
    mockSessionUser = defaultAdminUser
    render(
      <MemoryRouter initialEntries={['/admin/staff']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText(/Maintenance Staff Management/i)).toBeInTheDocument()
    })

    // Simulate Tab 2 logging in as Student (overwriting the browser session cookie)
    mockSessionUser = {
      ...defaultStudentUser,
      fullName: 'Mangal Pandey',
      rollNumber: 'BETN1CS25002',
    }

    // Count `/api/v1/auth/me` calls when both visibilitychange and focus fire simultaneously
    const fetchSpy = globalThis.fetch
    const callsBefore = fetchSpy.mock.calls.filter(([u]) => u === '/api/v1/auth/me').length

    fireEvent(window, new Event('focus'))
    fireEvent(document, new Event('visibilitychange'))

    // Stale Admin Staff page is removed and redirected to Student Dashboard
    await waitFor(() => {
      expect(screen.getByText(/Namaste, Mangal Pandey/i)).toBeInTheDocument()
    })
    expect(screen.queryByText(/Maintenance Staff Management/i)).not.toBeInTheDocument()

    // Simultaneous focus + visibilitychange only triggered a single in-flight `/api/v1/auth/me` request
    const callsAfter = fetchSpy.mock.calls.filter(([u]) => u === '/api/v1/auth/me').length
    expect(callsAfter - callsBefore).toBe(1)
  })

  it('distinguishes a genuine 403 permission denial from a session change without logging out', async () => {
    mockSessionUser = defaultAdminUser
    mockStaffState = []
    render(
      <MemoryRouter initialEntries={['/admin/staff']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText(/No Maintenance Staff Records Found/i)).toBeInTheDocument()
    })

    // Simulate a genuine 403 error on POST /api/v1/admin/staff while /api/v1/auth/me still returns Admin
    mockStaffError = {
      status: 403,
      code: 'forbidden',
      message: 'You do not have permission to perform this action.',
    }

    fireEvent.click(screen.getByRole('button', { name: /\+ Add New Staff Record/i }))
    fireEvent.change(screen.getByPlaceholderText(/e\.g\. Ramesh Babu/i), {
      target: { value: 'Kishan Lal' },
    })
    fireEvent.change(screen.getByPlaceholderText(/e\.g\. ramesh\.electrician@hostelcare\.in/i), {
      target: { value: 'kishan@hostelcare.in' },
    })
    fireEvent.change(screen.getByPlaceholderText(/\+91 98765 43210/i), {
      target: { value: '+91 98111 22334' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Save Staff Member/i }))

    // Error alert is shown AND the admin portal remains active (not logged out or redirected)
    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(
        /You do not have permission to perform this action\./i,
      )
    })
    expect(screen.getByText(/Maintenance Staff Management/i)).toBeInTheDocument()
  })

  it('renders empty staff state, handles failed staff API request with retry, and creates real staff', async () => {
    mockSessionUser = defaultAdminUser
    mockStaffState = []
    mockStaffError = {
      status: 500,
      code: 'internal_error',
      message: 'Temporary database connection error while loading staff.',
    }

    render(
      <MemoryRouter initialEntries={['/admin/staff']}>
        <App />
      </MemoryRouter>,
    )

    // 1. Failed staff API request displays error alert and Retry button (never restores mock staff)
    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(
        /Temporary database connection error while loading staff\./i,
      )
    })
    expect(screen.queryByText(/Ramesh Babu/i)).not.toBeInTheDocument()

    // 2. Clicking Retry when backend recovers shows empty staff state
    mockStaffError = null
    fireEvent.click(screen.getByRole('button', { name: /Retry/i }))

    await waitFor(() => {
      expect(screen.getByText(/No Maintenance Staff Records Found/i)).toBeInTheDocument()
    })

    // 3. Creating a real staff record succeeds and renders the newly created staff card
    fireEvent.click(screen.getByRole('button', { name: /\+ Add New Staff Record/i }))
    fireEvent.change(screen.getByPlaceholderText(/e\.g\. Ramesh Babu/i), {
      target: { value: 'Suresh Nair' },
    })
    fireEvent.change(screen.getByPlaceholderText(/e\.g\. STF-0005/i), {
      target: { value: 'STF-0009' },
    })
    fireEvent.change(screen.getByPlaceholderText(/e\.g\. ramesh\.electrician@hostelcare\.in/i), {
      target: { value: 'suresh.nair@hostelcare.in' },
    })
    fireEvent.change(screen.getByPlaceholderText(/\+91 98765 43210/i), {
      target: { value: '+91 94421 55667' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Save Staff Member/i }))

    await waitFor(() => {
      expect(screen.getByText(/Provisioned staff account for Suresh Nair/i)).toBeInTheDocument()
    })
    expect(screen.getByText('Suresh Nair')).toBeInTheDocument()
    expect(screen.getByText(/Active \(toggle\)/i)).toBeInTheDocument()
  })

  it('renders empty room occupancy state and real active room occupancy with vacant beds', async () => {
    mockSessionUser = defaultAdminUser
    mockRoomsState = []

    const { unmount } = render(
      <MemoryRouter initialEntries={['/admin/rooms']}>
        <App />
      </MemoryRouter>,
    )

    // 1. Empty room occupancy state (never shows sample residents like Aarav Sharma or Nikhil Jain)
    await waitFor(() => {
      expect(screen.getByText(/No Hostel Rooms Configured/i)).toBeInTheDocument()
    })
    expect(screen.queryByText(/Nikhil Jain/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/Aarav Sharma/i)).not.toBeInTheDocument()
    unmount()

    // 2. Real room occupancy calculated from active allocations with vacant bed representation
    mockRoomsState = [
      {
        id: 'A-204',
        room_number: 'A-204',
        block: 'Block A (Nalanda)',
        floor: '2nd Floor',
        capacity: 2,
        occupied: 1,
        vacant_beds: 1,
        residents: ['Mangal Pandey'],
        students: ['Mangal Pandey', '(Vacant Bed)'],
      },
    ]

    render(
      <MemoryRouter initialEntries={['/admin/rooms']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('A-204')).toBeInTheDocument()
    })
    expect(screen.getByText('1/2 Beds')).toBeInTheDocument()
    expect(screen.getByText(/• Mangal Pandey/i)).toBeInTheDocument()
    expect(screen.getByText(/• \(Vacant Bed\)/i)).toBeInTheDocument()
  })

  it('renders student room page for student without allocation and student with actual allocation', async () => {
    // 1. Student without an active room allocation
    mockSessionUser = {
      id: 'stu-unassigned',
      role: 'student',
      status: 'active',
      fullName: 'Mangal Pandey',
      rollNumber: 'BETN1CS25002',
      email: 'student1@hostelcare.test',
      phone: '+91 00000 00001',
      hasActiveRoom: false,
      room: 'Unassigned',
      block: 'Not Assigned',
      floor: 'Not Assigned',
      bed: 'Not Assigned',
      roommate: 'No Roommate Assigned',
      roommateRoll: null,
    }

    const { unmount } = render(
      <MemoryRouter initialEntries={['/student/room']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /My Room & Allotment/i })).toBeInTheDocument()
    })
    expect(screen.getAllByText('Not Assigned').length).toBeGreaterThan(0)
    expect(screen.getByText('No Roommate Assigned')).toBeInTheDocument()
    expect(screen.queryByText('A-203')).not.toBeInTheDocument()
    expect(screen.queryByText(/Rohan Kulkarni/i)).not.toBeInTheDocument()
    expect(screen.queryByText('2023CSB1058')).not.toBeInTheDocument()
    unmount()

    // 2. Student with an actual room allocation and roommate
    mockSessionUser = {
      id: 'stu-assigned',
      role: 'student',
      status: 'active',
      fullName: 'Chandrashekhar Azad',
      rollNumber: 'BETN1CS25010',
      email: 'azad@hostelcare.in',
      phone: '+91 9811100001',
      hasActiveRoom: true,
      room: 'B-105',
      block: 'Block B (Takshashila)',
      floor: '1st Floor',
      bed: 'Bed 1',
      allocationStartDate: '10/11/2026',
      roommate: 'Ashfaqulla Khan',
      roommateRoll: 'BETN1CS25011',
      roommateBed: 'Bed 2',
      roommatePhone: '+91 9811100002',
    }

    render(
      <MemoryRouter initialEntries={['/student/room']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('B-105')).toBeInTheDocument()
    })
    expect(screen.getByText('Ashfaqulla Khan')).toBeInTheDocument()
    expect(screen.getByText('BETN1CS25011')).toBeInTheDocument()
  })

  it('renders admin room management tabs, block configuration modal, and empty allocation state', async () => {
    mockSessionUser = defaultAdminUser
    mockRoomsState = []
    mockBlocksState = []
    mockAllocationsState = []

    render(
      <MemoryRouter initialEntries={['/admin/rooms']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /Room & Occupancy Management/i }),
      ).toBeInTheDocument()
    })

    // 1. Verify 3 tabs are present
    expect(screen.getByRole('button', { name: /Rooms & Occupancy Map/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Hostel Blocks/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Resident Allocations/i })).toBeInTheDocument()

    // 2. Switch to Hostel Blocks tab
    fireEvent.click(screen.getByRole('button', { name: /Hostel Blocks/i }))
    await waitFor(() => {
      expect(
        screen.getByText(
          /No blocks found. Click "\+ Add Block" to configure your first hostel wing./i,
        ),
      ).toBeInTheDocument()
    })

    // Open Add Block modal
    fireEvent.click(screen.getByRole('button', { name: /\+ Add Block/i }))
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Add New Hostel Block/i })).toBeInTheDocument()
      expect(screen.getByLabelText(/Block Code/i)).toBeInTheDocument()
    })

    // Close modal
    fireEvent.click(screen.getByRole('button', { name: /Cancel/i }))

    // 3. Switch to Resident Allocations tab
    fireEvent.click(screen.getByRole('button', { name: /Resident Allocations/i }))
    await waitFor(() => {
      expect(
        screen.getByText(/No room allocations match your search criteria./i),
      ).toBeInTheDocument()
    })
  })

  it('validates missing block name, preserves form input on failure, and creates block successfully', async () => {
    mockSessionUser = defaultAdminUser
    mockRoomsState = []
    mockBlocksState = []
    mockAllocationsState = []

    render(
      <MemoryRouter initialEntries={['/admin/rooms']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /Room & Occupancy Management/i }),
      ).toBeInTheDocument()
    })

    // 1. Open Add Block modal
    fireEvent.click(screen.getByRole('button', { name: /\+ Add Block/i }))
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Add New Hostel Block/i })).toBeInTheDocument()
    })

    const nameInput = screen.getByLabelText(/Block Name/i)
    const codeInput = screen.getByLabelText(/Block Code/i)
    const orderInput = screen.getByLabelText(/Display Order/i)

    // 2. Enter code and order but leave name empty
    fireEvent.change(codeInput, { target: { value: 'BLKA' } })
    fireEvent.change(orderInput, { target: { value: '1' } })

    const submitBtn = screen.getByRole('button', { name: /Create Block/i })
    fireEvent.click(submitBtn)

    // 3. Verify field-specific validation error is shown and form values are preserved
    await waitFor(() => {
      expect(screen.getByText(/Block name is required\./i)).toBeInTheDocument()
    })
    expect(codeInput.value).toBe('BLKA')
    expect(orderInput.value).toBe('1')

    // 4. Fill in valid Block Name and submit
    fireEvent.change(nameInput, { target: { value: 'Block A (New Tapti)' } })
    fireEvent.click(screen.getByRole('button', { name: /Create Block/i }))

    // 5. Verify modal closes, success notice is displayed, and block directory includes the new block
    await waitFor(() => {
      expect(
        screen.getByText(/Successfully created block "Block A \(New Tapti\)" \(BLKA\)\./i),
      ).toBeInTheDocument()
    })
    expect(screen.queryByRole('heading', { name: /Add New Hostel Block/i })).not.toBeInTheDocument()

    // Switch to blocks tab and verify table shows the created block
    fireEvent.click(screen.getByRole('button', { name: /Hostel Blocks/i }))
    await waitFor(() => {
      expect(screen.getByText('BLKA')).toBeInTheDocument()
      expect(screen.getByText('Block A (New Tapti)')).toBeInTheDocument()
    })
  })

  it('allows admin to edit staff email with validation and dispatch password setup link', async () => {
    mockSessionUser = defaultAdminUser

    render(
      <MemoryRouter initialEntries={['/admin/staff']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText(/Maintenance Staff Management/i)).toBeInTheDocument()
      expect(screen.getByText(/Ramesh Babu/i)).toBeInTheDocument()
    })

    // 1. Click "Edit Profile" on Ramesh Babu
    const editButtons = screen.getAllByRole('button', { name: /Edit Profile/i })
    fireEvent.click(editButtons[0])

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Edit Staff: Ramesh Babu/i })).toBeInTheDocument()
    })

    // 2. Verify Email Address field is prepopulated
    const emailInput = screen.getByLabelText(/Email Address \*/i)
    expect(emailInput.value).toBe('ramesh.electrician@hostelcare.in')

    // 3. Test invalid email rejection
    fireEvent.change(emailInput, { target: { value: 'invalid-email-format' } })
    fireEvent.click(screen.getByRole('button', { name: /Update Record/i }))

    await waitFor(() => {
      expect(screen.getByText(/Please provide a valid email address\./i)).toBeInTheDocument()
    })

    // 4. Test duplicate email rejection
    fireEvent.change(emailInput, { target: { value: 'santosh.plumber@hostelcare.in' } })
    fireEvent.click(screen.getByRole('button', { name: /Update Record/i }))

    await waitFor(() => {
      expect(screen.getByText(/Email address is already in use/i)).toBeInTheDocument()
    })

    // 5. Submit valid new email
    fireEvent.change(emailInput, { target: { value: 'ramesh.verified@hostelcare.in' } })
    fireEvent.click(screen.getByRole('button', { name: /Update Record/i }))

    // 6. Verify success banner and updated email
    await waitFor(() => {
      expect(
        screen.getByText(
          /Updated staff record for Ramesh Babu \(ramesh\.verified@hostelcare\.in\)\./i,
        ),
      ).toBeInTheDocument()
    })
    expect(
      screen.queryByRole('heading', { name: /Edit Staff: Ramesh Babu/i }),
    ).not.toBeInTheDocument()

    // 7. Verify "Send Password Setup Link" action button in banner dispatches link
    const sendLinkBannerBtn = screen.getByRole('button', { name: /Send Password Setup Link/i })
    fireEvent.click(sendLinkBannerBtn)

    await waitFor(() => {
      expect(
        screen.getByText(
          /Dispatched a 30-minute password setup\/reset link to ramesh\.verified@hostelcare\.in\./i,
        ),
      ).toBeInTheDocument()
    })
  })

  it('blocks IDOR access to another student or roommate complaint and never leaks description or notes', async () => {
    mockSessionUser = defaultStudentUser
    // Add a roommate complaint in the EXACT SAME room (A-203) belonging to another student
    mockComplaintsState = [
      ...mockComplaintsState,
      {
        id: 'CMP-2026-095',
        referenceNo: 'CMP-2026-095',
        studentId: 'stu-roommate-999',
        title: 'Roommate Private Wardrobe Lock Broken',
        category: 'Furniture',
        priority: 'High',
        status: 'In Progress',
        reporterName: 'Rohan Kulkarni',
        reporterRoll: '2023CSB1058',
        room: 'A-203',
        block: 'Block A',
        dateSubmitted: '14/11/2026',
        description: 'CONFIDENTIAL ROOMMATE DESCRIPTION THAT MUST NOT BE VISIBLE',
        assignedStaff: 'Ramesh Babu',
        assignedStaffRole: 'Electrician',
        internalNotes: [
          {
            id: 'note-secret',
            author: 'Chief Warden',
            note: 'CONFIDENTIAL WARDEN NOTE',
          },
        ],
        updates: [
          {
            id: 'upd-secret',
            authorName: 'Ramesh Babu',
            authorRole: 'Electrician',
            body: 'SECRET PROGRESS UPDATE',
          },
        ],
        history: [
          {
            action: 'Submitted',
            actor: 'Rohan Kulkarni',
            timestamp: '14/11/2026',
            note: 'SECRET HISTORY NOTE',
          },
        ],
      },
    ]

    // 1. Navigating to Student Complaints list must NOT display roommate complaint despite shared room A-203
    const { unmount } = render(
      <MemoryRouter initialEntries={['/student/complaints']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText(/CMP-2026-089/i)).toBeInTheDocument()
    })
    expect(screen.queryByText(/CMP-2026-095/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/Roommate Private Wardrobe Lock Broken/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/CMP-2026-092/i)).not.toBeInTheDocument()
    unmount()

    // 2. Directly opening roommate's complaint URL must show Access Restricted and leak nothing
    render(
      <MemoryRouter initialEntries={['/student/complaints/CMP-2026-095']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Access Restricted/i })).toBeInTheDocument()
    })
    expect(screen.queryByText(/Roommate Private Wardrobe Lock Broken/i)).not.toBeInTheDocument()
    expect(
      screen.queryByText(/CONFIDENTIAL ROOMMATE DESCRIPTION THAT MUST NOT BE VISIBLE/i),
    ).not.toBeInTheDocument()
    expect(screen.queryByText(/CONFIDENTIAL WARDEN NOTE/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/SECRET PROGRESS UPDATE/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/SECRET HISTORY NOTE/i)).not.toBeInTheDocument()
  })

  it('allows Student B to view own complaint while denying Student A complaint and unknown IDs', async () => {
    const roommateStudentB = {
      id: 'stu-roommate-999',
      role: 'student',
      status: 'active',
      hasActiveRoom: true,
      rollNumber: '2023CSB1058',
      fullName: 'Rohan Kulkarni',
      email: 'rohan.kulkarni@hostelcare.in',
      block: 'Block A',
      floor: '2nd Floor',
      room: 'A-203',
    }
    mockSessionUser = roommateStudentB
    mockComplaintsState = [
      ...mockComplaintsState,
      {
        id: 'CMP-2026-095',
        referenceNo: 'CMP-2026-095',
        studentId: 'stu-roommate-999',
        title: 'Roommate Private Wardrobe Lock Broken',
        category: 'Furniture',
        priority: 'High',
        status: 'In Progress',
        reporterName: 'Rohan Kulkarni',
        reporterRoll: '2023CSB1058',
        room: 'A-203',
        block: 'Block A',
        dateSubmitted: '14/11/2026',
        description: 'Private locker door hinge snapped near study desk.',
        assignedStaff: 'Ramesh Babu',
        assignedStaffRole: 'Electrician',
        internalNotes: [
          {
            id: 'note-secret',
            author: 'Chief Warden',
            note: 'CONFIDENTIAL WARDEN NOTE FOR B',
          },
        ],
        updates: [
          {
            id: 'upd-secret',
            authorName: 'Ramesh Babu',
            authorRole: 'Electrician',
            body: 'Replaced hinge screws cleanly.',
          },
        ],
        history: [
          {
            action: 'Submitted',
            actor: 'Rohan Kulkarni',
            timestamp: '14/11/2026',
            note: 'Complaint logged by Rohan Kulkarni.',
          },
        ],
      },
    ]

    // 1. Student B can view B's own complaint (without internal warden notes)
    const { unmount: unmountOwn } = render(
      <MemoryRouter initialEntries={['/student/complaints/CMP-2026-095']}>
        <App />
      </MemoryRouter>,
    )
    await waitFor(() => {
      expect(screen.getByText(/Roommate Private Wardrobe Lock Broken/i)).toBeInTheDocument()
    })
    expect(screen.getByText(/Replaced hinge screws cleanly\./i)).toBeInTheDocument()
    expect(screen.queryByText(/CONFIDENTIAL WARDEN NOTE FOR B/i)).not.toBeInTheDocument()
    unmountOwn()

    // 2. Student B CANNOT view Student A's complaint in the same room (CMP-2026-089)
    const { unmount: unmountIdor } = render(
      <MemoryRouter initialEntries={['/student/complaints/CMP-2026-089']}>
        <App />
      </MemoryRouter>,
    )
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Access Restricted/i })).toBeInTheDocument()
    })
    expect(screen.queryByText(/Ceiling fan making clicking noise/i)).not.toBeInTheDocument()
    unmountIdor()

    // 3. Non-existent complaint shows Complaint Not Found safely
    render(
      <MemoryRouter initialEntries={['/student/complaints/CMP-9999-999']}>
        <App />
      </MemoryRouter>,
    )
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Complaint Not Found/i })).toBeInTheDocument()
    })
  })

  describe('Student Complaint Detail Page Robustness and Security', () => {
    it('Test 1 — loads student own complaint, dismisses loading state, and avoids repeated requests (including StrictMode)', async () => {
      mockSessionUser = defaultStudentUser

      const recordedUrls = []
      const currentMock = globalThis.fetch.getMockImplementation()
      globalThis.fetch.mockImplementation((url, options = {}) => {
        const urlStr = typeof url === 'string' ? url : url.toString()
        recordedUrls.push({ url: urlStr, method: (options?.method || 'GET').toUpperCase() })
        return currentMock(url, options)
      })

      render(
        <StrictMode>
          <MemoryRouter initialEntries={['/student/complaints/CMP-2026-089']}>
            <App />
          </MemoryRouter>
        </StrictMode>,
      )

      // Details appear
      await waitFor(() => {
        expect(
          screen.getByRole('heading', { name: /Ceiling fan making clicking noise/i }),
        ).toBeInTheDocument()
      })
      // Loading screen disappears
      expect(screen.queryByText(/Loading complaint details\.\.\./i)).not.toBeInTheDocument()
      // Reference ID is properly displayed
      expect(screen.getByText('CMP-2026-089')).toBeInTheDocument()

      const complaintDetailRequests = recordedUrls.filter(
        (r) => r.url === '/api/v1/student/complaints/CMP-2026-089' && r.method === 'GET',
      )
      // In StrictMode mount+remount may execute initial mount, but must NOT loop indefinitely
      expect(complaintDetailRequests.length).toBeLessThanOrEqual(2)
    })

    it("Test 2 — restricts another student's complaint with HTTP 403, prevents auth loops, and preserves student authentication (including StrictMode)", async () => {
      mockSessionUser = defaultStudentUser

      mockComplaintsState = [
        ...mockComplaintsState,
        {
          id: 'CMP-2026-00002',
          referenceNo: 'CMP-2026-00002',
          studentId: 'stu-other-student',
          studentRoll: '2023CSB9999',
          reporterRoll: '2023CSB9999',
          title: "Other Student's Personal Issue",
          category: 'Electrical',
          priority: 'Medium',
          status: 'Open',
          reporterName: 'Other Student',
          room: 'B-101',
          block: 'Block B',
          dateSubmitted: '15/11/2026',
          description: 'Private room issue.',
        },
      ]

      const recordedUrls = []
      const currentMock = globalThis.fetch.getMockImplementation()
      globalThis.fetch.mockImplementation((url, options = {}) => {
        const urlStr = typeof url === 'string' ? url : url.toString()
        recordedUrls.push({ url: urlStr, method: (options?.method || 'GET').toUpperCase() })
        return currentMock(url, options)
      })

      render(
        <StrictMode>
          <MemoryRouter initialEntries={['/student/complaints/CMP-2026-00002']}>
            <App />
          </MemoryRouter>
        </StrictMode>,
      )

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: /Access Restricted/i })).toBeInTheDocument()
      })

      // Complaint information is protected
      expect(screen.queryByText(/Other Student's Personal Issue/i)).not.toBeInTheDocument()
      expect(screen.queryByText(/Loading complaint details\.\.\./i)).not.toBeInTheDocument()

      const complaintDetailRequests = recordedUrls.filter(
        (r) => r.url === '/api/v1/student/complaints/CMP-2026-00002' && r.method === 'GET',
      )
      const authMeRequests = recordedUrls.filter(
        (r) => r.url === '/api/v1/auth/me' && r.method === 'GET',
      )

      // Exactly bounded requests, no endless loop
      expect(complaintDetailRequests.length).toBeLessThanOrEqual(2)
      expect(authMeRequests.length).toBeLessThanOrEqual(3)

      // Student A remains authenticated
      expect(mockSessionUser.id).toBe(defaultStudentUser.id)
    })

    it('Test 3 — navigates correctly between complaints without getting stuck', async () => {
      mockSessionUser = defaultStudentUser

      render(
        <MemoryRouter initialEntries={['/student/complaints']}>
          <App />
        </MemoryRouter>,
      )

      // Wait for complaints list to load
      await waitFor(() => {
        expect(screen.getByText('CMP-2026-089')).toBeInTheDocument()
        expect(screen.getByText('CMP-2026-090')).toBeInTheDocument()
      })

      // Click on the first complaint
      fireEvent.click(screen.getByText('CMP-2026-089'))

      // Detail page for first complaint loads
      await waitFor(() => {
        expect(
          screen.getByRole('heading', { name: /Ceiling fan making clicking noise/i }),
        ).toBeInTheDocument()
      })
      expect(screen.queryByText(/Loading complaint details\.\.\./i)).not.toBeInTheDocument()

      // Navigate back to list
      fireEvent.click(screen.getByText(/Back to all complaints/i))

      // Wait for complaints list again
      await waitFor(() => {
        expect(screen.getByText('CMP-2026-090')).toBeInTheDocument()
      })

      // Click on the second complaint
      fireEvent.click(screen.getByText('CMP-2026-090'))

      // Detail page for second complaint loads
      await waitFor(() => {
        expect(
          screen.getByRole('heading', { name: /Window latch loose during windy nights/i }),
        ).toBeInTheDocument()
      })
      expect(screen.queryByText(/Loading complaint details\.\.\./i)).not.toBeInTheDocument()
    })

    it('Test 4 — terminates loading on temporary error and allows usable retry', async () => {
      mockSessionUser = defaultStudentUser

      const unCachedComplaint = {
        id: 'CMP-2026-00999',
        referenceNo: 'CMP-2026-00999',
        studentId: defaultStudentUser.id,
        studentRoll: defaultStudentUser.rollNumber,
        reporterRoll: defaultStudentUser.rollNumber,
        title: 'Water pipe leaking under washbasin',
        category: 'Plumbing',
        priority: 'High',
        status: 'Open',
        reporterName: defaultStudentUser.fullName,
        room: defaultStudentUser.room,
        block: defaultStudentUser.block,
        dateSubmitted: '15/11/2026',
        description: 'Major water leakage under washbasin.',
      }

      // Simulate 500 error on first fetch
      mockComplaintDetailError = { status: 500, message: 'Database query timed out' }

      render(
        <MemoryRouter initialEntries={['/student/complaints/CMP-2026-00999']}>
          <App />
        </MemoryRouter>,
      )

      // Verify loading terminates and error screen appears with Try Again button
      await waitFor(() => {
        expect(
          screen.getByRole('heading', { name: /Unable to Load Complaint/i }),
        ).toBeInTheDocument()
      })
      expect(screen.queryByText(/Loading complaint details\.\.\./i)).not.toBeInTheDocument()
      expect(screen.getByText(/Database query timed out/i)).toBeInTheDocument()

      // Fix the error and register the complaint data for the retry
      mockComplaintDetailError = null
      mockComplaintsState = [unCachedComplaint, ...mockComplaintsState]
      fireEvent.click(screen.getByRole('button', { name: /Try Again/i }))

      // Complaint details load successfully on retry
      await waitFor(() => {
        expect(
          screen.getByRole('heading', { name: /Water pipe leaking under washbasin/i }),
        ).toBeInTheDocument()
      })
      expect(screen.queryByText(/Loading complaint details\.\.\./i)).not.toBeInTheDocument()
    })

    it('Test 5 — handles authentication delay and starts fetching once identity is ready', async () => {
      mockSessionUser = defaultStudentUser

      let resolveAuth
      const authPromise = new Promise((resolve) => {
        resolveAuth = resolve
      })

      const currentMock = globalThis.fetch.getMockImplementation()
      globalThis.fetch.mockImplementation((url, options = {}) => {
        const path = typeof url === 'string' ? url : url.toString()
        if (path === '/api/v1/auth/me') {
          return authPromise.then(() => currentMock(url, options))
        }
        return currentMock(url, options)
      })

      render(
        <MemoryRouter initialEntries={['/student/complaints/CMP-2026-089']}>
          <App />
        </MemoryRouter>,
      )

      // Auth is still restoring
      expect(screen.getByText(/Restoring HostelCare session\.\.\./i)).toBeInTheDocument()

      // Resolve authentication
      resolveAuth()

      // Complaint details load without remaining stuck
      await waitFor(() => {
        expect(
          screen.getByRole('heading', { name: /Ceiling fan making clicking noise/i }),
        ).toBeInTheDocument()
      })
      expect(screen.queryByText(/Loading complaint details\.\.\./i)).not.toBeInTheDocument()
    })

    it('scrubs legacy Warden Note and Instructions suffixes from student complaint history timeline', async () => {
      mockSessionUser = defaultStudentUser
      mockComplaintsState = [
        {
          id: 'CMP-2026-00001',
          studentId: defaultStudentUser.id,
          studentName: defaultStudentUser.fullName,
          studentRoll: defaultStudentUser.rollNumber,
          title: 'Ceiling fan making clicking noise',
          category: 'Electrical',
          priority: 'high',
          status: 'assigned',
          room: 'A-204',
          block: 'Aryabhatta Block',
          description: 'Fan wobbles at speed 3 and clicks.',
          date: '01/04/2026',
          history: [
            {
              id: 1,
              actionCode: 'assigned',
              action: 'Assigned to Duty Staff',
              actor: 'Dr. K. S. Verma',
              timestamp: '01/04/2026, 11:00 AM',
              note: 'Assigned to Ramesh Babu (Electrician). Warden Note: Fix it as soon as possible',
            },
            {
              id: 2,
              actionCode: 'reassigned',
              action: 'Reassigned Duty Staff',
              actor: 'Dr. K. S. Verma',
              timestamp: '01/04/2026, 12:00 PM',
              note: 'Reassigned from Ramesh Babu to Santosh Kumar (Plumber). Instructions: Private instruction',
            },
          ],
        },
      ]

      render(
        <MemoryRouter initialEntries={['/student/complaints/CMP-2026-00001']}>
          <App />
        </MemoryRouter>,
      )

      await waitFor(() => {
        expect(screen.getByText('Assigned to Ramesh Babu (Electrician).')).toBeInTheDocument()
      })
      expect(
        screen.getByText('Reassigned from Ramesh Babu to Santosh Kumar (Plumber).'),
      ).toBeInTheDocument()
      expect(screen.queryByText(/Warden Note/i)).not.toBeInTheDocument()
      expect(screen.queryByText(/Fix it as soon as possible/i)).not.toBeInTheDocument()
      expect(screen.queryByText(/Private instruction/i)).not.toBeInTheDocument()
    })
  })

  describe('Admin Complaint Queue Wing/Block Filter', () => {
    it('populates block filter from real blocks API without hardcoded placeholders and supports filtering', async () => {
      mockSessionUser = defaultAdminUser
      mockBlocksState = [{ id: 1, code: 'BLKA', name: 'Block A', is_active: true }]
      mockComplaintsState = [
        {
          id: 'CMP-2026-00001',
          studentId: defaultStudentUser.id,
          studentName: defaultStudentUser.fullName,
          studentRoll: defaultStudentUser.rollNumber,
          title: 'Fan noise in Block A',
          category: 'Electrical',
          priority: 'High',
          status: 'Submitted',
          room: 'A-101',
          block: 'Block A',
          description: 'Fan clicking.',
          date: '15/11/2026',
        },
        {
          id: 'CMP-2026-00002',
          studentId: defaultStudentUser.id,
          studentName: defaultStudentUser.fullName,
          studentRoll: defaultStudentUser.rollNumber,
          title: 'Common corridor light out',
          category: 'Electrical',
          priority: 'Medium',
          status: 'Submitted',
          room: 'B-201',
          block: '',
          description: 'No block set on record.',
          date: '15/11/2026',
        },
      ]

      render(
        <MemoryRouter initialEntries={['/admin/complaints']}>
          <App />
        </MemoryRouter>,
      )

      const blockSelect = await screen.findByLabelText(/Filter by block/i)
      await waitFor(() => {
        const optionLabels = Array.from(blockSelect.options).map((o) => o.textContent)
        expect(optionLabels).toEqual(['All Wings/Blocks', 'Block A'])
      })

      const optionLabels = Array.from(blockSelect.options).map((o) => o.textContent)
      expect(optionLabels).not.toContain('Aryabhatta Block')
      expect(optionLabels).not.toContain('Block B')
      expect(optionLabels).not.toContain('Block C')

      // Both complaints visible under All Wings/Blocks
      expect(screen.getByText('Fan noise in Block A')).toBeInTheDocument()
      expect(screen.getByText('Common corridor light out')).toBeInTheDocument()

      // Filter by Block A shows only Block A complaint
      fireEvent.change(blockSelect, { target: { value: 'Block A' } })
      expect(screen.getByText('Fan noise in Block A')).toBeInTheDocument()
      expect(screen.queryByText('Common corridor light out')).not.toBeInTheDocument()

      // Filter back to All Wings/Blocks restores all complaints
      fireEvent.change(blockSelect, { target: { value: 'ALL' } })
      expect(screen.getByText('Fan noise in Block A')).toBeInTheDocument()
      expect(screen.getByText('Common corridor light out')).toBeInTheDocument()
    })

    it('does not generate synthetic block options when blocks list is empty and complaint block is missing', async () => {
      mockSessionUser = defaultAdminUser
      mockBlocksState = []
      mockComplaintsState = [
        {
          id: 'CMP-2026-00003',
          studentId: defaultStudentUser.id,
          studentName: defaultStudentUser.fullName,
          studentRoll: defaultStudentUser.rollNumber,
          title: 'Unassigned wing tap leak',
          category: 'Plumbing',
          priority: 'Low',
          status: 'Submitted',
          room: 'B-105',
          block: '',
          description: 'Missing block field should not synthesize Block B.',
          date: '15/11/2026',
        },
      ]

      render(
        <MemoryRouter initialEntries={['/admin/complaints']}>
          <App />
        </MemoryRouter>,
      )

      const blockSelect = await screen.findByLabelText(/Filter by block/i)
      await waitFor(() => {
        expect(screen.getByText('Unassigned wing tap leak')).toBeInTheDocument()
      })

      const optionLabels = Array.from(blockSelect.options).map((o) => o.textContent)
      expect(optionLabels).toEqual(['All Wings/Blocks'])
      expect(optionLabels).not.toContain('Aryabhatta Block')
      expect(optionLabels).not.toContain('Block A')
      expect(optionLabels).not.toContain('Block B')
      expect(optionLabels).not.toContain('Block C')
    })
  })

  describe('Phase 3E.4 Fines, Disputes & Payments Integration', () => {
    it('allows admin to issue a fine with ISO dates and prevents duplicate submission', async () => {
      mockSessionUser = defaultAdminUser
      render(
        <MemoryRouter initialEntries={['/admin/fines/new']}>
          <App />
        </MemoryRouter>,
      )

      await waitFor(() => {
        expect(
          screen.getByRole('heading', { name: /Issue Disciplinary Fine Notice/i }),
        ).toBeInTheDocument()
      })

      const studentBtn = await screen.findByText(defaultStudentUser.fullName)
      fireEvent.click(studentBtn)

      const descArea = screen.getByPlaceholderText(/Describe in exact factual detail/i)
      fireEvent.change(descArea, {
        target: { value: 'Unauthorized 1500W immersion heater found during inspection.' },
      })

      const submitBtn = screen.getByRole('button', { name: /Issue Disciplinary Notice/i })
      fireEvent.click(submitBtn)

      await waitFor(() => {
        expect(screen.getByText(/Fine Notice: FIN-2026-00001/i)).toBeInTheDocument()
      })
      expect(mockFinesState.length).toBe(1)
      expect(mockFinesState[0].issueDate).toMatch(/^\d{4}-\d{2}-\d{2}$/)
      expect(mockFinesState[0].dueDate).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    })

    it('supports admin fine listing error retry and manual payment recording with receipt modal', async () => {
      mockSessionUser = defaultAdminUser
      mockFinesError = { status: 500, message: 'Database unavailable' }

      render(
        <MemoryRouter initialEntries={['/admin/fines']}>
          <App />
        </MemoryRouter>,
      )

      await waitFor(() => {
        expect(screen.getByText(/Database unavailable/i)).toBeInTheDocument()
      })

      mockFinesError = null
      mockFinesState = [
        {
          id: 'fine-10',
          referenceNo: 'FIN-2026-00010',
          studentId: defaultStudentUser.id,
          studentName: defaultStudentUser.fullName,
          studentRoll: defaultStudentUser.rollNumber,
          room: 'A-204',
          block: 'Block A',
          category: 'Noise & Silent Hours',
          description: 'Loud music after midnight curfew.',
          amountInr: '500.00',
          amount: 500,
          issueDate: '2026-11-10',
          dueDate: '2026-11-24',
          issuedBy: 'Chief Warden',
          status: 'pending',
          dispute: null,
          history: [],
        },
      ]

      fireEvent.click(screen.getByRole('button', { name: /Retry/i }))

      await waitFor(() => {
        expect(screen.getByText('FIN-2026-00010')).toBeInTheDocument()
      })

      fireEvent.click(screen.getByRole('link', { name: /Manage/i }))

      await waitFor(() => {
        expect(screen.getByText(/Fine Notice: FIN-2026-00010/i)).toBeInTheDocument()
      })

      fireEvent.click(screen.getByRole('button', { name: /Record Payment/i }))

      const refInput = screen.getByPlaceholderText(/CASH-REG-104/i)
      fireEvent.change(refInput, { target: { value: 'CASH-2026-99' } })
      fireEvent.click(screen.getByRole('checkbox'))
      fireEvent.click(screen.getByRole('button', { name: /Confirm Full Payment/i }))

      await waitFor(() => {
        expect(screen.getByText(/Official Payment Receipt/i)).toBeInTheDocument()
      })
      expect(screen.getByText('RCP-2026-00001')).toBeInTheDocument()
      expect(screen.getAllByText('CASH-2026-99').length).toBeGreaterThan(0)
    })

    it('allows admin to review and approve/reject a dispute from the dispute queue', async () => {
      mockSessionUser = defaultAdminUser
      mockFinesState = [
        {
          id: 'fine-20',
          referenceNo: 'FIN-2026-00020',
          studentId: defaultStudentUser.id,
          studentName: defaultStudentUser.fullName,
          studentRoll: defaultStudentUser.rollNumber,
          room: 'A-204',
          block: 'Block A',
          category: 'Mess Discipline',
          description: 'Missed mess biometric sign-out.',
          amountInr: '300.00',
          amount: 300,
          issueDate: '2026-11-11',
          dueDate: '2026-11-25',
          issuedBy: 'Chief Warden',
          status: 'disputed',
          dispute: {
            id: 'DSP-20',
            status: 'open',
            reason: 'Biometric terminal was offline at 9:30 PM.',
            createdAt: '2026-11-12 10:00',
          },
          history: [],
        },
      ]

      render(
        <MemoryRouter initialEntries={['/admin/fine-disputes']}>
          <App />
        </MemoryRouter>,
      )

      await waitFor(() => {
        expect(screen.getByText('FIN-2026-00020')).toBeInTheDocument()
      })

      fireEvent.click(screen.getByRole('button', { name: /Adjudicate Now/i }))
      fireEvent.change(screen.getByPlaceholderText(/State the findings/i), {
        target: { value: 'Verified mess log outage on 11 Nov.' },
      })
      fireEvent.click(screen.getByRole('button', { name: /Commit Determination/i }))

      await waitFor(() => {
        expect(screen.getByText(/Dispute decision recorded as Approved/i)).toBeInTheDocument()
      })
    })

    it('allows student to submit a dispute, blocks IDOR 403 access, and renders receipt in history', async () => {
      mockSessionUser = defaultStudentUser
      mockFinesState = [
        {
          id: 'fine-30',
          referenceNo: 'FIN-2026-00030',
          studentId: defaultStudentUser.id,
          studentName: defaultStudentUser.fullName,
          studentRoll: defaultStudentUser.rollNumber,
          room: 'A-204',
          block: 'Block A',
          category: 'Sanitation & Cleanliness',
          description: 'Corridor trash bag left outside room.',
          amountInr: '250.00',
          amount: 250,
          issueDate: '2026-11-12',
          dueDate: '2026-11-26',
          issuedBy: 'Chief Warden',
          status: 'pending',
          dispute: null,
          history: [],
        },
        {
          id: 'fine-other',
          referenceNo: 'FIN-2026-00099',
          studentId: 'other-student-999',
          studentName: 'Other Student',
          studentRoll: '2026CSB9999',
          room: 'B-101',
          block: 'Block B',
          category: 'Noise',
          description: 'Other student fine.',
          amountInr: '400.00',
          amount: 400,
          issueDate: '2026-11-12',
          dueDate: '2026-11-26',
          issuedBy: 'Chief Warden',
          status: 'pending',
          dispute: null,
          history: [],
        },
      ]

      // 1. Student disputes own fine
      const { unmount } = render(
        <MemoryRouter initialEntries={['/student/fines/fine-30/dispute']}>
          <App />
        </MemoryRouter>,
      )

      await waitFor(() => {
        expect(screen.getByText(/Notice: FIN-2026-00030/i)).toBeInTheDocument()
      })

      fireEvent.change(screen.getByPlaceholderText(/Explain clearly what occurred/i), {
        target: { value: 'I was away at the library and did not leave any bag in the corridor.' },
      })
      fireEvent.click(screen.getByRole('button', { name: /Submit Formal Dispute/i }))

      await waitFor(() => {
        expect(screen.getByText(/Fine Notice: FIN-2026-00030/i)).toBeInTheDocument()
      })
      expect(mockFinesState[0].status).toBe('disputed')
      unmount()

      // 2. IDOR 403 check on another student's fine
      const { unmount: unmountIdor } = render(
        <MemoryRouter initialEntries={['/student/fines/fine-other']}>
          <App />
        </MemoryRouter>,
      )

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: /Access Restricted/i })).toBeInTheDocument()
      })
      unmountIdor()

      // 3. Student fine history & receipt modal
      mockFinesState[0].status = 'paid'
      mockFinesState[0].payment = {
        id: 'pay-30',
        status: 'completed',
        amountInr: '250.00',
        paymentMethod: 'upi',
        manualReference: 'UPI-REF-30',
        receiptNumber: 'RCP-2026-00030',
        paidAt: '2026-11-15 14:00',
      }
      mockFinePaymentsState['fine-30'] = [mockFinesState[0].payment]
      mockReceiptsState['RCP-2026-00030'] = {
        institution: 'HostelCare',
        receiptNumber: 'RCP-2026-00030',
        fineReference: 'FIN-2026-00030',
        studentName: defaultStudentUser.fullName,
        studentRoll: defaultStudentUser.rollNumber,
        fineCategory: 'Sanitation & Cleanliness',
        fineDescription: 'Corridor trash bag left outside room.',
        amountInr: '250.00',
        paymentMethod: 'upi',
        transactionReference: 'UPI-REF-30',
        paidAt: '2026-11-15 14:00',
        paymentStatus: 'completed',
      }

      render(
        <MemoryRouter initialEntries={['/student/fines/history']}>
          <App />
        </MemoryRouter>,
      )

      await waitFor(() => {
        expect(screen.getByText('FIN-2026-00030')).toBeInTheDocument()
      })

      fireEvent.click(screen.getByRole('button', { name: /View Receipt/i }))

      await waitFor(() => {
        expect(screen.getByText(/Official Payment Receipt/i)).toBeInTheDocument()
      })
      expect(screen.getByText('RCP-2026-00030')).toBeInTheDocument()
      expect(screen.getByText('UPI-REF-30')).toBeInTheDocument()
    })

    it('opens RCP-2026-00001 from Student Payment History when backend returns status "paid" and no nested fine.payment, and renders print-safe SVG logo', async () => {
      mockSessionUser = defaultStudentUser
      mockFinesState = [
        {
          id: 'FIN-2026-00001',
          referenceNo: 'FIN-2026-00001',
          studentId: defaultStudentUser.id,
          studentName: 'Mangal Pandey',
          studentRoll: defaultStudentUser.rollNumber,
          room: 'A-204',
          block: 'Block A',
          category: 'Disciplinary Violation',
          description: 'Late hostel entry.',
          amountInr: '500.00',
          amount: 500,
          issueDate: '2026-11-10',
          dueDate: '2026-11-24',
          issuedByName: 'Chief Warden',
          status: 'paid',
          paidAt: '2026-11-16T01:00:00Z',
          dispute: null,
          history: [],
        },
      ]
      mockFinePaymentsState['FIN-2026-00001'] = [
        {
          id: 'pay-00001',
          receiptNumber: 'RCP-2026-00001',
          channel: 'manual',
          paymentMethod: 'upi',
          amountInr: '500.00',
          amount: 500,
          currency: 'INR',
          reference: 'TEST-UPI-001',
          status: 'paid',
          paidAt: '2026-11-16T01:00:00Z',
        },
      ]
      mockReceiptsState['RCP-2026-00001'] = {
        institution: 'HostelCare',
        receiptNumber: 'RCP-2026-00001',
        fineReference: 'FIN-2026-00001',
        studentName: 'Mangal Pandey',
        studentRoll: defaultStudentUser.rollNumber,
        fineCategory: 'Disciplinary Violation',
        fineDescription: 'Late hostel entry.',
        amountInr: '500.00',
        paymentMethod: 'upi',
        transactionReference: 'TEST-UPI-001',
        paidAt: '2026-11-16T01:00:00Z',
        paymentStatus: 'paid',
      }

      render(
        <MemoryRouter initialEntries={['/student/fines/history']}>
          <App />
        </MemoryRouter>,
      )

      await waitFor(() => {
        expect(screen.getByText('FIN-2026-00001')).toBeInTheDocument()
      })

      fireEvent.click(screen.getByRole('button', { name: /View Receipt/i }))

      await waitFor(() => {
        expect(screen.getByText(/Official Payment Receipt/i)).toBeInTheDocument()
      })
      expect(screen.getByText('RCP-2026-00001')).toBeInTheDocument()
      expect(screen.getByText('TEST-UPI-001')).toBeInTheDocument()

      const fetchCalls = globalThis.fetch.mock.calls.map((c) => String(c[0]))
      expect(fetchCalls).toContain('/api/v1/student/fines/FIN-2026-00001/payments')
      expect(fetchCalls).toContain('/api/v1/student/receipts/RCP-2026-00001')

      // Print-safe SVG logo inside the receipt modal has explicit vector rect + linearGradient
      const dialog = screen.getByRole('dialog', { name: /Official Payment Receipt/i })
      const rect = dialog.querySelector('svg rect')
      expect(rect).not.toBeNull()
      expect(rect.getAttribute('fill')).toBe('url(#hostelcare-logo-grad)')
    })

    it('shows clear error in Student Payment History when receipt is genuinely missing', async () => {
      mockSessionUser = defaultStudentUser
      mockFinesState = [
        {
          id: 'FIN-2026-00002',
          referenceNo: 'FIN-2026-00002',
          studentId: defaultStudentUser.id,
          studentName: defaultStudentUser.fullName,
          studentRoll: defaultStudentUser.rollNumber,
          room: 'A-204',
          block: 'Block A',
          category: 'Noise',
          description: 'Corridor noise.',
          amountInr: '200.00',
          amount: 200,
          issueDate: '2026-11-10',
          dueDate: '2026-11-24',
          issuedByName: 'Chief Warden',
          status: 'paid',
          dispute: null,
          history: [],
        },
      ]
      mockFinePaymentsState['FIN-2026-00002'] = []

      render(
        <MemoryRouter initialEntries={['/student/fines/history']}>
          <App />
        </MemoryRouter>,
      )

      await waitFor(() => {
        expect(screen.getByText('FIN-2026-00002')).toBeInTheDocument()
      })

      fireEvent.click(screen.getByRole('button', { name: /View Receipt/i }))

      await waitFor(() => {
        expect(screen.getByText(/No receipt number found for this payment/i)).toBeInTheDocument()
      })
    })

    it('renders ReceiptModal on document.body, formats timestamp, omits redundant print action, and closes on Close', async () => {
      mockSessionUser = defaultStudentUser
      mockFinesState = [
        {
          id: 'FIN-2026-00001',
          referenceNo: 'FIN-2026-00001',
          studentId: defaultStudentUser.id,
          studentName: 'Mangal Pandey',
          studentRoll: defaultStudentUser.rollNumber,
          room: 'A-204',
          block: 'Block A',
          category: 'Disciplinary Violation',
          description: 'Late hostel entry.',
          amountInr: '500.00',
          amount: 500,
          issueDate: '2026-11-10',
          dueDate: '2026-11-24',
          issuedByName: 'Chief Warden',
          status: 'paid',
          paidAt: '2026-11-16T01:00:00Z',
          dispute: null,
          history: [],
        },
      ]
      mockFinePaymentsState['FIN-2026-00001'] = [
        {
          id: 'pay-00001',
          receiptNumber: 'RCP-2026-00001',
          channel: 'manual',
          paymentMethod: 'upi',
          amountInr: '500.00',
          amount: 500,
          currency: 'INR',
          reference: 'TEST-UPI-001',
          status: 'paid',
          paidAt: '2026-11-16T01:00:00Z',
        },
      ]
      mockReceiptsState['RCP-2026-00001'] = {
        institution: 'HostelCare',
        receiptNumber: 'RCP-2026-00001',
        fineReference: 'FIN-2026-00001',
        studentName: 'Mangal Pandey',
        studentRoll: defaultStudentUser.rollNumber,
        fineCategory: 'Disciplinary Violation',
        fineDescription: 'Late hostel entry.',
        amountInr: '500.00',
        paymentMethod: 'upi',
        transactionReference: 'TEST-UPI-001',
        paidAt: '2026-11-16T01:00:00Z',
        paymentStatus: 'paid',
      }

      const { container } = render(
        <MemoryRouter initialEntries={['/student/fines/FIN-2026-00001']}>
          <App />
        </MemoryRouter>,
      )

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /View Official Receipt/i })).toBeInTheDocument()
      })

      fireEvent.click(screen.getByRole('button', { name: /View Official Receipt/i }))

      await waitFor(() => {
        expect(
          screen.getByRole('dialog', { name: /Official Payment Receipt/i }),
        ).toBeInTheDocument()
      })

      const dialog = screen.getByRole('dialog', { name: /Official Payment Receipt/i })
      // Isolated as direct child of document.body, outside the app container
      expect(dialog.parentElement).toBe(document.body)
      expect(container.contains(dialog)).toBe(false)

      // Raw ISO timestamp is formatted into readable local date/time
      expect(dialog.textContent).not.toContain('2026-11-16T01:00:00Z')

      // Redundant print action is removed; Download PDF is present
      expect(screen.queryByRole('button', { name: /Print Receipt/i })).not.toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Download PDF/i })).toBeInTheDocument()

      // Closing receipt dismisses modal
      fireEvent.click(screen.getByRole('button', { name: /^Close$/i }))
      await waitFor(() => {
        expect(
          screen.queryByRole('dialog', { name: /Official Payment Receipt/i }),
        ).not.toBeInTheDocument()
      })
    })

    it('downloads official PDF receipt with correct endpoint and filename across Admin, Student Detail, and Student History, and handles download errors', async () => {
      const createObjectURLSpy = vi.fn(() => 'blob:http://localhost:5173/mock-pdf')
      const revokeObjectURLSpy = vi.fn()
      const origCreateObjectURL = URL.createObjectURL
      const origRevokeObjectURL = URL.revokeObjectURL
      URL.createObjectURL = createObjectURLSpy
      URL.revokeObjectURL = revokeObjectURLSpy

      const anchorClicks = []
      const origCreateElement = document.createElement.bind(document)
      const createElementSpy = vi.spyOn(document, 'createElement').mockImplementation((tagName) => {
        const el = origCreateElement(tagName)
        if (String(tagName).toLowerCase() === 'a') {
          el.click = () => {
            anchorClicks.push({ download: el.download, href: el.href })
          }
        }
        return el
      })

      try {
        mockFinesState = [
          {
            id: 'FIN-2026-00001',
            referenceNo: 'FIN-2026-00001',
            studentId: defaultStudentUser.id,
            studentName: 'Mangal Pandey',
            studentRoll: defaultStudentUser.rollNumber,
            room: 'A-204',
            block: 'Block A',
            category: 'Disciplinary Violation',
            description: 'Late hostel entry.',
            amountInr: '500.00',
            amount: 500,
            issueDate: '2026-11-10',
            dueDate: '2026-11-24',
            issuedBy: 'Chief Warden',
            issuedByName: 'Chief Warden',
            status: 'paid',
            paidAt: '2026-11-16T01:00:00Z',
            dispute: null,
            history: [],
          },
        ]
        mockFinePaymentsState['FIN-2026-00001'] = [
          {
            id: 'pay-00001',
            receiptNumber: 'RCP-2026-00001',
            channel: 'manual',
            paymentMethod: 'upi',
            amountInr: '500.00',
            amount: 500,
            currency: 'INR',
            reference: 'TEST-UPI-001',
            manualReference: 'TEST-UPI-001',
            status: 'paid',
            paidAt: '2026-11-16T01:00:00Z',
          },
        ]
        mockReceiptsState['RCP-2026-00001'] = {
          institution: 'HostelCare',
          receiptNumber: 'RCP-2026-00001',
          fineReference: 'FIN-2026-00001',
          studentName: 'Mangal Pandey',
          studentRoll: defaultStudentUser.rollNumber,
          fineCategory: 'Disciplinary Violation',
          fineDescription: 'Late hostel entry.',
          amountInr: '500.00',
          paymentMethod: 'upi',
          transactionReference: 'TEST-UPI-001',
          paidAt: '2026-11-16T01:00:00Z',
          paymentStatus: 'paid',
        }

        // 1. Admin Fine Detail -> Download PDF
        mockSessionUser = defaultAdminUser
        const adminRender = render(
          <MemoryRouter initialEntries={['/admin/fines/FIN-2026-00001']}>
            <App />
          </MemoryRouter>,
        )
        await waitFor(() => {
          expect(screen.getByRole('button', { name: /View Official Receipt/i })).toBeInTheDocument()
        })
        fireEvent.click(screen.getByRole('button', { name: /View Official Receipt/i }))
        await waitFor(() => {
          expect(screen.getByRole('button', { name: /Download PDF/i })).toBeInTheDocument()
        })
        fireEvent.click(screen.getByRole('button', { name: /Download PDF/i }))
        await waitFor(() => {
          expect(anchorClicks.length).toBe(1)
        })
        expect(anchorClicks[0].download).toBe('HostelCare-RCP-2026-00001.pdf')
        expect(globalThis.fetch.mock.calls.map((c) => String(c[0]))).toContain(
          '/api/v1/admin/receipts/RCP-2026-00001/pdf',
        )
        adminRender.unmount()

        // 2. Student Fine Detail -> Download PDF
        mockSessionUser = defaultStudentUser
        const studentDetailRender = render(
          <MemoryRouter initialEntries={['/student/fines/FIN-2026-00001']}>
            <App />
          </MemoryRouter>,
        )
        await waitFor(() => {
          expect(screen.getByRole('button', { name: /View Official Receipt/i })).toBeInTheDocument()
        })
        fireEvent.click(screen.getByRole('button', { name: /View Official Receipt/i }))
        await waitFor(() => {
          expect(screen.getByRole('button', { name: /Download PDF/i })).toBeInTheDocument()
        })
        fireEvent.click(screen.getByRole('button', { name: /Download PDF/i }))
        await waitFor(() => {
          expect(anchorClicks.length).toBe(2)
        })
        expect(anchorClicks[1].download).toBe('HostelCare-RCP-2026-00001.pdf')
        expect(globalThis.fetch.mock.calls.map((c) => String(c[0]))).toContain(
          '/api/v1/student/receipts/RCP-2026-00001/pdf',
        )
        studentDetailRender.unmount()

        // 3. Student Payment History -> Download PDF + Error state
        const studentHistoryRender = render(
          <MemoryRouter initialEntries={['/student/fines/history']}>
            <App />
          </MemoryRouter>,
        )
        await waitFor(() => {
          expect(screen.getByRole('button', { name: /View Receipt/i })).toBeInTheDocument()
        })
        fireEvent.click(screen.getByRole('button', { name: /View Receipt/i }))
        await waitFor(() => {
          expect(screen.getByRole('button', { name: /Download PDF/i })).toBeInTheDocument()
        })
        fireEvent.click(screen.getByRole('button', { name: /Download PDF/i }))
        await waitFor(() => {
          expect(anchorClicks.length).toBe(3)
        })
        expect(anchorClicks[2].download).toBe('HostelCare-RCP-2026-00001.pdf')

        // Error state when PDF endpoint fails
        mockReceiptPdfError = { status: 500, message: 'PDF generator failed.' }
        fireEvent.click(screen.getByRole('button', { name: /Download PDF/i }))
        await waitFor(() => {
          expect(screen.getByText(/PDF generator failed\./i)).toBeInTheDocument()
        })
        expect(revokeObjectURLSpy).toHaveBeenCalledTimes(3)
        studentHistoryRender.unmount()
      } finally {
        createElementSpy.mockRestore()
        URL.createObjectURL = origCreateObjectURL
        URL.revokeObjectURL = origRevokeObjectURL
      }
    })

    it('supports student Razorpay online checkout, cancellation handling, verification errors, and admin online channel visibility', async () => {
      mockSessionUser = {
        id: 'stu-rzp-1',
        email: 'aarav.rzp@hostelcare.test',
        fullName: 'Aarav Sharma',
        rollNumber: 'CS26B001',
        role: 'student',
        status: 'active',
        roomNumber: '101',
        block: 'A',
      }
      mockFinesState = [
        {
          id: 'FIN-2026-00010',
          referenceNo: 'FIN-2026-00010',
          studentId: 'stu-rzp-1',
          studentName: 'Aarav Sharma',
          studentRoll: 'CS26B001',
          room: '101',
          block: 'A',
          category: 'Curfew Delay',
          description: 'Returned after midnight.',
          amountInr: '500.00',
          amount: 500,
          issueDate: '2026-11-14',
          dueDate: '2026-11-20',
          status: 'pending',
          issuedBy: 'Chief Warden',
          dispute: null,
          history: [],
        },
        {
          id: 'FIN-2026-00011',
          referenceNo: 'FIN-2026-00011',
          studentId: 'stu-rzp-1',
          studentName: 'Aarav Sharma',
          studentRoll: 'CS26B001',
          category: 'Room Inspection',
          description: 'Disputed penalty.',
          amountInr: '250.00',
          amount: 250,
          issueDate: '2026-11-14',
          dueDate: '2026-11-20',
          status: 'disputed',
          issuedBy: 'Chief Warden',
          dispute: { id: 'DSP-1', status: 'open', reason: 'Wrong room.' },
          history: [],
        },
      ]

      const origRazorpay = window.Razorpay
      let lastRazorpayOptions = null
      window.Razorpay = class MockRazorpay {
        constructor(options) {
          lastRazorpayOptions = options
        }
        on() {}
        open() {}
      }

      try {
        // 1. StudentFinesPage renders Pay Now on pending fine only (not on disputed fine)
        const listRender = render(
          <MemoryRouter initialEntries={['/student/fines']}>
            <App />
          </MemoryRouter>,
        )
        await waitFor(() => {
          expect(screen.getByText('FIN-2026-00010')).toBeInTheDocument()
        })
        const payButtons = screen.getAllByRole('button', { name: /^Pay Now$/i })
        expect(payButtons).toHaveLength(1)
        listRender.unmount()

        // 2. StudentFineDetailPage: dismiss checkout -> logs cancellation and leaves fine pending
        const detailRender = render(
          <MemoryRouter initialEntries={['/student/fines/FIN-2026-00010']}>
            <App />
          </MemoryRouter>,
        )
        await waitFor(() => {
          expect(screen.getByRole('button', { name: /^Pay Now$/i })).toBeInTheDocument()
        })
        fireEvent.click(screen.getByRole('button', { name: /^Pay Now$/i }))
        await waitFor(() => {
          expect(lastRazorpayOptions?.order_id).toBe('order_TestRzp123')
        })
        expect(lastRazorpayOptions.amount).toBe(50000)

        await act(async () => {
          await lastRazorpayOptions.modal.ondismiss()
        })
        await waitFor(() => {
          expect(
            screen.getByText(/Checkout cancelled\. No payment was captured\./i),
          ).toBeInTheDocument()
        })

        // 3. Re-click Pay Now and trigger invalid signature error -> error shown cleanly
        fireEvent.click(screen.getByRole('button', { name: /^Pay Now$/i }))
        await waitFor(() => {
          expect(lastRazorpayOptions?.order_id).toBe('order_TestRzp123')
        })
        await act(async () => {
          await lastRazorpayOptions.handler({
            razorpay_order_id: 'order_TestRzp123',
            razorpay_payment_id: 'pay_Bad001',
            razorpay_signature: 'bad_sig',
          })
        })
        await waitFor(() => {
          expect(screen.getByText(/Payment signature verification failed\./i)).toBeInTheDocument()
        })

        // 4. Successful Razorpay handler -> verifies payment, settles fine, opens official receipt
        fireEvent.click(screen.getByRole('button', { name: /^Pay Now$/i }))
        await waitFor(() => {
          expect(lastRazorpayOptions?.order_id).toBe('order_TestRzp123')
        })
        await act(async () => {
          await lastRazorpayOptions.handler({
            razorpay_order_id: 'order_TestRzp123',
            razorpay_payment_id: 'pay_Good001',
            razorpay_signature: 'valid_sig',
          })
        })
        let receiptDialog
        await waitFor(() => {
          receiptDialog = screen.getByRole('dialog', { name: /Official Payment Receipt/i })
          expect(receiptDialog).toBeInTheDocument()
        })
        expect(within(receiptDialog).getByText('pay_Good001')).toBeInTheDocument()
        detailRender.unmount()

        // 5. AdminFineDetailPage displays Online (Razorpay) channel and gateway order/payment IDs
        mockSessionUser = {
          id: 'admin-1',
          email: 'warden@hostelcare.test',
          fullName: 'Chief Warden',
          role: 'admin',
          status: 'active',
        }
        const adminRender = render(
          <MemoryRouter initialEntries={['/admin/fines/FIN-2026-00010']}>
            <App />
          </MemoryRouter>,
        )
        await waitFor(() => {
          expect(screen.getByText(/Online \(Razorpay\)/i)).toBeInTheDocument()
        })
        expect(screen.getByText(/pay_Good001/i)).toBeInTheDocument()
        expect(screen.getByText(/Order: order_TestRzp123/i)).toBeInTheDocument()
        adminRender.unmount()
      } finally {
        window.Razorpay = origRazorpay
      }
    })
  })
})
