import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App.jsx'

const ok = (body) => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) })

describe('App', () => {
  afterEach(() => vi.restoreAllMocks())

  it('shows the hostel name once the server responds', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((url) => ok(url.includes('meta') ? { hostel_name: 'Test Hostel', blocks: [] } : {})),
    )
    render(<App />)
    expect(await screen.findByText(/Test Hostel/)).toBeInTheDocument()
  })

  it('shows an error when the server is unreachable', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(new Error('down'))),
    )
    render(<App />)
    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })
})
