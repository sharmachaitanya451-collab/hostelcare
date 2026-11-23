import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import App from './App.jsx'

const ADMIN_USER = {
  id: 'adm-1',
  role: 'admin',
  status: 'active',
  fullName: 'Dr. K. S. Verma',
  email: 'warden@hostelcare.in',
  designation: 'Chief Hostel Warden',
}

function jsonResponse(body, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    headers: {
      get: (key) => {
        const lower = key.toLowerCase()
        if (lower === 'content-type') return 'application/json'
        if (lower === 'x-csrf-token') return 'test-csrf-token'
        return null
      },
    },
    json: () => Promise.resolve(body),
  })
}

function makeOverviewPayload(overrides = {}) {
  return {
    dateRange: {
      preset: '30d',
      dateFrom: '2026-10-20',
      dateTo: '2026-11-18',
      timezone: 'Asia/Kolkata',
      ...overrides.dateRange,
    },
    complaints: {
      total: 14,
      newSubmissions: 4,
      underReview: 2,
      assigned: 2,
      accepted: 1,
      inProgress: 2,
      completed: 1,
      closed: 1,
      rejected: 1,
      unassigned: 6,
      resolved: 2,
      byStatus: {
        submitted: 4,
        under_review: 2,
        assigned: 2,
        accepted: 1,
        in_progress: 2,
        completed: 1,
        closed: 1,
        rejected: 1,
      },
      ...overrides.complaints,
    },
    approvals: {
      pendingCount: 3,
      approvedCount: 42,
      rejectedCount: 1,
      totalStudents: 46,
      ...overrides.approvals,
    },
    occupancy: {
      referenceDate: '2026-11-18',
      totalCapacity: 100,
      occupiedBeds: 75,
      vacantBeds: 25,
      occupancyRate: 75.0,
      activeRoomsCount: 50,
      blocks: [
        {
          blockId: 1,
          code: 'A',
          name: 'Block A - Aryabhatta',
          activeRoomsCount: 25,
          totalCapacity: 50,
          occupiedBeds: 40,
          vacantBeds: 10,
          occupancyRate: 80.0,
        },
        {
          blockId: 2,
          code: 'B',
          name: 'Block B - Bhaskara',
          activeRoomsCount: 25,
          totalCapacity: 50,
          occupiedBeds: 35,
          vacantBeds: 15,
          occupancyRate: 70.0,
        },
      ],
      ...overrides.occupancy,
    },
    residents: {
      activeCount: 74,
      ...overrides.residents,
    },
    finances: {
      leviedAmount: 4500,
      leviedAmountInr: '4500.00',
      leviedCount: 5,
      collectedAmount: 3000,
      collectedAmountInr: '3000.00',
      collectedCount: 3,
      outstandingAmount: 1500,
      outstandingAmountInr: '1500.00',
      outstandingCount: 2,
      waivedAmount: 250,
      waivedAmountInr: '250.00',
      waivedCount: 1,
      cancelledAmount: 0,
      cancelledAmountInr: '0.00',
      cancelledCount: 0,
      pendingDisputesCount: 1,
      ...overrides.finances,
    },
    recentActivity:
      overrides.recentActivity !== undefined
        ? overrides.recentActivity
        : [
            {
              id: 'CMP-2026-00014',
              referenceNo: 'CMP-2026-00014',
              room: 'A-101',
              block: 'Block A - Aryabhatta',
              category: 'Electrical',
              title: 'Ceiling fan speed regulator sparking',
              assignedStaff: 'Ramesh Kumar',
              priority: 'High',
              rawPriority: 'high',
              status: 'In Progress',
              rawStatus: 'in_progress',
              createdAt: '2026-11-17T10:30:00+00:00',
            },
          ],
  }
}

function makeComplaintAnalyticsPayload(overrides = {}) {
  return {
    dateRange: {
      preset: '30d',
      dateFrom: '2026-10-20',
      dateTo: '2026-11-18',
      timezone: 'Asia/Kolkata',
      ...overrides.dateRange,
    },
    categories:
      overrides.categories !== undefined
        ? overrides.categories
        : [
            { category: 'Electrical', count: 8, percentage: 57.1 },
            { category: 'Plumbing', count: 6, percentage: 42.9 },
          ],
    trends: overrides.trends || {
      interval: 'daily',
      series: [
        { period: '2026-11-16', label: '16 Nov', submitted: 3, completed: 1 },
        { period: '2026-11-17', label: '17 Nov', submitted: 5, completed: 3 },
        { period: '2026-11-18', label: '18 Nov', submitted: 6, completed: 4 },
      ],
    },
    resolution: {
      completedCount: 8,
      averageSeconds: 66600,
      averageHours: 18.5,
      medianSeconds: 43200,
      medianHours: 12.0,
      ...overrides.resolution,
    },
    sla: {
      eligibleCount: 13,
      activeOverdue: 2,
      activeWithinSla: 3,
      completedWithinSla: 6,
      completedAfterSla: 1,
      complianceRate: 85.7,
      byPriority: [
        {
          priority: 'high',
          label: 'High',
          targetHours: 24,
          total: 6,
          activeOverdue: 2,
          activeWithinSla: 1,
          completedWithinSla: 2,
          completedAfterSla: 1,
          complianceRate: 66.7,
        },
        {
          priority: 'medium',
          label: 'Medium',
          targetHours: 72,
          total: 4,
          activeOverdue: 0,
          activeWithinSla: 1,
          completedWithinSla: 2,
          completedAfterSla: 1,
          complianceRate: 66.7,
        },
        {
          priority: 'low',
          label: 'Low',
          targetHours: 168,
          total: 3,
          activeOverdue: 0,
          activeWithinSla: 1,
          completedWithinSla: 2,
          completedAfterSla: 0,
          complianceRate: 100.0,
        },
      ],
      ...overrides.sla,
    },
    staff:
      overrides.staff !== undefined
        ? overrides.staff
        : [
            {
              staffId: 'stf-uuid-1',
              staffCode: 'STF-0001',
              name: 'Ramesh Kumar',
              trade: 'Electrical',
              activeAssigned: 3,
              assignedTasks: 1,
              acceptedTasks: 1,
              inProgressTasks: 1,
              completedCount: 6,
              avgCompletionSeconds: 21600,
              avgCompletionHours: 6.0,
              avgAcceptanceSeconds: 3600,
              avgAcceptanceHours: 1.0,
              workloadIndicator: 'Busy',
            },
            {
              staffId: 'stf-uuid-2',
              staffCode: 'STF-0002',
              name: 'Suresh Nair',
              trade: 'Plumbing',
              activeAssigned: 0,
              assignedTasks: 0,
              acceptedTasks: 0,
              inProgressTasks: 0,
              completedCount: 2,
              avgCompletionSeconds: 18000,
              avgCompletionHours: 5.0,
              avgAcceptanceSeconds: 1800,
              avgAcceptanceHours: 0.5,
              workloadIndicator: 'Available',
            },
          ],
  }
}

describe('Phase 4.1 Admin Dashboard & KPI Engine', () => {
  let overviewHandler
  let complaintAnalyticsHandler
  let complaintsListHandler
  let fetchSpy

  beforeEach(() => {
    overviewHandler = () => jsonResponse(makeOverviewPayload(), 200)
    complaintAnalyticsHandler = () => jsonResponse(makeComplaintAnalyticsPayload(), 200)
    complaintsListHandler = () => []

    fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      const path = typeof url === 'string' ? url : url.toString()

      if (path === '/api/v1/auth/me') {
        return jsonResponse({ user: ADMIN_USER, csrf_token: 'test-csrf-token' }, 200)
      }
      if (path.startsWith('/api/v1/admin/analytics/overview')) {
        return overviewHandler(path)
      }
      if (path.startsWith('/api/v1/admin/analytics/complaints')) {
        return complaintAnalyticsHandler(path)
      }
      if (path.startsWith('/api/v1/notifications')) {
        return jsonResponse({ notifications: [], unreadCount: 0 }, 200)
      }
      if (path.startsWith('/api/v1/admin/complaints/')) {
        const cid = decodeURIComponent(path.split('/').pop())
        return jsonResponse(
          {
            complaint: {
              id: cid,
              referenceNo: cid,
              title: 'Ceiling fan speed regulator sparking',
              category: 'Electrical',
              priority: 'High',
              status: 'In Progress',
              room: 'A-101',
              block: 'Block A - Aryabhatta',
              studentName: 'Aarav Sharma',
              studentRoll: '2026CSB1042',
              description: 'Regulator is sparking when turned on.',
              history: [],
              updates: [],
              internalNotes: [],
            },
          },
          200,
        )
      }
      if (path.startsWith('/api/v1/admin/complaints')) {
        return jsonResponse({ complaints: complaintsListHandler() }, 200)
      }
      if (path.startsWith('/api/v1/admin/fines')) {
        return jsonResponse(
          { fines: [], pagination: { page: 1, pageSize: 20, total: 0, totalPages: 1 } },
          200,
        )
      }
      if (path.startsWith('/api/v1/admin/students')) {
        return jsonResponse({ students: [] }, 200)
      }
      if (path.startsWith('/api/v1/admin/staff')) {
        return jsonResponse({ staff: [] }, 200)
      }
      if (path.startsWith('/api/v1/admin/audit-logs')) {
        return jsonResponse({ audit_logs: [] }, 200)
      }
      if (path.startsWith('/api/v1/admin/rooms')) {
        return jsonResponse({ rooms: [] }, 200)
      }
      if (path.startsWith('/api/v1/admin/blocks')) {
        return jsonResponse({ blocks: [] }, 200)
      }
      if (path.startsWith('/api/v1/admin/room-allocations')) {
        return jsonResponse({ allocations: [] }, 200)
      }
      return jsonResponse({}, 200)
    })
  })

  it('loads authoritative KPI values, occupancy, finances, and recent activity from backend API', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/dashboard']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('Hostel Operations & Maintenance Dashboard')).toBeInTheDocument()
      expect(screen.getByText('14')).toBeInTheDocument() // Total complaints from API (even though AppContext complaints array is [])
    })

    // Pending approvals alert driven by API count (3)
    expect(
      screen.getByText(/3 Student Registration\(s\) Awaiting Warden Verification/i),
    ).toBeInTheDocument()

    // Occupancy stats
    expect(screen.getByText('Hostel Occupancy Overview')).toBeInTheDocument()
    expect(screen.getByText('100')).toBeInTheDocument() // Total beds
    expect(screen.getByText('75')).toBeInTheDocument() // Occupied beds
    expect(screen.getByText('25')).toBeInTheDocument() // Vacant beds
    expect(screen.getByText('75%')).toBeInTheDocument()
    expect(screen.getByText(/Block A - Aryabhatta/i)).toBeInTheDocument()
    expect(screen.getByText(/Block B - Bhaskara/i)).toBeInTheDocument()

    // Financial stats formatted in INR
    expect(screen.getByText('Disciplinary Fines & Collections')).toBeInTheDocument()
    expect(screen.getByText(/₹4,500\.00/)).toBeInTheDocument()
    expect(screen.getByText(/₹3,000\.00/)).toBeInTheDocument()
    expect(screen.getByText(/₹1,500\.00/)).toBeInTheDocument()
    expect(screen.getByText(/₹250\.00/)).toBeInTheDocument()

    // Recent complaint row & Inspect navigation
    expect(screen.getByText('CMP-2026-00014')).toBeInTheDocument()
    expect(screen.getByText('Ceiling fan speed regulator sparking')).toBeInTheDocument()

    const inspectBtn = screen.getByRole('button', { name: /Inspect/i })
    fireEvent.click(inspectBtn)

    await waitFor(() => {
      expect(screen.getByText(/CMP-2026-00014/i)).toBeInTheDocument()
    })

    // Verify no duplicate overview call on initial mount
    const overviewCalls = fetchSpy.mock.calls.filter(([url]) =>
      String(url).startsWith('/api/v1/admin/analytics/overview'),
    )
    expect(overviewCalls).toHaveLength(1)
    expect(overviewCalls[0][0]).toBe('/api/v1/admin/analytics/overview?preset=30d')
  })

  it('triggers API requests when changing presets and validates custom date ranges', async () => {
    overviewHandler = (path) => {
      if (path.includes('preset=7d')) {
        return jsonResponse(
          makeOverviewPayload({
            dateRange: { preset: '7d', dateFrom: '2026-11-12', dateTo: '2026-11-18' },
            complaints: { total: 5, newSubmissions: 1, unassigned: 1, inProgress: 1, resolved: 1 },
          }),
          200,
        )
      }
      if (path.includes('preset=custom')) {
        return jsonResponse(
          makeOverviewPayload({
            dateRange: { preset: 'custom', dateFrom: '2026-11-01', dateTo: '2026-11-10' },
            complaints: { total: 9, newSubmissions: 2, unassigned: 2, inProgress: 2, resolved: 3 },
          }),
          200,
        )
      }
      return jsonResponse(makeOverviewPayload(), 200)
    }

    render(
      <MemoryRouter initialEntries={['/admin/dashboard']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('14')).toBeInTheDocument()
    })

    // Switch to Last 7 Days
    fireEvent.click(screen.getByRole('button', { name: 'Last 7 Days' }))
    await waitFor(() => {
      expect(screen.getByText('5')).toBeInTheDocument()
    })
    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/v1/admin/analytics/overview?preset=7d',
      expect.any(Object),
    )

    // Switch to Custom Range and test client-side validation (reversed dates)
    fireEvent.click(screen.getByRole('button', { name: 'Custom Range' }))
    const fromInput = screen.getByLabelText('Date From')
    const toInput = screen.getByLabelText('Date To')
    fireEvent.change(fromInput, { target: { value: '2026-11-15' } })
    fireEvent.change(toInput, { target: { value: '2026-11-01' } })
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }))

    expect(screen.getByRole('alert')).toHaveTextContent(/Start date cannot be after end date/i)

    // Apply valid custom range
    fireEvent.change(fromInput, { target: { value: '2026-11-01' } })
    fireEvent.change(toInput, { target: { value: '2026-11-10' } })
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }))

    await waitFor(() => {
      expect(screen.getByText('9')).toBeInTheDocument()
    })
    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/v1/admin/analytics/overview?preset=custom&date_from=2026-11-01&date_to=2026-11-10',
      expect.any(Object),
    )
  })

  it('prevents stale responses from overwriting newer filter selections', async () => {
    let resolveSlow7d
    overviewHandler = (path) => {
      if (path.includes('preset=7d')) {
        return new Promise((resolve) => {
          resolveSlow7d = () =>
            resolve(
              jsonResponse(
                makeOverviewPayload({
                  dateRange: { preset: '7d', dateFrom: '2026-11-12', dateTo: '2026-11-18' },
                  complaints: { total: 999 },
                }),
                200,
              ),
            )
        })
      }
      if (path.includes('preset=this_month')) {
        return jsonResponse(
          makeOverviewPayload({
            dateRange: { preset: 'this_month', dateFrom: '2026-11-01', dateTo: '2026-11-18' },
            complaints: { total: 42 },
          }),
          200,
        )
      }
      return jsonResponse(makeOverviewPayload(), 200)
    }

    render(
      <MemoryRouter initialEntries={['/admin/dashboard']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('14')).toBeInTheDocument()
    })

    // Trigger slow 7d request, then immediately trigger faster this_month request
    fireEvent.click(screen.getByRole('button', { name: 'Last 7 Days' }))
    fireEvent.click(screen.getByRole('button', { name: 'This Month' }))

    await waitFor(() => {
      expect(screen.getByText('42')).toBeInTheDocument()
    })

    // Now resolve the older slower 7d request; it must NOT overwrite 42 with 999
    resolveSlow7d()
    await new Promise((r) => setTimeout(r, 30))
    expect(screen.getByText('42')).toBeInTheDocument()
    expect(screen.queryByText('999')).not.toBeInTheDocument()
  })

  it('displays error banner without fabricated zero cards and recovers on Retry', async () => {
    let shouldFail = true
    overviewHandler = () => {
      if (shouldFail) {
        return jsonResponse(
          { error: { code: 'internal_error', message: 'Database analytics unavailable' } },
          500,
        )
      }
      return jsonResponse(makeOverviewPayload(), 200)
    }

    render(
      <MemoryRouter initialEntries={['/admin/dashboard']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/Database analytics unavailable/i)
    })

    // Ensure no fabricated zero KPI cards are rendered
    expect(screen.queryByText('Total Complaints')).not.toBeInTheDocument()
    expect(screen.queryByText('Hostel Occupancy Overview')).not.toBeInTheDocument()

    // Recover on Retry
    shouldFail = false
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))

    await waitFor(() => {
      expect(screen.getByText('Total Complaints')).toBeInTheDocument()
      expect(screen.getByText('14')).toBeInTheDocument()
    })
  })

  it('renders clean empty states when database has zero complaints and blocks, preserving sidebar nav', async () => {
    overviewHandler = () =>
      jsonResponse(
        makeOverviewPayload({
          complaints: {
            total: 0,
            newSubmissions: 0,
            underReview: 0,
            assigned: 0,
            accepted: 0,
            inProgress: 0,
            completed: 0,
            closed: 0,
            rejected: 0,
            unassigned: 0,
            resolved: 0,
          },
          approvals: { pendingCount: 0, approvedCount: 0, rejectedCount: 0, totalStudents: 0 },
          occupancy: {
            referenceDate: '2026-11-18',
            totalCapacity: 0,
            occupiedBeds: 0,
            vacantBeds: 0,
            occupancyRate: 0,
            activeRoomsCount: 0,
            blocks: [],
          },
          residents: { activeCount: 0 },
          finances: {
            leviedAmount: 0,
            leviedAmountInr: '0.00',
            leviedCount: 0,
            collectedAmount: 0,
            collectedAmountInr: '0.00',
            collectedCount: 0,
            outstandingAmount: 0,
            outstandingAmountInr: '0.00',
            outstandingCount: 0,
            waivedAmount: 0,
            waivedAmountInr: '0.00',
            waivedCount: 0,
            cancelledAmount: 0,
            cancelledAmountInr: '0.00',
            cancelledCount: 0,
            pendingDisputesCount: 0,
          },
          recentActivity: [],
        }),
        200,
      )

    render(
      <MemoryRouter initialEntries={['/admin/dashboard']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('No active hostel blocks configured.')).toBeInTheDocument()
      expect(
        screen.getByText(
          'No maintenance complaints recorded during the selected reporting window.',
        ),
      ).toBeInTheDocument()
    })

    // Sidebar navigation remains intact
    const nav = screen.getByRole('navigation')
    expect(within(nav).getByText('Admin Overview')).toBeInTheDocument()
    expect(within(nav).getByText('Complaint Queue')).toBeInTheDocument()
    expect(within(nav).getByText('Room Occupancy Map')).toBeInTheDocument()
    expect(within(nav).getByText('Fines & Disciplinary')).toBeInTheDocument()
  })

  describe('Complaint KPI & Lifecycle Navigation to Complaint Queue', () => {
    const sampleQueueComplaints = [
      {
        id: 'CMP-2026-00001',
        title: 'Submitted Fan Issue',
        category: 'Electrical',
        priority: 'High',
        status: 'submitted',
        room: 'A-101',
        block: 'Block A',
        assignedStaff: null,
        description: 'Submitted complaint.',
      },
      {
        id: 'CMP-2026-00002',
        title: 'Under Review Pipe Leak',
        category: 'Plumbing',
        priority: 'Medium',
        status: 'under_review',
        room: 'A-102',
        block: 'Block A',
        assignedStaff: null,
        description: 'Under review complaint.',
      },
      {
        id: 'CMP-2026-00003',
        title: 'Assigned Door Lock',
        category: 'Carpentry',
        priority: 'Low',
        status: 'assigned',
        room: 'B-201',
        block: 'Block B',
        assignedStaff: 'Ramesh Kumar',
        description: 'Assigned complaint.',
      },
      {
        id: 'CMP-2026-00004',
        title: 'Accepted WiFi Drop',
        category: 'Internet',
        priority: 'Medium',
        status: 'accepted',
        room: 'B-202',
        block: 'Block B',
        assignedStaff: 'Ramesh Kumar',
        description: 'Accepted complaint.',
      },
      {
        id: 'CMP-2026-00005',
        title: 'In Progress MCB Repair',
        category: 'Electrical',
        priority: 'High',
        status: 'in_progress',
        room: 'A-103',
        block: 'Block A',
        assignedStaff: 'Ramesh Kumar',
        description: 'In progress complaint.',
      },
      {
        id: 'CMP-2026-00006',
        title: 'Completed Light Replacement',
        category: 'Electrical',
        priority: 'Low',
        status: 'completed',
        room: 'A-104',
        block: 'Block A',
        assignedStaff: 'Ramesh Kumar',
        description: 'Completed complaint.',
      },
      {
        id: 'CMP-2026-00007',
        title: 'Closed AC Servicing',
        category: 'Electrical',
        priority: 'Medium',
        status: 'closed',
        room: 'B-203',
        block: 'Block B',
        assignedStaff: 'Ramesh Kumar',
        description: 'Closed complaint.',
      },
      {
        id: 'CMP-2026-00008',
        title: 'Rejected Duplicate Report',
        category: 'General',
        priority: 'Low',
        status: 'rejected',
        room: 'A-105',
        block: 'Block A',
        assignedStaff: null,
        description: 'Rejected complaint without active staff.',
      },
    ]

    beforeEach(() => {
      complaintsListHandler = () => sampleQueueComplaints
    })

    it('Total Complaints KPI opens the unfiltered complaint queue showing all complaints', async () => {
      render(
        <MemoryRouter initialEntries={['/admin/dashboard']}>
          <App />
        </MemoryRouter>,
      )

      const link = await screen.findByRole('link', { name: /View all 14 complaints/i })
      expect(link).toHaveAttribute('href', '/admin/complaints')
      fireEvent.click(link)

      await waitFor(() => {
        expect(screen.getByText('Hostel Complaint Management')).toBeInTheDocument()
      })
      expect(screen.getByText('Submitted Fan Issue')).toBeInTheDocument()
      expect(screen.getByText('Under Review Pipe Leak')).toBeInTheDocument()
      expect(screen.getByText('Completed Light Replacement')).toBeInTheDocument()
      expect(screen.getByText('Closed AC Servicing')).toBeInTheDocument()
      expect(screen.getByText('Rejected Duplicate Report')).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Clear Filters' })).not.toBeInTheDocument()
    })

    it('New Submissions KPI navigates and applies submitted status filter, and Clear Filters resets', async () => {
      render(
        <MemoryRouter initialEntries={['/admin/dashboard']}>
          <App />
        </MemoryRouter>,
      )

      const link = await screen.findByRole('link', { name: /View 4 submitted complaints/i })
      expect(link).toHaveAttribute('href', '/admin/complaints?status=submitted')
      fireEvent.click(link)

      await waitFor(() => {
        expect(screen.getByText('Hostel Complaint Management')).toBeInTheDocument()
      })
      expect(screen.getByLabelText('Filter by status')).toHaveValue('submitted')
      expect(screen.getByText('Submitted Fan Issue')).toBeInTheDocument()
      expect(screen.queryByText('Under Review Pipe Leak')).not.toBeInTheDocument()
      expect(screen.getByText(/Status: Submitted \(New\)/i)).toBeInTheDocument()

      // Clear Filters returns to full queue
      fireEvent.click(screen.getByRole('button', { name: 'Clear Filters' }))
      await waitFor(() => {
        expect(screen.getByLabelText('Filter by status')).toHaveValue('ALL')
        expect(screen.getByText('Under Review Pipe Leak')).toBeInTheDocument()
      })
    })

    it('Unassigned KPI navigates and filters strictly active unassigned complaints (excluding rejected)', async () => {
      render(
        <MemoryRouter initialEntries={['/admin/dashboard']}>
          <App />
        </MemoryRouter>,
      )

      const link = await screen.findByRole('link', { name: /View 6 unassigned complaints/i })
      expect(link).toHaveAttribute('href', '/admin/complaints?staff=unassigned')
      fireEvent.click(link)

      await waitFor(() => {
        expect(screen.getByText('Hostel Complaint Management')).toBeInTheDocument()
      })
      expect(screen.getByLabelText('Filter by assigned staff')).toHaveValue('UNASSIGNED')
      expect(screen.getByText('Submitted Fan Issue')).toBeInTheDocument()
      expect(screen.getByText('Under Review Pipe Leak')).toBeInTheDocument()
      // Assigned & terminal (including unassigned rejected) are excluded
      expect(screen.queryByText('Assigned Door Lock')).not.toBeInTheDocument()
      expect(screen.queryByText('Rejected Duplicate Report')).not.toBeInTheDocument()
    })

    it('In Progress KPI navigates and applies in_progress status filter', async () => {
      render(
        <MemoryRouter initialEntries={['/admin/dashboard']}>
          <App />
        </MemoryRouter>,
      )

      const link = await screen.findByRole('link', { name: /View 2 in-progress complaints/i })
      expect(link).toHaveAttribute('href', '/admin/complaints?status=in_progress')
      fireEvent.click(link)

      await waitFor(() => {
        expect(screen.getByText('Hostel Complaint Management')).toBeInTheDocument()
      })
      expect(screen.getByLabelText('Filter by status')).toHaveValue('in_progress')
      expect(screen.getByText('In Progress MCB Repair')).toBeInTheDocument()
      expect(screen.queryByText('Accepted WiFi Drop')).not.toBeInTheDocument()
      expect(screen.queryByText('Submitted Fan Issue')).not.toBeInTheDocument()
    })

    it('Resolved KPI navigates and includes BOTH completed and closed complaints', async () => {
      render(
        <MemoryRouter initialEntries={['/admin/dashboard']}>
          <App />
        </MemoryRouter>,
      )

      const link = await screen.findByRole('link', {
        name: /View 2 resolved \(completed and closed\) complaints/i,
      })
      expect(link).toHaveAttribute('href', '/admin/complaints?status=completed,closed')
      fireEvent.click(link)

      await waitFor(() => {
        expect(screen.getByText('Hostel Complaint Management')).toBeInTheDocument()
      })
      expect(screen.getByLabelText('Filter by status')).toHaveValue('completed,closed')
      expect(screen.getByText('Completed Light Replacement')).toBeInTheDocument()
      expect(screen.getByText('Closed AC Servicing')).toBeInTheDocument()
      expect(screen.queryByText('Submitted Fan Issue')).not.toBeInTheDocument()
      expect(screen.queryByText('Rejected Duplicate Report')).not.toBeInTheDocument()
    })

    it.each([
      {
        label: 'Under Review',
        status: 'under_review',
        visible: 'Under Review Pipe Leak',
        hidden: 'Submitted Fan Issue',
      },
      {
        label: 'Assigned',
        status: 'assigned',
        visible: 'Assigned Door Lock',
        hidden: 'Accepted WiFi Drop',
      },
      {
        label: 'Accepted',
        status: 'accepted',
        visible: 'Accepted WiFi Drop',
        hidden: 'In Progress MCB Repair',
      },
      {
        label: 'Completed',
        status: 'completed',
        visible: 'Completed Light Replacement',
        hidden: 'Closed AC Servicing',
      },
      {
        label: 'Closed',
        status: 'closed',
        visible: 'Closed AC Servicing',
        hidden: 'Completed Light Replacement',
      },
      {
        label: 'Rejected',
        status: 'rejected',
        visible: 'Rejected Duplicate Report',
        hidden: 'Submitted Fan Issue',
      },
    ])(
      'Lifecycle breakdown item "$label" filters exact status "$status"',
      async ({ label, status, visible, hidden }) => {
        render(
          <MemoryRouter initialEntries={['/admin/dashboard']}>
            <App />
          </MemoryRouter>,
        )

        const link = await screen.findByRole('link', {
          name: new RegExp(`Filter complaint queue by ${label}`, 'i'),
        })
        expect(link).toHaveAttribute('href', `/admin/complaints?status=${status}`)
        fireEvent.click(link)

        await waitFor(() => {
          expect(screen.getByText('Hostel Complaint Management')).toBeInTheDocument()
        })
        expect(screen.getByLabelText('Filter by status')).toHaveValue(status)
        expect(screen.getByText(visible)).toBeInTheDocument()
        expect(screen.queryByText(hidden)).not.toBeInTheDocument()
      },
    )

    it('keeps zero-count KPI cards keyboard-focusable and navigable, and preserves existing filters + pagination reset', async () => {
      overviewHandler = () =>
        jsonResponse(
          makeOverviewPayload({
            complaints: {
              total: 0,
              newSubmissions: 0,
              underReview: 0,
              assigned: 0,
              accepted: 0,
              inProgress: 0,
              completed: 0,
              closed: 0,
              rejected: 0,
              unassigned: 0,
              resolved: 0,
            },
          }),
          200,
        )

      // Generate 25 complaints to test pagination + reset when filter applied
      const manyComplaints = Array.from({ length: 25 }, (_, idx) => ({
        id: `CMP-2026-${String(idx + 1).padStart(5, '0')}`,
        title: idx < 22 ? `Submitted Task ${idx + 1}` : `Closed Task ${idx + 1}`,
        category: idx % 2 === 0 ? 'Electrical' : 'Plumbing',
        priority: idx % 3 === 0 ? 'High' : 'Low',
        status: idx < 22 ? 'submitted' : 'closed',
        room: `A-${101 + idx}`,
        block: 'Block A',
        assignedStaff: idx < 22 ? null : 'Ramesh Kumar',
        description: `Details ${idx + 1}`,
      }))
      complaintsListHandler = () => manyComplaints

      render(
        <MemoryRouter initialEntries={['/admin/dashboard']}>
          <App />
        </MemoryRouter>,
      )

      // Zero-count KPI link still has link semantics, can receive focus, and navigates
      const zeroTotalLink = await screen.findByRole('link', { name: /View all 0 complaints/i })
      zeroTotalLink.focus()
      expect(document.activeElement).toBe(zeroTotalLink)
      fireEvent.click(zeroTotalLink)

      await waitFor(() => {
        expect(screen.getByText('Hostel Complaint Management')).toBeInTheDocument()
        expect(screen.getByText(/Page/i)).toHaveTextContent('Page 1 of 2')
      })

      // Go to Page 2
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))
      await waitFor(() => {
        expect(screen.getByText(/Page/i)).toHaveTextContent('Page 2 of 2')
        expect(screen.getByText('Closed Task 25')).toBeInTheDocument()
      })

      // Apply existing status filter -> pagination resets to Page 1 automatically
      fireEvent.change(screen.getByLabelText('Filter by status'), { target: { value: 'closed' } })
      await waitFor(() => {
        expect(screen.queryByRole('button', { name: 'Previous' })).not.toBeInTheDocument()
        expect(screen.getByText('Closed Task 25')).toBeInTheDocument()
        expect(screen.queryByText('Submitted Task 1')).not.toBeInTheDocument()
      })
    })
  })

  describe('Active Residents KPI Card & Resident Directory Navigation', () => {
    it('displays backend residents.activeCount and navigates to /admin/students when clicked', async () => {
      render(
        <MemoryRouter initialEntries={['/admin/dashboard']}>
          <App />
        </MemoryRouter>,
      )

      const residentsCard = await screen.findByRole('link', {
        name: /View 74 active residents in Resident Directory/i,
      })
      expect(residentsCard).toHaveAttribute('href', '/admin/students')
      expect(within(residentsCard).getByText('Active Residents')).toBeInTheDocument()
      expect(within(residentsCard).getByText('74')).toBeInTheDocument()
      expect(
        within(residentsCard).getByText('Students with active hostel allocations'),
      ).toBeInTheDocument()

      residentsCard.focus()
      expect(document.activeElement).toBe(residentsCard)

      fireEvent.click(residentsCard)
      await waitFor(() => {
        expect(screen.getByText('Resident Student Directory')).toBeInTheDocument()
      })
    })

    it('renders zero active residents cleanly and keeps card navigable to /admin/students', async () => {
      overviewHandler = () =>
        jsonResponse(
          makeOverviewPayload({
            residents: { activeCount: 0 },
          }),
          200,
        )

      render(
        <MemoryRouter initialEntries={['/admin/dashboard']}>
          <App />
        </MemoryRouter>,
      )

      const zeroCard = await screen.findByRole('link', {
        name: /View 0 active residents in Resident Directory/i,
      })
      expect(zeroCard).toHaveAttribute('href', '/admin/students')
      expect(within(zeroCard).getByText('0')).toBeInTheDocument()
      fireEvent.click(zeroCard)

      await waitFor(() => {
        expect(screen.getByText('Resident Student Directory')).toBeInTheDocument()
      })
    })
  })

  describe('Phase 4.2 Complaint Analytics, SLA Monitoring & Staff Performance', () => {
    it('renders category bars, trend SVG chart, MTTR, SLA priority table, and staff workload', async () => {
      render(
        <MemoryRouter initialEntries={['/admin/dashboard']}>
          <App />
        </MemoryRouter>,
      )

      await waitFor(() => {
        expect(screen.getByText('Complaint Category Distribution')).toBeInTheDocument()
      })

      // Categories
      expect(screen.getByText(/\(57\.1%\)/)).toBeInTheDocument()
      expect(screen.getByText(/\(42\.9%\)/)).toBeInTheDocument()

      // Trend SVG & totals
      expect(
        screen.getByRole('img', { name: /Complaint submission and completion trends chart/i }),
      ).toBeInTheDocument()
      expect(screen.getByText(/Submitted \(14\)/i)).toBeInTheDocument()
      expect(screen.getByText(/Completed \(8\)/i)).toBeInTheDocument()

      // MTTR & Median
      expect(screen.getByText('Resolution Performance')).toBeInTheDocument()
      expect(screen.getByText('18.5 hrs')).toBeInTheDocument()
      expect(screen.getByText('12.0 hrs')).toBeInTheDocument()

      // SLA compliance & priority rows
      expect(screen.getByText('SLA Compliance & Breach Monitoring')).toBeInTheDocument()
      expect(screen.getByText('85.7%')).toBeInTheDocument()
      expect(screen.getAllByText(/\(24h\)/).length).toBeGreaterThanOrEqual(2)
      expect(screen.getAllByText(/\(72h\)/).length).toBeGreaterThanOrEqual(2)
      expect(screen.getAllByText(/\(168h\)/).length).toBeGreaterThanOrEqual(2)

      // Staff workload
      expect(screen.getByText('Maintenance Staff Workload & Turnaround')).toBeInTheDocument()
      expect(screen.getByText('Busy')).toBeInTheDocument()
      expect(screen.getByText('Available')).toBeInTheDocument()
      expect(screen.getByText('Suresh Nair')).toBeInTheDocument()
    })

    it('requests /api/v1/admin/analytics/complaints with updated params when date range changes', async () => {
      complaintAnalyticsHandler = (path) => {
        if (path.includes('preset=7d')) {
          return jsonResponse(
            makeComplaintAnalyticsPayload({
              categories: [{ category: 'Internet', count: 3, percentage: 100.0 }],
              resolution: {
                completedCount: 1,
                averageSeconds: 12600,
                averageHours: 3.5,
                medianSeconds: 9000,
                medianHours: 2.5,
              },
            }),
            200,
          )
        }
        return jsonResponse(makeComplaintAnalyticsPayload(), 200)
      }

      render(
        <MemoryRouter initialEntries={['/admin/dashboard']}>
          <App />
        </MemoryRouter>,
      )

      await waitFor(() => {
        expect(screen.getByText('18.5 hrs')).toBeInTheDocument()
      })

      fireEvent.click(screen.getByRole('button', { name: 'Last 7 Days' }))
      await waitFor(() => {
        expect(screen.getByText('3.5 hrs')).toBeInTheDocument()
        expect(screen.getByText('Internet')).toBeInTheDocument()
      })
      expect(fetchSpy).toHaveBeenCalledWith(
        '/api/v1/admin/analytics/complaints?preset=7d',
        expect.any(Object),
      )
    })

    it('shows complaint analytics error and recovers on Retry without hiding Phase 4.1 KPIs', async () => {
      let failComplaintsAnalytics = true
      complaintAnalyticsHandler = () => {
        if (failComplaintsAnalytics) {
          return jsonResponse(
            { error: { code: 'internal_error', message: 'Complaint telemetry query failed' } },
            500,
          )
        }
        return jsonResponse(makeComplaintAnalyticsPayload(), 200)
      }

      render(
        <MemoryRouter initialEntries={['/admin/dashboard']}>
          <App />
        </MemoryRouter>,
      )

      await waitFor(() => {
        expect(screen.getByText('Hostel Operations & Maintenance Dashboard')).toBeInTheDocument()
        expect(screen.getByText(/Complaint telemetry query failed/i)).toBeInTheDocument()
      })

      // Retry recovers complaint analytics section cleanly
      failComplaintsAnalytics = false
      const alertBox = screen.getByRole('alert')
      fireEvent.click(within(alertBox).getByRole('button', { name: 'Retry' }))

      await waitFor(() => {
        expect(screen.getByText('Complaint Category Distribution')).toBeInTheDocument()
        expect(screen.getByText('18.5 hrs')).toBeInTheDocument()
      })
    })

    it('renders clean empty states when complaints analytics has zero data and zero staff', async () => {
      complaintAnalyticsHandler = () =>
        jsonResponse(
          makeComplaintAnalyticsPayload({
            categories: [],
            trends: {
              interval: 'daily',
              series: [{ period: '2026-11-18', label: '18 Nov', submitted: 0, completed: 0 }],
            },
            resolution: {
              completedCount: 0,
              averageSeconds: null,
              averageHours: null,
              medianSeconds: null,
              medianHours: null,
            },
            sla: {
              eligibleCount: 0,
              activeOverdue: 0,
              activeWithinSla: 0,
              completedWithinSla: 0,
              completedAfterSla: 0,
              complianceRate: null,
              byPriority: [],
            },
            staff: [],
          }),
          200,
        )

      render(
        <MemoryRouter initialEntries={['/admin/dashboard']}>
          <App />
        </MemoryRouter>,
      )

      await waitFor(() => {
        expect(
          screen.getByText('No complaints recorded during the selected reporting window.'),
        ).toBeInTheDocument()
        expect(
          screen.getByText('No complaint submissions or completions occurred during this period.'),
        ).toBeInTheDocument()
        expect(screen.getByText('N/A')).toBeInTheDocument()
        expect(
          screen.getByText('No active maintenance staff members configured.'),
        ).toBeInTheDocument()
      })
    })
  })
})
