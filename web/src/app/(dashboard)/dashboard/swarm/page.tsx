'use client'

import { useState, useEffect, useCallback } from 'react'
import { useTenantApi } from '@/hooks/useTenantApi'

interface Worker {
    worker_id: string
    name: string
    status: string
    last_seen: string
    capabilities: string[]
    is_sse_connected?: boolean
}

interface Task {
    id: string
    title: string
    status: string
    created_at?: string
    metadata?: Record<string, unknown>
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

const statusColors: Record<string, string> = {
    running: 'bg-cyan-500/20 text-cyan-400',
    completed: 'bg-green-500/20 text-green-400',
    failed: 'bg-red-500/20 text-red-400',
    pending: 'bg-yellow-500/20 text-yellow-400',
    queued: 'bg-gray-500/20 text-gray-400',
}

export default function SwarmPage() {
    const [activeTab, setActiveTab] = useState<'monitor' | 'strategies' | 'guide'>('monitor')
    const { tenantFetch, isAuthenticated, isLoading: authLoading } = useTenantApi()

    const [workers, setWorkers] = useState<Worker[]>([])
    const [tasks, setTasks] = useState<Task[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    const fetchData = useCallback(async () => {
        const [workersRes, tasksRes] = await Promise.all([
            tenantFetch<Worker[]>('/v1/agent/workers'),
            tenantFetch<Task[]>('/v1/agent/tasks'),
        ])

        if (workersRes.error || tasksRes.error) {
            setError(workersRes.error || tasksRes.error || 'Failed to load data')
        } else {
            setError(null)
        }

        setWorkers(Array.isArray(workersRes.data) ? workersRes.data : [])
        setTasks(Array.isArray(tasksRes.data) ? tasksRes.data : [])
    }, [tenantFetch])

    useEffect(() => {
        if (!isAuthenticated) return
        setLoading(true)
        fetchData().finally(() => setLoading(false))
        const interval = setInterval(fetchData, 10000)
        return () => clearInterval(interval)
    }, [isAuthenticated, fetchData])

    const onlineWorkers = workers.filter(w => (new Date().getTime() - new Date(w.last_seen).getTime()) < 120000)
    const swarmCapableWorkers = workers.filter(w => (w.capabilities || []).some(c => c.toLowerCase().includes('swarm')))
    const runningTasks = tasks.filter(t => t.status === 'running')
    const recentTasks = tasks.slice(0, 10)

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Swarm Execution</h1>
                    <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                        Decompose complex tasks into subtasks and execute them concurrently with parallel sub-agents.
                    </p>
                </div>
                {isAuthenticated && (
                    <button
                        onClick={() => { setLoading(true); fetchData().finally(() => setLoading(false)) }}
                        disabled={loading}
                        className="px-4 py-2 text-sm bg-cyan-600 text-white rounded-lg hover:bg-cyan-500 disabled:opacity-50"
                    >
                        {loading ? 'Refreshing...' : 'Refresh'}
                    </button>
                )}
            </div>

            {/* Live stats bar */}
            {isAuthenticated && !authLoading && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                        <div className="text-2xl font-bold text-green-600">{onlineWorkers.length}</div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">Workers Online</div>
                    </div>
                    <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-cyan-200 dark:border-cyan-800">
                        <div className="text-2xl font-bold text-cyan-600">{swarmCapableWorkers.length}</div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">Swarm-Capable</div>
                    </div>
                    <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-orange-200 dark:border-orange-800">
                        <div className="text-2xl font-bold text-orange-600">{runningTasks.length}</div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">Running Tasks</div>
                    </div>
                    <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                        <div className="text-2xl font-bold text-gray-900 dark:text-white">{tasks.length}</div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">Total Tasks</div>
                    </div>
                </div>
            )}

            {/* Tabs */}
            <div className="border-b border-gray-700">
                <nav className="flex gap-4">
                    {([
                        { key: 'monitor' as const, label: 'Live Monitor' },
                        { key: 'strategies' as const, label: 'Strategies' },
                        { key: 'guide' as const, label: 'Guide' },
                    ]).map(tab => (
                        <button
                            key={tab.key}
                            onClick={() => setActiveTab(tab.key)}
                            className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${activeTab === tab.key
                                ? 'border-cyan-500 text-cyan-400'
                                : 'border-transparent text-gray-400 hover:text-gray-300'
                                }`}
                        >
                            {tab.label}
                        </button>
                    ))}
                </nav>
            </div>

            {activeTab === 'monitor' && (
                <div className="space-y-6">
                    {!isAuthenticated && !authLoading ? (
                        <div className="rounded-xl border border-yellow-500/30 bg-yellow-500/5 p-8 text-center">
                            <h3 className="text-lg font-semibold text-white mb-2">Sign in to monitor swarm activity</h3>
                            <p className="text-sm text-gray-400">Connect your account to see live worker and task data.</p>
                        </div>
                    ) : loading && workers.length === 0 ? (
                        <div className="flex items-center gap-2 text-gray-400 py-12 justify-center">
                            <div className="h-4 w-4 animate-spin rounded-full border-2 border-cyan-500 border-t-transparent" />
                            Loading swarm data...
                        </div>
                    ) : error ? (
                        <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-4 text-sm text-red-400">{error}</div>
                    ) : (
                        <>
                            {/* Available workers */}
                            <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-6">
                                <h3 className="text-lg font-semibold text-white mb-4">Available Workers</h3>
                                {onlineWorkers.length === 0 ? (
                                    <p className="text-sm text-gray-400">No workers online. Deploy a worker to enable swarm execution.</p>
                                ) : (
                                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                                        {onlineWorkers.map(w => (
                                            <div key={w.worker_id} className="rounded-lg bg-gray-700/50 p-4">
                                                <div className="flex items-center gap-2 mb-1">
                                                    <span className="h-2 w-2 rounded-full bg-green-500" />
                                                    <span className="text-sm font-medium text-white truncate">{w.name}</span>
                                                </div>
                                                <p className="text-xs text-gray-500 font-mono">{w.worker_id.slice(0, 12)}...</p>
                                                <div className="mt-2 flex flex-wrap gap-1">
                                                    {(w.capabilities || []).slice(0, 5).map((cap, i) => (
                                                        <span key={i} className="px-1.5 py-0.5 text-[10px] bg-cyan-500/10 text-cyan-400 rounded">
                                                            {cap}
                                                        </span>
                                                    ))}
                                                </div>
                                                <p className="text-[10px] text-gray-500 mt-2">{formatTimeAgo(w.last_seen)}</p>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>

                            {/* Recent tasks */}
                            <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-6">
                                <h3 className="text-lg font-semibold text-white mb-4">Recent Tasks</h3>
                                {recentTasks.length === 0 ? (
                                    <p className="text-sm text-gray-400">No tasks yet. Start a swarm from the CLI or create a task.</p>
                                ) : (
                                    <div className="space-y-2">
                                        {recentTasks.map(task => (
                                            <div key={task.id} className="flex items-center gap-3 rounded-lg bg-gray-700/50 px-4 py-3">
                                                <span className={`px-2 py-0.5 text-xs font-medium rounded-full shrink-0 ${statusColors[task.status] || 'bg-gray-500/20 text-gray-400'}`}>
                                                    {task.status}
                                                </span>
                                                <span className="text-sm text-gray-300 truncate flex-1">{task.title}</span>
                                                <span className="text-xs text-gray-500 font-mono shrink-0">{task.id.slice(0, 8)}</span>
                                                {task.created_at && (
                                                    <span className="text-xs text-gray-500 shrink-0">{formatTimeAgo(task.created_at)}</span>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </>
                    )}
                </div>
            )}

            {activeTab === 'strategies' && (
                <div className="space-y-4">
                    {[
                        {
                            name: 'auto',
                            label: 'Auto (Default)',
                            desc: 'Automatically selects the best decomposition strategy based on task analysis. Examines the task description and workspace context to pick domain, data, stage, or none.',
                            when: 'Most tasks — let the system decide.',
                        },
                        {
                            name: 'domain',
                            label: 'Domain',
                            desc: 'Splits by domain or module boundaries. Each sub-agent works on a distinct part of the workspace context (e.g., content, ops, backend, compliance).',
                            when: 'Refactoring, feature work spanning multiple modules.',
                        },
                        {
                            name: 'data',
                            label: 'Data',
                            desc: 'Splits by data partitions or input segments. Useful when the same operation needs to be applied across multiple data sets or files.',
                            when: 'Batch processing, migrations, data transforms.',
                        },
                        {
                            name: 'stage',
                            label: 'Stage',
                            desc: 'Splits by execution stages in a pipeline. Each sub-agent handles one phase (e.g., analysis → implementation → testing → documentation).',
                            when: 'End-to-end feature delivery, multi-phase work.',
                        },
                        {
                            name: 'none',
                            label: 'None',
                            desc: 'No decomposition — runs the task as a single agent. Useful when the task is already atomic or decomposition would add overhead.',
                            when: 'Simple tasks, debugging, single-file changes.',
                        },
                    ].map(strategy => (
                        <div key={strategy.name} className="rounded-xl border border-gray-700 bg-gray-800/50 p-5">
                            <div className="flex items-center gap-3 mb-2">
                                <code className="text-sm font-mono text-cyan-400 bg-cyan-500/10 px-2 py-0.5 rounded">{strategy.name}</code>
                                <h3 className="text-base font-semibold text-white">{strategy.label}</h3>
                            </div>
                            <p className="text-sm text-gray-300">{strategy.desc}</p>
                            <p className="mt-2 text-xs text-gray-500"><span className="text-gray-400 font-medium">Best for:</span> {strategy.when}</p>
                        </div>
                    ))}
                </div>
            )}

            {activeTab === 'guide' && (
                <div className="space-y-6">
                    {/* How it works */}
                    <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-6">
                        <h3 className="text-lg font-semibold text-white mb-4">How Swarm Works</h3>
                        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                            {[
                                { step: '1', title: 'Decompose', desc: 'Complex task is broken into independent subtasks using the selected strategy' },
                                { step: '2', title: 'Distribute', desc: 'Subtasks are assigned to parallel sub-agents' },
                                { step: '3', title: 'Execute', desc: 'Sub-agents work concurrently with real-time progress' },
                                { step: '4', title: 'Synthesize', desc: 'Results are collected, validated, and merged into a final output' },
                            ].map(item => (
                                <div key={item.step} className="rounded-lg bg-gray-700/50 p-4">
                                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-cyan-600 text-white text-sm font-bold mb-3">
                                        {item.step}
                                    </div>
                                    <h4 className="text-sm font-medium text-white">{item.title}</h4>
                                    <p className="mt-1 text-xs text-gray-400">{item.desc}</p>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Local vs Kubernetes comparison */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/5 p-6">
                            <div className="flex items-center gap-2 mb-4">
                                <span className="text-xs font-semibold px-2 py-1 rounded bg-cyan-500/20 text-cyan-400">🖥️ Local Mode</span>
                                <span className="text-xs text-gray-500">Default</span>
                            </div>
                            <ul className="space-y-3 text-sm text-gray-300">
                                <li className="flex items-start gap-2">
                                    <span className="text-cyan-400 mt-0.5 shrink-0">•</span>
                                    Sub-agents run as <strong className="text-white">threads</strong> in the same process
                                </li>
                                <li className="flex items-start gap-2">
                                    <span className="text-cyan-400 mt-0.5 shrink-0">•</span>
                                    Shared filesystem — all agents work in the same directory
                                </li>
                                <li className="flex items-start gap-2">
                                    <span className="text-cyan-400 mt-0.5 shrink-0">•</span>
                                    Zero infrastructure — just run <code className="text-xs bg-gray-700 px-1 rounded text-cyan-400">codetether swarm</code>
                                </li>
                            </ul>
                            <div className="mt-4 rounded-lg bg-gray-900 p-3 font-mono text-xs">
                                <span className="text-cyan-400">$</span> <span className="text-gray-300">codetether swarm &quot;Implement auth with tests&quot;</span>
                            </div>
                        </div>

                        <div className="rounded-xl border border-purple-500/30 bg-purple-500/5 p-6">
                            <div className="flex items-center gap-2 mb-4">
                                <span className="text-xs font-semibold px-2 py-1 rounded bg-purple-500/20 text-purple-400">☸️ Kubernetes Mode</span>
                            </div>
                            <ul className="space-y-3 text-sm text-gray-300">
                                <li className="flex items-start gap-2">
                                    <span className="text-purple-400 mt-0.5 shrink-0">•</span>
                                    Sub-agents run as <strong className="text-white">isolated K8s pods</strong> with resource limits
                                </li>
                                <li className="flex items-start gap-2">
                                    <span className="text-purple-400 mt-0.5 shrink-0">•</span>
                                    Each pod gets its own environment and workspace clone
                                </li>
                                <li className="flex items-start gap-2">
                                    <span className="text-purple-400 mt-0.5 shrink-0">•</span>
                                    Vault env vars forwarded automatically to pods
                                </li>
                            </ul>
                            <div className="mt-4 rounded-lg bg-gray-900 p-3 font-mono text-xs">
                                <span className="text-cyan-400">$</span> <span className="text-gray-300">codetether swarm &quot;Ship feature X&quot; \</span><br />
                                <span className="text-gray-500 ml-4">--execution-mode k8s --k8s-pod-budget 6</span>
                            </div>
                        </div>
                    </div>

                    {/* K8s config */}
                    <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-6">
                        <h3 className="text-lg font-semibold text-white mb-4">Kubernetes Configuration</h3>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div>
                                <h4 className="text-sm font-semibold text-white mb-3">Flags</h4>
                                <div className="space-y-3">
                                    {[
                                        { flag: '--execution-mode k8s', desc: 'Enable Kubernetes pod execution' },
                                        { flag: '--k8s-pod-budget N', desc: 'Max concurrent speculative pods' },
                                        { flag: '--k8s-image <ref>', desc: 'Container image for sub-agent pods' },
                                    ].map(item => (
                                        <div key={item.flag}>
                                            <code className="text-xs font-mono text-cyan-400">{item.flag}</code>
                                            <p className="text-xs text-gray-400 mt-0.5">{item.desc}</p>
                                        </div>
                                    ))}
                                </div>
                            </div>
                            <div>
                                <h4 className="text-sm font-semibold text-white mb-3">Forwarded Env Vars</h4>
                                <div className="flex flex-wrap gap-2">
                                    {['VAULT_ADDR', 'VAULT_TOKEN', 'VAULT_MOUNT', 'VAULT_SECRETS_PATH', 'CODETETHER_AUTH_TOKEN'].map(v => (
                                        <code key={v} className="text-xs font-mono bg-gray-700 text-cyan-400 px-2 py-1 rounded">{v}</code>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
