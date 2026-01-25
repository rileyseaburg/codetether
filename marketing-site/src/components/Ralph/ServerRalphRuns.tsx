'use client'

import { useState, useCallback, useEffect } from 'react'
import { RalphRefreshIcon } from '../ui/RalphIcons'
import { listRalphRunsV1RalphRunsGet, cancelRalphRunV1RalphRunsRunIdCancelPost, deleteRalphRunV1RalphRunsRunIdDelete } from '@/lib/api'

export function ServerRalphRuns() {
    const [runs, setRuns] = useState<any[]>([])
    const [loading, setLoading] = useState(false)
    const [expanded, setExpanded] = useState<string | null>(null)

    const loadRuns = useCallback(async () => {
        setLoading(true)
        try { const { data } = await listRalphRunsV1RalphRunsGet({ query: { limit: 20 } }); if (data) setRuns(data) } finally { setLoading(false) }
    }, [])

    const handleCancel = useCallback(async (id: string) => { await cancelRalphRunV1RalphRunsRunIdCancelPost({ path: { run_id: id } }); loadRuns() }, [loadRuns])

    const handleDelete = useCallback(async (id: string) => { if (!confirm('Delete this Ralph run?')) return; await deleteRalphRunV1RalphRunsRunIdDelete({ path: { run_id: id } }); loadRuns() }, [loadRuns])

    useEffect(() => { loadRuns() }, [loadRuns])

    return (
        <div className="rounded-lg bg-white shadow-sm dark:bg-gray-800 dark:ring-1 dark:ring-white/10" data-cy="ralph-runs-panel">
            <div className="flex justify-between p-4 border-b">
                <h2 className="text-sm font-semibold">Ralph Run History</h2>
                <button onClick={loadRuns} disabled={loading} data-cy="ralph-refresh-btn">
                    <RalphRefreshIcon className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                </button>
            </div>
            {runs.length === 0 ? (
                <div className="p-8 text-center text-gray-500 text-sm" data-cy="ralph-no-runs">No Ralph runs yet</div>
            ) : (
                <div className="divide-y" data-cy="ralph-runs-list">
                    {runs.map((run) => {
                        const passed = run.story_results?.filter((r: any) => r.status === 'passed').length || 0
                        const total = run.prd?.user_stories?.length || 0
                        const isExpanded = expanded === run.id
                        return (
                            <div key={run.id} className="p-4" data-cy="ralph-run-item" data-run-id={run.id} data-run-status={run.status}>
                                <div className="flex items-center justify-between cursor-pointer" onClick={() => setExpanded(isExpanded ? null : run.id)}>
                                    <div className="flex items-center gap-3">
                                        <span className="text-lg" data-cy="ralph-run-icon">
                                            {run.status === 'completed' && passed === total ? '✅' : run.status === 'running' ? '⏳' : run.status === 'failed' ? '❌' : '○'}
                                        </span>
                                        <div>
                                            <div className="font-medium" data-cy="ralph-run-project">{run.prd?.project || 'Unknown'}</div>
                                            <div className="text-xs text-gray-500" data-cy="ralph-run-progress">{run.prd?.branch_name} • {passed}/{total}</div>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-3">
                                        <span className={`px-2 py-1 text-xs rounded ${run.status === 'completed' ? 'bg-emerald-100 text-emerald-700' : run.status === 'running' ? 'bg-blue-100 text-blue-700' : run.status === 'failed' ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-700'}`} data-cy="ralph-run-status">{run.status}</span>
                                        <span className="text-xs text-gray-500">{new Date(run.created_at).toLocaleString()}</span>
                                        <svg className={`w-4 h-4 text-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                                    </div>
                                </div>
                            </div>
                        )
                    })}
                </div>
            )}
        </div>
    )
}
