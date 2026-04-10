'use client'

import { useEffect, useMemo, useState } from 'react'
import { useTenantApi } from '@/hooks/useTenantApi'

export interface Worker {
    worker_id: string
    name?: string
    capabilities?: string[]
    hostname?: string
    status?: string
    codebases?: string[]
    last_seen?: string
    worker_runtime?: 'rust' | 'python'
    worker_runtime_label?: string
    is_sse_connected?: boolean
}

interface ConnectedWorker {
    worker_id?: string
    agent_name?: string
    last_heartbeat?: string
}

export interface WorkerSelectorProps {
    value: string
    onChange: (workerId: string) => void
    className?: string
    workers?: Worker[]
    onlyConnected?: boolean
    disableDisconnected?: boolean
    includeAutoOption?: boolean
    autoOptionLabel?: string
    disabled?: boolean
    loading?: boolean
    error?: string | null
}

function isConnected(worker: Worker): boolean {
    if (typeof worker.is_sse_connected === 'boolean') {
        return worker.is_sse_connected
    }
    if (!worker.last_seen) return false
    const lastSeen = new Date(worker.last_seen).getTime()
    if (Number.isNaN(lastSeen)) return false
    return Date.now() - lastSeen < 120000
}

function formatWorkerLabel(worker: Worker): string {
    const displayName = (worker.name || worker.worker_id).trim()
    const effectiveRuntimeLabel = isConnected(worker) ? 'Rust Worker' : undefined
    const runtimeLabel =
        effectiveRuntimeLabel ||
        worker.worker_runtime_label ||
        (worker.worker_runtime === 'rust' ? 'Rust Worker' : 'CodeTether Python Worker')
    const connectionLabel = isConnected(worker) ? 'connected' : 'not connected'
    const statusValue = worker.status || connectionLabel
    return `${displayName} - ${runtimeLabel} (${statusValue})`
}

function mergeWorkerSources(
    workers: Worker[],
    connectedWorkers: ConnectedWorker[]
): Worker[] {
    const connectedMap = new Map(
        connectedWorkers
            .filter((w) => w.worker_id)
            .map((w) => [
                String(w.worker_id),
                {
                    name: w.agent_name,
                    last_seen: w.last_heartbeat,
                },
            ])
    )

    return workers.map((worker) => {
        const connected = connectedMap.get(worker.worker_id)
        return {
            ...worker,
            name: connected?.name || worker.name,
            last_seen: connected?.last_seen || worker.last_seen,
            is_sse_connected: Boolean(connected),
        }
    })
}

export function useWorkers(enabled: boolean = true) {
    const { tenantFetch } = useTenantApi()
    const [workers, setWorkers] = useState<Worker[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        if (!enabled) {
            setLoading(false)
            return
        }

        let cancelled = false

        const fetchWorkers = async () => {
            try {
                const [workersResponse, connectedResponse] = await Promise.all([
                    tenantFetch<Worker[]>('/v1/agent/workers'),
                    tenantFetch<{ workers?: ConnectedWorker[] }>('/v1/worker/connected'),
                ])

                if (workersResponse.error) {
                    throw new Error(workersResponse.error)
                }

                const baseWorkers = Array.isArray(workersResponse.data) ? workersResponse.data : []
                const connectedWorkers = connectedResponse.data?.workers || []
                const mergedWorkers = mergeWorkerSources(baseWorkers, connectedWorkers)

                if (!cancelled) {
                    setWorkers(mergedWorkers)
                    setError(null)
                }
            } catch (e) {
                if (!cancelled) {
                    setError(e instanceof Error ? e.message : 'Failed to load workers')
                    setWorkers([])
                }
            } finally {
                if (!cancelled) setLoading(false)
            }
        }

        fetchWorkers()
        return () => {
            cancelled = true
        }
    }, [enabled, tenantFetch])

    return { workers, loading, error }
}

export function WorkerSelector({
    value,
    onChange,
    className = '',
    workers: workersProp,
    onlyConnected = true,
    disableDisconnected = true,
    includeAutoOption = true,
    autoOptionLabel = 'Select a worker...',
    disabled = false,
    loading: loadingProp,
    error: errorProp,
}: WorkerSelectorProps) {
    const fetched = useWorkers(workersProp === undefined)
    const workers = workersProp ?? fetched.workers
    const loading = loadingProp ?? (workersProp ? false : fetched.loading)
    const error = errorProp ?? (workersProp ? null : fetched.error)

    const visibleWorkers = useMemo(() => {
        if (onlyConnected) return workers.filter(isConnected)
        return workers
    }, [onlyConnected, workers])

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

    if (workers.length === 0) {
        return (
            <div className={`px-3 py-2 text-sm text-yellow-600 dark:text-yellow-400 ${className}`}>
                No workers available
            </div>
        )
    }

    if (visibleWorkers.length === 0) {
        return (
            <div className={`px-3 py-2 text-sm text-orange-600 dark:text-orange-400 ${className}`}>
                No connected workers
            </div>
        )
    }

    return (
        <select
            value={value}
            onChange={(e) => onChange(e.target.value)}
            data-cy="worker-selector"
            disabled={disabled}
            className={`px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-white focus:ring-2 focus:ring-cyan-500 disabled:opacity-50 ${className}`}
        >
            {includeAutoOption ? <option value="">{autoOptionLabel}</option> : null}
            {visibleWorkers.map((worker) => {
                const connected = isConnected(worker)
                return (
                    <option
                        key={worker.worker_id}
                        value={worker.worker_id}
                        disabled={disableDisconnected && !connected}
                    >
                        {formatWorkerLabel(worker)}
                    </option>
                )
            })}
        </select>
    )
}

export default WorkerSelector
