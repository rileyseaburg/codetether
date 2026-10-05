'use client'

import { useEffect } from 'react'
import { useSession } from 'next-auth/react'
import { setApiAuthToken } from '@/lib/api'

import { getApiAuth, subscribeToAuthChanges } from '@/lib/auth-token'

/**
 * Syncs the NextAuth session token to the @hey-api SDK client.
 * Render this component inside any layout that needs authenticated API calls.
 * It renders nothing visible.
 *
 * On mount it also checks localStorage for a stored self-service token so SDK
 * calls made in the same render cycle aren't unauthenticated.
 */
export function ApiAuthSync() {
  const { data: session, status } = useSession()

  // Keep SDK credentials synchronized with UI identity, including token
  // rotation and logout in another tab (which do not change a NextAuth session).
  useEffect(() => {
    const sync = () => {
      const { token, tenantId } = getApiAuth({
        accessToken: session?.accessToken,
        tenantId: session?.tenantId,
      })
      setApiAuthToken(token, tenantId)
    }
    sync()
    return subscribeToAuthChanges(sync)
  }, [session?.accessToken, session?.tenantId, status])

  return null
}
