'use client'

import { useEffect } from 'react'
import { useSession } from 'next-auth/react'
import { setApiAuthToken } from '@/lib/api'

function getStoredApiAuth(): { token?: string; tenantId?: string } {
    if (typeof window === 'undefined') {
        return {}
    }

    const token = localStorage.getItem('a2a_token') || localStorage.getItem('access_token') || undefined
    let tenantId: string | undefined

    try {
        const rawUser = localStorage.getItem('a2a_user')
        const user = rawUser ? JSON.parse(rawUser) : undefined
        tenantId = user?.tenantId || user?.tenant_id
    } catch {
        tenantId = undefined
    }

    return { token, tenantId }
}

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

    // Eager: seed from localStorage on mount so SDK calls made by globally
    // rendered components (for example the chat widget) are not anonymous while
    // NextAuth is still loading.
    useEffect(() => {
        const { token, tenantId } = getStoredApiAuth()
        if (token) {
            setApiAuthToken(token, tenantId)
        }
    }, [])

    // Primary: sync from NextAuth session whenever it changes. If the root
    // provider has no session but a self-service token exists in localStorage,
    // keep using that token instead of clearing the SDK auth state.
    useEffect(() => {
        if (session?.accessToken) {
            setApiAuthToken(session.accessToken, session.tenantId)
            return
        }

        const { token, tenantId } = getStoredApiAuth()
        if (token) {
            setApiAuthToken(token, tenantId)
            return
        }

        setApiAuthToken()
    }, [session?.accessToken, session?.tenantId, status])

    return null
}
