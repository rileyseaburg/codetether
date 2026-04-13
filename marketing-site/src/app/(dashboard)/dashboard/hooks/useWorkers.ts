// useWorkers Hook
// Worker state management

import { useState, useCallback, useEffect } from 'react'
import { listWorkersV1AgentWorkersGet, hasApiAuthToken } from '@/lib/api'
import type { Worker } from '../types'

interface UseWorkersReturn {
    workers: Worker[]
    loading: boolean
    error: string | null
    refresh: () => Promise<void>
}

export function useWorkers(): UseWorkersReturn {
    const [workers, setWorkers] = useState<Worker[]>([])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const refresh = useCallback(async () => {
        if (!hasApiAuthToken()) return
        setLoading(true)
        setError(null)
        try {
            const res = await listWorkersV1AgentWorkersGet({})
            const data = res.data as Record<string, unknown> | undefined
            const items = Array.isArray(data) ? data : (data?.workers ?? [])
            setWorkers((items as Worker[]).map((w: Worker) => ({
                ...w,
                worker_id: String(w.worker_id ?? ''),
                name: String(w.name ?? w.worker_id ?? ''),
                status: String(w.status ?? 'unknown'),
            })))
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to fetch workers')
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        refresh()
    }, [refresh])

    return { workers, loading, error, refresh }
}