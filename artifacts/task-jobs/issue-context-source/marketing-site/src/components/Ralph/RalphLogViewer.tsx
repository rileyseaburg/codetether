'use client'

import { useRef, useEffect } from 'react'
import type { RalphLogEntry, RalphRun, PRD } from '@/app/(dashboard)/dashboard/ralph/store'

interface RalphLogViewerProps { run: RalphRun | null; prd: PRD | null; isRunning: boolean; maxIterations: number }

export function RalphLogViewer({ run, prd, isRunning, maxIterations }: RalphLogViewerProps) {
    const logsRef = useRef<HTMLDivElement>(null)
    useEffect(() => { if (logsRef.current) logsRef.current.scrollTop = logsRef.current.scrollHeight }, [run?.logs])
    
    const getLogInfo = (type: RalphLogEntry['type']) => {
        const info: Record<string, { color: string; icon: string }> = {
            story_pass: { color: 'text-emerald-400', icon: '✅' }, story_fail: { color: 'text-red-400', icon: '❌' },
            error: { color: 'text-red-400', icon: '⚠️' }, rlm: { color: 'text-pink-400', icon: '🗜️' },
            complete: { color: 'text-emerald-400', icon: '🎉' }, story_start: { color: 'text-yellow-400', icon: '📋' },
            code: { color: 'text-cyan-400', icon: '💻' }, commit: { color: 'text-purple-400', icon: '📦' },
            check: { color: 'text-green-400', icon: '✓' }, tool: { color: 'text-blue-400', icon: '🔧' },
            ai: { color: 'text-indigo-400', icon: '🤖' }, waiting: { color: 'text-gray-500', icon: '⏳' }
        }
        return info[type] || { color: 'text-gray-400', icon: '→' }
    }

    return (
        <div className="rounded-lg bg-gray-900 shadow-sm overflow-hidden h-full flex flex-col" data-cy="ralph-log-viewer">
            <div className="flex items-center justify-between px-4 py-3 bg-gray-800 border-b border-gray-700">
                <div className="flex items-center gap-2">
                    <div className="flex gap-1.5"><div className="h-3 w-3 rounded-full bg-red-500" /><div className="h-3 w-3 rounded-full bg-yellow-500" /><div className="h-3 w-3 rounded-full bg-green-500" /></div>
                    <span className="ml-3 text-sm text-gray-400 font-mono" data-cy="ralph-log-title">Ralph + RLM Loop{prd && ` — ${prd.project}`}</span>
                </div>
                <div className="flex items-center gap-4">
                    {isRunning && <div className="flex items-center gap-2 text-xs text-purple-400" data-cy="ralph-running-indicator"><div className="h-2 w-2 rounded-full bg-purple-500 animate-pulse" />Running {run?.currentIteration || 0}/{maxIterations}</div>}
                    {run && !isRunning && <span className={`text-xs px-2 py-1 rounded ${run.status === 'completed' ? 'bg-emerald-100 text-emerald-700' : run.status === 'running' ? 'bg-blue-100 text-blue-700' : run.status === 'failed' ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-700'}`} data-cy="ralph-status-badge">{run.status}</span>}
                </div>
            </div>
            <div ref={logsRef} className="flex-1 overflow-y-auto p-4 min-h-[400px] max-h-[600px]" data-cy="ralph-log-container">
                {!run ? (
                    <div className="flex flex-col items-center justify-center h-full text-gray-500 text-sm" data-cy="ralph-empty-state">
                        <p>Paste prd.json and click "Start Ralph"</p>
                    </div>
                ) : run.logs.map((log) => {
                    const { color, icon } = getLogInfo(log.type)
                    return (
                        <div key={log.id} className="flex gap-2 py-1 font-mono text-xs" data-cy="ralph-log-entry" data-log-type={log.type}>
                            <span className="text-gray-600 shrink-0">{new Date(log.timestamp).toLocaleTimeString()}</span>
                            <span className={color}>{icon}</span>
                            <span className={color}>{log.storyId && <span className="text-gray-500">[{log.storyId}] </span>}{log.message}</span>
                        </div>
                    )
                })}
                {isRunning && <div className="flex items-center gap-2 py-2 text-purple-400 text-xs font-mono" data-cy="ralph-streaming-indicator"><div className="flex gap-1"><span className="h-2 w-2 rounded-full bg-purple-500 animate-pulse" /></div><span>Live streaming...</span></div>}
            </div>
        </div>
    )
}
