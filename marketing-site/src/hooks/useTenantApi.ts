'use client'

import { useSession, signOut } from 'next-auth/react'
import { useMemo, useCallback, useEffect, useRef } from 'react'

function decodeJwtPayload(token: string): Record<string, any> {
  try {
    const parts = token.split('.')
    if (parts.length < 2) return {}
    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const json = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => `%${`00${c.charCodeAt(0).toString(16)}`.slice(-2)}`)
        .join('')
    )
    return JSON.parse(json)
  } catch {
    return {}
  }
}

function extractTenantFromToken(token?: string): { tenantId?: string; tenantSlug?: string } {
  if (!token) return {}
  const payload = decodeJwtPayload(token)
  return {
    tenantId:
      payload.tenant_id ||
      payload.tenantId ||
      payload['codetether:tenant_id'] ||
      payload.tid,
    tenantSlug:
      payload.tenant_slug ||
      payload.tenantSlug ||
      payload['codetether:tenant_slug'],
  }
}

/**
 * Hook to get tenant-aware API configuration.
 *
 * Returns the correct API URL based on the user's tenant:
 * - If user has a dedicated tenant instance: https://{slug}.codetether.run
 * - Otherwise: https://api.codetether.run (shared API)
 *
 * Usage:
 * ```tsx
 * const { apiUrl, tenantId, tenantSlug, tenantFetch } = useTenantApi()
 *
 * // Make API calls to the correct endpoint
 * const data = await tenantFetch('/v1/tasks')
 * ```
 */
export function useTenantApi() {
  const { data: session, status } = useSession()
  const unauthorizedHandledRef = useRef(false)
  const typedSession = session as any
  const localUser =
    typeof window !== 'undefined'
      ? (() => {
          try {
            const raw = localStorage.getItem('a2a_user')
            return raw ? JSON.parse(raw) : undefined
          } catch {
            return undefined
          }
        })()
      : undefined

  const tenantConfig = useMemo(() => {
    const defaultApiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://api.codetether.run'
    const sessionToken = typedSession?.accessToken as string | undefined
    const storedToken =
      typeof window !== 'undefined'
        ? localStorage.getItem('a2a_token') || localStorage.getItem('access_token') || undefined
        : undefined
    const authToken = sessionToken || storedToken
    const tokenTenant = extractTenantFromToken(authToken)

    const resolvedTenantId =
      typedSession?.tenantId ||
      typedSession?.tenant_id ||
      typedSession?.user?.tenantId ||
      typedSession?.user?.tenant_id ||
      localUser?.tenantId ||
      localUser?.tenant_id ||
      tokenTenant.tenantId

    const resolvedTenantSlug =
      typedSession?.tenantSlug ||
      typedSession?.tenant_slug ||
      typedSession?.user?.tenantSlug ||
      typedSession?.user?.tenant_slug ||
      localUser?.tenantSlug ||
      localUser?.tenant_slug ||
      tokenTenant.tenantSlug

    if (!typedSession && !authToken) {
      return {
        apiUrl: defaultApiUrl,
        tenantId: undefined,
        tenantSlug: undefined,
        hasDedicatedInstance: false,
      }
    }

    // Ensure HTTPS to prevent mixed content errors
    let tenantApiUrl = typedSession?.tenantApiUrl || defaultApiUrl
    if (tenantApiUrl.startsWith('http://')) {
      tenantApiUrl = tenantApiUrl.replace('http://', 'https://')
    }
    const hasDedicatedInstance = !!(
      resolvedTenantSlug &&
      tenantApiUrl.includes(resolvedTenantSlug)
    )

    return {
      apiUrl: tenantApiUrl,
      tenantId: resolvedTenantId,
      tenantSlug: resolvedTenantSlug,
      hasDedicatedInstance,
    }
  }, [localUser?.tenantId, localUser?.tenantSlug, localUser?.tenant_id, localUser?.tenant_slug, typedSession])

  useEffect(() => {
    unauthorizedHandledRef.current = false
  }, [typedSession?.accessToken])

  /**
   * Tenant-aware fetch function.
   * Automatically adds auth headers and routes to the correct tenant API.
   */
  const tenantFetch = useCallback(async <T = unknown>(
    path: string,
    options: RequestInit = {}
  ): Promise<{ data?: T; error?: string }> => {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string> || {}),
    }

    const sessionToken = typedSession?.accessToken as string | undefined
    const storedToken =
      typeof window !== 'undefined'
        ? localStorage.getItem('a2a_token') || localStorage.getItem('access_token')
        : null
    const authToken = sessionToken || storedToken

    if (authToken) {
      headers['Authorization'] = `Bearer ${authToken}`
    }

    if (tenantConfig.tenantId) {
      headers['X-Tenant-ID'] = tenantConfig.tenantId
    }

    try {
      const url = path.startsWith('http') ? path : `${tenantConfig.apiUrl}${path}`
      const response = await fetch(url, {
        ...options,
        headers,
      })

      if (response.status === 401) {
        if (!unauthorizedHandledRef.current) {
          unauthorizedHandledRef.current = true

          if (typeof window !== 'undefined') {
            localStorage.removeItem('a2a_token')
            localStorage.removeItem('access_token')
            localStorage.removeItem('a2a_refresh_token')
            localStorage.removeItem('a2a_session')
            localStorage.removeItem('a2a_user')
            document.cookie = 'a2a_token=; path=/; max-age=0'
          }

          signOut({ callbackUrl: '/login?error=session_expired' }).catch(() => {})
        }

        return { error: 'Session expired. Please sign in again.' }
      }

      if (!response.ok) {
        const errorText = await response.text()
        const isHtmlResponse =
          /^\s*<!doctype html/i.test(errorText) ||
          /^\s*<html/i.test(errorText) ||
          errorText.includes('<!DOCTYPE html>')

        if (isHtmlResponse) {
          const usingApiProxy =
            tenantConfig.apiUrl === '/api' ||
            tenantConfig.apiUrl.endsWith('/api')

          if (response.status === 404 && usingApiProxy) {
            return {
              error:
                'API proxy route returned 404 HTML instead of JSON. Ensure Next.js rewrite is configured with A2A_API_BACKEND and restart `next dev`.',
            }
          }

          return {
            error: `Unexpected HTML response from API (HTTP ${response.status}). Check NEXT_PUBLIC_API_URL and Next.js rewrites.`,
          }
        }

        let detail = errorText
        try {
          const parsed = JSON.parse(errorText)
          detail = parsed?.detail || parsed?.message || errorText
        } catch {
          // Non-JSON error payload.
        }
        if (typeof detail === 'string' && detail.toLowerCase().includes('no tenant associated')) {
          return {
            error:
              'No tenant is associated with this account yet. Complete tenant setup in registration/admin before using tenant-scoped features.',
          }
        }
        return { error: detail || `HTTP ${response.status}` }
      }

      const data = await response.json()
      return { data }
    } catch (err) {
      return { error: err instanceof Error ? err.message : 'Unknown error' }
    }
  }, [typedSession?.accessToken, tenantConfig])

  return {
    ...tenantConfig,
    tenantFetch,
    isLoading: status === 'loading',
    isAuthenticated:
      status === 'authenticated' ||
      (typeof window !== 'undefined' &&
        Boolean(localStorage.getItem('a2a_token') || localStorage.getItem('access_token'))),
    hasTenant: Boolean(tenantConfig.tenantId),
  }
}

/**
 * Get headers for tenant-aware API calls.
 * Includes the access token and tenant context.
 */
export function useTenantHeaders() {
  const { data: session } = useSession()
  const typedSession = session as any

  return useMemo(() => {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    }

    if (typedSession?.accessToken) {
      headers['Authorization'] = `Bearer ${typedSession.accessToken}`
    }

    if (typedSession?.tenantId) {
      headers['X-Tenant-ID'] = typedSession.tenantId
    }

    return headers
  }, [typedSession])
}
