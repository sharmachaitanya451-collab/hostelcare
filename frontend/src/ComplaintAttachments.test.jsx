import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import App from './App.jsx'
import { ComplaintAttachmentsGallery } from './components/ComplaintAttachmentsGallery.jsx'

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

function imageBlobResponse(mime = 'image/jpeg', status = 200) {
  const blob = new Blob([new Uint8Array([0xff, 0xd8, 0xff, 0xe0])], { type: mime })
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    headers: {
      get: (key) => {
        const lower = key.toLowerCase()
        if (lower === 'content-type') return mime
        if (lower === 'content-disposition') return 'inline; filename="photo.jpg"'
        return null
      },
    },
    blob: () => Promise.resolve(blob),
  })
}

describe('Complaint Photo Attachments (Frontend)', () => {
  const studentUser = {
    id: 'stu-1',
    role: 'student',
    status: 'active',
    fullName: 'Aarav Sharma',
    rollNumber: '2026CSB1042',
    room: 'A-204',
    block: 'Aryabhatta Block',
    hasActiveRoom: true,
  }

  let currentUser = studentUser
  let submittedRequests = []
  let complaintDetailFixture = null
  let attachmentFetchShouldFail = false
  let createUrlMock
  let revokeUrlMock
  let originalCreateObjectURL
  let originalRevokeObjectURL

  beforeEach(() => {
    currentUser = studentUser
    submittedRequests = []
    attachmentFetchShouldFail = false
    complaintDetailFixture = {
      id: 'CMP-2026-00050',
      referenceNo: 'CMP-2026-00050',
      studentId: 'stu-1',
      studentName: 'Aarav Sharma',
      studentRoll: '2026CSB1042',
      locationType: 'room',
      room: 'A-204',
      block: 'Aryabhatta Block',
      title: 'Broken fan switch',
      category: 'Electrical',
      description: 'Fan regulator sparks when adjusted.',
      priority: 'high',
      status: 'submitted',
      assignedStaffId: 'stf-1',
      assignedStaff: 'Ramesh Babu',
      attachments: [
        {
          id: 'att-uuid-1',
          publicId: 'att-uuid-1',
          filename: 'fan_switch.jpg',
          mimeType: 'image/jpeg',
          fileSizeBytes: 24576,
          url: '/api/v1/complaints/CMP-2026-00050/attachments/att-uuid-1',
        },
      ],
      updates: [],
      history: [],
    }

    let urlCounter = 0
    createUrlMock = vi.fn(() => `blob:mock-url-${++urlCounter}`)
    revokeUrlMock = vi.fn()
    originalCreateObjectURL = URL.createObjectURL
    originalRevokeObjectURL = URL.revokeObjectURL
    URL.createObjectURL = createUrlMock
    URL.revokeObjectURL = revokeUrlMock

    vi.spyOn(globalThis, 'fetch').mockImplementation((url, options = {}) => {
      const path = typeof url === 'string' ? url : url.toString()
      const method = (options.method || 'GET').toUpperCase()

      if (path === '/api/v1/auth/me' && method === 'GET') {
        return jsonResponse({ user: currentUser, csrf_token: 'test-csrf-token' })
      }
      if (path === '/api/v1/blocks' && method === 'GET') {
        return jsonResponse({ blocks: [{ id: 1, code: 'BLKA', name: 'Aryabhatta Block' }] })
      }
      if (path === '/api/v1/notifications' && method === 'GET') {
        return jsonResponse({ notifications: [] })
      }
      if (path === '/api/v1/student/complaints' && method === 'GET') {
        return jsonResponse({ complaints: [complaintDetailFixture] })
      }
      if (path === '/api/v1/student/complaints/CMP-2026-00050' && method === 'GET') {
        return jsonResponse({ complaint: complaintDetailFixture })
      }
      if (path === '/api/v1/staff/tasks' && method === 'GET') {
        return jsonResponse({
          tasks: [complaintDetailFixture],
          complaints: [complaintDetailFixture],
        })
      }
      if (path === '/api/v1/staff/tasks/CMP-2026-00050' && method === 'GET') {
        return jsonResponse({
          task: complaintDetailFixture,
          complaint: complaintDetailFixture,
        })
      }
      if (path === '/api/v1/admin/complaints' && method === 'GET') {
        return jsonResponse({ complaints: [complaintDetailFixture] })
      }
      if (path === '/api/v1/admin/complaints/CMP-2026-00050' && method === 'GET') {
        return jsonResponse({ complaint: complaintDetailFixture })
      }
      if (path.startsWith('/api/v1/admin/') && method === 'GET') {
        return jsonResponse({ users: [], students: [], staff: [], rooms: [], logs: [] })
      }
      if (path === '/api/v1/student/complaints' && method === 'POST') {
        submittedRequests.push({
          headers: options.headers || {},
          body: options.body,
          isFormData: options.body instanceof FormData,
        })
        return jsonResponse(
          {
            complaint: {
              ...complaintDetailFixture,
              id: 'CMP-2026-00051',
              referenceNo: 'CMP-2026-00051',
            },
          },
          201,
        )
      }
      if (path.includes('/attachments/')) {
        if (attachmentFetchShouldFail) {
          return jsonResponse(
            { error: { code: 'attachment_file_missing', message: 'Photo unavailable.' } },
            404,
          )
        }
        return imageBlobResponse('image/jpeg')
      }

      return jsonResponse({})
    })
  })

  afterEach(() => {
    URL.createObjectURL = originalCreateObjectURL
    URL.revokeObjectURL = originalRevokeObjectURL
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('validates max 3 photos, max 5 MB size, unsupported format, and removes previews', async () => {
    render(
      <MemoryRouter initialEntries={['/student/complaints/new']}>
        <App />
      </MemoryRouter>,
    )

    const fileInput = await screen.findByLabelText(/Problem Photos/i)

    // Unsupported format (SVG) rejected
    const svgFile = new File(['<svg></svg>'], 'vector.svg', { type: 'image/svg+xml' })
    fireEvent.change(fileInput, { target: { files: [svgFile] } })
    expect(
      await screen.findByText(/is not a supported JPEG, PNG, or WebP image/i),
    ).toBeInTheDocument()
    expect(screen.getByText('0/3 attached')).toBeInTheDocument()

    // File > 5 MB rejected
    const bigFile = new File([new Uint8Array(10)], 'huge.jpg', { type: 'image/jpeg' })
    Object.defineProperty(bigFile, 'size', { value: 5 * 1024 * 1024 + 1 })
    fireEvent.change(fileInput, { target: { files: [bigFile] } })
    expect(await screen.findByText(/exceeds the 5 MB per-photo limit/i)).toBeInTheDocument()
    expect(screen.getByText('0/3 attached')).toBeInTheDocument()

    // Select 4 valid photos -> only first 3 accepted, 4th rejected
    const validFiles = [1, 2, 3, 4].map(
      (n) =>
        new File([new Uint8Array([0xff, 0xd8, 0xff])], `photo_${n}.jpg`, {
          type: 'image/jpeg',
          lastModified: 1000 + n,
        }),
    )
    fireEvent.change(fileInput, { target: { files: validFiles } })
    expect(
      await screen.findByText(/You may attach at most 3 photos per complaint/i),
    ).toBeInTheDocument()
    expect(screen.getByText('3/3 attached')).toBeInTheDocument()
    expect(screen.getByText('photo_1.jpg')).toBeInTheDocument()
    expect(screen.getByText('photo_3.jpg')).toBeInTheDocument()
    expect(screen.queryByText('photo_4.jpg')).not.toBeInTheDocument()

    // Remove one photo -> count drops to 2/3 and temporary object URL is revoked
    fireEvent.click(screen.getByRole('button', { name: /Remove photo_2\.jpg/i }))
    expect(screen.getByText('2/3 attached')).toBeInTheDocument()
    expect(revokeUrlMock).toHaveBeenCalledTimes(1)
  })

  it('submits FormData with attached photos without Content-Type override and keeps empty submissions as JSON', async () => {
    const firstRender = render(
      <MemoryRouter initialEntries={['/student/complaints/new']}>
        <App />
      </MemoryRouter>,
    )

    const titleInput = await screen.findByPlaceholderText(/Broken bed frame/i)
    const descInput = screen.getByPlaceholderText(/Explain any hostel-related issue/i)
    const fileInput = screen.getByLabelText(/Problem Photos/i)

    fireEvent.change(titleInput, { target: { value: 'Leaking bathroom tap' } })
    fireEvent.change(descInput, {
      target: { value: 'Water drips continuously onto bathroom floor.' },
    })

    const photo = new File([new Uint8Array([0x89, 0x50, 0x4e, 0x47])], 'tap.png', {
      type: 'image/png',
      lastModified: 2001,
    })
    fireEvent.change(fileInput, { target: { files: [photo] } })

    fireEvent.click(screen.getByRole('button', { name: /Submit Maintenance Complaint/i }))

    await waitFor(() => {
      expect(submittedRequests).toHaveLength(1)
    })

    const mpReq = submittedRequests[0]
    expect(mpReq.isFormData).toBe(true)
    expect(mpReq.headers['Content-Type']).toBeUndefined()
    expect(mpReq.headers['X-CSRF-Token']).toBe('test-csrf-token')
    expect(mpReq.body.get('title')).toBe('Leaking bathroom tap')
    expect(mpReq.body.getAll('photos')).toHaveLength(1)
    expect(mpReq.body.getAll('photos')[0].name).toBe('tap.png')

    firstRender.unmount()

    // Submit without photos -> sends standard JSON request
    render(
      <MemoryRouter initialEntries={['/student/complaints/new']}>
        <App />
      </MemoryRouter>,
    )

    fireEvent.change(await screen.findByPlaceholderText(/Broken bed frame/i), {
      target: { value: 'Door hinge squeaking' },
    })
    fireEvent.change(screen.getByPlaceholderText(/Explain any hostel-related issue/i), {
      target: { value: 'Main room door hinge needs lubrication.' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Submit Maintenance Complaint/i }))

    await waitFor(() => {
      expect(submittedRequests).toHaveLength(2)
    })

    const jsonReq = submittedRequests[1]
    expect(jsonReq.isFormData).toBe(false)
    expect(jsonReq.headers['Content-Type']).toBe('application/json')
    expect(JSON.parse(jsonReq.body).title).toBe('Door hinge squeaking')
  })

  it('renders authenticated attachment gallery, opens lightbox preview, and handles errors with retry', async () => {
    attachmentFetchShouldFail = true
    const { rerender } = render(
      <ComplaintAttachmentsGallery attachments={complaintDetailFixture.attachments} />,
    )

    expect(await screen.findByText(/Photo unavailable\./i)).toBeInTheDocument()

    attachmentFetchShouldFail = false
    fireEvent.click(screen.getByRole('button', { name: /^Retry$/i }))

    const previewTrigger = await screen.findByRole('button', { name: /View fan_switch\.jpg/i })
    expect(previewTrigger).toBeInTheDocument()

    fireEvent.click(previewTrigger)
    const dialog = await screen.findByRole('dialog', { name: /Photo preview: fan_switch\.jpg/i })
    expect(dialog).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Close photo preview/i }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    // Empty attachments renders nothing
    rerender(<ComplaintAttachmentsGallery attachments={[]} />)
    expect(screen.queryByText(/Attached Photos/i)).not.toBeInTheDocument()
  })

  it('displays attached photos across student, staff, and admin complaint detail portals', async () => {
    // Student detail
    const stuRender = render(
      <MemoryRouter initialEntries={['/student/complaints/CMP-2026-00050']}>
        <App />
      </MemoryRouter>,
    )
    expect(await screen.findByText(/Attached Photos \(1\)/i)).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: /View fan_switch\.jpg/i })).toBeInTheDocument()
    stuRender.unmount()

    // Staff detail
    currentUser = {
      id: 'stf-1',
      role: 'staff',
      status: 'active',
      fullName: 'Ramesh Babu',
      trade: 'Electrician',
    }
    const stfRender = render(
      <MemoryRouter initialEntries={['/staff/tasks/CMP-2026-00050']}>
        <App />
      </MemoryRouter>,
    )
    expect(await screen.findByText(/Attached Photos \(1\)/i)).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: /View fan_switch\.jpg/i })).toBeInTheDocument()
    stfRender.unmount()

    // Admin detail
    currentUser = {
      id: 'adm-1',
      role: 'admin',
      status: 'active',
      fullName: 'Dr. K. S. Verma',
      designation: 'Chief Hostel Warden',
    }
    const admRender = render(
      <MemoryRouter initialEntries={['/admin/complaints/CMP-2026-00050']}>
        <App />
      </MemoryRouter>,
    )
    expect(await screen.findByText(/Attached Photos \(1\)/i)).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: /View fan_switch\.jpg/i })).toBeInTheDocument()
    admRender.unmount()
  })
})
