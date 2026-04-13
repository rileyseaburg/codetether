// useWorkspaces Hook
// Workspace state management

import { useState, useCallback, useEffect } from 'react'
import { listWorkspacesV1AgentWorkspacesListGet, registerWorkspaceV1AgentWorkspacesPost, unregisterWorkspaceV1AgentWorkspacesWorkspaceIdDelete, hasApiAuthToken } from '@/lib/api'
import type { Workspace } from '../types'

interface RegisterOptions {
    name: string
    path?: string
    description?: string
    git_url?: string
    git_branch?: string
    runtime?: 'container' | 'vm'
    external_provider?: string
    external_reference?: string
}

interface UseWorkspacesReturn {
    workspaces: Workspace[]
    loading: boolean
    error: string | null
    refresh: () => Promise<void>
    register: (options: RegisterOptions) => Promise<void>
    remove: (id: string) => Promise<void>
}

export function useWorkspaces(): UseWorkspacesReturn {
    const [workspaces, setWorkspaces] = useState<Workspace[]>([])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const refresh = useCallback(async () => {
        if (!hasApiAuthToken()) return
        setLoading(true)
        setError(null)
        try {
            const res = await listWorkspacesV1AgentWorkspacesListGet({})
            const data = res.data as Record<string, unknown> | undefined
            const items = Array.isArray(data) ? data : (data?.workspaces ?? data?.codebases ?? data?.data ?? [])
            setWorkspaces((items as Array<Record<string, unknown>>).map((cb) => ({
                id: String(cb.id ?? ''),
                name: String(cb.name ?? cb.id ?? ''),
                path: String(cb.path ?? ''),
                description: typeof cb.description === 'string' ? cb.description : undefined,
                status: String(cb.status ?? 'unknown'),
                worker_id: typeof cb.worker_id === 'string' ? cb.worker_id : undefined,
                runtime: cb.runtime === 'vm' ? ('vm' as const) : ('container' as const),
                vm_status: typeof cb.vm_status === 'string' ? cb.vm_status : undefined,
                vm_name: typeof cb.vm_name === 'string' ? cb.vm_name : undefined,
                vm_ssh_host: typeof cb.vm_ssh_host === 'string' ? cb.vm_ssh_host : undefined,
                vm_ssh_port: typeof cb.vm_ssh_port === 'number' ? cb.vm_ssh_port : undefined,
            })).filter((cb) => cb.id))
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to fetch workspaces')
        } finally {
            setLoading(false)
        }
    }, [])

    const register = useCallback(async (options: RegisterOptions) => {
        const body: Record<string, unknown> = {
            name: options.name,
            ...(options.path && { path: options.path }),
            ...(options.description && { description: options.description }),
            ...(options.git_url && { git_url: options.git_url }),
            ...(options.git_branch && { git_branch: options.git_branch }),
            ...(options.runtime && { runtime: options.runtime }),
        }
        if (options.external_provider) {
            body.path = options.path || `external://${options.external_provider.toLowerCase().replace(/[^a-z0-9]+/g, '-')}/${options.external_reference || options.name}`
            body.agent_config = {
                source_type: 'external',
                source_provider: options.external_provider,
                ...(options.external_reference && { source_reference: options.external_reference }),
            }
        }
        await registerWorkspaceV1AgentWorkspacesPost({ body: body as Parameters<typeof registerWorkspaceV1AgentWorkspacesPost>[0]['body'] })
        await refresh()
    }, [refresh])

    const remove = useCallback(async (id: string) => {
        await unregisterWorkspaceV1AgentWorkspacesWorkspaceIdDelete({ path: { workspace_id: id } })
        await refresh()
    }, [refresh])

    useEffect(() => {
        refresh()
    }, [refresh])

    return { workspaces, loading, error, refresh, register, remove }
}