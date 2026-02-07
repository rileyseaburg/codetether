'use client'

import { useState, useEffect } from 'react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.codetether.run'

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
}

interface Codebase {
    id: string
    name: string
    path: string
    worker_id?: string
    status: string
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

type WorkerType = 'codetether-agent' | 'opencode' | 'unknown'

function detectWorkerType(worker: Worker): WorkerType {
    const name = (worker.name || '').toLowerCase()
    const caps = (worker.capabilities || []).map(c => c.toLowerCase())
    // codetether-agent: name contains 'codetether', or has ralph/swarm/rlm capabilities
    if (name.includes('codetether') || caps.includes('ralph') || caps.includes('swarm') || caps.includes('rlm')) {
        return 'codetether-agent'
    }
    // opencode worker: has 'opencode' capability, or name contains 'opencode'
    if (caps.includes('opencode') || name.includes('opencode')) {
        return 'opencode'
    }
    return 'unknown'
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
    'unknown': {
        label: 'Worker',
        color: 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-600',
        icon: '⚙️',
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

function StatusBadge({ status, lastSeen }: { status: string, lastSeen: string }) {
    const isRecent = (new Date().getTime() - new Date(lastSeen).getTime()) < 120000
    const color = isRecent ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400' : 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400'
    return <span className={`px-2 py-1 text-xs font-medium rounded-full ${color}`}>{isRecent ? 'Online' : 'Stale'}</span>
}

function WorkerCard({ worker, codebases }: { worker: Worker, codebases: Codebase[] }) {
    const [expanded, setExpanded] = useState(false)
    const linkedCodebases = codebases.filter(cb => (worker.codebases || []).includes(cb.id) || cb.worker_id === worker.worker_id)
    const modelCount = worker.models?.length || 0

    return (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
            <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                        <WorkerTypeBadge worker={worker} />
                    </div>
                    <div className="flex items-center gap-2">
                        <h3 className="text-sm font-semibold text-gray-900 dark:text-white truncate">{worker.name}</h3>
                        <StatusBadge status={worker.status} lastSeen={worker.last_seen} />
                    </div>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 font-mono truncate">{worker.worker_id}</p>
                    {worker.hostname && <p className="text-xs text-gray-400 dark:text-gray-500">{worker.hostname}</p>}
                </div>
                <button onClick={() => setExpanded(!expanded)} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
                    <svg className={`w-5 h-5 transition-transform ${expanded ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                </button>
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
                            <span className="text-xs text-gray-400">{detectWorkerType(worker) === 'codetether-agent' ? 'Rust-based agent with ralph/swarm/rlm capabilities' : detectWorkerType(worker) === 'opencode' ? 'Python-based worker with opencode/build/deploy capabilities' : 'Unknown worker type'}</span>
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
    const [workers, setWorkers] = useState<Worker[]>([])
    const [codebases, setCodebases] = useState<Codebase[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    const fetchData = async () => {
        try {
            const [workersRes, codebasesRes] = await Promise.all([
                fetch(`${API_URL}/v1/opencode/workers`),
                fetch(`${API_URL}/v1/opencode/codebases/list`)
            ])
            if (!workersRes.ok || !codebasesRes.ok) throw new Error('Failed to fetch data')
            const [workersData, codebasesData] = await Promise.all([workersRes.json(), codebasesRes.json()])
            setWorkers(workersData)
            setCodebases(codebasesData)
            setError(null)
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to load')
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchData()
        const interval = setInterval(fetchData, 10000)
        return () => clearInterval(interval)
    }, [])

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
                    <div className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1">\ud83e\udd80 CodeTether</div>
                </div>
                <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-indigo-200 dark:border-indigo-800">
                    <div className="text-2xl font-bold text-indigo-600">{opencodeWorkers.length}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1">\ud83d\udc0d OpenCode</div>
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
                    {workers.map(w => <WorkerCard key={w.worker_id} worker={w} codebases={codebases} />)}
                </div>
            )}
        </div>
    )
}
