'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { useCodebases } from '../sessions/hooks/useCodebases'
import { getTaskOutputV1AgentTasksTaskIdOutputGet, listAllTasksV1AgentTasksGet } from '@/lib/api'
import { useTenantApi } from '@/hooks/useTenantApi'

interface Task {
    id: string
    title?: string
    prompt?: string
    agent_type: string
    status: string
    created_at: string
    result?: string
    codebase_id?: string
    priority?: number
    started_at?: string
    completed_at?: string
    error?: string
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
    error?: string
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
        recentLines: [...state.recentLines, trimmed].slice(-180),
    }

    const startedMatch = trimmed.match(/started\b.*planned_subtasks=(\d+)/i)
    if (startedMatch) {
        const planned = Number(startedMatch[1])
        next.status = 'running'
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

const isSwarmTask = (task?: Task | null) => {
    if (!task?.agent_type) return false
    const normalized = task.agent_type.toLowerCase()
    return normalized === 'swarm' || normalized === 'parallel' || normalized === 'multi-agent'
}

function ClipboardIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
        </svg>
    )
}

export default function TasksPage() {
    const [tasks, setTasks] = useState<Task[]>([])
    const [filter, setFilter] = useState('all')
    const [selectedTask, setSelectedTask] = useState<Task | null>(null)
    const { codebases } = useCodebases()
    const { apiUrl } = useTenantApi()
    const [selectedCodebase, setSelectedCodebase] = useState<string>('all')
    const [taskSwarmMonitors, setTaskSwarmMonitors] = useState<Record<string, SwarmMonitorState>>({})
    const taskStreamRef = useRef<EventSource | null>(null)

    const updateTaskSwarmMonitor = useCallback((taskId: string, updater: (prev: SwarmMonitorState) => SwarmMonitorState) => {
        setTaskSwarmMonitors((prev) => ({
            ...prev,
            [taskId]: updater(prev[taskId] ?? INITIAL_SWARM_MONITOR),
        }))
    }, [])

    const ingestSwarmLineForTask = useCallback((taskId: string, line: string) => {
        if (!line.trim()) return
        updateTaskSwarmMonitor(taskId, (prev) => applySwarmLine(prev, line))
    }, [updateTaskSwarmMonitor])

    const ingestTaskOutputPayload = useCallback((taskId: string, payload: unknown) => {
        const ingestText = (text: string) => {
            text
                .split(/\r?\n/)
                .map((line) => line.trim())
                .filter(Boolean)
                .forEach((line) => ingestSwarmLineForTask(taskId, line))
        }

        if (typeof payload === 'string') {
            ingestText(payload)
            return
        }

        if (payload && typeof payload === 'object') {
            const event = payload as Record<string, unknown>
            const output = typeof event.output === 'string'
                ? event.output
                : typeof event.content === 'string'
                    ? event.content
                    : typeof event.message === 'string'
                        ? event.message
                        : undefined
            if (output) {
                ingestText(output)
            }
        }
    }, [ingestSwarmLineForTask])

    const loadTasks = useCallback(async () => {
        try {
            const { data, error } = await listAllTasksV1AgentTasksGet()
            if (!error && data) {
                const response = data as any
                const nextTasks: Task[] = Array.isArray(response) ? response : (response?.tasks ?? [])
                setTasks(nextTasks)
                setSelectedTask((current) => {
                    if (!current) return current
                    return nextTasks.find((task) => task.id === current.id) ?? current
                })
            }
        } catch (error) {
            console.error('Failed to load tasks:', error)
        }
    }, [])

    useEffect(() => {
        loadTasks()
        const interval = setInterval(loadTasks, 5000)
        return () => clearInterval(interval)
    }, [loadTasks])

    const selectedTaskId = selectedTask?.id ?? null
    const selectedTaskStatus = selectedTask?.status ?? null
    const selectedTaskAgentType = selectedTask?.agent_type ?? null

    useEffect(() => {
        if (taskStreamRef.current) {
            taskStreamRef.current.close()
            taskStreamRef.current = null
        }

        if (!selectedTaskId || !selectedTaskAgentType) {
            return
        }

        const normalizedAgentType = selectedTaskAgentType.toLowerCase()
        if (normalizedAgentType !== 'swarm' && normalizedAgentType !== 'parallel' && normalizedAgentType !== 'multi-agent') {
            return
        }

        const taskId = selectedTaskId
        updateTaskSwarmMonitor(taskId, (prev) => ({ ...prev, connected: false }))

        let cancelled = false

        const hydrateFromCurrentOutput = async () => {
            try {
                const { data, error } = await getTaskOutputV1AgentTasksTaskIdOutputGet({
                    path: { task_id: taskId },
                })
                if (cancelled || error || !data) return

                const response = data as any
                const outputs = Array.isArray(response?.outputs) ? response.outputs : []
                for (const chunk of outputs) {
                    ingestTaskOutputPayload(taskId, chunk)
                }
            } catch (error) {
                console.error('Failed to hydrate task output stream:', error)
            }
        }

        hydrateFromCurrentOutput()

        const isActive = selectedTaskStatus === 'pending' || selectedTaskStatus === 'running'
        if (!isActive) {
            return () => {
                cancelled = true
            }
        }

        const baseUrl = apiUrl.replace(/\/+$/, '')
        const eventSource = new EventSource(
            `${baseUrl}/v1/agent/tasks/${encodeURIComponent(taskId)}/output/stream`
        )
        taskStreamRef.current = eventSource

        eventSource.onopen = () => {
            updateTaskSwarmMonitor(taskId, (prev) => ({ ...prev, connected: true }))
        }

        eventSource.onerror = () => {
            updateTaskSwarmMonitor(taskId, (prev) => ({ ...prev, connected: false }))
        }

        eventSource.addEventListener('output', (rawEvent) => {
            const event = rawEvent as MessageEvent<string>
            if (!event.data) return
            try {
                ingestTaskOutputPayload(taskId, JSON.parse(event.data))
            } catch {
                ingestTaskOutputPayload(taskId, event.data)
            }
        })

        eventSource.addEventListener('done', (rawEvent) => {
            const event = rawEvent as MessageEvent<string>
            let status = selectedTaskStatus ?? 'completed'
            if (event.data) {
                try {
                    const done = JSON.parse(event.data) as { status?: string }
                    if (done?.status) {
                        status = done.status
                    }
                } catch {
                    // ignore parse errors for done payload
                }
            }
            updateTaskSwarmMonitor(taskId, (prev) => ({
                ...prev,
                connected: false,
                status: status === 'failed' ? 'failed' : 'completed',
            }))
        })

        return () => {
            cancelled = true
            eventSource.close()
            if (taskStreamRef.current === eventSource) {
                taskStreamRef.current = null
            }
        }
    }, [apiUrl, ingestTaskOutputPayload, selectedTaskAgentType, selectedTaskId, selectedTaskStatus, updateTaskSwarmMonitor])

    const filteredTasks = tasks.filter((task: Task) => {
        const statusMatch = filter === 'all' || task.status === filter
        const codebaseMatch = selectedCodebase === 'all' || task.codebase_id === selectedCodebase
        return statusMatch && codebaseMatch
    })

    const getStatusClasses = (status: string) => {
        const classes: Record<string, string> = {
            pending: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300',
            running: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300',
            completed: 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300',
            failed: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300',
        }
        return classes[status] || classes.pending
    }

    const getPriorityBadge = (priority?: number) => {
        switch (priority) {
            case 4: return <span className="px-2 py-1 text-xs rounded-full bg-red-100 text-red-800">Urgent</span>
            case 3: return <span className="px-2 py-1 text-xs rounded-full bg-orange-100 text-orange-800">High</span>
            case 1: return <span className="px-2 py-1 text-xs rounded-full bg-blue-100 text-blue-800">Low</span>
            default: return <span className="px-2 py-1 text-xs rounded-full bg-gray-100 text-gray-800">Normal</span>
        }
    }

    const parseTaskResult = (result: string) => {
        try {
            const lines = result.split('\n').filter(l => l.trim())
            const output: string[] = []
            for (const line of lines) {
                try {
                    const event = JSON.parse(line)
                    if (event.type === 'text' && event.part?.text) {
                        output.push(event.part.text)
                    } else if (event.type === 'tool_use') {
                        output.push(`[Tool: ${event.part?.tool}] ${event.part?.state?.output || ''}`)
                    }
                } catch {
                    output.push(line)
                }
            }
            return output.join('\n\n')
        } catch {
            return result
        }
    }

    const selectedTaskSwarmMonitor = selectedTask ? taskSwarmMonitors[selectedTask.id] : undefined
    const showSwarmMonitor = isSwarmTask(selectedTask) || Boolean(selectedTaskSwarmMonitor?.recentLines.length)
    const swarmSubtasks = selectedTaskSwarmMonitor
        ? Object.values(selectedTaskSwarmMonitor.subtasks).sort((a, b) => b.updatedAt - a.updatedAt)
        : []
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
    const recentSwarmLines = selectedTaskSwarmMonitor?.recentLines.slice(-20) ?? []

    return (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            {/* Task List */}
            <div className="lg:col-span-2">
                <div className="rounded-lg bg-white shadow-sm dark:bg-gray-800 dark:ring-1 dark:ring-white/10">
                    <div className="p-4 border-b border-gray-200 dark:border-gray-700">
                        <div className="flex items-center justify-between">
                            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Task Queue</h2>
                            <div className="flex gap-2">
                                <select
                                    value={selectedCodebase}
                                    onChange={(e) => setSelectedCodebase(e.target.value)}
                                    className="px-3 py-2 border rounded-lg text-sm"
                                >
                                    <option value="all">All Codebases</option>
                                    {codebases.map((cb: any) => (
                                        <option key={cb.id} value={cb.id}>{cb.name}</option>
                                    ))}
                                </select>
                                {['all', 'pending', 'running', 'completed'].map((f) => (
                                    <button
                                        key={f}
                                        onClick={() => setFilter(f)}
                                        className={`rounded-md px-3 py-1 text-xs font-medium ${filter === f
                                            ? 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900 dark:text-indigo-300'
                                            : 'text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-700'
                                            }`}
                                    >
                                        {f.charAt(0).toUpperCase() + f.slice(1)}
                                    </button>
                                ))}
                            </div>
                        </div>
                    </div>
                    <div className="divide-y divide-gray-200 dark:divide-gray-700 max-h-[calc(100vh-300px)] overflow-y-auto">
                        {filteredTasks.length === 0 ? (
                            <div className="p-8 text-center text-gray-500 dark:text-gray-400">
                                <ClipboardIcon className="mx-auto h-12 w-12 text-gray-400" />
                                <p className="mt-2 text-sm">No tasks found</p>
                            </div>
                        ) : (
                            filteredTasks.map((task) => (
                                <div
                                    key={task.id}
                                    className="p-4 hover:bg-gray-50 dark:hover:bg-gray-700/50 cursor-pointer"
                                    onClick={() => setSelectedTask(task)}
                                >
                                    <div className="flex items-start justify-between">
                                        <div className="min-w-0 flex-1">
                                            <p className="text-sm font-medium text-gray-900 dark:text-white">
                                                {task.title || task.prompt?.substring(0, 50) || 'Untitled'}
                                            </p>
                                            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                                                {task.agent_type} • {new Date(task.created_at).toLocaleTimeString()}
                                            </p>
                                        </div>
                                        <span className={`ml-2 inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${getStatusClasses(task.status)}`}>
                                            {task.status}
                                        </span>
                                        <span className="ml-2">
                                            {getPriorityBadge(task.priority)}
                                        </span>
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </div>
            </div>

            {/* Task Detail */}
            <div className="lg:col-span-1">
                <div className="rounded-lg bg-white shadow-sm dark:bg-gray-800 dark:ring-1 dark:ring-white/10 sticky top-24">
                    <div className="p-4 border-b border-gray-200 dark:border-gray-700">
                        <h3 className="text-sm font-semibold text-gray-900 dark:text-white">Task Details</h3>
                    </div>
                    <div className="p-4">
                        {selectedTask ? (
                            <div className="space-y-4">
                                <div>
                                    <p className="text-xs text-gray-500 dark:text-gray-400">Title</p>
                                    <p className="text-sm text-gray-900 dark:text-white">
                                        {selectedTask.title || 'Untitled'}
                                    </p>
                                </div>
                                <div>
                                    <p className="text-xs text-gray-500 dark:text-gray-400">Agent</p>
                                    <p className="text-sm text-gray-900 dark:text-white">{selectedTask.agent_type}</p>
                                </div>
                                <div>
                                    <p className="text-xs text-gray-500 dark:text-gray-400">Status</p>
                                    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${getStatusClasses(selectedTask.status)}`}>
                                        {selectedTask.status}
                                    </span>
                                </div>
                                <div>
                                    <p className="text-xs text-gray-500 dark:text-gray-400">Priority</p>
                                    <span className="mt-1">{getPriorityBadge(selectedTask.priority)}</span>
                                </div>
                                {showSwarmMonitor && (
                                    <div className="rounded-md border border-indigo-200 bg-indigo-50/60 p-3 dark:border-indigo-700 dark:bg-indigo-900/20 space-y-3">
                                        <div className="flex items-center justify-between">
                                            <p className="text-xs font-semibold text-indigo-900 dark:text-indigo-200">Swarm Timeline</p>
                                            <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium ${selectedTaskSwarmMonitor?.connected
                                                ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'
                                                : 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
                                                }`}>
                                                {selectedTaskSwarmMonitor?.connected ? 'LIVE' : 'IDLE'}
                                            </span>
                                        </div>

                                        <div className="grid grid-cols-4 gap-2">
                                            <div className="rounded bg-white/80 dark:bg-gray-900/40 p-2 text-center">
                                                <p className="text-[10px] uppercase tracking-wide text-gray-500 dark:text-gray-400">Pending</p>
                                                <p className="text-xs font-semibold text-gray-900 dark:text-white">{swarmCounts.pending}</p>
                                            </div>
                                            <div className="rounded bg-blue-50 dark:bg-blue-900/20 p-2 text-center">
                                                <p className="text-[10px] uppercase tracking-wide text-blue-600 dark:text-blue-300">Running</p>
                                                <p className="text-xs font-semibold text-blue-700 dark:text-blue-200">{swarmCounts.running}</p>
                                            </div>
                                            <div className="rounded bg-green-50 dark:bg-green-900/20 p-2 text-center">
                                                <p className="text-[10px] uppercase tracking-wide text-green-600 dark:text-green-300">Done</p>
                                                <p className="text-xs font-semibold text-green-700 dark:text-green-200">{swarmCounts.completed}</p>
                                            </div>
                                            <div className="rounded bg-red-50 dark:bg-red-900/20 p-2 text-center">
                                                <p className="text-[10px] uppercase tracking-wide text-red-600 dark:text-red-300">Failed</p>
                                                <p className="text-xs font-semibold text-red-700 dark:text-red-200">{swarmCounts.failed}</p>
                                            </div>
                                        </div>

                                        <div className="flex flex-wrap items-center gap-2 text-[11px] text-gray-600 dark:text-gray-300">
                                            <span className={`inline-flex items-center rounded-full px-2 py-0.5 font-medium ${getSwarmRunStatusClasses(selectedTaskSwarmMonitor?.status ?? 'idle')}`}>
                                                {(selectedTaskSwarmMonitor?.status ?? 'idle').toUpperCase()}
                                            </span>
                                            {selectedTaskSwarmMonitor?.plannedSubtasks !== null && selectedTaskSwarmMonitor?.plannedSubtasks !== undefined && (
                                                <span>planned={selectedTaskSwarmMonitor.plannedSubtasks}</span>
                                            )}
                                            {selectedTaskSwarmMonitor?.currentStage !== null && selectedTaskSwarmMonitor?.currentStage !== undefined && (
                                                <span>stage={selectedTaskSwarmMonitor.currentStage}</span>
                                            )}
                                            {selectedTaskSwarmMonitor?.speedup !== null && selectedTaskSwarmMonitor?.speedup !== undefined && (
                                                <span>speedup={selectedTaskSwarmMonitor.speedup.toFixed(2)}x</span>
                                            )}
                                        </div>

                                        {swarmSubtasks.length > 0 && (
                                            <div className="max-h-28 overflow-y-auto space-y-1">
                                                {swarmSubtasks.slice(0, 8).map((task) => (
                                                    <div key={task.id} className="rounded border border-gray-200 dark:border-gray-700 bg-white/70 dark:bg-gray-900/30 p-2">
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
                                                            <p className="mt-1 text-[10px] text-red-600 dark:text-red-300 whitespace-pre-wrap">{task.error}</p>
                                                        )}
                                                    </div>
                                                ))}
                                            </div>
                                        )}

                                        <div className="rounded bg-white/70 dark:bg-gray-900/40 p-2 max-h-32 overflow-y-auto space-y-1">
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
                                    </div>
                                )}
                                {selectedTask.codebase_id && (
                                    <div>
                                        <p className="text-xs text-gray-500 dark:text-gray-400">Codebase ID</p>
                                        <p className="text-sm text-gray-900 dark:text-white">{selectedTask.codebase_id}</p>
                                    </div>
                                )}
                                <div>
                                    <p className="text-xs text-gray-500 dark:text-gray-400">Created</p>
                                    <p className="text-sm text-gray-900 dark:text-white">{new Date(selectedTask.created_at).toLocaleString()}</p>
                                </div>
                                {selectedTask.started_at && (
                                    <div>
                                        <p className="text-xs text-gray-500 dark:text-gray-400">Started</p>
                                        <p className="text-sm text-gray-900 dark:text-white">{new Date(selectedTask.started_at).toLocaleString()}</p>
                                    </div>
                                )}
                                {selectedTask.completed_at && (
                                    <div>
                                        <p className="text-xs text-gray-500 dark:text-gray-400">Completed</p>
                                        <p className="text-sm text-gray-900 dark:text-white">{new Date(selectedTask.completed_at).toLocaleString()}</p>
                                    </div>
                                )}
                                {selectedTask.error && (
                                    <div>
                                        <p className="text-xs text-gray-500 dark:text-gray-400">Error</p>
                                        <p className="text-sm text-red-600 dark:text-red-400 whitespace-pre-wrap">{selectedTask.error}</p>
                                    </div>
                                )}
                                {selectedTask.prompt && (
                                    <div>
                                        <p className="text-xs text-gray-500 dark:text-gray-400">Prompt</p>
                                        <p className="text-sm text-gray-900 dark:text-white whitespace-pre-wrap">
                                            {selectedTask.prompt}
                                        </p>
                                    </div>
                                )}
                                {selectedTask.result && (
                                    <div>
                                        <p className="text-xs text-gray-500 dark:text-gray-400">Result</p>
                                        <div className="mt-1 p-2 bg-gray-50 dark:bg-gray-700 rounded text-xs font-mono max-h-64 overflow-y-auto">
                                            {parseTaskResult(selectedTask.result)}
                                        </div>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-8">
                                Select a task to view details
                            </p>
                        )}
                    </div>
                </div>
            </div>
        </div>
    )
}
