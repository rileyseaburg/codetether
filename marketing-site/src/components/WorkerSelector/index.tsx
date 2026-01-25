'use client'

import { useState, useEffect } from 'react'
import { listWorkersV1OpencodeWorkersGet } from '@/lib/api'

export interface Worker {
    worker_id: string
    name: string
    capabilities: string[]
    hostname?: string
    status?: string
    codebases?: string[]
    last_seen?: string
}

export function useWorkers() {
    const [workers, setWorkers] = useState<Worker[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        const fetchWorkers = async () => {
            try {
                const result = await listWorkersV1OpencodeWorkersGet()
                if (result.data) {
                    const workersData = result.data as any
                    setWorkers(workersData.map((w: any) => ({
                        worker_id: w.worker_id,
                        name: w.name,
                        capabilities: w.capabilities,
                        hostname: w.hostname,
                        status: w.status,
                        codebases: w.codebases,
                        last_seen: w.last_seen,
                    })))
                }
            } catch (e) {
                setError(e instanceof Error ? e.message : 'Failed to load workers')
            } finally {
                setLoading(false)
            }
        }
        fetchWorkers()
    }, [])

    return { workers, loading, error }
}

function isOnline(worker: Worker): boolean {
    if (!worker.last_seen) return false
    const now = Date.now()
    const lastSeen = new Date(worker.last_seen).getTime()
    return (now - lastSeen) < 120000 // Less than 2 minutes ago
}

export function WorkerSelector({ 
    value, 
    onChange, 
    className 
}: { 
    value: string
    onChange: (workerId: string) => void
    className?: string
}) {
    const { workers, loading, error } = useWorkers()

    if (loading) {
        return (
            <div className={`px-3 py-2 text-sm text-gray-500 dark:text-gray-400 ${className}`}>
                Loading workers...
            </div>
        )
    }

    if (error) {
        return (
            <div className={`px-3 py-2 text-sm text-red-500 ${className}`}>
                {error}
            </div>
        )
    }

    const onlineWorkers = workers.filter(isOnline)

    if (workers.length === 0) {
        return (
            <div className={`px-3 py-2 text-sm text-yellow-600 dark:text-yellow-400 ${className}`}>
                No workers available
            </div>
        )
    }

    if (onlineWorkers.length === 0) {
        return (
            <div className={`px-3 py-2 text-sm text-orange-600 dark:text-orange-400 ${className}`}>
                No online workers - {workers.length} stale
            </div>
        )
    }

    return (
        <select
            value={value}
            onChange={(e) => onChange(e.target.value)}
            data-cy="worker-selector"
            className={`px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-white focus:ring-2 focus:ring-cyan-500 ${className}`}
        >
            <option value="">Select a worker...</option>
            {onlineWorkers.map((w) => (
                <option key={w.worker_id} value={w.worker_id}>
                    {w.name} ({w.worker_id})
                </option>
            ))}
        </select>
    )
}

export default WorkerSelector
