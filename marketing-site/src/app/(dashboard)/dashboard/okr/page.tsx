'use client'

import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { useTenantApi } from '@/hooks/useTenantApi'

interface KeyResult {
    id: string
    description: string
    progress: number
    status: 'not-started' | 'in-progress' | 'completed' | 'blocked'
}

interface OKR {
    id: string
    objective: string
    status: 'draft' | 'approved' | 'running' | 'completed' | 'denied'
    created_at?: string
    updated_at?: string
    key_results?: KeyResult[]
    run_id?: string
}

interface OKRStats {
    total: number
    by_status: Record<string, number>
    completion_rate?: number
}

interface OKRRun {
    id: string
    okr_id: string
    status: string
    started_at?: string
    completed_at?: string
    error?: string
}

function TargetIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
    )
}

function CheckCircleIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
    )
}

const statusColors: Record<string, string> = {
    draft: 'bg-yellow-500/20 text-yellow-400',
    approved: 'bg-blue-500/20 text-blue-400',
    running: 'bg-cyan-500/20 text-cyan-400',
    completed: 'bg-green-500/20 text-green-400',
    denied: 'bg-red-500/20 text-red-400',
    'not-started': 'bg-gray-500/20 text-gray-400',
    'in-progress': 'bg-cyan-500/20 text-cyan-400',
    blocked: 'bg-red-500/20 text-red-400',
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

export default function OKRPage() {
    const [activeTab, setActiveTab] = useState<'okrs' | 'create' | 'stats' | 'guide'>('okrs')
    const { tenantFetch, isAuthenticated, isLoading: authLoading, hasTenant } = useTenantApi()

    // Live data state
    const [okrs, setOkrs] = useState<OKR[]>([])
    const [stats, setStats] = useState<OKRStats | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [expandedOkr, setExpandedOkr] = useState<string | null>(null)
    const [runs, setRuns] = useState<Record<string, OKRRun[]>>({})

    // Create form state
    const [objective, setObjective] = useState('')
    const [creating, setCreating] = useState(false)
    const [createError, setCreateError] = useState<string | null>(null)
    const [createSuccess, setCreateSuccess] = useState(false)

    const fetchOkrs = useCallback(async () => {
        if (!hasTenant) return
        const { data, error: err } = await tenantFetch<OKR[]>('/v1/okr')
        if (err) {
            setError(err)
            return
        }
        setOkrs(Array.isArray(data) ? data : [])
        setError(null)
    }, [hasTenant, tenantFetch])

    const fetchStats = useCallback(async () => {
        if (!hasTenant) return
        const { data, error: err } = await tenantFetch<OKRStats>('/v1/okr/stats')
        if (err) {
            setError(err)
            return
        }
        if (data) setStats(data)
    }, [hasTenant, tenantFetch])

    const fetchRuns = useCallback(async (okrId: string) => {
        if (!hasTenant) return
        const { data } = await tenantFetch<OKRRun[]>(`/v1/okr/${encodeURIComponent(okrId)}/runs`)
        if (data && Array.isArray(data)) {
            setRuns(prev => ({ ...prev, [okrId]: data }))
        }
    }, [hasTenant, tenantFetch])

    const handleCreate = useCallback(async () => {
        if (!hasTenant) return
        if (!objective.trim()) return
        setCreating(true)
        setCreateError(null)
        setCreateSuccess(false)

        const { data, error: err } = await tenantFetch<OKR>('/v1/okr', {
            method: 'POST',
            body: JSON.stringify({ objective: objective.trim() }),
        })

        if (err) {
            setCreateError(err)
        } else if (data) {
            setCreateSuccess(true)
            setObjective('')
            fetchOkrs()
            fetchStats()
        }
        setCreating(false)
    }, [hasTenant, objective, tenantFetch, fetchOkrs, fetchStats])

    const handleApprove = useCallback(async (okrId: string) => {
        if (!hasTenant) return
        await tenantFetch(`/v1/okr/${encodeURIComponent(okrId)}`, {
            method: 'PUT',
            body: JSON.stringify({ status: 'approved' }),
        })
        fetchOkrs()
        fetchStats()
    }, [hasTenant, tenantFetch, fetchOkrs, fetchStats])

    const handleDeny = useCallback(async (okrId: string) => {
        if (!hasTenant) return
        await tenantFetch(`/v1/okr/${encodeURIComponent(okrId)}`, {
            method: 'PUT',
            body: JSON.stringify({ status: 'denied' }),
        })
        fetchOkrs()
        fetchStats()
    }, [hasTenant, tenantFetch, fetchOkrs, fetchStats])

    const handleStartRun = useCallback(async (okrId: string) => {
        if (!hasTenant) return
        await tenantFetch(`/v1/okr/${encodeURIComponent(okrId)}/runs`, { method: 'POST' })
        fetchOkrs()
        fetchRuns(okrId)
    }, [hasTenant, tenantFetch, fetchOkrs, fetchRuns])

    const handleDelete = useCallback(async (okrId: string) => {
        if (!hasTenant) return
        await tenantFetch(`/v1/okr/${encodeURIComponent(okrId)}`, { method: 'DELETE' })
        fetchOkrs()
        fetchStats()
    }, [hasTenant, tenantFetch, fetchOkrs, fetchStats])

    useEffect(() => {
        if (!isAuthenticated || !hasTenant) {
            setLoading(false)
            return
        }
        setLoading(true)
        Promise.all([fetchOkrs(), fetchStats()]).finally(() => setLoading(false))
        const interval = setInterval(() => { fetchOkrs(); fetchStats() }, 15000)
        return () => clearInterval(interval)
    }, [isAuthenticated, hasTenant, fetchOkrs, fetchStats])

    useEffect(() => {
        if (expandedOkr) fetchRuns(expandedOkr)
    }, [expandedOkr, fetchRuns])

    const draftCount = okrs.filter(o => o.status === 'draft').length
    const runningCount = okrs.filter(o => o.status === 'running').length
    const completedCount = okrs.filter(o => o.status === 'completed').length

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 dark:text-white">OKR-Driven Execution</h1>
                    <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                        Strategic execution with measurable outcomes. Use <code className="px-1.5 py-0.5 rounded bg-gray-700 text-cyan-400 text-xs">/go</code> for
                        approval-gated OKR workflows, or <code className="px-1.5 py-0.5 rounded bg-gray-700 text-cyan-400 text-xs">/autochat</code> for tactical fast-path.
                    </p>
                </div>
                {isAuthenticated && hasTenant && (
                    <button
                        onClick={() => { setLoading(true); Promise.all([fetchOkrs(), fetchStats()]).finally(() => setLoading(false)) }}
                        disabled={loading}
                        className="px-4 py-2 text-sm bg-cyan-600 text-white rounded-lg hover:bg-cyan-500 disabled:opacity-50"
                    >
                        {loading ? 'Refreshing...' : 'Refresh'}
                    </button>
                )}
            </div>

            {/* Stats bar — visible only for authenticated tenant users */}
            {isAuthenticated && !authLoading && hasTenant && (
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                    <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                        <div className="text-2xl font-bold text-gray-900 dark:text-white">{okrs.length}</div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">Total OKRs</div>
                    </div>
                    <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-yellow-200 dark:border-yellow-800">
                        <div className="text-2xl font-bold text-yellow-600">{draftCount}</div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">Drafts</div>
                    </div>
                    <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-cyan-200 dark:border-cyan-800">
                        <div className="text-2xl font-bold text-cyan-600">{runningCount}</div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">Running</div>
                    </div>
                    <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-green-200 dark:border-green-800">
                        <div className="text-2xl font-bold text-green-600">{completedCount}</div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">Completed</div>
                    </div>
                    {stats?.completion_rate !== undefined && (
                        <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-purple-200 dark:border-purple-800">
                            <div className="text-2xl font-bold text-purple-600">{Math.round(stats.completion_rate * 100)}%</div>
                            <div className="text-xs text-gray-500 dark:text-gray-400">Completion Rate</div>
                        </div>
                    )}
                </div>
            )}

            {isAuthenticated && !authLoading && !hasTenant && (
                <div className="rounded-xl border border-yellow-500/30 bg-yellow-500/5 p-6">
                    <h2 className="text-sm font-semibold text-yellow-300">Tenant Setup Required</h2>
                    <p className="mt-2 text-sm text-yellow-200/90">
                        OKRs are tenant-scoped. This account currently has no tenant context, so OKR APIs are unavailable.
                    </p>
                </div>
            )}

            {/* Tabs */}
            <div className="border-b border-gray-700">
                <nav className="flex gap-4">
                    {([
                        { key: 'okrs' as const, label: 'My OKRs' },
                        { key: 'create' as const, label: 'Create OKR' },
                        { key: 'stats' as const, label: 'Stats' },
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

            {activeTab === 'okrs' && (
                <div className="space-y-4">
                    {!isAuthenticated && !authLoading ? (
                        <div className="rounded-xl border border-yellow-500/30 bg-yellow-500/5 p-8 text-center">
                            <h3 className="text-lg font-semibold text-white mb-2">Sign in to view your OKRs</h3>
                            <p className="text-sm text-gray-400">Connect your account to see live OKR data from your workers.</p>
                        </div>
                    ) : loading && okrs.length === 0 ? (
                        <div className="flex items-center gap-2 text-gray-400 py-12 justify-center">
                            <div className="h-4 w-4 animate-spin rounded-full border-2 border-cyan-500 border-t-transparent" />
                            Loading OKRs...
                        </div>
                    ) : error ? (
                        <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-4 text-sm text-red-400">{error}</div>
                    ) : okrs.length === 0 ? (
                        <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-8 text-center">
                            <TargetIcon className="h-12 w-12 text-gray-600 mx-auto mb-3" />
                            <h3 className="text-lg font-semibold text-white mb-2">No OKRs yet</h3>
                            <p className="text-sm text-gray-400 mb-4">Create your first OKR or use <code className="text-xs bg-gray-700 text-cyan-400 px-1 rounded">/go</code> in the CLI.</p>
                            <button onClick={() => setActiveTab('create')} className="px-4 py-2 text-sm bg-cyan-600 text-white rounded-lg hover:bg-cyan-500">
                                Create OKR
                            </button>
                        </div>
                    ) : (
                        okrs.map(okr => (
                            <div key={okr.id} className="rounded-xl border border-gray-700 bg-gray-800/50 p-5">
                                <div className="flex items-start justify-between gap-4">
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-1">
                                            <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${statusColors[okr.status] || 'bg-gray-500/20 text-gray-400'}`}>
                                                {okr.status}
                                            </span>
                                            {okr.created_at && (
                                                <span className="text-xs text-gray-500">{formatTimeAgo(okr.created_at)}</span>
                                            )}
                                        </div>
                                        <h3 className="text-sm font-semibold text-white">{okr.objective}</h3>
                                        <p className="text-xs text-gray-500 font-mono mt-1">{okr.id}</p>
                                    </div>
                                    <div className="flex items-center gap-2 shrink-0">
                                        {okr.status === 'draft' && (
                                            <>
                                                <button onClick={() => handleApprove(okr.id)} className="px-3 py-1.5 text-xs font-medium bg-green-600 text-white rounded-md hover:bg-green-500">
                                                    Approve
                                                </button>
                                                <button onClick={() => handleDeny(okr.id)} className="px-3 py-1.5 text-xs font-medium bg-red-600 text-white rounded-md hover:bg-red-500">
                                                    Deny
                                                </button>
                                            </>
                                        )}
                                        {okr.status === 'approved' && (
                                            <button onClick={() => handleStartRun(okr.id)} className="px-3 py-1.5 text-xs font-medium bg-cyan-600 text-white rounded-md hover:bg-cyan-500">
                                                Start Run
                                            </button>
                                        )}
                                        <button onClick={() => handleDelete(okr.id)} className="px-2 py-1.5 text-xs text-gray-400 hover:text-red-400">
                                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                                        </button>
                                        <button onClick={() => setExpandedOkr(expandedOkr === okr.id ? null : okr.id)} className="text-gray-400 hover:text-gray-300">
                                            <svg className={`w-5 h-5 transition-transform ${expandedOkr === okr.id ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                            </svg>
                                        </button>
                                    </div>
                                </div>

                                {/* Key Results */}
                                {okr.key_results && okr.key_results.length > 0 && (
                                    <div className="mt-3 space-y-2">
                                        {okr.key_results.map(kr => (
                                            <div key={kr.id} className="flex items-center gap-3">
                                                <div className="flex-1 min-w-0">
                                                    <div className="flex items-center gap-2">
                                                        <span className={`px-1.5 py-0.5 text-[10px] rounded ${statusColors[kr.status] || 'bg-gray-500/20 text-gray-400'}`}>
                                                            {kr.status}
                                                        </span>
                                                        <span className="text-xs text-gray-300 truncate">{kr.description}</span>
                                                    </div>
                                                    <div className="mt-1 h-1.5 w-full bg-gray-700 rounded-full overflow-hidden">
                                                        <div className="h-full bg-cyan-500 rounded-full transition-all" style={{ width: `${Math.min(100, kr.progress)}%` }} />
                                                    </div>
                                                </div>
                                                <span className="text-xs text-gray-400 shrink-0">{kr.progress}%</span>
                                            </div>
                                        ))}
                                    </div>
                                )}

                                {/* Expanded: Runs */}
                                {expandedOkr === okr.id && (
                                    <div className="mt-4 pt-4 border-t border-gray-700">
                                        <h4 className="text-xs font-medium text-gray-400 mb-2">Runs</h4>
                                        {(runs[okr.id] || []).length === 0 ? (
                                            <p className="text-xs text-gray-500">No runs yet</p>
                                        ) : (
                                            <div className="space-y-2">
                                                {(runs[okr.id] || []).map(run => (
                                                    <div key={run.id} className="flex items-center gap-3 rounded-lg bg-gray-700/50 px-3 py-2">
                                                        <span className={`px-1.5 py-0.5 text-[10px] rounded ${statusColors[run.status] || 'bg-gray-500/20 text-gray-400'}`}>
                                                            {run.status}
                                                        </span>
                                                        <span className="text-xs text-gray-400 font-mono">{run.id.slice(0, 8)}</span>
                                                        {run.started_at && <span className="text-xs text-gray-500">{formatTimeAgo(run.started_at)}</span>}
                                                        {run.error && <span className="text-xs text-red-400 truncate">{run.error}</span>}
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                        ))
                    )}
                </div>
            )}

            {activeTab === 'create' && (
                <div className="max-w-2xl space-y-6">
                    {!isAuthenticated && !authLoading ? (
                        <div className="rounded-xl border border-yellow-500/30 bg-yellow-500/5 p-8 text-center">
                            <h3 className="text-lg font-semibold text-white mb-2">Sign in to create OKRs</h3>
                            <p className="text-sm text-gray-400">Connect your account to create and manage OKRs from the dashboard.</p>
                        </div>
                    ) : (
                        <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-6">
                            <h3 className="text-lg font-semibold text-white mb-2">Create an OKR</h3>
                            <p className="text-sm text-gray-400 mb-6">
                                Define your objective. The agent will generate measurable Key Results, then wait for your approval before executing.
                            </p>
                            <div className="space-y-4">
                                <div>
                                    <label className="block text-sm font-medium text-gray-300 mb-1">Objective</label>
                                    <textarea
                                        rows={3}
                                        value={objective}
                                        onChange={e => setObjective(e.target.value)}
                                        placeholder="e.g., Make the QR-to-booking pipeline production-ready for Q3 launch"
                                        className="w-full rounded-lg border border-gray-600 bg-gray-700 px-4 py-2.5 text-sm text-white placeholder-gray-400 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500"
                                    />
                                </div>
                                {createError && (
                                    <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-3 text-sm text-red-400">{createError}</div>
                                )}
                                {createSuccess && (
                                    <div className="rounded-lg border border-green-500/30 bg-green-500/5 p-3 text-sm text-green-400">
                                        OKR created successfully! Switch to the &quot;My OKRs&quot; tab to approve and run it.
                                    </div>
                                )}
                                <button
                                    onClick={handleCreate}
                                    disabled={creating || !objective.trim()}
                                    className="px-4 py-2.5 text-sm font-medium bg-cyan-600 text-white rounded-lg hover:bg-cyan-500 disabled:opacity-50"
                                >
                                    {creating ? 'Creating...' : 'Create OKR'}
                                </button>
                            </div>
                        </div>
                    )}

                    <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-6">
                        <h3 className="text-sm font-semibold text-white mb-2">Alternative: CLI / TUI</h3>
                        <div className="rounded bg-gray-900 p-3 font-mono text-xs text-gray-300">
                            <span className="text-cyan-400">$</span> codetether okr create<br />
                            <span className="text-gray-500"># or from the TUI:</span><br />
                            <span className="text-cyan-400">&gt;</span> /go Make the QR-to-booking pipeline production-ready
                        </div>
                    </div>
                </div>
            )}

            {activeTab === 'stats' && (
                <div className="space-y-6">
                    {!isAuthenticated && !authLoading ? (
                        <div className="rounded-xl border border-yellow-500/30 bg-yellow-500/5 p-8 text-center">
                            <h3 className="text-lg font-semibold text-white mb-2">Sign in to view stats</h3>
                            <p className="text-sm text-gray-400">Connect your account to see OKR aggregate statistics.</p>
                        </div>
                    ) : stats ? (
                        <>
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-6 text-center">
                                    <div className="text-3xl font-bold text-white">{stats.total}</div>
                                    <div className="text-sm text-gray-400 mt-1">Total OKRs</div>
                                </div>
                                {stats.completion_rate !== undefined && (
                                    <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-6 text-center">
                                        <div className="text-3xl font-bold text-green-400">{Math.round(stats.completion_rate * 100)}%</div>
                                        <div className="text-sm text-gray-400 mt-1">Completion Rate</div>
                                    </div>
                                )}
                                <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-6 text-center">
                                    <div className="text-3xl font-bold text-cyan-400">{stats.by_status?.running || 0}</div>
                                    <div className="text-sm text-gray-400 mt-1">Currently Running</div>
                                </div>
                            </div>

                            {/* Status breakdown */}
                            {stats.by_status && Object.keys(stats.by_status).length > 0 && (
                                <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-6">
                                    <h3 className="text-lg font-semibold text-white mb-4">Status Breakdown</h3>
                                    <div className="space-y-3">
                                        {Object.entries(stats.by_status).map(([status, count]) => (
                                            <div key={status} className="flex items-center gap-3">
                                                <span className={`px-2 py-0.5 text-xs font-medium rounded-full w-24 text-center ${statusColors[status] || 'bg-gray-500/20 text-gray-400'}`}>
                                                    {status}
                                                </span>
                                                <div className="flex-1 h-2 bg-gray-700 rounded-full overflow-hidden">
                                                    <div
                                                        className="h-full bg-cyan-500 rounded-full"
                                                        style={{ width: `${stats.total ? (count / stats.total) * 100 : 0}%` }}
                                                    />
                                                </div>
                                                <span className="text-sm text-gray-300 w-8 text-right">{count}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </>
                    ) : loading ? (
                        <div className="flex items-center gap-2 text-gray-400 py-12 justify-center">
                            <div className="h-4 w-4 animate-spin rounded-full border-2 border-cyan-500 border-t-transparent" />
                            Loading stats...
                        </div>
                    ) : (
                        <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-8 text-center">
                            <p className="text-sm text-gray-400">No stats available yet. Create your first OKR to get started.</p>
                        </div>
                    )}
                </div>
            )}

            {activeTab === 'guide' && (
                <div className="space-y-8">
                    {/* /go vs /autochat comparison */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/5 p-6">
                            <div className="flex items-center gap-3 mb-4">
                                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-cyan-500/20">
                                    <TargetIcon className="h-6 w-6 text-cyan-400" />
                                </div>
                                <div>
                                    <h3 className="text-lg font-semibold text-white">/go — Strategic Execution</h3>
                                    <span className="text-xs text-cyan-400">OKR-gated, approval required</span>
                                </div>
                            </div>
                            <ul className="space-y-2 text-sm text-gray-300">
                                <li className="flex items-start gap-2">
                                    <CheckCircleIcon className="h-4 w-4 text-cyan-400 mt-0.5 shrink-0" />
                                    Draft → Approve/Deny → Run lifecycle
                                </li>
                                <li className="flex items-start gap-2">
                                    <CheckCircleIcon className="h-4 w-4 text-cyan-400 mt-0.5 shrink-0" />
                                    Measurable Key Results with progress tracking
                                </li>
                                <li className="flex items-start gap-2">
                                    <CheckCircleIcon className="h-4 w-4 text-cyan-400 mt-0.5 shrink-0" />
                                    Relay checkpointing for crash recovery
                                </li>
                                <li className="flex items-start gap-2">
                                    <CheckCircleIcon className="h-4 w-4 text-cyan-400 mt-0.5 shrink-0" />
                                    Full audit trail with correlation IDs
                                </li>
                            </ul>
                            <div className="mt-4 rounded-lg bg-gray-800 p-3 font-mono text-xs text-gray-300">
                                <span className="text-cyan-400">$</span> codetether run &quot;/go audit the billing system for Q3 readiness&quot;
                            </div>
                        </div>

                        <div className="rounded-xl border border-orange-500/30 bg-orange-500/5 p-6">
                            <div className="flex items-center gap-3 mb-4">
                                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-orange-500/20">
                                    <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" className="h-6 w-6 text-orange-400">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                                    </svg>
                                </div>
                                <div>
                                    <h3 className="text-lg font-semibold text-white">/autochat — Tactical Execution</h3>
                                    <span className="text-xs text-orange-400">Immediate, no approval gate</span>
                                </div>
                            </div>
                            <ul className="space-y-2 text-sm text-gray-300">
                                <li className="flex items-start gap-2">
                                    <CheckCircleIcon className="h-4 w-4 text-orange-400 mt-0.5 shrink-0" />
                                    Runs immediately — no draft/approve step
                                </li>
                                <li className="flex items-start gap-2">
                                    <CheckCircleIcon className="h-4 w-4 text-orange-400 mt-0.5 shrink-0" />
                                    Same relay execution engine underneath
                                </li>
                                <li className="flex items-start gap-2">
                                    <CheckCircleIcon className="h-4 w-4 text-orange-400 mt-0.5 shrink-0" />
                                    Best for quick tasks, bug fixes, direct orders
                                </li>
                                <li className="flex items-start gap-2">
                                    <CheckCircleIcon className="h-4 w-4 text-orange-400 mt-0.5 shrink-0" />
                                    No OKR lifecycle overhead
                                </li>
                            </ul>
                            <div className="mt-4 rounded-lg bg-gray-800 p-3 font-mono text-xs text-gray-300">
                                <span className="text-cyan-400">$</span> codetether run &quot;/autochat fix the login page redirect bug&quot;
                            </div>
                        </div>
                    </div>

                    {/* Lifecycle diagram */}
                    <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-6">
                        <h3 className="text-lg font-semibold text-white mb-4">The /go Lifecycle</h3>
                        <div className="flex flex-wrap items-center gap-3 text-sm">
                            {[
                                { step: '1', label: 'State Intent', color: 'bg-gray-600' },
                                { step: '2', label: 'System Reframes as OKR', color: 'bg-blue-600' },
                                { step: '3', label: 'Approve / Deny', color: 'bg-yellow-600' },
                                { step: '4', label: 'Autonomous Execution', color: 'bg-cyan-600' },
                                { step: '5', label: 'KR Progress Updates', color: 'bg-purple-600' },
                                { step: '6', label: 'Completion + Outcome', color: 'bg-green-600' },
                            ].map((item, i) => (
                                <div key={item.step} className="flex items-center gap-2">
                                    <div className={`flex h-7 w-7 items-center justify-center rounded-full ${item.color} text-white text-xs font-bold`}>
                                        {item.step}
                                    </div>
                                    <span className="text-gray-300">{item.label}</span>
                                    {i < 5 && <span className="text-gray-600 mx-1">→</span>}
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* CLI Reference */}
                    <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-6">
                        <h3 className="text-lg font-semibold text-white mb-4">OKR CLI Commands</h3>
                        <div className="space-y-3 font-mono text-sm">
                            {[
                                { cmd: 'codetether okr list', desc: 'List all OKRs and their status' },
                                { cmd: 'codetether okr status --id <uuid>', desc: 'Detailed status of a specific OKR' },
                                { cmd: 'codetether okr create', desc: 'Create a new OKR interactively' },
                                { cmd: 'codetether okr runs --id <uuid>', desc: 'List runs for an OKR' },
                                { cmd: 'codetether okr stats', desc: 'Aggregate stats across all OKRs' },
                            ].map(item => (
                                <div key={item.cmd} className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-4 rounded-lg bg-gray-700/50 px-4 py-3">
                                    <code className="text-cyan-400 shrink-0">{item.cmd}</code>
                                    <span className="text-gray-400 text-xs">{item.desc}</span>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Deployment context */}
                    <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-6">
                        <h3 className="text-lg font-semibold text-white mb-3">Where OKRs Run</h3>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="rounded-lg bg-gray-700/50 p-4">
                                <span className="text-xs font-semibold px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-400">🖥️ Local</span>
                                <p className="mt-2 text-sm text-gray-300">
                                    Use <code className="text-xs bg-gray-700 text-cyan-400 px-1 rounded">/go</code> in the TUI — the agent
                                    creates Key Results, you approve, and it executes locally using thread-based swarm.
                                </p>
                            </div>
                            <div className="rounded-lg bg-gray-700/50 p-4">
                                <span className="text-xs font-semibold px-2 py-0.5 rounded bg-purple-500/20 text-purple-400">☸️ Kubernetes</span>
                                <p className="mt-2 text-sm text-gray-300">
                                    OKR tasks dispatched to K8s workers via the A2A server. Workers pick up approved OKRs
                                    and execute with pod-based swarm agents.
                                </p>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
