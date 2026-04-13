'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { useSession } from 'next-auth/react'
import { useRalphStore } from '@/app/(dashboard)/dashboard/ralph/store'
import {
    listAllTasksV1AgentTasksGet,
    resumeSessionV1AgentWorkspacesWorkspaceIdSessionsSessionIdResumePost,
    createRalphRunV1RalphRunsPost,
    hasApiAuthToken,
} from '@/lib/api'

interface RecentSession {
    id: string
    title: string
    workspace_id: string
    workspace_name: string
    updated_at?: string
}

interface Props {
    activeWorkspaceId?: string
    workspaces?: Array<{ id: string; name: string }>
    selectedModel?: string
    onActionNotification?: (n: { type: 'success' | 'error' | 'warning'; message: string; detail?: string }) => void
}

export function CodeTetherCommands({ activeWorkspaceId, workspaces = [], selectedModel, onActionNotification }: Props) {
    const router = useRouter()
    const { data: session } = useSession()
    const { setSelectedCodebase } = useRalphStore()

    const [recentSessions, setRecentSessions] = useState<RecentSession[]>([])
    const [selectedSessionId, setSelectedSessionId] = useState('')
    const [resumePrompt, setResumePrompt] = useState('')
    const [resuming, setResuming] = useState(false)

    const [ralphTask, setRalphTask] = useState('')
    const [ralphWorkspace, setRalphWorkspace] = useState(activeWorkspaceId || '')
    const [ralphRunning, setRalphRunning] = useState(false)

    const [activeTab, setActiveTab] = useState<'resume' | 'ralph'>('resume')

    // Sync workspace selector with parent
    useEffect(() => {
        if (activeWorkspaceId && !ralphWorkspace) {
            setRalphWorkspace(activeWorkspaceId)
        }
    }, [activeWorkspaceId, ralphWorkspace])

    const loadRecentSessions = useCallback(async () => {
        if (!activeWorkspaceId) return
        try {
            const { data } = await listAllTasksV1AgentTasksGet({
                query: { workspace_id: activeWorkspaceId },
            })
            if (!data) return
            const tasks = Array.isArray(data) ? data : (data as any)?.tasks ?? []
            const sessions: RecentSession[] = []
            const seen = new Set<string>()
            for (const task of tasks) {
                const meta = task?.metadata ?? {}
                const sid = meta?.resume_session_id || meta?.session_id || task?.session_id
                if (!sid || seen.has(sid)) continue
                seen.add(sid)
                sessions.push({
                    id: sid,
                    title: task?.title || sid.slice(0, 8),
                    workspace_id: activeWorkspaceId,
                    workspace_name: workspaces.find(w => w.id === activeWorkspaceId)?.name || activeWorkspaceId,
                    updated_at: task?.updated_at || task?.created_at,
                })
                if (sessions.length >= 10) break
            }
            setRecentSessions(sessions)
            if (sessions.length > 0 && !selectedSessionId) {
                setSelectedSessionId(sessions[0].id)
            }
        } catch {
            // ignore
        }
    }, [activeWorkspaceId, workspaces, selectedSessionId])

    useEffect(() => {
        if (!session?.accessToken && !hasApiAuthToken()) return
        loadRecentSessions()
    }, [loadRecentSessions, session?.accessToken])

    const handleResume = async () => {
        if (!selectedSessionId || !activeWorkspaceId) return
        setResuming(true)
        try {
            const { data, error } = await resumeSessionV1AgentWorkspacesWorkspaceIdSessionsSessionIdResumePost({
                path: { workspace_id: activeWorkspaceId, session_id: selectedSessionId },
                body: {
                    prompt: resumePrompt.trim() || undefined,
                    agent: 'build',
                    ...(selectedModel ? { model: selectedModel, model_ref: selectedModel } : {}),
                },
            })
            if (error) {
                onActionNotification?.({ type: 'error', message: 'Resume failed', detail: String(error) })
                return
            }
            onActionNotification?.({ type: 'success', message: 'Session resumed', detail: 'Task dispatched to worker.' })
            setResumePrompt('')
            setSelectedCodebase(activeWorkspaceId)
            router.push(`/dashboard/sessions?workspace=${encodeURIComponent(activeWorkspaceId)}`)
        } finally {
            setResuming(false)
        }
    }

    const handleRalphRun = async () => {
        const task = ralphTask.trim()
        if (!task) return
        const wsId = ralphWorkspace || activeWorkspaceId
        if (!wsId) {
            onActionNotification?.({ type: 'warning', message: 'Select a workspace first' })
            return
        }
        setRalphRunning(true)
        try {
            // Build a minimal single-story PRD from the free-text task
            const storyId = `US-${Date.now().toString().slice(-6)}`
            const prd = {
                project: 'quick-task',
                branchName: `ralph/task-${storyId.toLowerCase()}`,
                description: task,
                userStories: [
                    {
                        id: storyId,
                        title: task.slice(0, 80),
                        description: task,
                        acceptanceCriteria: ['Task completed successfully'],
                        priority: 1,
                        passes: false,
                    },
                ],
            }
            const { data, error } = await createRalphRunV1RalphRunsPost({
                body: {
                    prd,
                    codebase_id: wsId,
                    ...(selectedModel ? { model: selectedModel } : {}),
                    max_iterations: 5,
                    run_mode: 'sequential',
                    max_parallel: 1,
                },
            })
            if (error) {
                onActionNotification?.({ type: 'error', message: 'Ralph run failed to start', detail: String(error) })
                return
            }
            onActionNotification?.({ type: 'success', message: 'Ralph run started', detail: 'Go to the Ralph tab to monitor progress.' })
            setRalphTask('')
            router.push('/dashboard/ralph')
        } finally {
            setRalphRunning(false)
        }
    }

    return (
        <div className="rounded-lg bg-white shadow-sm dark:bg-gray-800 dark:ring-1 dark:ring-white/10">
            <div className="border-b border-gray-200 dark:border-gray-700 p-4">
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">CodeTether Commands</h2>
                <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">Quick access to resume and Ralph</p>
            </div>

            {/* Tab bar */}
            <div className="flex border-b border-gray-200 dark:border-gray-700">
                <button
                    onClick={() => setActiveTab('resume')}
                    className={`flex-1 py-2.5 text-sm font-medium ${activeTab === 'resume'
                        ? 'border-b-2 border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400'
                        : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
                        }`}
                    data-cy="codetether-tab-resume"
                >
                    ↩ Resume
                </button>
                <button
                    onClick={() => setActiveTab('ralph')}
                    className={`flex-1 py-2.5 text-sm font-medium ${activeTab === 'ralph'
                        ? 'border-b-2 border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400'
                        : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
                        }`}
                    data-cy="codetether-tab-ralph"
                >
                    ⚡ Ralph
                </button>
            </div>

            <div className="p-4 space-y-3">
                {activeTab === 'resume' && (
                    <>
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                            Pick a recent session and optionally add a follow-up prompt. The worker will reload context and continue.
                        </p>
                        {recentSessions.length === 0 ? (
                            <p className="text-xs italic text-gray-400 dark:text-gray-500">
                                {activeWorkspaceId ? 'No sessions found for this workspace.' : 'Select a workspace to see recent sessions.'}
                            </p>
                        ) : (
                            <select
                                value={selectedSessionId}
                                onChange={e => setSelectedSessionId(e.target.value)}
                                className="w-full rounded-md border-gray-300 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                                data-cy="resume-session-select"
                            >
                                {recentSessions.map(s => (
                                    <option key={s.id} value={s.id}>
                                        {s.title} – {s.id.slice(0, 8)}
                                    </option>
                                ))}
                            </select>
                        )}
                        <textarea
                            value={resumePrompt}
                            onChange={e => setResumePrompt(e.target.value)}
                            placeholder="Optional follow-up prompt..."
                            rows={2}
                            className="w-full rounded-md border-gray-300 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500 placeholder-gray-400"
                            data-cy="resume-prompt-input"
                            onKeyDown={e => {
                                if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                                    e.preventDefault()
                                    void handleResume()
                                }
                            }}
                        />
                        <button
                            onClick={handleResume}
                            disabled={resuming || !selectedSessionId || !activeWorkspaceId}
                            className="w-full rounded-md bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
                            data-cy="resume-session-btn"
                        >
                            {resuming ? 'Resuming…' : '↩ Resume Session'}
                        </button>
                        <button
                            onClick={() => router.push(`/dashboard/sessions${activeWorkspaceId ? `?workspace=${encodeURIComponent(activeWorkspaceId)}` : ''}`)}
                            className="w-full rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-700"
                            data-cy="open-sessions-btn"
                        >
                            Open Sessions →
                        </button>
                    </>
                )}

                {activeTab === 'ralph' && (
                    <>
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                            Describe a task. Ralph will build a one-story PRD and run the autonomous development loop.
                        </p>
                        {workspaces.length > 1 && (
                            <select
                                value={ralphWorkspace}
                                onChange={e => setRalphWorkspace(e.target.value)}
                                className="w-full rounded-md border-gray-300 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                                data-cy="ralph-workspace-select"
                            >
                                <option value="">Select workspace…</option>
                                {workspaces.map(w => (
                                    <option key={w.id} value={w.id}>{w.name}</option>
                                ))}
                            </select>
                        )}
                        <textarea
                            value={ralphTask}
                            onChange={e => setRalphTask(e.target.value)}
                            placeholder="e.g. Add pagination to the user list endpoint"
                            rows={3}
                            className="w-full rounded-md border-gray-300 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500 placeholder-gray-400"
                            data-cy="ralph-task-input"
                            onKeyDown={e => {
                                if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                                    e.preventDefault()
                                    void handleRalphRun()
                                }
                            }}
                        />
                        <button
                            onClick={handleRalphRun}
                            disabled={ralphRunning || !ralphTask.trim()}
                            className="w-full rounded-md bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed"
                            data-cy="ralph-quick-run-btn"
                        >
                            {ralphRunning ? 'Starting…' : '⚡ Run Ralph'}
                        </button>
                        <button
                            onClick={() => router.push('/dashboard/ralph')}
                            className="w-full rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-700"
                            data-cy="open-ralph-btn"
                        >
                            Open Ralph Dashboard →
                        </button>
                    </>
                )}
            </div>
        </div>
    )
}
