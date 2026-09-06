type ApiSession = { accessToken?: string; tenantId?: string } | null | undefined

const AUTH_CHANGE_EVENT = 'codetether-auth-change'
const AUTH_STORAGE_KEYS = ['a2a_token', 'access_token', 'a2a_user']

/** Observe sign-in/profile changes, including logout in another browser tab. */
export function subscribeToAuthChanges(notify: () => void) {
  const onStorage = (event: StorageEvent) => {
    if (event.key === null || AUTH_STORAGE_KEYS.includes(event.key)) notify()
  }
  window.addEventListener('storage', onStorage)
  window.addEventListener(AUTH_CHANGE_EVENT, notify)
  return () => {
    window.removeEventListener('storage', onStorage)
    window.removeEventListener(AUTH_CHANGE_EVENT, notify)
  }
}

/** Storage events only cross tabs; notify same-tab consumers after a write. */
export function notifyApiAuthChange() {
  window.dispatchEvent(new Event(AUTH_CHANGE_EVENT))
}

/** Resolve API credentials for both SSO and the supported password login. */
export function getApiAuth(session?: ApiSession): {
  token?: string
  tenantId?: string
} {
  if (session?.accessToken) {
    return { token: session.accessToken, tenantId: session.tenantId }
  }
  if (typeof window === 'undefined') return {}
  try {
    const token =
      localStorage.getItem('a2a_token') ||
      localStorage.getItem('access_token') ||
      undefined
    let tenantId: string | undefined
    try {
      const rawUser = localStorage.getItem('a2a_user')
      const user = rawUser ? JSON.parse(rawUser) : undefined
      tenantId = user?.tenantId || user?.tenant_id
    } catch {
      // A malformed profile must not discard an otherwise usable token.
    }
    return { token, tenantId }
  } catch {
    // Storage can be disabled by browser privacy settings.
    return {}
  }
}
