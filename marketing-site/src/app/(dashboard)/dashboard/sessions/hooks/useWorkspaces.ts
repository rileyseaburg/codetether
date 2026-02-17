import { useState, useEffect, useCallback } from 'react'
import { useSession } from 'next-auth/react'
import { Workspace } from '../types'
import { listWorkspacesV1AgentWorkspacesListGet, hasApiAuthToken } from '@/lib/api'

export function useWorkspaces() {
    const { data: session } = useSession()
    const [workspaces, setWorkspaces] = useState<Workspace[]>([])

    const loadWorkspaces = useCallback(async () => {
        if (!hasApiAuthToken()) return
        try {
            const result = await listWorkspacesV1AgentWorkspacesListGet()
            if (result.data) {
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
            }
        } catch (error) {
            console.error('Failed to load workspaces:', error)
        }
    }, [])

    useEffect(() => {
        if (!session?.accessToken && !hasApiAuthToken()) return
        loadWorkspaces()
    }, [loadWorkspaces, session?.accessToken])

    return { workspaces, loadWorkspaces }
}

/** @deprecated Use useWorkspaces instead */
export const useCodebases = useWorkspaces
