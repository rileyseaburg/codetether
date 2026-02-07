'use client'

import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.codetether.run'

interface CognitionStatus {
    enabled: boolean
    running: boolean
    loop_interval_ms: number
    started_at: string | null
    last_tick_at: string | null
    persona_count: number
    active_persona_count: number
    events_buffered: number
    snapshots_buffered: number
}

interface MemorySnapshot {
    id: string
    generated_at: string
    swarm_id: string | null
    persona_scope: string[]
    summary: string
    hot_event_count: number
    warm_fact_count: number
    cold_snapshot_count: number
    metadata: Record<string, unknown>
}

interface LineageNode {
    persona_id: string
    parent_id: string | null
    children: string[]
    depth: number
    status: string
}

interface LineageGraph {
    nodes: LineageNode[]
    roots: string[]
    total_edges: number
}

interface ThoughtEvent {
    id: string
    event_type: string
    persona_id: string | null
    swarm_id: string | null
    timestamp: string
    payload: Record<string, unknown> | unknown
}

interface PersonaRuntimeState {
    identity: {
        id: string
    }
}

interface ReapPersonaResponse {
    reaped_ids: string[]
    count: number
}

interface PersonaFormState {
    persona_id: string
    name: string
    role: string
    charter: string
    swarm_id: string
}

const inputClassName =
    'mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 ' +
    'focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500 dark:border-gray-700 ' +
    'dark:bg-gray-900 dark:text-gray-100'

function formatDateTime(timestamp: string | null | undefined) {
    if (!timestamp) return 'N/A'
    const date = new Date(timestamp)
    if (Number.isNaN(date.getTime())) return 'N/A'
    return date.toLocaleString()
}

function formatEventType(eventType: string) {
    return eventType.replaceAll('_', ' ')
}

function statusBadgeClass(status: string) {
    switch (status) {
        case 'active':
            return 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
        case 'idle':
            return 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
        case 'reaped':
            return 'bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
        case 'error':
            return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
        default:
            return 'bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
    }
}

async function readErrorMessage(response: Response): Promise<string> {
    const text = await response.text()
    if (!text) {
        return `Request failed (${response.status})`
    }

    try {
        const parsed = JSON.parse(text) as { detail?: string; error?: string; message?: string }
        if (typeof parsed.detail === 'string' && parsed.detail.length > 0) return parsed.detail
        if (typeof parsed.error === 'string' && parsed.error.length > 0) return parsed.error
        if (typeof parsed.message === 'string' && parsed.message.length > 0) return parsed.message
    } catch {
        return text
    }

    return text
}

function getAuthHeaders(includeJson: boolean, extraHeaders?: HeadersInit): Headers {
    const headers = new Headers(extraHeaders)
    if (includeJson && !headers.has('Content-Type')) {
        headers.set('Content-Type', 'application/json')
    }

    if (typeof window !== 'undefined') {
        const token = localStorage.getItem('a2a_token')
        if (token && !headers.has('Authorization')) {
            headers.set('Authorization', `Bearer ${token}`)
        }
    }

    return headers
}

export default function CognitionPage() {
    const [status, setStatus] = useState<CognitionStatus | null>(null)
    const [snapshot, setSnapshot] = useState<MemorySnapshot | null>(null)
    const [lineage, setLineage] = useState<LineageGraph | null>(null)
    const [events, setEvents] = useState<ThoughtEvent[]>([])

    const [connected, setConnected] = useState(false)
    const [streamLagNotice, setStreamLagNotice] = useState<string | null>(null)
    const [loading, setLoading] = useState(true)
    const [refreshing, setRefreshing] = useState(false)
    const [submitting, setSubmitting] = useState<string | null>(null)

    const [error, setError] = useState<string | null>(null)
    const [success, setSuccess] = useState<string | null>(null)

    const [loopIntervalMs, setLoopIntervalMs] = useState('2000')
    const [seedEnabled, setSeedEnabled] = useState(false)
    const [seedPersonaId, setSeedPersonaId] = useState('')
    const [seedName, setSeedName] = useState('')
    const [seedRole, setSeedRole] = useState('')
    const [seedCharter, setSeedCharter] = useState('')
    const [seedSwarmId, setSeedSwarmId] = useState('')
    const [stopReason, setStopReason] = useState('')

    const [createPersona, setCreatePersona] = useState<PersonaFormState>({
        persona_id: '',
        name: '',
        role: '',
        charter: '',
        swarm_id: '',
    })
    const [spawnParentId, setSpawnParentId] = useState('')
    const [spawnPersona, setSpawnPersona] = useState<PersonaFormState>({
        persona_id: '',
        name: '',
        role: '',
        charter: '',
        swarm_id: '',
    })
    const [reapPersonaId, setReapPersonaId] = useState('')
    const [reapCascade, setReapCascade] = useState(false)
    const [reapReason, setReapReason] = useState('')

    const request = useCallback(
        async <T,>(
            path: string,
            init: RequestInit = {},
            allowNotFound = false
        ): Promise<T | null> => {
            const response = await fetch(`${API_URL}${path}`, {
                ...init,
                headers: getAuthHeaders(Boolean(init.body), init.headers),
                credentials: 'include',
            })

            if (allowNotFound && response.status === 404) {
                return null
            }

            if (!response.ok) {
                throw new Error(await readErrorMessage(response))
            }

            if (response.status === 204) {
                return null
            }

            return (await response.json()) as T
        },
        []
    )

    const loadStatus = useCallback(async () => {
        const data = await request<CognitionStatus>('/v1/cognition/status')
        if (data) {
            setStatus(data)
            setLoopIntervalMs(String(data.loop_interval_ms))
        }
    }, [request])

    const loadSnapshot = useCallback(async () => {
        const data = await request<MemorySnapshot>('/v1/cognition/snapshots/latest', {}, true)
        setSnapshot(data)
    }, [request])

    const loadLineage = useCallback(async () => {
        const data = await request<LineageGraph>('/v1/swarm/lineage')
        if (data) {
            setLineage(data)
        }
    }, [request])

    const refreshAll = useCallback(
        async (showSpinner: boolean) => {
            if (showSpinner) setRefreshing(true)
            try {
                await Promise.all([loadStatus(), loadSnapshot(), loadLineage()])
                setError(null)
            } catch (refreshError) {
                setError(
                    refreshError instanceof Error
                        ? refreshError.message
                        : 'Failed to refresh cognition state'
                )
            } finally {
                if (showSpinner) setRefreshing(false)
            }
        },
        [loadLineage, loadSnapshot, loadStatus]
    )

    useEffect(() => {
        let stopped = false

        const initialize = async () => {
            try {
                await refreshAll(false)
            } finally {
                if (!stopped) setLoading(false)
            }
        }

        initialize()
        const interval = setInterval(() => {
            void refreshAll(false)
        }, 10000)

        return () => {
            stopped = true
            clearInterval(interval)
        }
    }, [refreshAll])

    useEffect(() => {
        const source = new EventSource(`${API_URL}/v1/cognition/stream`)

        const handleCognitionEvent = (event: MessageEvent) => {
            try {
                const parsed = JSON.parse(event.data as string) as ThoughtEvent
                setEvents((current) => [parsed, ...current].slice(0, 120))
                if (parsed.event_type === 'persona_spawned' || parsed.event_type === 'persona_reaped') {
                    void loadLineage()
                    void loadStatus()
                }
                if (parsed.event_type === 'snapshot_compressed') {
                    void loadSnapshot()
                    void loadStatus()
                }
            } catch {
                // Ignore parse failures from non-event payloads.
            }
        }

        const handleLagEvent = (event: MessageEvent) => {
            setStreamLagNotice(event.data as string)
        }

        source.onopen = () => {
            setConnected(true)
            setStreamLagNotice(null)
        }
        source.onerror = () => {
            setConnected(false)
        }

        source.addEventListener('cognition', handleCognitionEvent as EventListener)
        source.addEventListener('lag', handleLagEvent as EventListener)

        return () => {
            source.removeEventListener('cognition', handleCognitionEvent as EventListener)
            source.removeEventListener('lag', handleLagEvent as EventListener)
            source.close()
        }
    }, [loadLineage, loadSnapshot, loadStatus])

    const clearMessages = () => {
        setError(null)
        setSuccess(null)
    }

    const handleStart = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault()
        clearMessages()
        setSubmitting('start')

        try {
            const payload: Record<string, unknown> = {}
            const intervalNumber = Number(loopIntervalMs)
            if (Number.isFinite(intervalNumber) && intervalNumber > 0) {
                payload.loop_interval_ms = intervalNumber
            }

            if (seedEnabled) {
                if (!seedName.trim() || !seedRole.trim() || !seedCharter.trim()) {
                    throw new Error('Seed persona requires name, role, and charter')
                }

                payload.seed_persona = {
                    persona_id: seedPersonaId.trim() || undefined,
                    name: seedName.trim(),
                    role: seedRole.trim(),
                    charter: seedCharter.trim(),
                    swarm_id: seedSwarmId.trim() || undefined,
                }
            }

            const nextStatus = await request<CognitionStatus>('/v1/cognition/start', {
                method: 'POST',
                body: JSON.stringify(payload),
            })

            if (nextStatus) setStatus(nextStatus)
            setSuccess('Cognition loop started')
            setStopReason('')
            await Promise.all([loadLineage(), loadSnapshot()])
        } catch (startError) {
            setError(startError instanceof Error ? startError.message : 'Failed to start cognition')
        } finally {
            setSubmitting(null)
        }
    }

    const handleStop = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault()
        clearMessages()
        setSubmitting('stop')

        try {
            const body = stopReason.trim() ? { reason: stopReason.trim() } : {}
            const nextStatus = await request<CognitionStatus>('/v1/cognition/stop', {
                method: 'POST',
                body: JSON.stringify(body),
            })

            if (nextStatus) setStatus(nextStatus)
            setSuccess('Cognition loop stopped')
        } catch (stopError) {
            setError(stopError instanceof Error ? stopError.message : 'Failed to stop cognition')
        } finally {
            setSubmitting(null)
        }
    }

    const handleCreatePersona = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault()
        clearMessages()
        setSubmitting('create')

        try {
            if (!createPersona.name.trim() || !createPersona.role.trim() || !createPersona.charter.trim()) {
                throw new Error('Create persona requires name, role, and charter')
            }

            const created = await request<PersonaRuntimeState>('/v1/swarm/personas', {
                method: 'POST',
                body: JSON.stringify({
                    persona_id: createPersona.persona_id.trim() || undefined,
                    name: createPersona.name.trim(),
                    role: createPersona.role.trim(),
                    charter: createPersona.charter.trim(),
                    swarm_id: createPersona.swarm_id.trim() || undefined,
                }),
            })

            setSuccess(`Created persona ${created?.identity.id || createPersona.name.trim()}`)
            setCreatePersona({
                persona_id: '',
                name: '',
                role: '',
                charter: '',
                swarm_id: createPersona.swarm_id,
            })
            await Promise.all([loadStatus(), loadLineage()])
        } catch (createError) {
            setError(createError instanceof Error ? createError.message : 'Failed to create persona')
        } finally {
            setSubmitting(null)
        }
    }

    const handleSpawnPersona = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault()
        clearMessages()
        setSubmitting('spawn')

        try {
            if (!spawnParentId.trim()) throw new Error('Parent persona id is required')
            if (!spawnPersona.name.trim() || !spawnPersona.role.trim() || !spawnPersona.charter.trim()) {
                throw new Error('Spawn persona requires name, role, and charter')
            }

            const created = await request<PersonaRuntimeState>(
                `/v1/swarm/personas/${encodeURIComponent(spawnParentId.trim())}/spawn`,
                {
                    method: 'POST',
                    body: JSON.stringify({
                        persona_id: spawnPersona.persona_id.trim() || undefined,
                        name: spawnPersona.name.trim(),
                        role: spawnPersona.role.trim(),
                        charter: spawnPersona.charter.trim(),
                        swarm_id: spawnPersona.swarm_id.trim() || undefined,
                    }),
                }
            )

            setSuccess(`Spawned persona ${created?.identity.id || spawnPersona.name.trim()}`)
            setSpawnPersona({
                persona_id: '',
                name: '',
                role: '',
                charter: '',
                swarm_id: spawnPersona.swarm_id,
            })
            await Promise.all([loadStatus(), loadLineage()])
        } catch (spawnError) {
            setError(spawnError instanceof Error ? spawnError.message : 'Failed to spawn persona')
        } finally {
            setSubmitting(null)
        }
    }

    const handleReapPersona = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault()
        clearMessages()
        setSubmitting('reap')

        try {
            if (!reapPersonaId.trim()) throw new Error('Persona id is required for reaping')

            const response = await request<ReapPersonaResponse>(
                `/v1/swarm/personas/${encodeURIComponent(reapPersonaId.trim())}/reap`,
                {
                    method: 'POST',
                    body: JSON.stringify({
                        cascade: reapCascade,
                        reason: reapReason.trim() || undefined,
                    }),
                }
            )

            setSuccess(`Reaped ${response?.count ?? 0} persona(s)`)
            await Promise.all([loadStatus(), loadLineage()])
        } catch (reapError) {
            setError(reapError instanceof Error ? reapError.message : 'Failed to reap persona')
        } finally {
            setSubmitting(null)
        }
    }

    const sortedNodes = useMemo(() => {
        return [...(lineage?.nodes ?? [])].sort(
            (left, right) => left.depth - right.depth || left.persona_id.localeCompare(right.persona_id)
        )
    }, [lineage])

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-100">
                <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-cyan-500" />
            </div>
        )
    }

    return (
        <div className="mx-auto max-w-7xl space-y-6 p-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Cognition</h1>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                        Perpetual persona swarm control plane and live thought stream
                    </p>
                </div>
                <button
                    onClick={() => void refreshAll(true)}
                    disabled={refreshing}
                    className="rounded-md bg-cyan-600 px-4 py-2 text-sm font-medium text-white hover:bg-cyan-500 disabled:opacity-50"
                >
                    {refreshing ? 'Refreshing...' : 'Refresh'}
                </button>
            </div>

            {error && (
                <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-900/30 dark:text-red-300">
                    {error}
                </div>
            )}
            {success && (
                <div className="rounded-md border border-green-200 bg-green-50 p-3 text-sm text-green-700 dark:border-green-900 dark:bg-green-900/30 dark:text-green-300">
                    {success}
                </div>
            )}

            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
                    <div className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Runtime</div>
                    <div className="mt-2 flex items-center gap-2">
                        <span
                            className={`h-2.5 w-2.5 rounded-full ${
                                status?.running ? 'bg-green-500 animate-pulse' : 'bg-gray-400'
                            }`}
                        />
                        <span className="text-sm font-semibold text-gray-900 dark:text-white">
                            {status?.running ? 'Running' : 'Stopped'}
                        </span>
                    </div>
                    <div className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                        Loop: {status?.loop_interval_ms ?? 'N/A'} ms
                    </div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                        Last tick: {formatDateTime(status?.last_tick_at)}
                    </div>
                </div>

                <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
                    <div className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Personas</div>
                    <div className="mt-2 text-2xl font-bold text-gray-900 dark:text-white">
                        {status?.persona_count ?? 0}
                    </div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                        Active: {status?.active_persona_count ?? 0}
                    </div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                        Roots: {lineage?.roots?.length ?? 0}
                    </div>
                </div>

                <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
                    <div className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Buffers</div>
                    <div className="mt-2 text-sm text-gray-700 dark:text-gray-200">
                        Events: {status?.events_buffered ?? 0}
                    </div>
                    <div className="text-sm text-gray-700 dark:text-gray-200">
                        Snapshots: {status?.snapshots_buffered ?? 0}
                    </div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                        Edges: {lineage?.total_edges ?? 0}
                    </div>
                </div>

                <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
                    <div className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Stream</div>
                    <div className="mt-2 flex items-center gap-2 text-sm font-semibold">
                        <span
                            className={`h-2.5 w-2.5 rounded-full ${
                                connected ? 'bg-green-500 animate-pulse' : 'bg-red-500'
                            }`}
                        />
                        <span className="text-gray-900 dark:text-white">
                            {connected ? 'Connected' : 'Disconnected'}
                        </span>
                    </div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                        Events shown: {events.length}
                    </div>
                    {streamLagNotice && (
                        <div className="mt-2 text-xs text-yellow-600 dark:text-yellow-400">
                            Stream lag: {streamLagNotice}
                        </div>
                    )}
                </div>
            </div>

            <div className="grid gap-6 xl:grid-cols-2">
                <div className="space-y-4 rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
                    <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Loop Controls</h2>

                    <form onSubmit={handleStart} className="space-y-3">
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-200">
                            Loop interval (ms)
                            <input
                                type="number"
                                min={250}
                                step={250}
                                value={loopIntervalMs}
                                onChange={(event) => setLoopIntervalMs(event.target.value)}
                                className={inputClassName}
                            />
                        </label>

                        <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-200">
                            <input
                                type="checkbox"
                                checked={seedEnabled}
                                onChange={(event) => setSeedEnabled(event.target.checked)}
                            />
                            Seed persona on start
                        </label>

                        {seedEnabled && (
                            <div className="grid gap-3 sm:grid-cols-2">
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-200">
                                    Seed name
                                    <input
                                        value={seedName}
                                        onChange={(event) => setSeedName(event.target.value)}
                                        className={inputClassName}
                                    />
                                </label>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-200">
                                    Seed role
                                    <input
                                        value={seedRole}
                                        onChange={(event) => setSeedRole(event.target.value)}
                                        className={inputClassName}
                                    />
                                </label>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-200">
                                    Seed charter
                                    <input
                                        value={seedCharter}
                                        onChange={(event) => setSeedCharter(event.target.value)}
                                        className={inputClassName}
                                    />
                                </label>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-200">
                                    Seed swarm id
                                    <input
                                        value={seedSwarmId}
                                        onChange={(event) => setSeedSwarmId(event.target.value)}
                                        className={inputClassName}
                                    />
                                </label>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-200 sm:col-span-2">
                                    Seed persona id (optional)
                                    <input
                                        value={seedPersonaId}
                                        onChange={(event) => setSeedPersonaId(event.target.value)}
                                        className={inputClassName}
                                    />
                                </label>
                            </div>
                        )}

                        <button
                            type="submit"
                            disabled={submitting === 'start'}
                            className="rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-500 disabled:opacity-50"
                        >
                            {submitting === 'start' ? 'Starting...' : 'Start Cognition'}
                        </button>
                    </form>

                    <form onSubmit={handleStop} className="space-y-3 border-t border-gray-200 pt-3 dark:border-gray-700">
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-200">
                            Stop reason (optional)
                            <input
                                value={stopReason}
                                onChange={(event) => setStopReason(event.target.value)}
                                className={inputClassName}
                            />
                        </label>
                        <button
                            type="submit"
                            disabled={submitting === 'stop'}
                            className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-500 disabled:opacity-50"
                        >
                            {submitting === 'stop' ? 'Stopping...' : 'Stop Cognition'}
                        </button>
                    </form>
                </div>

                <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
                    <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Latest Snapshot</h2>
                    {!snapshot ? (
                        <p className="mt-3 text-sm text-gray-500 dark:text-gray-400">
                            No snapshots available yet.
                        </p>
                    ) : (
                        <div className="mt-3 space-y-2 text-sm">
                            <div className="text-gray-700 dark:text-gray-200">
                                <span className="font-medium">Generated:</span>{' '}
                                {formatDateTime(snapshot.generated_at)}
                            </div>
                            <div className="text-gray-700 dark:text-gray-200">
                                <span className="font-medium">Swarm:</span> {snapshot.swarm_id || 'N/A'}
                            </div>
                            <div className="text-gray-700 dark:text-gray-200">
                                <span className="font-medium">Scope:</span>{' '}
                                {snapshot.persona_scope.length > 0
                                    ? snapshot.persona_scope.join(', ')
                                    : 'N/A'}
                            </div>
                            <div className="rounded-md bg-gray-50 p-3 text-sm text-gray-700 dark:bg-gray-900 dark:text-gray-200">
                                {snapshot.summary}
                            </div>
                            <div className="grid grid-cols-3 gap-2 text-xs text-gray-500 dark:text-gray-400">
                                <span>Hot: {snapshot.hot_event_count}</span>
                                <span>Warm: {snapshot.warm_fact_count}</span>
                                <span>Cold: {snapshot.cold_snapshot_count}</span>
                            </div>
                        </div>
                    )}
                </div>
            </div>

            <div className="grid gap-4 xl:grid-cols-3">
                <form
                    onSubmit={handleCreatePersona}
                    className="space-y-3 rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800"
                >
                    <h2 className="text-base font-semibold text-gray-900 dark:text-white">Create Root Persona</h2>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-200">
                        Name
                        <input
                            value={createPersona.name}
                            onChange={(event) =>
                                setCreatePersona((current) => ({ ...current, name: event.target.value }))
                            }
                            className={inputClassName}
                        />
                    </label>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-200">
                        Role
                        <input
                            value={createPersona.role}
                            onChange={(event) =>
                                setCreatePersona((current) => ({ ...current, role: event.target.value }))
                            }
                            className={inputClassName}
                        />
                    </label>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-200">
                        Charter
                        <input
                            value={createPersona.charter}
                            onChange={(event) =>
                                setCreatePersona((current) => ({ ...current, charter: event.target.value }))
                            }
                            className={inputClassName}
                        />
                    </label>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-200">
                        Swarm id
                        <input
                            value={createPersona.swarm_id}
                            onChange={(event) =>
                                setCreatePersona((current) => ({ ...current, swarm_id: event.target.value }))
                            }
                            className={inputClassName}
                        />
                    </label>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-200">
                        Persona id (optional)
                        <input
                            value={createPersona.persona_id}
                            onChange={(event) =>
                                setCreatePersona((current) => ({ ...current, persona_id: event.target.value }))
                            }
                            className={inputClassName}
                        />
                    </label>
                    <button
                        type="submit"
                        disabled={submitting === 'create'}
                        className="rounded-md bg-cyan-600 px-4 py-2 text-sm font-medium text-white hover:bg-cyan-500 disabled:opacity-50"
                    >
                        {submitting === 'create' ? 'Creating...' : 'Create Persona'}
                    </button>
                </form>

                <form
                    onSubmit={handleSpawnPersona}
                    className="space-y-3 rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800"
                >
                    <h2 className="text-base font-semibold text-gray-900 dark:text-white">Spawn Child Persona</h2>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-200">
                        Parent persona id
                        <input
                            value={spawnParentId}
                            onChange={(event) => setSpawnParentId(event.target.value)}
                            className={inputClassName}
                        />
                    </label>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-200">
                        Name
                        <input
                            value={spawnPersona.name}
                            onChange={(event) =>
                                setSpawnPersona((current) => ({ ...current, name: event.target.value }))
                            }
                            className={inputClassName}
                        />
                    </label>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-200">
                        Role
                        <input
                            value={spawnPersona.role}
                            onChange={(event) =>
                                setSpawnPersona((current) => ({ ...current, role: event.target.value }))
                            }
                            className={inputClassName}
                        />
                    </label>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-200">
                        Charter
                        <input
                            value={spawnPersona.charter}
                            onChange={(event) =>
                                setSpawnPersona((current) => ({ ...current, charter: event.target.value }))
                            }
                            className={inputClassName}
                        />
                    </label>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-200">
                        Swarm id
                        <input
                            value={spawnPersona.swarm_id}
                            onChange={(event) =>
                                setSpawnPersona((current) => ({ ...current, swarm_id: event.target.value }))
                            }
                            className={inputClassName}
                        />
                    </label>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-200">
                        Persona id (optional)
                        <input
                            value={spawnPersona.persona_id}
                            onChange={(event) =>
                                setSpawnPersona((current) => ({ ...current, persona_id: event.target.value }))
                            }
                            className={inputClassName}
                        />
                    </label>
                    <button
                        type="submit"
                        disabled={submitting === 'spawn'}
                        className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
                    >
                        {submitting === 'spawn' ? 'Spawning...' : 'Spawn Persona'}
                    </button>
                </form>

                <form
                    onSubmit={handleReapPersona}
                    className="space-y-3 rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800"
                >
                    <h2 className="text-base font-semibold text-gray-900 dark:text-white">Reap Persona</h2>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-200">
                        Persona id
                        <input
                            value={reapPersonaId}
                            onChange={(event) => setReapPersonaId(event.target.value)}
                            className={inputClassName}
                        />
                    </label>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-200">
                        Reason (optional)
                        <input
                            value={reapReason}
                            onChange={(event) => setReapReason(event.target.value)}
                            className={inputClassName}
                        />
                    </label>
                    <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-200">
                        <input
                            type="checkbox"
                            checked={reapCascade}
                            onChange={(event) => setReapCascade(event.target.checked)}
                        />
                        Cascade to descendants
                    </label>
                    <button
                        type="submit"
                        disabled={submitting === 'reap'}
                        className="rounded-md bg-orange-600 px-4 py-2 text-sm font-medium text-white hover:bg-orange-500 disabled:opacity-50"
                    >
                        {submitting === 'reap' ? 'Reaping...' : 'Reap Persona'}
                    </button>
                </form>
            </div>

            <div className="grid gap-6 xl:grid-cols-2">
                <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
                    <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Lineage</h2>
                    {sortedNodes.length === 0 ? (
                        <p className="mt-3 text-sm text-gray-500 dark:text-gray-400">
                            No personas currently in lineage.
                        </p>
                    ) : (
                        <div className="mt-3 max-h-[420px] space-y-2 overflow-y-auto pr-1">
                            {sortedNodes.map((node) => (
                                <div
                                    key={node.persona_id}
                                    className="rounded-md border border-gray-200 p-2 dark:border-gray-700"
                                >
                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                        <div
                                            className="font-mono text-xs text-gray-800 dark:text-gray-200"
                                            style={{ paddingLeft: `${Math.min(node.depth, 8) * 12}px` }}
                                        >
                                            {node.persona_id}
                                        </div>
                                        <span
                                            className={`rounded-full px-2 py-0.5 text-xs ${statusBadgeClass(
                                                node.status
                                            )}`}
                                        >
                                            {node.status}
                                        </span>
                                    </div>
                                    <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                        parent: {node.parent_id || 'root'} | depth: {node.depth} | children:{' '}
                                        {node.children.length}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
                    <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Live Thought Stream</h2>
                    {events.length === 0 ? (
                        <p className="mt-3 text-sm text-gray-500 dark:text-gray-400">
                            Waiting for cognition events...
                        </p>
                    ) : (
                        <div className="mt-3 max-h-[420px] space-y-2 overflow-y-auto pr-1">
                            {events.map((item) => (
                                <div
                                    key={item.id}
                                    className="rounded-md border border-gray-200 p-3 dark:border-gray-700"
                                >
                                    <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                                        <span className="rounded bg-gray-100 px-2 py-0.5 font-mono text-gray-700 dark:bg-gray-900 dark:text-gray-300">
                                            {formatEventType(item.event_type)}
                                        </span>
                                        <span className="text-gray-500 dark:text-gray-400">
                                            {formatDateTime(item.timestamp)}
                                        </span>
                                    </div>
                                    <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                        persona: {item.persona_id || 'system'} | swarm:{' '}
                                        {item.swarm_id || 'N/A'}
                                    </div>
                                    <pre className="mt-2 max-h-24 overflow-y-auto whitespace-pre-wrap break-all rounded bg-gray-50 p-2 text-xs text-gray-700 dark:bg-gray-900 dark:text-gray-300">
                                        {JSON.stringify(item.payload, null, 2)}
                                    </pre>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}
