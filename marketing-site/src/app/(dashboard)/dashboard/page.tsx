'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { useSession, signOut } from 'next-auth/react'
import VoiceChatButton from './components/voice/VoiceChatButton'
import TenantStatusBanner from '@/components/TenantStatusBanner'
import { ModelSelector } from '@/components/ModelSelector'
import { WorkerSelector } from '@/components/WorkerSelector'
import { useRalphStore } from './ralph/store'
import { useTenantApi } from '@/hooks/useTenantApi'
import {
    listCodebasesV1AgentCodebasesListGet,
    listAllTasksV1AgentTasksGet,
    listWorkersV1AgentWorkersGet,
    triggerAgentV1AgentCodebasesCodebaseIdTriggerPost,
    registerCodebaseV1AgentCodebasesPost,
    unregisterCodebaseV1AgentCodebasesCodebaseIdDelete,
    hasApiAuthToken,
} from '@/lib/api'

interface Codebase {
    id: string
    name: string
    path: string
    description?: string
    status: string
    worker_id?: string
}

interface Worker {
    worker_id: string
    name: string
    hostname?: string
    status: string
    global_codebase_id?: string
    last_seen?: string
    is_sse_connected?: boolean
}

type SwarmSubtaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'timed_out' | 'cancelled' | 'unknown'

interface SwarmSubtaskState {
    id: string
    status: SwarmSubtaskStatus
    tool?: string
    error?: string
    updatedAt: number
}

interface SwarmMonitorState {
    connected: boolean
    status: 'idle' | 'running' | 'completed' | 'failed'
    plannedSubtasks: number | null
    currentStage: number | null
    stageCompleted: number
    stageFailed: number
    speedup: number | null
    subtasks: Record<string, SwarmSubtaskState>
    recentLines: string[]
    lastUpdatedAt: number | null
    routing?: SwarmRoutingSnapshot
    error?: string
}

interface SwarmRoutingSnapshot {
    complexity?: string
    modelTier?: string
    modelRef?: string
    targetAgentName?: string
    workerPersonality?: string
    source: 'trigger' | 'task' | 'stream'
    updatedAt: number
}

const INITIAL_SWARM_MONITOR: SwarmMonitorState = {
    connected: false,
    status: 'idle',
    plannedSubtasks: null,
    currentStage: null,
    stageCompleted: 0,
    stageFailed: 0,
    speedup: null,
    subtasks: {},
    recentLines: [],
    lastUpdatedAt: null,
}

const asRecord = (value: unknown): Record<string, unknown> | null => {
    if (!value || typeof value !== 'object') {
        return null
    }
    return value as Record<string, unknown>
}

const getString = (record: Record<string, unknown> | null, keys: string[]): string | undefined => {
    if (!record) return undefined
    for (const key of keys) {
        const value = record[key]
        if (typeof value === 'string') {
            const trimmed = value.trim()
            if (trimmed) return trimmed
        }
    }
    return undefined
}

const extractRoutingSnapshot = (value: unknown): Omit<SwarmRoutingSnapshot, 'source' | 'updatedAt'> | null => {
    const root = asRecord(value)
    if (!root) return null
    const nestedRouting = asRecord(root.routing)
    const routing = nestedRouting ?? root
    const complexity = getString(routing, ['complexity'])
    const modelTier = getString(routing, ['model_tier', 'modelTier', 'tier'])
    const modelRef =
        getString(routing, ['model_ref', 'modelRef']) ??
        getString(root, ['model_ref', 'modelRef'])
    const targetAgentName = getString(routing, ['target_agent_name', 'targetAgentName'])
    const workerPersonality = getString(routing, ['worker_personality', 'workerPersonality'])

    if (!complexity && !modelTier && !modelRef && !targetAgentName && !workerPersonality) {
        return null
    }

    return {
        complexity,
        modelTier,
        modelRef,
        targetAgentName,
        workerPersonality,
    }
}

const isSwarmAgentType = (value: unknown): boolean => {
    if (typeof value !== 'string') return false
    const normalized = value.trim().toLowerCase()
    return normalized === 'swarm' || normalized === 'parallel' || normalized === 'multi-agent'
}

const normalizeSwarmStatus = (raw: string): SwarmSubtaskStatus => {
    const normalized = raw.trim().toLowerCase().replace(/\s+/g, '_')
    if (normalized === 'pending' || normalized === 'running' || normalized === 'completed' || normalized === 'failed' || normalized === 'timed_out' || normalized === 'cancelled') {
        return normalized
    }
    if (normalized === 'timedout') {
        return 'timed_out'
    }
    return 'unknown'
}

const applySwarmLine = (state: SwarmMonitorState, line: string): SwarmMonitorState => {
    const trimmed = line.trim()
    if (!trimmed.toLowerCase().includes('[swarm]')) {
        return state
    }

    const now = Date.now()
    const next: SwarmMonitorState = {
        ...state,
        lastUpdatedAt: now,
        recentLines: [...state.recentLines, trimmed].slice(-120),
    }

    const startedMatch = trimmed.match(/started\b.*planned_subtasks=(\d+)/i)
    if (startedMatch) {
        next.status = 'running'
        const planned = Number(startedMatch[1])
        next.plannedSubtasks = Number.isFinite(planned) ? planned : null
        next.error = undefined
        return next
    }

    const stageMatch =
        trimmed.match(/stage=(\d+)\s+completed=(\d+)\s+failed=(\d+)/i) ||
        trimmed.match(/stage\s+(\d+)\s+complete:\s+(\d+)\s+succeeded,\s+(\d+)\s+failed/i)
    if (stageMatch) {
        next.currentStage = Number(stageMatch[1]) || 0
        next.stageCompleted = Number(stageMatch[2]) || 0
        next.stageFailed = Number(stageMatch[3]) || 0
        return next
    }

    const routingMatch = trimmed.match(
        /\[swarm\]\s+routing\s+complexity=([^\s]+)\s+tier=([^\s]+)\s+personality=([^\s]+)\s+target_agent=([^\s]+)/i
    )
    if (routingMatch) {
        const complexity = routingMatch[1]
        const modelTier = routingMatch[2]
        const workerPersonality = routingMatch[3]
        const targetAgentName = routingMatch[4]
        next.routing = {
            ...next.routing,
            complexity: complexity === 'unknown' ? next.routing?.complexity : complexity,
            modelTier: modelTier === 'unknown' ? next.routing?.modelTier : modelTier,
            workerPersonality: workerPersonality === 'auto' ? next.routing?.workerPersonality : workerPersonality,
            targetAgentName: targetAgentName === 'auto' ? next.routing?.targetAgentName : targetAgentName,
            source: 'stream',
            updatedAt: now,
        }
        return next
    }

    const configTierMatch = trimmed.match(/\[swarm\]\s+config\b.*\btier=([A-Za-z0-9_-]+)/i)
    if (configTierMatch) {
        next.routing = {
            ...next.routing,
            modelTier: configTierMatch[1],
            source: 'stream',
            updatedAt: now,
        }
        return next
    }

    const subtaskStatusMatch =
        trimmed.match(/subtask(?:\s+id=|\s+)([A-Za-z0-9_-]+)\s+status=([A-Za-z_]+)/i) ||
        trimmed.match(/subtask\s+([A-Za-z0-9_-]+)\s+->\s+([A-Za-z_]+)/i)
    if (subtaskStatusMatch) {
        const id = subtaskStatusMatch[1]
        const status = normalizeSwarmStatus(subtaskStatusMatch[2])
        next.subtasks = {
            ...next.subtasks,
            [id]: {
                ...(next.subtasks[id] ?? { id, updatedAt: now }),
                id,
                status,
                updatedAt: now,
            },
        }
        return next
    }

    const toolMatch =
        trimmed.match(/subtask(?:\s+id=|\s+)([A-Za-z0-9_-]+)\s+tool(?:=|:\s*)(.+)$/i) ||
        trimmed.match(/\[swarm\]\s+([A-Za-z0-9_-]+)\s+tool:\s+(.+)$/i)
    if (toolMatch) {
        const id = toolMatch[1]
        const tool = toolMatch[2].trim()
        next.subtasks = {
            ...next.subtasks,
            [id]: {
                ...(next.subtasks[id] ?? { id, status: 'running' as SwarmSubtaskStatus, updatedAt: now }),
                id,
                status: next.subtasks[id]?.status ?? 'running',
                tool,
                updatedAt: now,
            },
        }
        return next
    }

    const subtaskErrorMatch =
        trimmed.match(/subtask(?:\s+id=|\s+)([A-Za-z0-9_-]+)\s+error(?:=|:\s*)(.+)$/i) ||
        trimmed.match(/\[swarm\]\s+([A-Za-z0-9_-]+)\s+error:\s+(.+)$/i)
    if (subtaskErrorMatch) {
        const id = subtaskErrorMatch[1]
        const error = subtaskErrorMatch[2].trim()
        next.subtasks = {
            ...next.subtasks,
            [id]: {
                ...(next.subtasks[id] ?? { id, updatedAt: now }),
                id,
                status: 'failed',
                error,
                updatedAt: now,
            },
        }
        next.status = 'failed'
        return next
    }

    const completeMatch = trimmed.match(/complete(?::|\s)+success=(true|false)\s+subtasks=(\d+)\s+speedup=([0-9.]+)/i)
    if (completeMatch) {
        const success = completeMatch[1].toLowerCase() === 'true'
        const parsedSubtasks = Number(completeMatch[2])
        const parsedSpeedup = Number(completeMatch[3])
        next.status = success ? 'completed' : 'failed'
        next.plannedSubtasks = Number.isFinite(parsedSubtasks) ? parsedSubtasks : next.plannedSubtasks
        next.speedup = Number.isFinite(parsedSpeedup) ? parsedSpeedup : null
        return next
    }

    const swarmErrorMatch = trimmed.match(/error(?:\s+message=|:\s*)(.+)$/i)
    if (swarmErrorMatch) {
        next.status = 'failed'
        next.error = swarmErrorMatch[1].trim()
        return next
    }

    return next
}

const getSwarmRunStatusClasses = (status: SwarmMonitorState['status']) => {
    if (status === 'completed') return 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'
    if (status === 'failed') return 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300'
    if (status === 'running') return 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
    return 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
}

const getSwarmSubtaskStatusClasses = (status: SwarmSubtaskStatus) => {
    if (status === 'completed') return 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'
    if (status === 'failed' || status === 'timed_out' || status === 'cancelled') return 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300'
    if (status === 'running') return 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
    return 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
}

function FolderIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
        </svg>
    )
}

function PlusIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
        </svg>
    )
}

function RefreshIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
    )
}

export default function DashboardPage() {
    const { data: session } = useSession()
    const { apiUrl, tenantId, tenantSlug, isAuthenticated, tenantFetch } = useTenantApi()
    const { selectedModel, setSelectedModel, selectedCodebase, setSelectedCodebase, setAgents, setLoadingAgents } = useRalphStore()
    const [codebases, setCodebases] = useState<Codebase[]>([])
    const [workers, setWorkers] = useState<Worker[]>([])
    const [selectedAgent, setSelectedAgent] = useState('build')
    const [selectedWorkerId, setSelectedWorkerId] = useState('')
    const [prompt, setPrompt] = useState('')
    const [loading, setLoading] = useState(false)
    const [workerPersonality, setWorkerPersonality] = useState('')
    const [swarmStrategy, setSwarmStrategy] = useState<'auto' | 'domain' | 'data' | 'stage' | 'none'>('auto')
    const [swarmMaxSubagents, setSwarmMaxSubagents] = useState(8)
    const [swarmMaxSteps, setSwarmMaxSteps] = useState(50)
    const [swarmTimeoutSecs, setSwarmTimeoutSecs] = useState(600)
    const [swarmParallelEnabled, setSwarmParallelEnabled] = useState(true)
    const [swarmMonitor, setSwarmMonitor] = useState<SwarmMonitorState>(INITIAL_SWARM_MONITOR)
    const swarmEventSourceRef = useRef<EventSource | null>(null)
    const [showRegisterModal, setShowRegisterModal] = useState(false)
    const [registerForm, setRegisterForm] = useState({
        name: '',
        path: '',
        description: '',
        worker_id: ''
    })

    const upsertRoutingSnapshot = useCallback(
        (
            snapshot: Omit<SwarmRoutingSnapshot, 'source' | 'updatedAt'>,
            source: SwarmRoutingSnapshot['source']
        ) => {
            const now = Date.now()
            setSwarmMonitor((prev) => ({
                ...prev,
                routing: {
                    ...prev.routing,
                    ...snapshot,
                    source,
                    updatedAt: now,
                },
            }))
        },
        []
    )

    // Auto sign out when token refresh fails
    const signingOut = useRef(false)
    useEffect(() => {
        if (session?.error === 'RefreshAccessTokenError' && !signingOut.current) {
            signingOut.current = true
            signOut({ callbackUrl: '/login?error=session_expired' })
        }
    }, [session])

    // Redirect to dedicated instance if user has one and we're on the shared site
    useEffect(() => {
        if (isAuthenticated && session?.tenantApiUrl && tenantSlug) {
            const currentHost = window.location.host
            const tenantHost = `${tenantSlug}.codetether.run`

            // If user has a dedicated instance and we're NOT on it, redirect
            if (!currentHost.includes(tenantSlug) &&
                session.tenantApiUrl.includes(tenantSlug) &&
                !currentHost.includes('localhost')) {
                console.log(`Redirecting to dedicated instance: ${session.tenantApiUrl}`)
                window.location.href = `${session.tenantApiUrl}/dashboard`
            }
        }
    }, [isAuthenticated, session?.tenantApiUrl, tenantSlug])

    // Log tenant info for debugging
    useEffect(() => {
        if (isAuthenticated) {
            console.log('Tenant API Config:', { apiUrl, tenantId, tenantSlug })
        }
    }, [apiUrl, tenantId, tenantSlug, isAuthenticated])

    const ingestSwarmLine = useCallback((line: string) => {
        if (!line.trim()) return
        setSwarmMonitor((prev) => applySwarmLine(prev, line))
    }, [])

    const ingestSwarmPayload = useCallback((payload: unknown) => {
        if (!payload) return

        const ingestText = (text: string) => {
            text
                .split(/\r?\n/)
                .map((line) => line.trim())
                .filter(Boolean)
                .forEach(ingestSwarmLine)
        }

        if (typeof payload === 'string') {
            ingestText(payload)
            return
        }

        if (typeof payload === 'object') {
            const event = payload as Record<string, unknown>
            const routingSnapshot =
                extractRoutingSnapshot(event) ??
                extractRoutingSnapshot(event.metadata) ??
                extractRoutingSnapshot(event.data)
            if (routingSnapshot) {
                upsertRoutingSnapshot(routingSnapshot, 'stream')
            }
            const content = typeof event.content === 'string'
                ? event.content
                : typeof event.message === 'string'
                    ? event.message
                    : undefined
            if (content) {
                ingestText(content)
            }
        }
    }, [ingestSwarmLine, upsertRoutingSnapshot])

    useEffect(() => {
        if (swarmEventSourceRef.current) {
            swarmEventSourceRef.current.close()
            swarmEventSourceRef.current = null
        }

        setSwarmMonitor(INITIAL_SWARM_MONITOR)

        if (!selectedCodebase || selectedCodebase === 'global') {
            return
        }

        const baseUrl = apiUrl.replace(/\/+$/, '')
        const sseUrl = new URL(`${baseUrl}/v1/agent/codebases/${encodeURIComponent(selectedCodebase)}/events`)
        if (session?.accessToken) {
            sseUrl.searchParams.set('access_token', session.accessToken)
        }
        const eventSource = new EventSource(sseUrl.toString())
        swarmEventSourceRef.current = eventSource

        eventSource.onopen = () => {
            setSwarmMonitor((prev) => ({ ...prev, connected: true }))
        }

        eventSource.onerror = () => {
            setSwarmMonitor((prev) => ({ ...prev, connected: false }))
        }

        eventSource.addEventListener('message', (rawEvent) => {
            const event = rawEvent as MessageEvent<string>
            if (!event.data) return
            try {
                ingestSwarmPayload(JSON.parse(event.data))
            } catch {
                ingestSwarmPayload(event.data)
            }
        })

        eventSource.addEventListener('status', (rawEvent) => {
            const event = rawEvent as MessageEvent<string>
            if (!event.data) return
            try {
                ingestSwarmPayload(JSON.parse(event.data))
            } catch {
                ingestSwarmPayload(event.data)
            }
        })

        return () => {
            eventSource.close()
            if (swarmEventSourceRef.current === eventSource) {
                swarmEventSourceRef.current = null
            }
        }
    }, [apiUrl, selectedCodebase, ingestSwarmPayload, session?.accessToken])

    const loadCodebases = useCallback(async () => {
        try {
            const { data, error } = await listCodebasesV1AgentCodebasesListGet()
            if (!error && data) {
                const response = data as any
                const items = Array.isArray(response) ? response : (response?.codebases ?? response?.data ?? [])
                setCodebases(
                    (items as any[])
                        .map((cb) => ({
                            id: String(cb?.id ?? ''),
                            name: String(cb?.name ?? cb?.id ?? ''),
                            path: String(cb?.path ?? ''),
                            description: typeof cb?.description === 'string' ? cb.description : undefined,
                            status: String(cb?.status ?? 'unknown'),
                            worker_id: typeof cb?.worker_id === 'string' ? cb.worker_id : undefined,
                        }))
                        .filter((cb) => cb.id)
                )
            }
        } catch (error) {
            console.error('Failed to load codebases:', error)
        }
    }, [])

    const loadWorkers = useCallback(async () => {
        try {
            setLoadingAgents(true)
            const [{ data, error }, connectedResponse] = await Promise.all([
                listWorkersV1AgentWorkersGet(),
                tenantFetch<{ workers?: Array<{ worker_id?: string, agent_name?: string, last_heartbeat?: string }> }>('/v1/worker/connected'),
            ])
            if (!error && data) {
                const workerList = Array.isArray(data) ? data : (data as any)?.workers ?? []
                const connectedWorkers = connectedResponse.data?.workers || []
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

                const mergedWorkers = workerList.map((w: any) => {
                    const connected = connectedMap.get(String(w.worker_id || ''))
                    return {
                        ...w,
                        name: connected?.name || w.name,
                        last_seen: connected?.last_seen || w.last_seen,
                        is_sse_connected: Boolean(connected),
                    }
                })

                setWorkers(mergedWorkers)
                // Sync into ralph store so ModelSelector can read models
                setAgents(mergedWorkers.map((w: any) => ({
                    name: w.name || '',
                    role: 'worker',
                    instance_id: w.worker_id || '',
                    models_supported: (w.models || []).map((m: any) => {
                        if (typeof m === 'string') return m
                        const provider = m.provider || m.provider_id || m.providerID || ''
                        const model = m.name || m.id || m.modelID || ''
                        return provider && model ? `${provider}:${model}` : model || provider || ''
                    }).filter(Boolean),
                })))
            }
        } catch (error) {
            console.error('Failed to load workers:', error)
        } finally {
            setLoadingAgents(false)
        }
    }, [setAgents, setLoadingAgents, tenantFetch])

    const loadRoutingFromTasks = useCallback(async () => {
        if (!selectedCodebase) return
        try {
            const { data, error } = await listAllTasksV1AgentTasksGet({
                query: { codebase_id: selectedCodebase },
            })
            if (error || !data) return

            const response = data as any
            const tasks = Array.isArray(response) ? response : (response?.tasks ?? [])
            const latestSwarmTask = tasks
                .filter((task: Record<string, unknown>) => isSwarmAgentType(task?.agent_type))
                .sort((a: Record<string, unknown>, b: Record<string, unknown>) => {
                    const aTime = Date.parse(String(a?.created_at ?? ''))
                    const bTime = Date.parse(String(b?.created_at ?? ''))
                    return bTime - aTime
                })[0]

            if (!latestSwarmTask) return

            const snapshot =
                extractRoutingSnapshot(latestSwarmTask?.metadata) ??
                extractRoutingSnapshot(latestSwarmTask)
            if (snapshot) {
                upsertRoutingSnapshot(snapshot, 'task')
            }
        } catch (error) {
            console.error('Failed to load routing snapshot from tasks:', error)
        }
    }, [selectedCodebase, upsertRoutingSnapshot])

    useEffect(() => {
        // Wait until we have an auth token before making SDK calls
        if (!session?.accessToken && !hasApiAuthToken()) return

        loadCodebases()
        loadWorkers()
        loadRoutingFromTasks()
        const interval = setInterval(() => {
            loadCodebases()
            loadWorkers()
            loadRoutingFromTasks()
        }, 10000)
        return () => clearInterval(interval)
    }, [loadCodebases, loadWorkers, loadRoutingFromTasks, session?.accessToken])

    useEffect(() => {
        const triggerWorkers = workers.filter((w) => w.is_sse_connected)
        if (triggerWorkers.length === 0) {
            if (selectedWorkerId) setSelectedWorkerId('')
            return
        }

        const selectedStillValid = triggerWorkers.some((w) => w.worker_id === selectedWorkerId)
        if (selectedStillValid) return

        const selectedCodebaseWorkerId = codebases.find((cb) => cb.id === selectedCodebase)?.worker_id
        const preferredWorker = triggerWorkers.find((w) => w.worker_id === selectedCodebaseWorkerId)
        setSelectedWorkerId(preferredWorker?.worker_id || triggerWorkers[0]?.worker_id || '')
    }, [codebases, selectedCodebase, selectedWorkerId, workers])

    const triggerAgent = async () => {
        if (!selectedCodebase || !prompt.trim()) return
        if (!selectedWorkerId) {
            alert('Select a connected worker before triggering an agent.')
            return
        }
        setLoading(true)
        try {
            const metadata: Record<string, unknown> = {}
            metadata.target_worker_id = selectedWorkerId
            if (selectedAgent === 'swarm') {
                metadata.decomposition_strategy = swarmStrategy
                metadata.swarm = {
                    strategy: swarmStrategy,
                    max_subagents: swarmMaxSubagents,
                    max_steps_per_subagent: swarmMaxSteps,
                    timeout_secs: swarmTimeoutSecs,
                    parallel_enabled: swarmParallelEnabled,
                }
                // Swarm work is generally complex; this helps model-tier routing.
                metadata.complexity = 'deep'
            }

            const body: any = {
                prompt,
                agent: selectedAgent,
                ...(selectedModel && { model: selectedModel, model_ref: selectedModel }),
                ...(workerPersonality.trim() && { worker_personality: workerPersonality.trim() }),
                ...(Object.keys(metadata).length > 0 && { metadata }),
            }

            const { data, error } = await triggerAgentV1AgentCodebasesCodebaseIdTriggerPost({
                path: { codebase_id: selectedCodebase },
                body
            })
            if (!error) {
                setPrompt('')
                const routing = (data as any)?.routing
                if (routing) {
                    const snapshot = extractRoutingSnapshot(routing)
                    if (snapshot) {
                        upsertRoutingSnapshot(snapshot, 'trigger')
                    }
                    const personalityLabel = routing.worker_personality ? `, personality: ${routing.worker_personality}` : ''
                    alert(`Task queued (${routing.model_tier || 'balanced'} tier${personalityLabel})`)
                } else {
                    alert('Agent triggered successfully!')
                }
            }
        } catch (error) {
            console.error('Failed to trigger agent:', error)
            alert('Failed to trigger agent')
        } finally {
            setLoading(false)
        }
    }

    const registerCodebase = async () => {
        if (!registerForm.name || !registerForm.path) return
        try {
            const { error } = await registerCodebaseV1AgentCodebasesPost({
                body: {
                    name: registerForm.name,
                    path: registerForm.path,
                    ...(registerForm.description && { description: registerForm.description }),
                    ...(registerForm.worker_id && { worker_id: registerForm.worker_id })
                }
            })
            if (!error) {
                setShowRegisterModal(false)
                setRegisterForm({ name: '', path: '', description: '', worker_id: '' })
                loadCodebases()
            }
        } catch (error) {
            console.error('Failed to register codebase:', error)
        }
    }

    const deleteCodebase = async (id: string) => {
        if (!confirm('Delete this codebase?')) return
        try {
            await unregisterCodebaseV1AgentCodebasesCodebaseIdDelete({ path: { codebase_id: id } })
            loadCodebases()
        } catch (error) {
            console.error('Failed to delete codebase:', error)
        }
    }

    const isWorkerOnline = (worker: Worker) => {
        if (!worker.last_seen) return false
        const lastSeen = new Date(worker.last_seen)
        const now = new Date()
        const hoursSinceLastSeen = (now.getTime() - lastSeen.getTime()) / (1000 * 60 * 60)
        return hoursSinceLastSeen < 24
    }

    const getStatusClasses = (status: string) => {
        const classes: Record<string, string> = {
            idle: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
            running: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300',
            watching: 'bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300',
            completed: 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300',
            failed: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300',
            pending: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300',
        }
        return classes[status] || classes.idle
    }

    const swarmSubtasks = Object.values(swarmMonitor.subtasks).sort((a, b) => b.updatedAt - a.updatedAt)
    const swarmCounts = swarmSubtasks.reduce(
        (acc, task) => {
            if (task.status === 'completed') acc.completed += 1
            else if (task.status === 'running') acc.running += 1
            else if (task.status === 'failed' || task.status === 'timed_out' || task.status === 'cancelled') acc.failed += 1
            else acc.pending += 1
            return acc
        },
        { pending: 0, running: 0, completed: 0, failed: 0 }
    )
    const recentSwarmLines = swarmMonitor.recentLines.slice(-16)
    const routingSnapshot = swarmMonitor.routing

    return (
        <div className="space-y-6">
            {/* Tenant Status Banner */}
            <TenantStatusBanner />

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-4">
                {/* Left sidebar - Codebases */}
                <div className="lg:col-span-1">
                    <div className="rounded-lg bg-white shadow-sm dark:bg-gray-800 dark:ring-1 dark:ring-white/10">
                        <div className="p-4 border-b border-gray-200 dark:border-gray-700">
                            <div className="flex items-center justify-between">
                                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Codebases</h2>
                                <button
                                    onClick={() => setShowRegisterModal(true)}
                                    className="rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-500"
                                >
                                    <PlusIcon className="h-4 w-4 inline mr-1" />
                                    Add
                                </button>
                            </div>
                        </div>
                        <div className="divide-y divide-gray-200 dark:divide-gray-700 max-h-[calc(100vh-300px)] overflow-y-auto">
                            {codebases.length === 0 ? (
                                <div className="p-8 text-center text-gray-500 dark:text-gray-400">
                                    <FolderIcon className="mx-auto h-12 w-12 text-gray-400" />
                                    <p className="mt-2 text-sm">No codebases registered</p>
                                </div>
                            ) : (
                                codebases.map((cb) => (
                                    <div
                                        key={cb.id}
                                        className="p-4 hover:bg-gray-50 dark:hover:bg-gray-700/50 cursor-pointer"
                                        onClick={() => setSelectedCodebase(cb.id)}
                                    >
                                        <div className="flex items-start justify-between">
                                            <div className="min-w-0 flex-1">
                                                <p className="text-sm font-medium text-gray-900 dark:text-white truncate">{cb.name}</p>
                                                <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{cb.path}</p>
                                            </div>
                                            <span className={`ml-2 inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${getStatusClasses(cb.status)}`}>
                                                {cb.status}
                                            </span>
                                        </div>
                                        {cb.worker_id && (
                                            <p className="mt-1 text-xs text-gray-400">Worker: {cb.worker_id}</p>
                                        )}
                                        <div className="mt-2 flex gap-2">
                                            <button
                                                onClick={(e) => { e.stopPropagation(); deleteCodebase(cb.id) }}
                                                className="text-xs text-red-600 dark:text-red-400 hover:underline"
                                            >
                                                🗑️ Delete
                                            </button>
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>
                </div>

                {/* Main content - Trigger Agent */}
                <div className="lg:col-span-2">
                    <div className="rounded-lg bg-white shadow-sm dark:bg-gray-800 dark:ring-1 dark:ring-white/10">
                        <div className="p-4 border-b border-gray-200 dark:border-gray-700">
                            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Trigger Agent</h2>
                            <p className="text-sm text-gray-500 dark:text-gray-400">Select a codebase and run an AI agent</p>
                        </div>
                        <div className="p-6 space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                    Codebase
                                </label>
                                <select
                                    value={selectedCodebase}
                                    onChange={(e) => setSelectedCodebase(e.target.value)}
                                    className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                                >
                                    <option value="">Select a codebase...</option>
                                    {codebases.map((cb) => (
                                        <option key={cb.id} value={cb.id}>{cb.name}</option>
                                    ))}
                                </select>
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                    Worker
                                </label>
                                <WorkerSelector
                                    value={selectedWorkerId}
                                    onChange={setSelectedWorkerId}
                                    workers={workers}
                                    onlyConnected
                                    includeAutoOption
                                    autoOptionLabel="Select a connected worker..."
                                    className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                                />
                                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                    Required. Tasks from this form are routed to the selected connected worker.
                                </p>
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                    Agent Type
                                </label>
                                <select
                                    value={selectedAgent}
                                    onChange={(e) => setSelectedAgent(e.target.value)}
                                    className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                                >
                                    <option value="build">🔧 Build - Full access agent</option>
                                    <option value="plan">📋 Plan - Read-only analysis</option>
                                    <option value="coder">💻 Coder - Code writing focused</option>
                                    <option value="explore">🔍 Explore - Codebase search</option>
                                    <option value="swarm">🕸️ Swarm - Parallel sub-agents</option>
                                </select>
                            </div>
                            <ModelSelector label="Model" showSelectedInfo showCountBadge />
                            <div>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                    Worker Personality (optional)
                                </label>
                                <input
                                    type="text"
                                    value={workerPersonality}
                                    onChange={(e) => setWorkerPersonality(e.target.value)}
                                    placeholder="e.g. deep-research, fast-fix, backend-specialist"
                                    className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500 placeholder-gray-400"
                                />
                                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                    Used by orchestration to route tasks to the right worker profile.
                                </p>
                            </div>
                            {selectedAgent === 'swarm' && (
                                <div className="rounded-md border border-indigo-200 bg-indigo-50/60 p-4 dark:border-indigo-700 dark:bg-indigo-900/20 space-y-3">
                                    <h3 className="text-sm font-semibold text-indigo-900 dark:text-indigo-200">
                                        Swarm Configuration
                                    </h3>
                                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                                        <div>
                                            <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                                                Decomposition Strategy
                                            </label>
                                            <select
                                                value={swarmStrategy}
                                                onChange={(e) => setSwarmStrategy(e.target.value as 'auto' | 'domain' | 'data' | 'stage' | 'none')}
                                                className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                                            >
                                                <option value="auto">Automatic</option>
                                                <option value="domain">By Domain</option>
                                                <option value="data">By Data</option>
                                                <option value="stage">By Stage</option>
                                                <option value="none">No Decomposition</option>
                                            </select>
                                        </div>
                                        <div>
                                            <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                                                Max Subagents
                                            </label>
                                            <input
                                                type="number"
                                                min={1}
                                                max={100}
                                                value={swarmMaxSubagents}
                                                onChange={(e) => setSwarmMaxSubagents(Math.min(100, Math.max(1, Number(e.target.value) || 1)))}
                                                className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                                                Max Steps / Subagent
                                            </label>
                                            <input
                                                type="number"
                                                min={1}
                                                max={200}
                                                value={swarmMaxSteps}
                                                onChange={(e) => setSwarmMaxSteps(Math.min(200, Math.max(1, Number(e.target.value) || 1)))}
                                                className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                                                Timeout (seconds)
                                            </label>
                                            <input
                                                type="number"
                                                min={30}
                                                max={3600}
                                                value={swarmTimeoutSecs}
                                                onChange={(e) => setSwarmTimeoutSecs(Math.min(3600, Math.max(30, Number(e.target.value) || 30)))}
                                                className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                                            />
                                        </div>
                                    </div>
                                    <label className="inline-flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
                                        <input
                                            type="checkbox"
                                            checked={swarmParallelEnabled}
                                            onChange={(e) => setSwarmParallelEnabled(e.target.checked)}
                                            className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 dark:border-gray-600 dark:bg-gray-700"
                                        />
                                        Enable parallel execution
                                    </label>
                                </div>
                            )}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                    Prompt
                                </label>
                                <textarea
                                    value={prompt}
                                    onChange={(e) => setPrompt(e.target.value)}
                                    rows={4}
                                    placeholder="Enter your instructions for the AI agent..."
                                    className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500 placeholder-gray-400"
                                />
                            </div>
                            <button
                                onClick={triggerAgent}
                                disabled={loading || !selectedCodebase || !selectedWorkerId || !prompt.trim()}
                                className="w-full rounded-md bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                {loading ? '⏳ Running...' : '🚀 Run Agent'}
                            </button>
                        </div>
                    </div>
                </div>

                {/* Right sidebar - Quick Actions & Workers */}
                <div className="lg:col-span-1 space-y-6">
                    {/* Swarm Monitor */}
                    <div className="rounded-lg bg-white shadow-sm dark:bg-gray-800 dark:ring-1 dark:ring-white/10">
                        <div className="p-4 border-b border-gray-200 dark:border-gray-700">
                            <div className="flex items-center justify-between">
                                <h3 className="text-sm font-semibold text-gray-900 dark:text-white">Swarm Monitor</h3>
                                <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium ${swarmMonitor.connected ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300' : 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'}`}>
                                    {swarmMonitor.connected ? 'LIVE' : 'OFFLINE'}
                                </span>
                            </div>
                            <p className="mt-1 text-[11px] text-gray-500 dark:text-gray-400">
                                {selectedCodebase
                                    ? `Streaming from ${selectedCodebase}`
                                    : 'Select a codebase to watch swarm execution'}
                            </p>
                        </div>
                        <div className="p-4 space-y-3">
                            {!selectedCodebase ? (
                                <p className="text-xs text-gray-500 dark:text-gray-400">
                                    No codebase selected.
                                </p>
                            ) : (
                                <>
                                    <div className="grid grid-cols-4 gap-2">
                                        <div className="rounded bg-gray-50 dark:bg-gray-900/40 p-2 text-center">
                                            <p className="text-[10px] uppercase tracking-wide text-gray-500 dark:text-gray-400">Pending</p>
                                            <p className="text-sm font-semibold text-gray-900 dark:text-white">{swarmCounts.pending}</p>
                                        </div>
                                        <div className="rounded bg-blue-50 dark:bg-blue-900/20 p-2 text-center">
                                            <p className="text-[10px] uppercase tracking-wide text-blue-600 dark:text-blue-300">Running</p>
                                            <p className="text-sm font-semibold text-blue-700 dark:text-blue-200">{swarmCounts.running}</p>
                                        </div>
                                        <div className="rounded bg-green-50 dark:bg-green-900/20 p-2 text-center">
                                            <p className="text-[10px] uppercase tracking-wide text-green-600 dark:text-green-300">Done</p>
                                            <p className="text-sm font-semibold text-green-700 dark:text-green-200">{swarmCounts.completed}</p>
                                        </div>
                                        <div className="rounded bg-red-50 dark:bg-red-900/20 p-2 text-center">
                                            <p className="text-[10px] uppercase tracking-wide text-red-600 dark:text-red-300">Failed</p>
                                            <p className="text-sm font-semibold text-red-700 dark:text-red-200">{swarmCounts.failed}</p>
                                        </div>
                                    </div>

                                    <div className="flex flex-wrap items-center gap-2 text-[11px] text-gray-600 dark:text-gray-300">
                                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 font-medium ${getSwarmRunStatusClasses(swarmMonitor.status)}`}>
                                            {swarmMonitor.status.toUpperCase()}
                                        </span>
                                        {swarmMonitor.plannedSubtasks !== null && (
                                            <span>planned={swarmMonitor.plannedSubtasks}</span>
                                        )}
                                        {swarmMonitor.currentStage !== null && (
                                            <span>stage={swarmMonitor.currentStage}</span>
                                        )}
                                        {swarmMonitor.speedup !== null && (
                                            <span>speedup={swarmMonitor.speedup.toFixed(2)}x</span>
                                        )}
                                    </div>

                                    {routingSnapshot && (
                                        <div className="rounded border border-gray-200 bg-gray-50 p-2 text-[11px] text-gray-700 dark:border-gray-700 dark:bg-gray-900/40 dark:text-gray-200">
                                            <div className="flex items-center justify-between">
                                                <span className="font-semibold uppercase tracking-wide text-[10px] text-gray-500 dark:text-gray-400">
                                                    Routing
                                                </span>
                                                <span className="text-[10px] text-gray-500 dark:text-gray-400">
                                                    {routingSnapshot.source}
                                                </span>
                                            </div>
                                            <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1">
                                                {routingSnapshot.complexity && <span>complexity={routingSnapshot.complexity}</span>}
                                                {routingSnapshot.modelTier && <span>tier={routingSnapshot.modelTier}</span>}
                                                {routingSnapshot.modelRef && <span className="break-all">model={routingSnapshot.modelRef}</span>}
                                                {routingSnapshot.workerPersonality && <span>personality={routingSnapshot.workerPersonality}</span>}
                                                {routingSnapshot.targetAgentName && <span>target={routingSnapshot.targetAgentName}</span>}
                                            </div>
                                        </div>
                                    )}

                                    {swarmSubtasks.length > 0 && (
                                        <div className="max-h-32 overflow-y-auto space-y-1">
                                            {swarmSubtasks.slice(0, 8).map((task) => (
                                                <div key={task.id} className="rounded border border-gray-200 dark:border-gray-700 p-2">
                                                    <div className="flex items-center justify-between gap-2">
                                                        <span className="font-mono text-[11px] text-gray-700 dark:text-gray-200">{task.id}</span>
                                                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium ${getSwarmSubtaskStatusClasses(task.status)}`}>
                                                            {task.status}
                                                        </span>
                                                    </div>
                                                    {task.tool && (
                                                        <p className="mt-1 text-[10px] text-blue-600 dark:text-blue-300">tool={task.tool}</p>
                                                    )}
                                                    {task.error && (
                                                        <p className="mt-1 text-[10px] text-red-600 dark:text-red-300 line-clamp-2">{task.error}</p>
                                                    )}
                                                </div>
                                            ))}
                                        </div>
                                    )}

                                    <div className="rounded bg-gray-50 dark:bg-gray-900/40 p-2 max-h-36 overflow-y-auto space-y-1">
                                        {recentSwarmLines.length === 0 ? (
                                            <p className="text-[11px] text-gray-500 dark:text-gray-400">
                                                Waiting for swarm output...
                                            </p>
                                        ) : (
                                            recentSwarmLines.map((line, index) => (
                                                <p key={`${line}-${index}`} className="font-mono text-[10px] text-gray-700 dark:text-gray-300 break-words">
                                                    {line}
                                                </p>
                                            ))
                                        )}
                                    </div>
                                </>
                            )}
                        </div>
                    </div>

                    {/* Workers Section */}
                    <div className="rounded-lg bg-white shadow-sm dark:bg-gray-800 dark:ring-1 dark:ring-white/10">
                        <div className="p-4 border-b border-gray-200 dark:border-gray-700">
                            <h3 className="text-sm font-semibold text-gray-900 dark:text-white">Active Workers</h3>
                        </div>
                        <div className="divide-y divide-gray-200 dark:divide-gray-700 max-h-[300px] overflow-y-auto">
                            {workers.filter(isWorkerOnline).length === 0 ? (
                                <div className="p-4 text-center text-xs text-gray-500 dark:text-gray-400">
                                    No workers connected
                                </div>
                            ) : (
                                workers.filter(isWorkerOnline).map((w) => (
                                    <div key={w.worker_id} className="p-3">
                                        <div className="flex items-center justify-between">
                                            <div className="min-w-0 flex-1">
                                                <p className="text-xs font-medium text-gray-900 dark:text-white truncate">{w.name}</p>
                                                <p className="text-[10px] text-gray-500 dark:text-gray-400 truncate">{w.hostname || w.worker_id}</p>
                                            </div>
                                            <span className="ml-2 h-2 w-2 rounded-full bg-green-500" />
                                        </div>
                                        {w.global_codebase_id && (
                                            <button
                                                onClick={() => setSelectedCodebase(w.global_codebase_id!)}
                                                className="mt-2 w-full rounded bg-indigo-50 dark:bg-indigo-900/30 px-2 py-1 text-[10px] font-medium text-indigo-600 dark:text-indigo-400 hover:bg-indigo-100 dark:hover:bg-indigo-900/50 flex items-center justify-center gap-1"
                                            >
                                                💬 Chat Directly
                                            </button>
                                        )}
                                    </div>
                                ))
                            )}
                        </div>
                    </div>

                    <div className="rounded-lg bg-white shadow-sm dark:bg-gray-800 dark:ring-1 dark:ring-white/10">
                        <div className="p-4 border-b border-gray-200 dark:border-gray-700">
                            <h3 className="text-sm font-semibold text-gray-900 dark:text-white">Quick Actions</h3>
                        </div>
                        <div className="p-4 space-y-2">
                            <div className="mb-3">
                                <VoiceChatButton
                                    codebaseId={selectedCodebase || undefined}
                                    mode="chat"
                                />
                            </div>
                            <button
                                onClick={() => setShowRegisterModal(true)}
                                className="w-full text-left px-3 py-2 rounded-md text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2"
                            >
                                <span>📁</span> Register Codebase
                            </button>
                            <button
                                onClick={loadCodebases}
                                className="w-full text-left px-3 py-2 rounded-md text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2"
                            >
                                <RefreshIcon className="h-4 w-4" /> Refresh All
                            </button>
                            <button
                                onClick={() => signOut({ callbackUrl: '/login' })}
                                className="w-full text-left px-3 py-2 rounded-md text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 flex items-center gap-2"
                            >
                                <span>🚪</span> Sign Out
                            </button>
                        </div>
                    </div>
                </div>

                {/* Register Modal */}
                {showRegisterModal && (
                    <div className="fixed inset-0 z-50">
                        <div className="fixed inset-0 bg-gray-500/75 dark:bg-gray-900/75" onClick={() => setShowRegisterModal(false)} />
                        <div className="fixed inset-0 z-10 overflow-y-auto">
                            <div className="flex min-h-full items-center justify-center p-4">
                                <div className="relative w-full max-w-lg rounded-lg bg-white dark:bg-gray-800 shadow-xl">
                                    <div className="p-6">
                                        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Register Codebase</h3>
                                        <div className="space-y-4">
                                            <div>
                                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Name</label>
                                                <input
                                                    type="text"
                                                    value={registerForm.name}
                                                    onChange={(e) => setRegisterForm({ ...registerForm, name: e.target.value })}
                                                    placeholder="my-project"
                                                    className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Path</label>
                                                <input
                                                    type="text"
                                                    value={registerForm.path}
                                                    onChange={(e) => setRegisterForm({ ...registerForm, path: e.target.value })}
                                                    placeholder="/home/user/projects/my-project"
                                                    className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Description (optional)</label>
                                                <input
                                                    type="text"
                                                    value={registerForm.description}
                                                    onChange={(e) => setRegisterForm({ ...registerForm, description: e.target.value })}
                                                    placeholder="A brief description"
                                                    className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Worker (optional)</label>
                                                <WorkerSelector
                                                    value={registerForm.worker_id}
                                                    onChange={(worker_id) => setRegisterForm({ ...registerForm, worker_id })}
                                                    workers={workers}
                                                    onlyConnected
                                                    includeAutoOption
                                                    autoOptionLabel="Auto-assign (default)"
                                                    className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                                                />
                                            </div>
                                        </div>
                                        <div className="mt-6 flex gap-3 justify-end">
                                            <button
                                                onClick={() => setShowRegisterModal(false)}
                                                className="rounded-md px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
                                            >
                                                Cancel
                                            </button>
                                            <button
                                                onClick={registerCodebase}
                                                className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500"
                                            >
                                                Register
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    )
}
