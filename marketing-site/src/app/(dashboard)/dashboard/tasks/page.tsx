'use client'

import { useState, useEffect, useCallback } from 'react'
import { useCodebases } from '../sessions/hooks/useCodebases'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.codetether.run'

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
    const [selectedCodebase, setSelectedCodebase] = useState<string>('all')

    const loadTasks = useCallback(async () => {
        try {
            const response = await fetch(`${API_URL}/v1/opencode/tasks`)
            if (response.ok) {
                const data = await response.json()
                setTasks(data)
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
