'use client'

import { useEffect } from 'react'
import { useSession } from 'next-auth/react'
import { setApiAuthToken } from '@/lib/api'

/**
 * Syncs the NextAuth session token to the @hey-api SDK client.
 * Render this component inside any layout that needs authenticated API calls.
 * It renders nothing visible.
 *
 * On mount it also checks localStorage for a fallback token so SDK calls
 * made in the same render cycle aren't unauthenticated.
 */
export function ApiAuthSync() {
    const { data: session, status } = useSession()

    // Eager: seed from localStorage BEFORE first paint so SDK calls in
    // sibling useEffects already have a token.
    useEffect(() => {
        if (status === 'loading') {
            const lsToken = localStorage.getItem('a2a_token') || localStorage.getItem('access_token')
            if (lsToken) {
                setApiAuthToken(lsToken)
            }
        }
    }, []) // eslint-disable-line react-hooks/exhaustive-deps -- intentionally run once

    // Primary: sync from NextAuth session whenever it changes
    useEffect(() => {
        if (session?.accessToken) {
            setApiAuthToken(session.accessToken, session.tenantId)
        }
        return () => { setApiAuthToken() }
    }, [session?.accessToken, session?.tenantId])

    return null
}
