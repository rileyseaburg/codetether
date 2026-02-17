'use client'

import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { useSession, signOut } from 'next-auth/react'
import VoiceAgentButton from './components/voice/VoiceAgentButton'
import TenantStatusBanner from '@/components/TenantStatusBanner'
import { ModelSelector } from '@/components/ModelSelector'
import { WorkerSelector } from '@/components/WorkerSelector'
import { useRalphStore } from './ralph/store'
import { useTenantApi } from '@/hooks/useTenantApi'
import {
    listWorkspacesV1AgentWorkspacesListGet,
    listAllTasksV1AgentTasksGet,
    listWorkersV1AgentWorkersGet,
    listModelsV1AgentModelsGet,
    triggerAgentV1AgentWorkspacesWorkspaceIdTriggerPost,
    registerWorkspaceV1AgentWorkspacesPost,
    unregisterWorkspaceV1AgentWorkspacesWorkspaceIdDelete,
    hasApiAuthToken,
} from '@/lib/api'

interface Workspace {
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
    global_workspace_id?: string
    // Legacy alias kept for backward compatibility in mixed deployments.
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

interface WorkspaceRuntimeContext {
    mode: 'knative' | 'worker' | 'unknown'
    source: 'task' | 'trigger' | 'inferred'
    taskId?: string
    status?: string
    workerId?: string
    sessionId?: string
    knativeServiceName?: string
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

const WORKSPACE_WIZARD_DISMISSED_KEY = 'codetether.workspaceWizardDismissed'

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

const getBoolean = (record: Record<string, unknown> | null, keys: string[]): boolean | undefined => {
    if (!record) return undefined
    for (const key of keys) {
        const value = record[key]
        if (typeof value === 'boolean') return value
        if (typeof value === 'string') {
            const normalized = value.trim().toLowerCase()
            if (normalized === 'true') return true
            if (normalized === 'false') return false
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
    const { selectedModel, selectedCodebase, setSelectedCodebase, setAgents, setLoadingAgents } = useRalphStore()
    const [workspaces, setWorkspaces] = useState<Workspace[]>([])
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
    const [showWorkspaceWizard, setShowWorkspaceWizard] = useState(false)
    const [workspaceWizardStep, setWorkspaceWizardStep] = useState(0)
    const [workspaceWizardMode, setWorkspaceWizardMode] = useState<'local' | 'git' | 'external'>('local')
    const [workspaceWizardDismissed, setWorkspaceWizardDismissed] = useState(false)
    const [registerMode, setRegisterMode] = useState<'local' | 'git' | 'external'>('local')
    const [registerForm, setRegisterForm] = useState({
        name: '',
        path: '',
        description: '',
        worker_id: '',
        git_url: '',
        git_branch: 'main',
        external_provider: '',
        external_reference: '',
    })
    const [runtimeContext, setRuntimeContext] = useState<WorkspaceRuntimeContext | null>(null)
    const fallbackWorkspaceId = useMemo(() => {
        const connectedWorker = workers.find(
            (w) => w.is_sse_connected && (w.global_workspace_id || w.global_codebase_id)
        )
        const connectedGlobal = connectedWorker?.global_workspace_id || connectedWorker?.global_codebase_id
        if (connectedGlobal) return connectedGlobal

        const anyWorker = workers.find((w) => w.global_workspace_id || w.global_codebase_id)
        const anyGlobal = anyWorker?.global_workspace_id || anyWorker?.global_codebase_id
        if (anyGlobal) return anyGlobal

        if (workspaces.length === 1) return workspaces[0]?.id || ''
        return ''
    }, [workers, workspaces])
    const selectedWorkspaceExists = useMemo(
        () => Boolean(selectedCodebase) && workspaces.some((cb) => cb.id === selectedCodebase),
        [workspaces, selectedCodebase]
    )
    const activeWorkspaceId = useMemo(() => {
        if (selectedWorkspaceExists && selectedCodebase) return selectedCodebase
        return fallbackWorkspaceId
    }, [fallbackWorkspaceId, selectedCodebase, selectedWorkspaceExists])

    useEffect(() => {
        if (!fallbackWorkspaceId) return
        if (!selectedCodebase) {
            setSelectedCodebase(fallbackWorkspaceId)
            return
        }
        if (!selectedWorkspaceExists && selectedCodebase !== fallbackWorkspaceId) {
            setSelectedCodebase(fallbackWorkspaceId)
        }
    }, [fallbackWorkspaceId, selectedCodebase, selectedWorkspaceExists, setSelectedCodebase])

    const activeWorkspace = useMemo(
        () => workspaces.find((workspace) => workspace.id === activeWorkspaceId),
        [activeWorkspaceId, workspaces]
    )
    const activeWorkspaceOwner = useMemo(
        () => workers.find((worker) => worker.worker_id === activeWorkspace?.worker_id),
        [activeWorkspace?.worker_id, workers]
    )
    const selectedWorker = useMemo(
        () => workers.find((worker) => worker.worker_id === selectedWorkerId),
        [selectedWorkerId, workers]
    )

    useEffect(() => {
        if (typeof window === 'undefined') return
        const dismissed = window.localStorage.getItem(WORKSPACE_WIZARD_DISMISSED_KEY) === '1'
        setWorkspaceWizardDismissed(dismissed)
    }, [])

    useEffect(() => {
        if (workspaces.length > 0) {
            setShowWorkspaceWizard(false)
            return
        }
        if (!workspaceWizardDismissed) {
            setWorkspaceWizardStep(0)
            setShowWorkspaceWizard(true)
        }
    }, [workspaceWizardDismissed, workspaces.length])

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

        if (!activeWorkspaceId) {
            return
        }

        // Handle relative API URLs (e.g., "/api") by resolving against window.location
        const baseApiUrl = apiUrl.startsWith('/') ? `${window.location.origin}${apiUrl}` : apiUrl
        const baseUrl = baseApiUrl.replace(/\/+$/, '')
        const sseUrl = new URL(`${baseUrl}/v1/agent/workspaces/${encodeURIComponent(activeWorkspaceId)}/events`)
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
    }, [activeWorkspaceId, apiUrl, ingestSwarmPayload, session?.accessToken])

    useEffect(() => {
        if (!activeWorkspaceId) {
            setRuntimeContext(null)
        }
    }, [activeWorkspaceId])

    const loadWorkspaces = useCallback(async () => {
        try {
            const { data, error } = await listWorkspacesV1AgentWorkspacesListGet()
            if (!error && data) {
                const response = data as any
                const items = Array.isArray(response)
                    ? response
                    : (response?.workspaces ?? response?.codebases ?? response?.data ?? [])
                setWorkspaces(
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
            console.error('Failed to load workspaces:', error)
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
                // Load models from dedicated models endpoint (aggregated + deduplicated)
                try {
                    const { data: modelsData } = await listModelsV1AgentModelsGet()
                    const modelsResp = modelsData as { models?: { id?: string }[]; default?: string } | undefined
                    if (modelsResp?.models?.length) {
                        const modelIds = modelsResp.models
                            .map((m: { id?: string }) => m.id)
                            .filter((id): id is string => Boolean(id))
                        setAgents([{ name: 'all', role: 'worker', models_supported: modelIds }])
                    } else {
                        // Fallback: extract from workers
                        setAgents(mergedWorkers.map((w: any) => ({
                            name: w.name || '',
                            role: 'worker',
                            instance_id: w.worker_id || '',
                            models_supported: (w.models || []).map((m: any) => {
                                if (typeof m === 'string') return m
                                const provider = m.provider || m.provider_id || m.providerID || ''
                                const model = m.name || m.id || m.modelID || ''
                                return provider && model ? `${provider}/${model}` : model || provider || ''
                            }).filter(Boolean),
                        })))
                    }
                } catch {
                    // Fallback: extract from workers
                    setAgents(mergedWorkers.map((w: any) => ({
                        name: w.name || '',
                        role: 'worker',
                        instance_id: w.worker_id || '',
                        models_supported: (w.models || []).map((m: any) => {
                            if (typeof m === 'string') return m
                            const provider = m.provider || m.provider_id || m.providerID || ''
                            const model = m.name || m.id || m.modelID || ''
                            return provider && model ? `${provider}/${model}` : model || provider || ''
                        }).filter(Boolean),
                    })))
                }
            }
        } catch (error) {
            console.error('Failed to load workers:', error)
        } finally {
            setLoadingAgents(false)
        }
    }, [setAgents, setLoadingAgents, tenantFetch])

    const loadRoutingFromTasks = useCallback(async () => {
        if (!activeWorkspaceId) return
        try {
            const { data, error } = await listAllTasksV1AgentTasksGet({
                query: { workspace_id: activeWorkspaceId },
            })
            if (error || !data) return

            const response = data as any
            const tasks = Array.isArray(response) ? response : (response?.tasks ?? [])
            const latestTask = [...tasks]
                .sort((a: Record<string, unknown>, b: Record<string, unknown>) => {
                    const aTime = Date.parse(String(a?.created_at ?? ''))
                    const bTime = Date.parse(String(b?.created_at ?? ''))
                    return bTime - aTime
                })[0]

            if (latestTask) {
                const taskRecord = asRecord(latestTask)
                const metadata = asRecord(taskRecord?.metadata)
                const knativeFlag = getBoolean(metadata, ['knative']) === true
                const knativeServiceName =
                    getString(metadata, ['knative_service_name', 'knative_service']) ??
                    getString(taskRecord, ['knative_service_name'])
                const workerId =
                    getString(metadata, ['target_worker_id', 'worker_id']) ??
                    getString(taskRecord, ['worker_id'])
                const sessionId =
                    getString(metadata, ['session_id']) ??
                    getString(taskRecord, ['session_id'])
                const status = getString(taskRecord, ['status'])

                setRuntimeContext({
                    mode: knativeFlag || Boolean(knativeServiceName) ? 'knative' : workerId ? 'worker' : 'unknown',
                    source: 'task',
                    taskId: getString(taskRecord, ['id']),
                    status,
                    workerId,
                    sessionId,
                    knativeServiceName,
                    updatedAt: Date.now(),
                })
            } else {
                setRuntimeContext(null)
            }

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
    }, [activeWorkspaceId, upsertRoutingSnapshot])

    useEffect(() => {
        // Wait until we have an auth token before making SDK calls
        if (!session?.accessToken && !hasApiAuthToken()) return

        loadWorkspaces()
        loadWorkers()
        loadRoutingFromTasks()
        const interval = setInterval(() => {
            loadWorkspaces()
            loadWorkers()
            loadRoutingFromTasks()
        }, 10000)
        return () => clearInterval(interval)
    }, [loadWorkspaces, loadWorkers, loadRoutingFromTasks, session?.accessToken])

    useEffect(() => {
        const triggerWorkers = workers.filter((w) => w.is_sse_connected)
        if (triggerWorkers.length === 0) {
            if (selectedWorkerId) setSelectedWorkerId('')
            return
        }

        const selectedWorkspaceWorkerId = workspaces.find((cb) => cb.id === activeWorkspaceId)?.worker_id
        const preferredWorker = triggerWorkers.find((w) => w.worker_id === selectedWorkspaceWorkerId)?.worker_id

        if (!selectedWorkerId) {
            if (preferredWorker) {
                setSelectedWorkerId(preferredWorker)
            }
            return
        }

        const selectedStillValid = triggerWorkers.some((w) => w.worker_id === selectedWorkerId)
        if (!selectedStillValid) {
            setSelectedWorkerId(preferredWorker || '')
        }
    }, [activeWorkspaceId, workspaces, selectedWorkerId, workers])

    const triggerAgent = async () => {
        if (!activeWorkspaceId || !prompt.trim()) return
        setLoading(true)
        try {
            const metadata: Record<string, unknown> = {}
            if (selectedWorkerId) {
                metadata.target_worker_id = selectedWorkerId
            }
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

            const { data, error } = await triggerAgentV1AgentWorkspacesWorkspaceIdTriggerPost({
                path: { workspace_id: activeWorkspaceId },
                body
            })
            if (!error) {
                const response = (data as Record<string, unknown> | undefined) ?? {}
                const responseKnative = response?.knative === true
                const responseSessionId =
                    typeof response?.session_id === 'string' ? response.session_id : undefined
                setRuntimeContext({
                    mode: responseKnative ? 'knative' : selectedWorkerId ? 'worker' : 'unknown',
                    source: 'trigger',
                    status: 'queued',
                    workerId: selectedWorkerId || activeWorkspace?.worker_id || undefined,
                    sessionId: responseSessionId,
                    knativeServiceName: responseSessionId
                        ? `codetether-session-${responseSessionId}`
                        : undefined,
                    updatedAt: Date.now(),
                })
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

    const registerWorkspace = async () => {
        const trimmedName = registerForm.name.trim()
        const trimmedPath = registerForm.path.trim()
        const trimmedGitUrl = registerForm.git_url.trim()
        const trimmedGitBranch = registerForm.git_branch.trim() || 'main'
        const trimmedExternalProvider = registerForm.external_provider.trim()
        const trimmedExternalReference = registerForm.external_reference.trim()

        if (!trimmedName) return
        if (registerMode === 'local' && !trimmedPath) return
        if (registerMode === 'git' && !trimmedGitUrl) return
        if (registerMode === 'external' && (!trimmedExternalProvider || !registerForm.worker_id)) return
        try {
            const body: Record<string, unknown> = {
                name: trimmedName,
                ...(registerForm.description && { description: registerForm.description }),
                ...(registerForm.worker_id && { worker_id: registerForm.worker_id }),
            }
            if (registerMode === 'local') {
                body.path = trimmedPath
            } else if (registerMode === 'git') {
                body.git_url = trimmedGitUrl
                body.git_branch = trimmedGitBranch
                if (trimmedPath) body.path = trimmedPath
            } else {
                const providerSlug = trimmedExternalProvider
                    .toLowerCase()
                    .replace(/[^a-z0-9]+/g, '-')
                    .replace(/^-+|-+$/g, '') || 'external'
                const referenceSlug = (trimmedExternalReference || trimmedName)
                    .toLowerCase()
                    .replace(/[^a-z0-9]+/g, '-')
                    .replace(/^-+|-+$/g, '') || 'workspace'
                body.path = trimmedPath || `external://${providerSlug}/${referenceSlug}`
                body.agent_config = {
                    source_type: 'external',
                    source_provider: trimmedExternalProvider,
                    ...(trimmedExternalReference && { source_reference: trimmedExternalReference }),
                }
            }
            const { error } = await registerWorkspaceV1AgentWorkspacesPost({
                body: body as any
            })
            if (!error) {
                setShowRegisterModal(false)
                setShowWorkspaceWizard(false)
                setRegisterMode('local')
                setRegisterForm({
                    name: '',
                    path: '',
                    description: '',
                    worker_id: '',
                    git_url: '',
                    git_branch: 'main',
                    external_provider: '',
                    external_reference: '',
                })
                loadWorkspaces()
            }
        } catch (error) {
            console.error('Failed to register workspace:', error)
        }
    }

    const deleteWorkspace = async (id: string) => {
        if (!confirm('Delete this workspace?')) return
        try {
            await unregisterWorkspaceV1AgentWorkspacesWorkspaceIdDelete({ path: { workspace_id: id } })
            loadWorkspaces()
        } catch (error) {
            console.error('Failed to delete workspace:', error)
        }
    }

    const openRegisterWorkspaceModal = (mode: 'local' | 'git' | 'external' = 'local') => {
        setRegisterMode(mode)
        setRegisterForm({
            name: '',
            path: '',
            description: '',
            worker_id: '',
            git_url: '',
            git_branch: 'main',
            external_provider: '',
            external_reference: '',
        })
        setShowRegisterModal(true)
    }

    const dismissWorkspaceWizard = (remember: boolean) => {
        setShowWorkspaceWizard(false)
        if (remember && typeof window !== 'undefined') {
            window.localStorage.setItem(WORKSPACE_WIZARD_DISMISSED_KEY, '1')
            setWorkspaceWizardDismissed(true)
        }
    }

    const launchWorkspaceSetupFromWizard = () => {
        setShowWorkspaceWizard(false)
        openRegisterWorkspaceModal(workspaceWizardMode)
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
    const effectiveRuntimeMode: WorkspaceRuntimeContext['mode'] = runtimeContext?.mode ?? (selectedWorker ? 'worker' : 'unknown')
    const runtimeModeLabel =
        effectiveRuntimeMode === 'knative'
            ? 'Knative Session Worker'
            : effectiveRuntimeMode === 'worker'
                ? 'Direct Connected Worker'
                : 'Not yet resolved'
    const canRegisterWorkspace =
        Boolean(registerForm.name.trim()) &&
        (
            (registerMode === 'local' && Boolean(registerForm.path.trim())) ||
            (registerMode === 'git' && Boolean(registerForm.git_url.trim())) ||
            (registerMode === 'external' && Boolean(registerForm.external_provider.trim()) && Boolean(registerForm.worker_id))
        )

    return (
        <div className="space-y-6">
            {/* Tenant Status Banner */}
            <TenantStatusBanner />

            {showWorkspaceWizard && workspaces.length === 0 && (
                <div className="fixed inset-0 z-50">
                    <div className="fixed inset-0 bg-gray-900/50" />
                    <div className="fixed inset-0 z-10 overflow-y-auto">
                        <div className="flex min-h-full items-center justify-center p-4">
                            <div className="w-full max-w-2xl rounded-xl bg-white shadow-2xl dark:bg-gray-800 dark:ring-1 dark:ring-white/10">
                                <div className="border-b border-gray-200 p-5 dark:border-gray-700">
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <p className="text-xs font-semibold uppercase tracking-wide text-indigo-600 dark:text-indigo-400">
                                                First-Time Setup
                                            </p>
                                            <h2 className="mt-1 text-xl font-semibold text-gray-900 dark:text-white">
                                                Create your first workspace
                                            </h2>
                                        </div>
                                        <span className="rounded-full bg-gray-100 px-2.5 py-1 text-xs text-gray-600 dark:bg-gray-700 dark:text-gray-300">
                                            Step {workspaceWizardStep + 1} / 3
                                        </span>
                                    </div>
                                </div>

                                <div className="p-6">
                                    {workspaceWizardStep === 0 && (
                                        <div className="space-y-3 text-sm text-gray-700 dark:text-gray-200">
                                            <p>
                                                A workspace is a durable context boundary.
                                            </p>
                                            <p>
                                                It binds source material, runtime configuration, routing, and history under one stable ID.
                                            </p>
                                            <p>
                                                Every task, session, and artifact in this dashboard is anchored to a selected workspace.
                                            </p>
                                        </div>
                                    )}

                                    {workspaceWizardStep === 1 && (
                                        <div className="space-y-4">
                                            <p className="text-sm text-gray-700 dark:text-gray-200">
                                                Choose how you want to attach source material to this workspace:
                                            </p>
                                            <div className="grid gap-3 sm:grid-cols-3">
                                                <button
                                                    type="button"
                                                    onClick={() => setWorkspaceWizardMode('local')}
                                                    className={`rounded-lg border p-4 text-left ${workspaceWizardMode === 'local'
                                                            ? 'border-indigo-500 bg-indigo-50 dark:border-indigo-400 dark:bg-indigo-900/30'
                                                            : 'border-gray-300 dark:border-gray-600'
                                                        }`}
                                                >
                                                    <p className="font-semibold text-gray-900 dark:text-white">Directory</p>
                                                    <p className="mt-1 text-xs text-gray-600 dark:text-gray-300">
                                                        Attach an existing folder already available in your runtime.
                                                    </p>
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() => setWorkspaceWizardMode('git')}
                                                    className={`rounded-lg border p-4 text-left ${workspaceWizardMode === 'git'
                                                            ? 'border-indigo-500 bg-indigo-50 dark:border-indigo-400 dark:bg-indigo-900/30'
                                                            : 'border-gray-300 dark:border-gray-600'
                                                        }`}
                                                >
                                                    <p className="font-semibold text-gray-900 dark:text-white">Repository URL</p>
                                                    <p className="mt-1 text-xs text-gray-600 dark:text-gray-300">
                                                        Attach a remote source URL and materialize it into workspace storage.
                                                    </p>
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() => setWorkspaceWizardMode('external')}
                                                    className={`rounded-lg border p-4 text-left ${workspaceWizardMode === 'external'
                                                            ? 'border-indigo-500 bg-indigo-50 dark:border-indigo-400 dark:bg-indigo-900/30'
                                                            : 'border-gray-300 dark:border-gray-600'
                                                        }`}
                                                >
                                                    <p className="font-semibold text-gray-900 dark:text-white">External App</p>
                                                    <p className="mt-1 text-xs text-gray-600 dark:text-gray-300">
                                                        Create a workspace identity for non-repo systems and connected tools.
                                                    </p>
                                                </button>
                                            </div>
                                        </div>
                                    )}

                                    {workspaceWizardStep === 2 && (
                                        <div className="space-y-3 text-sm text-gray-700 dark:text-gray-200">
                                            <p>
                                                Runtime mapping:
                                            </p>
                                            <p>
                                                Direct mode routes work to an active connected runtime.
                                            </p>
                                            <p>
                                                Knative mode creates a per-session service/pod while keeping the same workspace identity.
                                            </p>
                                            <p>
                                                External app workspaces use the same identity model, so tasks, permissions, and activity stay consistent across systems.
                                            </p>
                                            <p className="rounded-md bg-gray-50 p-3 text-xs text-gray-600 dark:bg-gray-900/40 dark:text-gray-300">
                                                Workspace details remain editable after setup.
                                            </p>
                                        </div>
                                    )}
                                </div>

                                <div className="flex items-center justify-between border-t border-gray-200 p-4 dark:border-gray-700">
                                    <button
                                        onClick={() => dismissWorkspaceWizard(true)}
                                        className="rounded-md px-3 py-2 text-sm text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700"
                                    >
                                        Dismiss tips
                                    </button>
                                    <div className="flex items-center gap-2">
                                        <button
                                            onClick={() => setWorkspaceWizardStep((step) => Math.max(0, step - 1))}
                                            disabled={workspaceWizardStep === 0}
                                            className="rounded-md px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed dark:text-gray-200 dark:hover:bg-gray-700"
                                        >
                                            Back
                                        </button>
                                        {workspaceWizardStep < 2 ? (
                                            <button
                                                onClick={() => setWorkspaceWizardStep((step) => Math.min(2, step + 1))}
                                                className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500"
                                            >
                                                Next
                                            </button>
                                        ) : (
                                            <button
                                                onClick={launchWorkspaceSetupFromWizard}
                                                className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500"
                                            >
                                                Open Workspace Form
                                            </button>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-4">
                {/* Left sidebar - Workspaces */}
                <div className="lg:col-span-1">
                    <div className="rounded-lg bg-white shadow-sm dark:bg-gray-800 dark:ring-1 dark:ring-white/10">
                        <div className="p-4 border-b border-gray-200 dark:border-gray-700">
                            <div className="flex items-center justify-between">
                                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Workspaces</h2>
                                <button
                                    onClick={openRegisterWorkspaceModal}
                                    className="rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-500"
                                >
                                    <PlusIcon className="h-4 w-4 inline mr-1" />
                                    Add
                                </button>
                            </div>
                        </div>
                        <div className="divide-y divide-gray-200 dark:divide-gray-700 max-h-[calc(100vh-300px)] overflow-y-auto">
                            {workspaces.length === 0 ? (
                                <div className="p-8 text-center text-gray-500 dark:text-gray-400">
                                    <FolderIcon className="mx-auto h-12 w-12 text-gray-400" />
                                    <p className="mt-2 text-sm">No workspaces registered</p>
                                    <button
                                        onClick={() => {
                                            setWorkspaceWizardStep(0)
                                            setShowWorkspaceWizard(true)
                                        }}
                                        className="mt-3 rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-500"
                                    >
                                        Start Workspace Wizard
                                    </button>
                                </div>
                            ) : (
                                workspaces.map((cb) => (
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
                                                onClick={(e) => { e.stopPropagation(); deleteWorkspace(cb.id) }}
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
                            <p className="text-sm text-gray-500 dark:text-gray-400">
                                Run work in any workspace. If none is selected, direct/global workspace is used.
                            </p>
                        </div>
                        <div className="p-6 space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                    Workspace
                                </label>
                                <select
                                    value={selectedCodebase}
                                    onChange={(e) => setSelectedCodebase(e.target.value)}
                                    className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                                >
                                    <option value="">
                                        {fallbackWorkspaceId ? 'Auto (Direct / Global Workspace)' : 'Select a workspace...'}
                                    </option>
                                    {workspaces.map((cb) => (
                                        <option key={cb.id} value={cb.id}>{cb.name}</option>
                                    ))}
                                </select>
                                <div className="mt-2 rounded-md border border-blue-200 bg-blue-50/70 p-2 text-xs text-blue-900 dark:border-blue-800 dark:bg-blue-900/20 dark:text-blue-200">
                                    <p className="font-medium">Workspace = context identity + source path + runtime owner</p>
                                    <p className="mt-1">
                                        Set a runtime-accessible path for this workspace. With Knative enabled, the same workspace ID maps to session pods without changing context.
                                    </p>
                                </div>
                                <div className="mt-2 rounded-md border border-gray-200 bg-gray-50 p-3 text-xs text-gray-700 dark:border-gray-700 dark:bg-gray-900/40 dark:text-gray-200">
                                    <p className="font-semibold uppercase tracking-wide text-[10px] text-gray-500 dark:text-gray-400">
                                        Execution Topology
                                    </p>
                                    <div className="mt-2 space-y-1">
                                        <p>
                                            <span className="font-medium">Workspace:</span>{' '}
                                            {activeWorkspace?.name || activeWorkspaceId || 'None'}
                                        </p>
                                        <p className="break-all">
                                            <span className="font-medium">Path:</span>{' '}
                                            {activeWorkspace?.path || 'Not set'}
                                        </p>
                                        <p>
                                            <span className="font-medium">Owner Worker:</span>{' '}
                                            {activeWorkspaceOwner?.name || activeWorkspace?.worker_id || 'Auto'}
                                        </p>
                                        <p>
                                            <span className="font-medium">Runtime Mode:</span>{' '}
                                            {runtimeModeLabel}
                                        </p>
                                        {runtimeContext?.sessionId && (
                                            <p>
                                                <span className="font-medium">Session:</span> {runtimeContext.sessionId}
                                            </p>
                                        )}
                                        {runtimeContext?.knativeServiceName && (
                                            <p className="break-all">
                                                <span className="font-medium">Knative Service:</span>{' '}
                                                {runtimeContext.knativeServiceName}
                                            </p>
                                        )}
                                        {runtimeContext?.workerId && (
                                            <p>
                                                <span className="font-medium">Target Worker:</span>{' '}
                                                {runtimeContext.workerId}
                                            </p>
                                        )}
                                        {runtimeContext?.status && (
                                            <p>
                                                <span className="font-medium">Latest Task Status:</span>{' '}
                                                {runtimeContext.status}
                                            </p>
                                        )}
                                    </div>
                                </div>
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
                                    autoOptionLabel="Auto routing (recommended)"
                                    className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                                />
                                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                    Optional override. Leave blank to use workspace owner or platform routing (including Knative when enabled).
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
                                    <option value="explore">🔍 Explore - Workspace search</option>
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
                                disabled={loading || !activeWorkspaceId || !prompt.trim()}
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
                                {activeWorkspaceId
                                    ? `Streaming from ${activeWorkspaceId}`
                                    : 'No workspace available for swarm stream'}
                            </p>
                        </div>
                        <div className="p-4 space-y-3">
                            {!activeWorkspaceId ? (
                                <p className="text-xs text-gray-500 dark:text-gray-400">
                                    Connect a worker or register a workspace to stream swarm events.
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
                                        {(w.global_workspace_id || w.global_codebase_id) && (
                                            <button
                                                onClick={() => setSelectedCodebase((w.global_workspace_id || w.global_codebase_id)!)}
                                                className="mt-2 w-full rounded bg-indigo-50 dark:bg-indigo-900/30 px-2 py-1 text-[10px] font-medium text-indigo-600 dark:text-indigo-400 hover:bg-indigo-100 dark:hover:bg-indigo-900/50 flex items-center justify-center gap-1"
                                            >
                                                💬 Use Global Workspace
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
                            {workspaces.length === 0 && (
                                <button
                                    onClick={() => {
                                        setWorkspaceWizardStep(0)
                                        setShowWorkspaceWizard(true)
                                    }}
                                    className="w-full text-left px-3 py-2 rounded-md text-sm text-indigo-700 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-900/20 hover:bg-indigo-100 dark:hover:bg-indigo-900/40 flex items-center gap-2"
                                >
                                    <span>🧭</span> First Workspace Wizard
                                </button>
                            )}
                            <div className="mb-3">
                                <VoiceAgentButton
                                    codebaseId={activeWorkspaceId || undefined}
                                    workers={workers}
                                    onWorkerDeployed={loadWorkers}
                                />
                            </div>
                            <button
                                onClick={openRegisterWorkspaceModal}
                                className="w-full text-left px-3 py-2 rounded-md text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2"
                            >
                                <span>📁</span> Register Workspace
                            </button>
                            <button
                                onClick={loadWorkspaces}
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
                                        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Register Workspace</h3>
                                        <div className="space-y-4">
                                            <div>
                                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Source</label>
                                                <div className="grid grid-cols-3 gap-2">
                                                    <button
                                                        type="button"
                                                        onClick={() => setRegisterMode('local')}
                                                        className={`rounded-md px-3 py-2 text-sm font-medium border ${registerMode === 'local'
                                                                ? 'border-indigo-500 bg-indigo-50 text-indigo-700 dark:border-indigo-400 dark:bg-indigo-900/30 dark:text-indigo-200'
                                                                : 'border-gray-300 text-gray-700 dark:border-gray-600 dark:text-gray-300'
                                                            }`}
                                                    >
                                                        Directory
                                                    </button>
                                                    <button
                                                        type="button"
                                                        onClick={() => setRegisterMode('git')}
                                                        className={`rounded-md px-3 py-2 text-sm font-medium border ${registerMode === 'git'
                                                                ? 'border-indigo-500 bg-indigo-50 text-indigo-700 dark:border-indigo-400 dark:bg-indigo-900/30 dark:text-indigo-200'
                                                                : 'border-gray-300 text-gray-700 dark:border-gray-600 dark:text-gray-300'
                                                            }`}
                                                    >
                                                        Repository URL
                                                    </button>
                                                    <button
                                                        type="button"
                                                        onClick={() => setRegisterMode('external')}
                                                        className={`rounded-md px-3 py-2 text-sm font-medium border ${registerMode === 'external'
                                                                ? 'border-indigo-500 bg-indigo-50 text-indigo-700 dark:border-indigo-400 dark:bg-indigo-900/30 dark:text-indigo-200'
                                                                : 'border-gray-300 text-gray-700 dark:border-gray-600 dark:text-gray-300'
                                                            }`}
                                                    >
                                                        External App
                                                    </button>
                                                </div>
                                            </div>
                                            <div>
                                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Name</label>
                                                <input
                                                    type="text"
                                                    value={registerForm.name}
                                                    onChange={(e) => setRegisterForm({ ...registerForm, name: e.target.value })}
                                                    placeholder="workspace-name"
                                                    className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                                                />
                                            </div>
                                            {registerMode === 'local' ? (
                                                <div>
                                                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Directory</label>
                                                    <input
                                                        type="text"
                                                        value={registerForm.path}
                                                        onChange={(e) => setRegisterForm({ ...registerForm, path: e.target.value })}
                                                        placeholder="/absolute/path/on-worker-or-mounted-volume"
                                                        className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                                                    />
                                                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                                        Required. This path must exist in the selected runtime environment.
                                                    </p>
                                                </div>
                                            ) : registerMode === 'git' ? (
                                                <>
                                                    <div>
                                                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Git URL</label>
                                                        <input
                                                            type="text"
                                                            value={registerForm.git_url}
                                                            onChange={(e) => setRegisterForm({ ...registerForm, git_url: e.target.value })}
                                                            placeholder="https://github.com/org/repo.git"
                                                            className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                                                        />
                                                    </div>
                                                    <div>
                                                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Git Branch</label>
                                                        <input
                                                            type="text"
                                                            value={registerForm.git_branch}
                                                            onChange={(e) => setRegisterForm({ ...registerForm, git_branch: e.target.value })}
                                                            placeholder="main"
                                                            className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                                                        />
                                                    </div>
                                                    <div>
                                                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Directory Override (optional)</label>
                                                        <input
                                                            type="text"
                                                            value={registerForm.path}
                                                            onChange={(e) => setRegisterForm({ ...registerForm, path: e.target.value })}
                                                            placeholder="/var/lib/codetether/repos/my-repo"
                                                            className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                                                        />
                                                    </div>
                                                    <p className="text-xs text-gray-500 dark:text-gray-400">
                                                        The source is materialized and bound to this workspace ID.
                                                    </p>
                                                </>
                                            ) : (
                                                <>
                                                    <div>
                                                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">External Provider</label>
                                                        <input
                                                            type="text"
                                                            value={registerForm.external_provider}
                                                            onChange={(e) => setRegisterForm({ ...registerForm, external_provider: e.target.value })}
                                                            placeholder="Canva, HubSpot, Mailchimp, Salesforce..."
                                                            className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                                                        />
                                                    </div>
                                                    <div>
                                                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">External Reference (optional)</label>
                                                        <input
                                                            type="text"
                                                            value={registerForm.external_reference}
                                                            onChange={(e) => setRegisterForm({ ...registerForm, external_reference: e.target.value })}
                                                            placeholder="campaign-2026-q1, brand-kit-main, legal-case-42"
                                                            className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                                                        />
                                                    </div>
                                                    <div>
                                                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Directory Override (optional)</label>
                                                        <input
                                                            type="text"
                                                            value={registerForm.path}
                                                            onChange={(e) => setRegisterForm({ ...registerForm, path: e.target.value })}
                                                            placeholder="/mounted/sync/path/if-available"
                                                            className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                                                        />
                                                    </div>
                                                    <p className="text-xs text-gray-500 dark:text-gray-400">
                                                        Use this mode to anchor workspace identity to non-repository systems while keeping routing, permissions, and history unified.
                                                    </p>
                                                </>
                                            )}
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
                                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                                    {registerMode === 'external' ? 'Worker (required for external app)' : 'Worker (optional)'}
                                                </label>
                                                <WorkerSelector
                                                    value={registerForm.worker_id}
                                                    onChange={(worker_id) => setRegisterForm({ ...registerForm, worker_id })}
                                                    workers={workers}
                                                    onlyConnected
                                                    includeAutoOption={registerMode !== 'external'}
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
                                                onClick={registerWorkspace}
                                                disabled={!canRegisterWorkspace}
                                                className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
                                            >
                                                {registerMode === 'git'
                                                    ? 'Register & Queue Clone'
                                                    : registerMode === 'external'
                                                        ? 'Create External Workspace'
                                                        : 'Register Workspace'}
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
