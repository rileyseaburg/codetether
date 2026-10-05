import { useState, useEffect, useCallback, useRef } from 'react'
import { getApiAuth } from '@/lib/auth-token'
import { useSession } from 'next-auth/react'
import { Workspace } from '../types'
import { listWorkspacesV1AgentWorkspacesListGet, hasApiAuthToken } from '@/lib/api'

export function useWorkspaces() {
    const { data: session, status } = useSession()
    const [workspaces, setWorkspaces] = useState<Workspace[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const requestId = useRef(0)
    const invalidateRequest = useCallback(() => { ++requestId.current }, [])

    const loadWorkspaces = useCallback(async () => {
        const request = ++requestId.current
        const { token } = getApiAuth({ accessToken: session?.accessToken, tenantId: session?.tenantId })
        if (!token && !hasApiAuthToken()) {
            setLoading(false)
            setError('Sign in to load your workspaces.')
            return
        }
        setLoading(true)
        setError(null)
        try {
            const result = await listWorkspacesV1AgentWorkspacesListGet(token ? { headers: { Authorization: `Bearer ${token}` } } : undefined)
            if (request !== requestId.current) return
            if (!result.error && result.data) {
                const payload = result.data as any
                const items: any[] = Array.isArray(payload)
                    ? payload
                    : (payload?.workspaces ?? payload?.codebases ?? [])
                setWorkspaces(
                    items
                        .map((ws) => ({
                            id: String(ws?.id ?? ''),
                            name: String(ws?.name ?? ws?.id ?? ''),
                            path: String(ws?.path ?? ''),
                            status: String(ws?.status ?? 'unknown'),
                            worker_id: typeof ws?.worker_id === 'string' ? ws.worker_id : null,
                            agent_port:
                                typeof ws?.agent_port === 'number'
                                    ? ws.agent_port
                                    : ws?.agent_port
                                        ? Number(ws.agent_port)
                                        : null,
                        }))
                        .filter((ws) => ws.id)
                )
            } else setError('Failed to load workspaces. Please retry.')
        } catch (error) {
            if (request === requestId.current) setError('Failed to load workspaces. Please retry.')
        } finally {
            if (request === requestId.current) setLoading(false)
        }
    }, [session?.accessToken, session?.tenantId])

    useEffect(() => {
        if (status === 'loading') return
        loadWorkspaces()
        return invalidateRequest
    }, [loadWorkspaces, status, invalidateRequest])

    return { workspaces, loadWorkspaces, loading, error }
}

/** @deprecated Use useWorkspaces instead */
export const useCodebases = useWorkspaces