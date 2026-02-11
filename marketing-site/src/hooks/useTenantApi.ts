'use client'

import { useSession } from 'next-auth/react'
import { useMemo, useCallback } from 'react'

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

  const tenantConfig = useMemo(() => {
    const defaultApiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://api.codetether.run'

    if (!session) {
      return {
        apiUrl: defaultApiUrl,
        tenantId: undefined,
        tenantSlug: undefined,
        hasDedicatedInstance: false,
      }
    }

    // Ensure HTTPS to prevent mixed content errors
    let tenantApiUrl = session.tenantApiUrl || defaultApiUrl
    if (tenantApiUrl.startsWith('http://')) {
      tenantApiUrl = tenantApiUrl.replace('http://', 'https://')
    }
    const hasDedicatedInstance = !!(
      session.tenantSlug &&
      tenantApiUrl.includes(session.tenantSlug)
    )

    return {
      apiUrl: tenantApiUrl,
      tenantId: session.tenantId,
      tenantSlug: session.tenantSlug,
      hasDedicatedInstance,
    }
  }, [session])

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

    if (session?.accessToken) {
      headers['Authorization'] = `Bearer ${session.accessToken}`
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

      if (!response.ok) {
        const errorText = await response.text()
        return { error: errorText || `HTTP ${response.status}` }
      }

      const data = await response.json()
      return { data }
    } catch (err) {
      return { error: err instanceof Error ? err.message : 'Unknown error' }
    }
  }, [session, tenantConfig])

  return {
    ...tenantConfig,
    tenantFetch,
    isLoading: status === 'loading',
    isAuthenticated: status === 'authenticated',
  }
}

/**
 * Get headers for tenant-aware API calls.
 * Includes the access token and tenant context.
 */
export function useTenantHeaders() {
  const { data: session } = useSession()

  return useMemo(() => {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    }

    if (session?.accessToken) {
      headers['Authorization'] = `Bearer ${session.accessToken}`
    }

    if (session?.tenantId) {
      headers['X-Tenant-ID'] = session.tenantId
    }

    return headers
  }, [session])
}
