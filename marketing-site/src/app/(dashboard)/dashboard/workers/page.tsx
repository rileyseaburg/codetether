'use client'

import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { useSession } from 'next-auth/react'
import { useTenantApi } from '@/hooks/useTenantApi'
import { ModelSelector } from '@/components/ModelSelector'

const FALLBACK_API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.codetether.run'

interface Worker {
    worker_id: string
    name: string
    hostname?: string
    status: string
    last_seen: string
    registered_at: string
    codebases: string[]
    models: Array<{ providerID?: string, modelID?: string, provider?: string, name?: string, id?: string } | string>
    capabilities: string[]
    global_codebase_id?: string
    worker_runtime?: 'rust' | 'opencode_python'
    worker_runtime_label?: string
    is_sse_connected?: boolean
}

interface Codebase {
    id: string
    name: string
    path: string
    worker_id?: string
    status: string
}

interface ConnectedWorkersResponse {
    workers?: Array<{
        worker_id?: string
        agent_name?: string
        last_heartbeat?: string
    }>
}

interface ChatMessage {
    id: string
    role: 'user' | 'assistant' | 'system'
    content: string
    createdAt: number
    status?: 'streaming' | 'complete' | 'error'
}

function normalizeModelRef(value: string): string {
    if (value.includes(':')) return value
    if (value.includes('/')) {
        const [provider, model] = value.split('/', 2)
        if (provider && model) return `${provider}:${model}`
    }
    return value
}

function toProviderModel(value: string): string {
    const normalized = normalizeModelRef(value)
    if (normalized.includes(':')) {
        const [provider, model] = normalized.split(':', 2)
        return `${provider}/${model}`
    }
    return normalized
}

function formatTimeAgo(dateString: string) {
    const date = new Date(dateString)
    const now = new Date()
    const seconds = Math.floor((now.getTime() - date.getTime()) / 1000)
    if (seconds < 60) return `${seconds}s ago`
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
    return `${Math.floor(seconds / 86400)}d ago`
}

function getModelString(m: Worker['models'][0]): string {
    if (typeof m === 'string') return m
    if (m.providerID && m.modelID) return `${m.providerID}:${m.modelID}`
    if (m.provider && m.name) return `${m.provider}:${m.name}`
    if (m.provider && m.id) return `${m.provider}:${m.id}`
    return m.name || m.id || 'unknown'
}

function uniqueWorkerModelRefs(worker: Worker): string[] {
    const seen = new Set<string>()
    const values: string[] = []
    for (const model of worker.models || []) {
        const raw = getModelString(model).trim()
        if (!raw || raw === 'unknown') continue
        const normalized = normalizeModelRef(raw)
        if (seen.has(normalized)) continue
        seen.add(normalized)
        values.push(normalized)
    }
    return values
}

function chooseRecommendedModel(modelRefs: string[]): string | null {
    if (!modelRefs.length) return null
    const providerPreference = [
        'openrouter',
        'bedrock',
        'cerebras',
        'minimax',
        'stepfun',
        'zhipuai',
        'novita',
        'moonshotai',
        'google',
        'github-copilot',
    ]

    for (const provider of providerPreference) {
        const found = modelRefs.find((ref) => ref.toLowerCase().startsWith(`${provider}:`))
        if (found) return found
    }
    return modelRefs[0] || null
}

type WorkerType = 'codetether-agent' | 'opencode'

function detectWorkerType(worker: Worker): WorkerType {
    if (worker.worker_runtime === 'rust') return 'codetether-agent'
    if (worker.worker_runtime === 'opencode_python') return 'opencode'

    const name = (worker.name || '').toLowerCase()
    const caps = (worker.capabilities || []).map(c => c.toLowerCase())
    if (name.includes('codetether') || caps.includes('ralph') || caps.includes('swarm') || caps.includes('rlm')) {
        return 'codetether-agent'
    }
    if (caps.includes('opencode') || name.includes('opencode')) {
        return 'opencode'
    }
    return 'opencode'
}

const workerTypeMeta: Record<WorkerType, { label: string, color: string, icon: string }> = {
    'codetether-agent': {
        label: 'CodeTether Agent',
        color: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400 border border-orange-200 dark:border-orange-800',
        icon: '🦀',
    },
    'opencode': {
        label: 'OpenCode Worker',
        color: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900/30 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-800',
        icon: '🐍',
    },
}

function WorkerTypeBadge({ worker }: { worker: Worker }) {
    const type = detectWorkerType(worker)
    const meta = workerTypeMeta[type]
    return (
        <span className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs font-semibold rounded-full ${meta.color}`}>
            <span>{meta.icon}</span>
            {meta.label}
        </span>
    )
}

function StatusBadge({ lastSeen }: { lastSeen: string }) {
    const isRecent = (new Date().getTime() - new Date(lastSeen).getTime()) < 120000
    const color = isRecent ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400' : 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400'
    return <span className={`px-2 py-1 text-xs font-medium rounded-full ${color}`}>{isRecent ? 'Online' : 'Stale'}</span>
}

function extractOutputText(payload: unknown): string {
    if (typeof payload === 'string') return payload
    if (!payload || typeof payload !== 'object') return ''
    const event = payload as Record<string, unknown>
    if (typeof event.output === 'string') return event.output
    if (typeof event.content === 'string') return event.content
    if (typeof event.message === 'string') return event.message
    return ''
}

function WorkerCard({
    worker,
    codebases,
    onOpenChat,
    chatOpen,
}: {
    worker: Worker
    codebases: Codebase[]
    onOpenChat: (workerId: string) => void
    chatOpen: boolean
}) {
    const [expanded, setExpanded] = useState(false)
    const linkedCodebases = codebases.filter(cb => (worker.codebases || []).includes(cb.id) || cb.worker_id === worker.worker_id)
    const modelCount = worker.models?.length || 0

    return (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
            <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                        <WorkerTypeBadge worker={worker} />
                        {worker.is_sse_connected ? (
                            <span className="px-2 py-0.5 text-[10px] rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">
                                SSE connected
                            </span>
                        ) : null}
                    </div>
                    <div className="flex items-center gap-2">
                        <h3 className="text-sm font-semibold text-gray-900 dark:text-white truncate">{worker.name}</h3>
                        <StatusBadge lastSeen={worker.last_seen} />
                    </div>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 font-mono truncate">{worker.worker_id}</p>
                    {worker.hostname && <p className="text-xs text-gray-400 dark:text-gray-500">{worker.hostname}</p>}
                </div>
                <div className="flex items-center gap-2">
                    <button
                        onClick={() => onOpenChat(worker.worker_id)}
                        disabled={!worker.is_sse_connected}
                        className={`px-2.5 py-1.5 text-xs font-medium rounded-md transition-colors ${
                            worker.is_sse_connected
                                ? 'bg-cyan-600 text-white hover:bg-cyan-500'
                                : 'bg-gray-100 text-gray-400 dark:bg-gray-700 dark:text-gray-500 cursor-not-allowed'
                        }`}
                    >
                        {chatOpen ? 'Open Chat' : 'Chat via SSE'}
                    </button>
                    <button onClick={() => setExpanded(!expanded)} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
                        <svg className={`w-5 h-5 transition-transform ${expanded ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                        </svg>
                    </button>
                </div>
            </div>

            <div className="mt-3 flex flex-wrap gap-2">
                <span className="px-2 py-1 text-xs bg-cyan-100 text-cyan-800 dark:bg-cyan-900/30 dark:text-cyan-400 rounded">{modelCount} models</span>
                <span className="px-2 py-1 text-xs bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400 rounded">{linkedCodebases.length} codebases</span>
                <span className="px-2 py-1 text-xs bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300 rounded">{formatTimeAgo(worker.last_seen)}</span>
            </div>

            {expanded && (
                <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700 space-y-4">
                    <div>
                        <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">Worker Type</h4>
                        <div className="flex items-center gap-2">
                            <WorkerTypeBadge worker={worker} />
                            <span className="text-xs text-gray-400">{detectWorkerType(worker) === 'codetether-agent' ? 'Rust-based agent with ralph/swarm/rlm capabilities' : 'Python-based worker with opencode/build/deploy capabilities'}</span>
                        </div>
                    </div>

                    <div>
                        <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">Linked Codebases</h4>
                        {linkedCodebases.length === 0 ? (
                            <p className="text-xs text-gray-400">No codebases linked</p>
                        ) : (
                            <div className="space-y-1">
                                {linkedCodebases.map(cb => (
                                    <div key={cb.id} className="flex items-center justify-between text-xs">
                                        <span className="text-gray-700 dark:text-gray-300">{cb.name}</span>
                                        <span className="font-mono text-gray-400">{cb.id.slice(0, 8)}</span>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>

                    <div>
                        <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">Models ({modelCount})</h4>
                        <div className="max-h-32 overflow-y-auto">
                            <div className="flex flex-wrap gap-1">
                                {(worker.models || []).slice(0, 20).map((m, i) => (
                                    <span key={i} className="px-1.5 py-0.5 text-[10px] bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 rounded">{getModelString(m)}</span>
                                ))}
                                {modelCount > 20 && <span className="px-1.5 py-0.5 text-[10px] text-gray-400">+{modelCount - 20} more</span>}
                            </div>
                        </div>
                    </div>

                    {worker.capabilities?.length > 0 && (
                        <div>
                            <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">Capabilities</h4>
                            <div className="flex flex-wrap gap-1">
                                {worker.capabilities.map((cap, i) => (
                                    <span key={i} className="px-1.5 py-0.5 text-[10px] bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded">{cap}</span>
                                ))}
                            </div>
                        </div>
                    )}

                    <div className="text-[10px] text-gray-400">
                        Registered: {new Date(worker.registered_at).toLocaleString()}
                    </div>
                </div>
            )}
        </div>
    )
}

export default function WorkersPage() {
    const { data: session } = useSession()
    const { apiUrl, tenantFetch } = useTenantApi()
    const resolvedApiUrl = apiUrl || FALLBACK_API_URL

    const [workers, setWorkers] = useState<Worker[]>([])
    const [codebases, setCodebases] = useState<Codebase[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [chatWorkerId, setChatWorkerId] = useState<string | null>(null)
    const [chatInput, setChatInput] = useState('')
    const [chatByWorker, setChatByWorker] = useState<Record<string, ChatMessage[]>>({})
    const [pendingTaskByWorker, setPendingTaskByWorker] = useState<Record<string, string | null>>({})
    const [selectedModelByWorker, setSelectedModelByWorker] = useState<Record<string, string>>({})

    const streamRef = useRef<{ workerId: string, taskId: string, source: EventSource, assistantMessageId: string } | null>(null)
    const messagesContainerRef = useRef<HTMLDivElement | null>(null)

    const appendMessage = useCallback((workerId: string, message: ChatMessage) => {
        setChatByWorker((prev) => ({
            ...prev,
            [workerId]: [...(prev[workerId] || []), message],
        }))
    }, [])

    const patchMessage = useCallback(
        (workerId: string, messageId: string, updater: (current: ChatMessage) => ChatMessage) => {
            setChatByWorker((prev) => {
                const messages = prev[workerId] || []
                return {
                    ...prev,
                    [workerId]: messages.map((m) => (m.id === messageId ? updater(m) : m)),
                }
            })
        },
        []
    )

    const fetchTaskFinalResult = useCallback(
        async (taskId: string): Promise<{ status?: string, result?: string, error?: string }> => {
            const { data, error: requestError } = await tenantFetch<any>(`/v1/agent/tasks/${taskId}`)
            if (requestError || !data) {
                return { error: requestError || 'Failed to fetch final task result' }
            }
            return {
                status: typeof data.status === 'string' ? data.status : undefined,
                result: typeof data.result === 'string' ? data.result : undefined,
                error: typeof data.error === 'string' ? data.error : undefined,
            }
        },
        [tenantFetch]
    )

    const clearPendingForWorker = useCallback((workerId: string) => {
        setPendingTaskByWorker((prev) => ({ ...prev, [workerId]: null }))
    }, [])

    const closeActiveStream = useCallback(() => {
        if (!streamRef.current) return
        streamRef.current.source.close()
        streamRef.current = null
    }, [])

    const startTaskStream = useCallback(async (
        workerId: string,
        taskId: string,
        assistantMessageId: string
    ) => {
        closeActiveStream()

        // Handle relative API URLs by resolving against window.location
        const absoluteApiUrl = resolvedApiUrl.startsWith('/') ? `${window.location.origin}${resolvedApiUrl}` : resolvedApiUrl
        const baseUrl = absoluteApiUrl.replace(/\/+$/, '')
        const sseUrl = new URL(`${baseUrl}/v1/agent/tasks/${encodeURIComponent(taskId)}/output/stream`)
        if (session?.accessToken) {
            sseUrl.searchParams.set('access_token', session.accessToken)
        }
        const source = new EventSource(sseUrl.toString())
        let closedByClient = false

        streamRef.current = { workerId, taskId, source, assistantMessageId }

        source.addEventListener('output', (rawEvent) => {
            const event = rawEvent as MessageEvent<string>
            if (!event.data) return

            let text = ''
            try {
                text = extractOutputText(JSON.parse(event.data))
            } catch {
                text = event.data
            }
            if (!text.trim()) return

            patchMessage(workerId, assistantMessageId, (current) => ({
                ...current,
                content: current.content ? `${current.content}${text}` : text,
                status: 'streaming',
            }))
        })

        source.addEventListener('done', async (rawEvent) => {
            closedByClient = true
            source.close()
            if (streamRef.current?.taskId === taskId) {
                streamRef.current = null
            }

            let doneStatus = 'completed'
            const event = rawEvent as MessageEvent<string>
            if (event.data) {
                try {
                    const parsed = JSON.parse(event.data) as { status?: string }
                    if (typeof parsed.status === 'string') {
                        doneStatus = parsed.status
                    }
                } catch {
                    // ignore malformed done payloads
                }
            }

            const final = await fetchTaskFinalResult(taskId)
            patchMessage(workerId, assistantMessageId, (current) => {
                const hasContent = current.content.trim().length > 0
                const fallbackText = final.result?.trim() || ''
                const content = hasContent ? current.content : fallbackText
                if (doneStatus === 'failed' || final.error) {
                    const errorText = final.error || 'Task failed'
                    return {
                        ...current,
                        content: content || errorText,
                        status: 'error',
                    }
                }
                return {
                    ...current,
                    content: content || 'Task completed without textual output.',
                    status: 'complete',
                }
            })
            clearPendingForWorker(workerId)
        })

        source.onerror = async () => {
            if (closedByClient) return
            closedByClient = true
            source.close()
            if (streamRef.current?.taskId === taskId) {
                streamRef.current = null
            }

            const final = await fetchTaskFinalResult(taskId)
            patchMessage(workerId, assistantMessageId, (current) => {
                if (current.content.trim()) {
                    return { ...current, status: 'complete' }
                }
                if (final.result?.trim()) {
                    return { ...current, content: final.result.trim(), status: 'complete' }
                }
                return {
                    ...current,
                    content: final.error || 'Live stream disconnected before any response was received.',
                    status: 'error',
                }
            })
            clearPendingForWorker(workerId)
        }
    }, [clearPendingForWorker, closeActiveStream, fetchTaskFinalResult, patchMessage, resolvedApiUrl])

    const fetchData = useCallback(async () => {
        try {
            const [workersRes, codebasesRes, connectedRes] = await Promise.all([
                tenantFetch<Worker[]>('/v1/opencode/workers'),
                tenantFetch<Codebase[]>('/v1/opencode/codebases/list'),
                tenantFetch<ConnectedWorkersResponse>('/v1/worker/connected'),
            ])

            if (workersRes.error || codebasesRes.error) {
                throw new Error(workersRes.error || codebasesRes.error || 'Failed to fetch data')
            }

            const connectedWorkers = connectedRes.data?.workers || []
            const connectedById = new Map(
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

            const workersData = Array.isArray(workersRes.data) ? workersRes.data : []
            const codebasesData = Array.isArray(codebasesRes.data) ? codebasesRes.data : []

            const mergedWorkers = workersData.map((worker) => {
                const connected = connectedById.get(worker.worker_id)
                return {
                    ...worker,
                    name: connected?.name || worker.name,
                    last_seen: connected?.last_seen || worker.last_seen,
                    is_sse_connected: Boolean(connected),
                }
            })

            setWorkers(mergedWorkers)
            setCodebases(codebasesData)
            setError(null)
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to load')
        } finally {
            setLoading(false)
        }
    }, [tenantFetch])

    const sendToWorker = useCallback(async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault()
        if (!chatWorkerId) return

        const text = chatInput.trim()
        if (!text) return

        const worker = workers.find((w) => w.worker_id === chatWorkerId)
        if (!worker?.is_sse_connected) {
            appendMessage(chatWorkerId, {
                id: `system-${Date.now()}`,
                role: 'system',
                content: 'Worker is not connected to SSE. Select a connected worker.',
                createdAt: Date.now(),
                status: 'error',
            })
            return
        }

        setChatInput('')

        const userMessage: ChatMessage = {
            id: `user-${Date.now()}`,
            role: 'user',
            content: text,
            createdAt: Date.now(),
            status: 'complete',
        }
        appendMessage(chatWorkerId, userMessage)

        const assistantMessageId = `assistant-${Date.now()}`
        appendMessage(chatWorkerId, {
            id: assistantMessageId,
            role: 'assistant',
            content: '',
            createdAt: Date.now(),
            status: 'streaming',
        })

        setPendingTaskByWorker((prev) => ({ ...prev, [chatWorkerId]: 'pending' }))

        const availableModels = uniqueWorkerModelRefs(worker)
        const selectedModelRef = selectedModelByWorker[chatWorkerId] || chooseRecommendedModel(availableModels)

        const title = `Worker chat: ${text.slice(0, 80)}`
        const payload = {
            title,
            prompt: text,
            agent_type: 'general',
            priority: 5,
            ...(selectedModelRef ? { model_ref: selectedModelRef, model: toProviderModel(selectedModelRef) } : {}),
            metadata: {
                source: 'workers_realtime_chat',
                target_worker_id: chatWorkerId,
                interactive: true,
                ...(selectedModelRef ? { model_ref: selectedModelRef } : {}),
            },
        }

        const { data, error: requestError } = await tenantFetch<{ id?: string }>('/v1/agent/tasks', {
            method: 'POST',
            body: JSON.stringify(payload),
        })

        if (requestError || !data?.id) {
            patchMessage(chatWorkerId, assistantMessageId, (current) => ({
                ...current,
                content: requestError || 'Failed to create worker task',
                status: 'error',
            }))
            clearPendingForWorker(chatWorkerId)
            return
        }

        setPendingTaskByWorker((prev) => ({ ...prev, [chatWorkerId]: data.id || null }))
        await startTaskStream(chatWorkerId, data.id, assistantMessageId)
    }, [appendMessage, chatInput, chatWorkerId, clearPendingForWorker, patchMessage, selectedModelByWorker, startTaskStream, tenantFetch, workers])

    useEffect(() => {
        fetchData()
        const interval = setInterval(fetchData, 10000)
        return () => clearInterval(interval)
    }, [fetchData])

    useEffect(() => {
        return () => closeActiveStream()
    }, [closeActiveStream])

    useEffect(() => {
        if (!chatWorkerId) {
            closeActiveStream()
        }
    }, [chatWorkerId, closeActiveStream])

    const activeWorker = useMemo(
        () => workers.find((w) => w.worker_id === chatWorkerId) || null,
        [chatWorkerId, workers]
    )
    const activeWorkerModelRefs = useMemo(() => (activeWorker ? uniqueWorkerModelRefs(activeWorker) : []), [activeWorker])
    const recommendedActiveWorkerModel = useMemo(() => chooseRecommendedModel(activeWorkerModelRefs), [activeWorkerModelRefs])
    const selectedActiveModel =
        chatWorkerId && selectedModelByWorker[chatWorkerId]
            ? selectedModelByWorker[chatWorkerId]
            : (recommendedActiveWorkerModel || '')
    const activeChatMessages = chatWorkerId ? (chatByWorker[chatWorkerId] || []) : []
    const activeTaskPending = Boolean(chatWorkerId && pendingTaskByWorker[chatWorkerId])

    useEffect(() => {
        if (!chatWorkerId || !activeWorker) return
        setSelectedModelByWorker((prev) => {
            if (prev[chatWorkerId]) return prev
            const fallback = chooseRecommendedModel(uniqueWorkerModelRefs(activeWorker))
            if (!fallback) return prev
            return { ...prev, [chatWorkerId]: fallback }
        })
    }, [activeWorker, chatWorkerId])

    useEffect(() => {
        if (!messagesContainerRef.current) return
        messagesContainerRef.current.scrollTop = messagesContainerRef.current.scrollHeight
    }, [activeChatMessages])

    const onlineWorkers = workers.filter(w => (new Date().getTime() - new Date(w.last_seen).getTime()) < 120000)
    const staleWorkers = workers.filter(w => (new Date().getTime() - new Date(w.last_seen).getTime()) >= 120000)
    const codetetherWorkers = workers.filter(w => detectWorkerType(w) === 'codetether-agent')
    const opencodeWorkers = workers.filter(w => detectWorkerType(w) === 'opencode')

    return (
        <div className="p-6 max-w-7xl mx-auto">
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Workers</h1>
                    <p className="text-sm text-gray-500 dark:text-gray-400">Manage and monitor registered workers</p>
                </div>
                <button onClick={() => { setLoading(true); fetchData() }} disabled={loading} className="px-4 py-2 text-sm bg-cyan-600 text-white rounded-lg hover:bg-cyan-500 disabled:opacity-50">
                    {loading ? 'Refreshing...' : 'Refresh'}
                </button>
            </div>

            {error && <div className="mb-4 p-3 bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 rounded-lg text-sm">{error}</div>}

            <div className="grid grid-cols-3 md:grid-cols-6 gap-4 mb-6">
                <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                    <div className="text-2xl font-bold text-gray-900 dark:text-white">{workers.length}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">Total Workers</div>
                </div>
                <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                    <div className="text-2xl font-bold text-green-600">{onlineWorkers.length}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">Online</div>
                </div>
                <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                    <div className="text-2xl font-bold text-yellow-600">{staleWorkers.length}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">Stale</div>
                </div>
                <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-orange-200 dark:border-orange-800">
                    <div className="text-2xl font-bold text-orange-600">{codetetherWorkers.length}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1">🦀 CodeTether</div>
                </div>
                <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-indigo-200 dark:border-indigo-800">
                    <div className="text-2xl font-bold text-indigo-600">{opencodeWorkers.length}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1">🐍 OpenCode</div>
                </div>
                <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                    <div className="text-2xl font-bold text-purple-600">{codebases.length}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">Codebases</div>
                </div>
            </div>

            {loading && workers.length === 0 ? (
                <div className="text-center py-12 text-gray-500">Loading workers...</div>
            ) : workers.length === 0 ? (
                <div className="text-center py-12 text-gray-500">No workers registered</div>
            ) : (
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {workers.map((worker) => (
                        <WorkerCard
                            key={worker.worker_id}
                            worker={worker}
                            codebases={codebases}
                            onOpenChat={setChatWorkerId}
                            chatOpen={chatWorkerId === worker.worker_id}
                        />
                    ))}
                </div>
            )}

            {chatWorkerId && activeWorker ? (
                <div className="fixed inset-0 z-[80] flex items-end justify-end bg-black/40 md:bg-black/30">
                    <div className="h-[85vh] w-full md:max-w-2xl bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-700 shadow-2xl flex flex-col">
                        <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
                            <div className="min-w-0">
                                <p className="text-sm text-gray-500 dark:text-gray-400">Real-time SSE chat</p>
                                <div className="flex items-center gap-2">
                                    <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100 truncate">{activeWorker.name}</h2>
                                    <WorkerTypeBadge worker={activeWorker} />
                                </div>
                                <p className="text-xs text-gray-500 dark:text-gray-400 font-mono truncate">{activeWorker.worker_id}</p>
                            </div>
                            <button
                                onClick={() => setChatWorkerId(null)}
                                className="px-3 py-1.5 rounded-md text-sm text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800"
                            >
                                Close
                            </button>
                        </div>

                        <div ref={messagesContainerRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-3 bg-gray-50 dark:bg-gray-950">
                            {activeChatMessages.length === 0 ? (
                                <div className="text-sm text-gray-500 dark:text-gray-400">
                                    Send a message to this worker. Responses stream live over SSE.
                                </div>
                            ) : (
                                activeChatMessages.map((message) => (
                                    <div key={message.id} className={`max-w-[90%] rounded-lg px-3 py-2 text-sm ${
                                        message.role === 'user'
                                            ? 'ml-auto bg-cyan-600 text-white'
                                            : message.role === 'system'
                                                ? 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300'
                                                : message.status === 'error'
                                                    ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300'
                                                    : 'bg-white text-gray-900 dark:bg-gray-800 dark:text-gray-100 border border-gray-200 dark:border-gray-700'
                                    }`}>
                                        <div className="whitespace-pre-wrap break-words">
                                            {message.content || (message.status === 'streaming' ? '...' : '')}
                                        </div>
                                        <div className={`mt-1 text-[10px] ${
                                            message.role === 'user' ? 'text-cyan-100' : 'text-gray-400 dark:text-gray-500'
                                        }`}>
                                            {new Date(message.createdAt).toLocaleTimeString()}
                                            {message.status === 'streaming' ? ' • streaming' : ''}
                                            {message.status === 'error' ? ' • error' : ''}
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>

                        <form onSubmit={sendToWorker} className="p-4 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
                            <div className="mb-2">
                                <ModelSelector
                                    visualVariant="default"
                                    label="Model"
                                    className="text-sm"
                                    showSelectedInfo={false}
                                    showEmptyState={false}
                                    selectedModel={selectedActiveModel}
                                    onSelectedModelChange={(value) => {
                                        if (!chatWorkerId) return
                                        setSelectedModelByWorker((prev) => ({
                                            ...prev,
                                            [chatWorkerId]: value,
                                        }))
                                    }}
                                    availableModels={activeWorkerModelRefs}
                                    loading={activeTaskPending}
                                    disabled={!activeWorker.is_sse_connected || activeTaskPending || activeWorkerModelRefs.length === 0}
                                />
                                {recommendedActiveWorkerModel ? (
                                    <p className="mt-1 text-[11px] text-gray-500 dark:text-gray-400">
                                        Recommended: {recommendedActiveWorkerModel}
                                    </p>
                                ) : null}
                                {!activeWorkerModelRefs.length ? (
                                    <p className="mt-1 text-[11px] text-gray-500 dark:text-gray-400">
                                        No advertised models for this worker. Requests will use worker default.
                                    </p>
                                ) : null}
                            </div>
                            <div className="flex items-end gap-2">
                                <textarea
                                    value={chatInput}
                                    onChange={(e) => setChatInput(e.target.value)}
                                    placeholder={activeWorker.is_sse_connected ? 'Message this worker...' : 'Worker is not connected'}
                                    rows={3}
                                    disabled={!activeWorker.is_sse_connected || activeTaskPending}
                                    className="flex-1 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 placeholder:text-gray-400 dark:placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-cyan-500 disabled:opacity-50"
                                />
                                <button
                                    type="submit"
                                    disabled={!activeWorker.is_sse_connected || activeTaskPending || !chatInput.trim()}
                                    className="px-4 py-2 rounded-lg text-sm font-medium bg-cyan-600 text-white hover:bg-cyan-500 disabled:opacity-50"
                                >
                                    {activeTaskPending ? 'Sending...' : 'Send'}
                                </button>
                            </div>
                            <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                                {activeWorker.is_sse_connected
                                    ? 'This uses /v1/agent/tasks + /v1/agent/tasks/{task_id}/output/stream and sends model_ref explicitly.'
                                    : 'Connect this worker via SSE to enable real-time chat.'}
                            </p>
                        </form>
                    </div>
                </div>
            ) : null}
        </div>
    )
}
