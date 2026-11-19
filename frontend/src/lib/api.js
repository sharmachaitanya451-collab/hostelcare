/**
 * Centralized HostelCare API client.
 *
 * Uses secure HTTP-only cookie sessions (`credentials: 'include'`) and attaches
 * `X-CSRF-Token` on all state-changing requests (`POST`, `PUT`, `PATCH`, `DELETE`).
 */

let csrfTokenMemory = null
let sessionExpiredListener = null
let authForbiddenListener = null

export class ApiError extends Error {
  constructor(message, { status = 500, code = 'internal_error', details = null } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

export function setCsrfToken(token) {
  if (typeof token === 'string' && token.trim()) {
    csrfTokenMemory = token.trim()
  }
}

export function clearCsrfToken() {
  csrfTokenMemory = null
}

export function getCsrfToken() {
  if (csrfTokenMemory) {
    return csrfTokenMemory
  }
  if (typeof document !== 'undefined' && document.cookie) {
    const match = document.cookie.split('; ').find((entry) => entry.startsWith('hc_csrf_token='))
    if (match) {
      return decodeURIComponent(match.split('=')[1] || '')
    }
  }
  return null
}

export function onSessionExpired(listener) {
  sessionExpiredListener = listener
  return () => {
    if (sessionExpiredListener === listener) {
      sessionExpiredListener = null
    }
  }
}

export function onAuthForbidden(listener) {
  authForbiddenListener = listener
  return () => {
    if (authForbiddenListener === listener) {
      authForbiddenListener = null
    }
  }
}

function _throwApiError(path, response, data) {
  const errObj = data?.error || {}
  const code = errObj.code || 'request_failed'
  const message = errObj.message || `Request failed with status ${response.status}`
  const details = errObj.details || null

  if (
    response.status === 401 &&
    (code === 'session_expired' || (code === 'unauthenticated' && path !== '/api/v1/auth/me'))
  ) {
    clearCsrfToken()
    if (typeof sessionExpiredListener === 'function') {
      sessionExpiredListener(code)
    }
  } else if (
    response.status === 403 &&
    code !== 'forbidden' &&
    code !== 'task_forbidden' &&
    code !== 'forbidden_action' &&
    code !== 'csrf_invalid' &&
    code !== 'csrf_missing' &&
    code !== 'origin_mismatch' &&
    path !== '/api/v1/auth/me' &&
    path !== '/api/v1/auth/login' &&
    path !== '/api/v1/auth/register'
  ) {
    if (typeof authForbiddenListener === 'function') {
      authForbiddenListener({ path, code, status: 403 })
    }
  }

  throw new ApiError(message, {
    status: response.status,
    code,
    details,
  })
}

export async function apiRequest(path, { method = 'GET', body, headers = {}, signal } = {}) {
  const upperMethod = method.toUpperCase()
  const isFormData = typeof FormData !== 'undefined' && body instanceof FormData
  const reqHeaders = {
    Accept: 'application/json',
    ...headers,
  }

  if (body !== undefined && !isFormData) {
    reqHeaders['Content-Type'] = 'application/json'
  }

  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(upperMethod)) {
    const csrf = getCsrfToken()
    if (csrf) {
      reqHeaders['X-CSRF-Token'] = csrf
    }
  }

  const serializedBody =
    body === undefined
      ? undefined
      : isFormData || typeof body === 'string'
        ? body
        : JSON.stringify(body)

  const response = await fetch(path, {
    method: upperMethod,
    credentials: 'include',
    headers: reqHeaders,
    body: serializedBody,
    ...(signal ? { signal } : {}),
  })

  const headerCsrf = response.headers?.get?.('X-CSRF-Token')
  if (headerCsrf) {
    setCsrfToken(headerCsrf)
  }

  let data = null
  const contentType = response.headers?.get?.('Content-Type') || ''
  if (contentType.includes('application/json')) {
    try {
      data = await response.json()
    } catch {
      data = null
    }
  }

  if (data && typeof data.csrf_token === 'string') {
    setCsrfToken(data.csrf_token)
  }

  if (!response.ok) {
    _throwApiError(path, response, data)
  }

  return data
}

export async function apiDownloadBlob(path, { accept = 'application/pdf' } = {}) {
  const response = await fetch(path, {
    method: 'GET',
    credentials: 'include',
    headers: { Accept: accept },
  })

  const headerCsrf = response.headers?.get?.('X-CSRF-Token')
  if (headerCsrf) {
    setCsrfToken(headerCsrf)
  }

  if (!response.ok) {
    let data = null
    const contentType = response.headers?.get?.('Content-Type') || ''
    if (contentType.includes('application/json')) {
      try {
        data = await response.json()
      } catch {
        data = null
      }
    }
    _throwApiError(path, response, data)
  }

  const disposition = response.headers?.get?.('Content-Disposition') || ''
  const match = disposition.match(/filename\*?=(?:UTF-8''|")?([^";\n]+)"?/i)
  const filename = match?.[1]?.trim() || null
  const blob = await response.blob()
  return { blob, filename }
}
