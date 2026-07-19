'use client'

import { useEffect } from 'react'
import { useSession } from 'next-auth/react'
import { setApiAuthToken } from '@/lib/api'

/**
 * Syncs the NextAuth session token to the @hey-api SDK client.
 * Render this component inside any layout that needs authenticated API calls.
 * It renders nothing visible.
 *
 * A2A receives the signed Keycloak access JWT from the NextAuth session.
 */
export function ApiAuthSync() {
    const { data: session, status } = useSession()

    // Sync from NextAuth whenever it changes. Browser auth is Keycloak-direct
    // and A2A calls use the signed JWT from that session.
    useEffect(() => {
        if (session?.accessToken) {
            setApiAuthToken(session.accessToken, session.tenantId)
            return
        }

        setApiAuthToken()
    }, [session?.accessToken, session?.tenantId, status])

    return null
}
