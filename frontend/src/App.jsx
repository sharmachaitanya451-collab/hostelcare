import { useEffect, useState } from 'react'
import { apiGet } from './lib/api.js'

export default function App() {
  const [state, setState] = useState({ status: 'loading' })

  useEffect(() => {
    let active = true
    Promise.all([apiGet('/api/v1/meta'), apiGet('/healthz')])
      .then(([meta]) => active && setState({ status: 'ready', meta }))
      .catch((error) => active && setState({ status: 'error', error }))
    return () => {
      active = false
    }
  }, [])

  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col items-center justify-center gap-2 p-6 text-center">
      <h1 className="text-3xl font-semibold text-blue-700">HostelCare</h1>
      {state.status === 'loading' && <p>Connecting to server…</p>}
      {state.status === 'ready' && (
        <p className="text-slate-600">{state.meta.hostel_name} — server connected</p>
      )}
      {state.status === 'error' && (
        <p role="alert" className="text-red-700">
          Cannot reach the server. Please try again shortly.
        </p>
      )}
    </main>
  )
}
