'use client'

import { useEffect, useCallback, useRef, useState } from 'react'
import { useCodebases } from '../sessions/hooks/useCodebases'
import { PRDBuilder } from './PRDBuilder'
import { 
    useRalphStore, 
    useAvailableModels,
    usePassedCount,
    useTotalCount,
    type PRD,
    type UserStory,
    type RalphLogEntry,
    type RalphRun,
    type Task,
    type Agent
} from './store'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.codetether.run'

// UUID generator that works in all browsers
function generateUUID(): string {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
        return crypto.randomUUID()
    }
    // Fallback for older browsers
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
        const r = Math.random() * 16 | 0
        const v = c === 'x' ? r : (r & 0x3 | 0x8)
        return v.toString(16)
    })
}

// Re-export types for backwards compatibility
export type { PRD, UserStory, RalphLogEntry, RalphRun, Task, Agent }

// ============================================================================
// Example PRD Template
// ============================================================================

const examplePRD: PRD = {
    project: "MyApp",
    branchName: "ralph/new-feature",
    description: "Add a new feature to the application",
    userStories: [
        {
            id: "US-001",
            title: "Add database migration",
            description: "As a developer, I need to add a new column to the database",
            acceptanceCriteria: [
                "Migration file created",
                "Column added with correct type",
                "Typecheck passes"
            ],
            priority: 1,
            passes: false
        },
        {
            id: "US-002",
            title: "Create API endpoint",
            description: "As a user, I want an API endpoint to access the new data",
            acceptanceCriteria: [
                "GET endpoint returns data",
                "POST endpoint creates records",
                "Typecheck passes"
            ],
            priority: 2,
            passes: false
        }
    ]
}

// ============================================================================
// Icons
// ============================================================================

function PlayIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
    )
}

function PauseIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
    )
}

function StopIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" />
        </svg>
    )
}

function UploadIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
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

function TrashIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
        </svg>
    )
}

function EyeIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
        </svg>
    )
}

function RetryIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
    )
}

// ============================================================================
// Story Card Component
// ============================================================================

interface StoryCardProps {
    story: UserStory
    isActive: boolean
    isRunning: boolean
    onRetry: () => void
    onViewTask: () => void
}

function StoryCard({ story, isActive, isRunning, onRetry, onViewTask }: StoryCardProps) {
    const [expanded, setExpanded] = useState(false)
    
    const getStatusIcon = () => {
        if (story.passes) return '✅'
        if (story.taskStatus === 'failed') return '❌'
        if (story.taskStatus === 'running' || isActive) return '⏳'
        if (story.taskStatus === 'pending') return '🔄'
        return '○'
    }
    
    const getStatusColor = () => {
        if (story.passes) return 'border-emerald-500 bg-emerald-50 dark:bg-emerald-900/20'
        if (story.taskStatus === 'failed') return 'border-red-500 bg-red-50 dark:bg-red-900/20'
        if (story.taskStatus === 'running' || isActive) return 'border-yellow-500 bg-yellow-50 dark:bg-yellow-900/20'
        return 'border-gray-200 dark:border-gray-700'
    }
    
    return (
        <div className={`p-3 border-l-4 ${getStatusColor()}`}>
            <div className="flex items-start justify-between">
                <div className="flex items-start gap-2 flex-1 min-w-0">
                    <span className="text-sm mt-0.5">{getStatusIcon()}</span>
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                            <span className="text-xs font-mono font-bold text-gray-700 dark:text-gray-300">
                                {story.id}
                            </span>
                            {story.taskStatus && (
                                <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                                    story.taskStatus === 'completed' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300' :
                                    story.taskStatus === 'failed' ? 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300' :
                                    story.taskStatus === 'running' ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300' :
                                    'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
                                }`}>
                                    {story.taskStatus}
                                </span>
                            )}
                        </div>
                        <p className="text-xs font-medium text-gray-900 dark:text-white mt-0.5">
                            {story.title}
                        </p>
                        {expanded && (
                            <div className="mt-2 space-y-2">
                                <p className="text-xs text-gray-600 dark:text-gray-400">
                                    {story.description}
                                </p>
                                <div className="text-xs text-gray-500 dark:text-gray-500">
                                    <span className="font-medium">Criteria:</span>
                                    <ul className="mt-1 list-disc list-inside">
                                        {story.acceptanceCriteria.map((c, i) => (
                                            <li key={i}>{c}</li>
                                        ))}
                                    </ul>
                                </div>
                                {story.taskId && (
                                    <p className="text-[10px] text-gray-400 font-mono">
                                        Task: {story.taskId}
                                    </p>
                                )}
                            </div>
                        )}
                    </div>
                </div>
                <div className="flex items-center gap-1 ml-2">
                    <button
                        onClick={() => setExpanded(!expanded)}
                        className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                        title={expanded ? 'Collapse' : 'Expand'}
                    >
                        <svg className={`w-4 h-4 transition-transform ${expanded ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                        </svg>
                    </button>
                    {story.taskId && (
                        <button
                            onClick={onViewTask}
                            className="p-1 text-gray-400 hover:text-blue-500"
                            title="View task result"
                        >
                            <EyeIcon className="w-4 h-4" />
                        </button>
                    )}
                    {(story.taskStatus === 'failed' || story.passes === false) && !isRunning && (
                        <button
                            onClick={onRetry}
                            className="p-1 text-gray-400 hover:text-orange-500"
                            title="Retry this story"
                        >
                            <RetryIcon className="w-4 h-4" />
                        </button>
                    )}
                </div>
            </div>
        </div>
    )
}

// ============================================================================
// Main Component
// ============================================================================

export default function RalphPage() {
    // Use Zustand store for all state
    const {
        prd, setPrd,
        prdJson, setPrdJson,
        run, setRun,
        tasks, setTasks,
        isRunning, setIsRunning,
        error, setError,
        maxIterations, setMaxIterations,
        runMode, setRunMode,
        maxParallel, setMaxParallel,
        selectedCodebase, setSelectedCodebase,
        selectedModel, setSelectedModel,
        agents, setAgents,
        loadingAgents, setLoadingAgents,
        showPRDBuilder, setShowPRDBuilder,
        addLog,
        reset,
    } = useRalphStore()
    
    // Derived state from store using memoized hooks
    const availableModels = useAvailableModels()
    const passedCount = usePassedCount()
    const totalCount = useTotalCount()
    
    const logsRef = useRef<HTMLDivElement>(null)
    const { codebases } = useCodebases()
    const pollingRef = useRef<NodeJS.Timeout | null>(null)
    
    // Use refs to track state for async functions (avoids stale closure)
    const isRunningRef = useRef(isRunning)
    const prdRef = useRef(prd)
    useEffect(() => {
        isRunningRef.current = isRunning
    }, [isRunning])
    useEffect(() => {
        prdRef.current = prd
    }, [prd])

    // Handle PRD from builder
    const handlePRDFromBuilder = (newPrd: PRD) => {
        setPrd(newPrd)
        setPrdJson(JSON.stringify(newPrd, null, 2))
        setShowPRDBuilder(false)
        setError(null)
    }

    // Load available agents and their models
    const loadAgents = useCallback(async () => {
        setLoadingAgents(true)
        try {
            let agentList: Agent[] = []
            
            // Use REST API to get workers
            try {
                const workersResponse = await fetch(`${API_URL}/v1/opencode/workers`)
                if (workersResponse.ok) {
                    const workers = await workersResponse.json()
                    // Convert workers format to agents format
                    agentList = (workers || []).map((w: Record<string, unknown>) => {
                        // Models can be strings or objects with various formats:
                        // - {providerID: 'anthropic', modelID: 'claude-3-5-sonnet'} (OpenCode format)
                        // - {id, name, provider, provider_id, capabilities}
                        // - plain strings like "anthropic:claude-3-5-sonnet"
                        type ModelObj = { 
                            providerID?: string; modelID?: string;  // OpenCode format
                            id?: string; name?: string; provider?: string; provider_id?: string;  // Alt format
                        }
                        const rawModels = w.models as Array<string | ModelObj> || []
                        const modelStrings = rawModels.map(m => {
                            if (typeof m === 'string') return m
                            if (!m || typeof m !== 'object') return null
                            // OpenCode format: {providerID, modelID}
                            if (m.providerID && m.modelID) return `${m.providerID}:${m.modelID}`
                            // Alt format with provider + name/id
                            if (m.provider && m.name && m.name !== m.provider) return `${m.provider}:${m.name}`
                            if (m.provider && m.id && m.id !== m.provider) return `${m.provider}:${m.id}`
                            // Just use name or id if available
                            if (m.name) return m.name
                            if (m.id) return m.id
                            return null
                        }).filter((m): m is string => m !== null && m.length > 0)
                        
                        return {
                            name: w.name || w.worker_id,
                            role: w.name || 'worker',
                            instance_id: w.worker_id as string,
                            models_supported: modelStrings,
                            last_seen: w.last_seen as string,
                        }
                    })
                }
            } catch (e) {
                console.debug('Workers endpoint failed', e)
            }
            
            setAgents(agentList)

            // If no model selected yet, try to pick a default
            if (!selectedModel && agentList.length > 0) {
                // Find first agent with models
                for (const agent of agentList) {
                    if (agent.models_supported && agent.models_supported.length > 0) {
                        const firstModel = agent.models_supported[0]
                        // Ensure it's a string
                        if (typeof firstModel === 'string') {
                            setSelectedModel(firstModel)
                            break
                        }
                    }
                }
            }
        } catch (err) {
            console.error('Failed to load agents:', err)
        } finally {
            setLoadingAgents(false)
        }
    }, [selectedModel, setAgents, setLoadingAgents, setSelectedModel])

    // Load agents on mount
    useEffect(() => {
        loadAgents()
    }, [loadAgents])

    // Load tasks for Ralph runs
    const loadTasks = useCallback(async () => {
        try {
            const response = await fetch(`${API_URL}/v1/opencode/tasks`)
            if (response.ok) {
                const data = await response.json()
                // Filter to Ralph tasks
                const ralphTasks = data.filter((t: Task) =>
                    t.metadata?.ralph === true || t.title?.startsWith('Ralph:')
                )
                setTasks(ralphTasks)

                // Update story statuses based on task results
                if (prd && run) {
                    const updatedStories = prd.userStories.map(story => {
                        const task = ralphTasks.find((t: Task) =>
                            t.metadata?.storyId === story.id || t.title?.includes(story.id)
                        )
                        if (task) {
                            return {
                                ...story,
                                taskId: task.id,
                                taskStatus: task.status,
                                passes: task.status === 'completed'
                            }
                        }
                        return story
                    })
                    setPrd({ ...prd, userStories: updatedStories })
                }
            }
        } catch (err) {
            console.error('Failed to load tasks:', err)
        }
    }, [prd, run])

    // Poll for task updates when running
    useEffect(() => {
        if (isRunning) {
            pollingRef.current = setInterval(loadTasks, 3000)
        } else if (pollingRef.current) {
            clearInterval(pollingRef.current)
            pollingRef.current = null
        }
        return () => {
            if (pollingRef.current) {
                clearInterval(pollingRef.current)
            }
        }
    }, [isRunning, loadTasks])

    // Auto-scroll logs
    useEffect(() => {
        if (logsRef.current) {
            logsRef.current.scrollTop = logsRef.current.scrollHeight
        }
    }, [run?.logs])

    // Sync story statuses with API tasks on mount
    const syncStoriesWithTasks = useCallback(async () => {
        if (!prd) return
        
        try {
            // Fetch all tasks and find Ralph tasks
            const response = await fetch(`${API_URL}/v1/opencode/tasks`)
            if (!response.ok) return
            
            const allTasks = await response.json()
            
            // Find Ralph tasks by title pattern or metadata
            const ralphTasks = allTasks.filter((t: Task) => 
                t.title?.startsWith('Ralph:') || t.metadata?.ralph === true
            )
            
            if (ralphTasks.length === 0) return
            
            // Match tasks to stories and update
            const updatedStories = prd.userStories.map(story => {
                // Find task for this story by metadata.storyId or title containing story.id
                const task = ralphTasks.find((t: Task) => 
                    t.metadata?.storyId === story.id || 
                    t.title?.includes(story.id)
                )
                
                if (task) {
                    const passes = task.status === 'completed' && 
                        (task.result?.includes('STORY_COMPLETE') || !task.result?.includes('STORY_BLOCKED'))
                    return {
                        ...story,
                        taskId: task.id,
                        taskStatus: task.status,
                        passes
                    }
                }
                return story
            })
            
            // Only update if something changed
            const hasChanges = updatedStories.some((s, i) => 
                s.taskId !== prd.userStories[i].taskId || 
                s.taskStatus !== prd.userStories[i].taskStatus ||
                s.passes !== prd.userStories[i].passes
            )
            
            if (hasChanges) {
                setPrd({ ...prd, userStories: updatedStories })
                // Silent sync - don't spam logs
            }
        } catch (err) {
            console.error('Failed to sync stories with tasks:', err)
        }
    }, [prd, setPrd, addLog])

    // Only sync stories with tasks while Ralph is running
    useEffect(() => {
        if (isRunning) {
            syncStoriesWithTasks()
        }
    }, [isRunning, syncStoriesWithTasks])

    // Restore in-progress run on mount (after page reload)
    useEffect(() => {
        const restoreRun = async () => {
            // If we have a run that was running, check task statuses and resume
            if (!run || run.status !== 'running' || !prd) return
            
            addLog('info', 'Restoring session after page reload...')
            
            // Fetch latest task statuses from API for all stories with taskIds
            const storiesWithTasks = prd.userStories.filter(s => s.taskId)
            
            for (const story of storiesWithTasks) {
                try {
                    const response = await fetch(`${API_URL}/v1/opencode/tasks/${story.taskId}`)
                    if (response.ok) {
                        const task = await response.json()
                        addLog('info', `${story.id}: ${task.status}`, story.id)
                        
                        // Update story status based on task
                        setPrd(prev => prev ? {
                            ...prev,
                            userStories: prev.userStories.map(s =>
                                s.id === story.id ? {
                                    ...s,
                                    taskStatus: task.status,
                                    passes: task.status === 'completed' && 
                                        (task.result?.includes('STORY_COMPLETE') || !task.result?.includes('STORY_BLOCKED'))
                                } : s
                            )
                        } : null)
                        
                        // If task is still running, resume polling
                        if (task.status === 'running' || task.status === 'pending') {
                            addLog('info', `Resuming polling for ${story.id}...`, story.id)
                            isRunningRef.current = true
                            prdRef.current = prd
                            setIsRunning(true)
                            
                            const result = await waitForTask(story.taskId!, story.id)
                            if (result.success) {
                                addLog('story_pass', `${story.id} PASSED!`, story.id)
                                setPrd(prev => prev ? {
                                    ...prev,
                                    userStories: prev.userStories.map(s =>
                                        s.id === story.id ? { ...s, passes: true, taskStatus: 'completed' } : s
                                    )
                                } : null)
                            } else {
                                addLog('story_fail', `${story.id} FAILED: ${result.result.slice(0, 200)}`, story.id)
                                setPrd(prev => prev ? {
                                    ...prev,
                                    userStories: prev.userStories.map(s =>
                                        s.id === story.id ? { ...s, taskStatus: 'failed' } : s
                                    )
                                } : null)
                            }
                        }
                    }
                } catch (err) {
                    addLog('error', `Failed to fetch ${story.id} status`, story.id)
                }
            }
            
            // Check if there are remaining incomplete stories to process
            const currentPrd = prdRef.current
            const hasIncomplete = currentPrd?.userStories.some(s => !s.passes)
            
            if (hasIncomplete && isRunningRef.current) {
                addLog('info', 'Continuing with remaining stories...')
                await runSequential()
            }
            
            setIsRunning(false)
            isRunningRef.current = false
            
            const allPassed = prdRef.current?.userStories.every(s => s.passes)
            setRun(prev => prev ? { 
                ...prev, 
                status: allPassed ? 'completed' : 'paused',
                completedAt: allPassed ? new Date().toISOString() : undefined
            } : null)
            
            if (allPassed) {
                addLog('complete', 'All stories complete!')
            }
        }
        
        restoreRun()
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []) // Only run once on mount

    // Parse PRD JSON
    const handlePrdChange = (json: string) => {
        setPrdJson(json)
        setError(null)
        try {
            if (json.trim()) {
                const parsed = JSON.parse(json)
                // Validate required fields
                if (!parsed.project || !parsed.branchName || !parsed.userStories) {
                    throw new Error('PRD must have project, branchName, and userStories')
                }
                setPrd(parsed)
            } else {
                setPrd(null)
            }
        } catch (err) {
            if (json.trim()) {
                setError(`Invalid JSON: ${err instanceof Error ? err.message : 'Parse error'}`)
            }
            setPrd(null)
        }
    }

    // Load example PRD
    const loadExample = () => {
        const json = JSON.stringify(examplePRD, null, 2)
        setPrdJson(json)
        setPrd(examplePRD)
        setError(null)
    }

    // Create A2A task for a story using REST API
    const createStoryTask = async (story: UserStory, iteration: number): Promise<string> => {
        const prompt = `# Ralph Iteration ${iteration}

## Story: ${story.id} - ${story.title}

${story.description}

### Acceptance Criteria
${story.acceptanceCriteria.map((c, i) => `${i + 1}. ${c}`).join('\n')}

## Instructions
1. Implement ONLY this story
2. Run quality checks (typecheck, tests)
3. Commit with message: "feat(${story.id}): ${story.title}"
4. If complete, output: <promise>STORY_COMPLETE</promise>
5. If blocked, output: <promise>STORY_BLOCKED: [reason]</promise>
`

        // Use REST API for task creation
        const response = await fetch(`${API_URL}/v1/opencode/tasks`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: `Ralph: ${story.id} - ${story.title}`,
                prompt: prompt,
                codebase_id: selectedCodebase === 'global' ? undefined : selectedCodebase,
                agent_type: 'build',
                priority: 10 - story.priority,
                model: selectedModel || undefined,
                metadata: {
                    ralph: true,
                    storyId: story.id,
                    iteration,
                }
            })
        })

        if (!response.ok) {
            throw new Error(`Failed to create task: ${await response.text()}`)
        }

        const data = await response.json()
        return data.id
    }

    // Parse SSE output event to extract meaningful info for logging
    const parseOutputEvent = (output: Record<string, unknown>, storyId: string) => {
        try {
            const outputStr = output?.output as string
            if (!outputStr) return

            // Try to parse as JSON (OpenCode output format)
            try {
                const event = JSON.parse(outputStr)

                if (event.type === 'text' && event.part?.text) {
                    const text = (event.part.text as string).slice(0, 200)
                    if (text.trim()) {
                        addLog('ai', `${text}${(event.part.text as string).length > 200 ? '...' : ''}`, storyId)
                    }
                } else if (event.type === 'tool_use') {
                    const tool = event.part?.tool || event.tool || 'unknown'
                    const state = event.part?.state || event.state
                    if (state?.status === 'running') {
                        addLog('tool', `Running: ${tool}`, storyId)
                    } else if (state?.status === 'completed') {
                        const resultStr = (state.output as string || '').slice(0, 80)
                        addLog('check', `${tool} completed${resultStr ? `: ${resultStr}...` : ''}`, storyId)
                    } else if (state?.status === 'error') {
                        addLog('error', `${tool} failed: ${state.error || 'unknown'}`, storyId)
                    } else {
                        // Tool starting
                        addLog('tool', `${tool}`, storyId)
                    }
                } else if (event.type === 'tool_result') {
                    const resultText = (event.part?.output as string || '').slice(0, 100)
                    if (resultText) {
                        addLog('check', `Result: ${resultText}...`, storyId)
                    }
                }
            } catch {
                // Not JSON, show as plain text if reasonable length
                if (outputStr.length > 0 && outputStr.length < 300) {
                    // Check for tool patterns in raw output
                    if (outputStr.includes('Running tool:') || outputStr.includes('Bash:')) {
                        addLog('tool', outputStr.slice(0, 150), storyId)
                    } else if (outputStr.includes('commit') || outputStr.includes('git')) {
                        addLog('commit', outputStr.slice(0, 150), storyId)
                    } else {
                        addLog('info', outputStr.slice(0, 150), storyId)
                    }
                }
            }
        } catch {
            // Ignore parsing errors
        }
    }

    // Wait for task completion with SSE streaming for real-time updates
    const waitForTask = async (taskId: string, storyId: string, timeoutMs: number = 600000): Promise<{ success: boolean; result: string }> => {
        return new Promise((resolve) => {
            const startTime = Date.now()
            let finalResult = ''
            let resolved = false
            let eventSource: EventSource | null = null
            let pollInterval: ReturnType<typeof setInterval> | null = null

            const cleanup = () => {
                if (eventSource) {
                    eventSource.close()
                    eventSource = null
                }
                if (pollInterval) {
                    clearInterval(pollInterval)
                    pollInterval = null
                }
            }

            const finish = (success: boolean, result: string) => {
                if (resolved) return
                resolved = true
                cleanup()
                resolve({ success, result })
            }

            // Start SSE stream for real-time output
            const streamUrl = `${API_URL}/v1/opencode/tasks/${taskId}/output/stream`
            addLog('waiting', `Connecting to task stream...`, storyId)

            try {
                eventSource = new EventSource(streamUrl)

                eventSource.addEventListener('output', (e) => {
                    try {
                        const data = JSON.parse(e.data)
                        parseOutputEvent(data, storyId)
                    } catch {
                        // Ignore parse errors
                    }
                })

                eventSource.addEventListener('done', (e) => {
                    try {
                        const data = JSON.parse(e.data)
                        if (data.status === 'completed') {
                            finish(true, finalResult)
                        } else if (data.status === 'failed') {
                            finish(false, data.error || 'Task failed')
                        } else if (data.status === 'cancelled') {
                            finish(false, 'Task cancelled')
                        }
                    } catch {
                        finish(false, 'Unknown error')
                    }
                })

                eventSource.onerror = () => {
                    // SSE connection failed, fall back to polling
                    if (eventSource) {
                        eventSource.close()
                        eventSource = null
                    }
                    addLog('info', `Streaming unavailable, polling for updates...`, storyId)
                }
            } catch {
                addLog('info', `SSE not supported, polling for updates...`, storyId)
            }

            // Also poll the task status as backup (and to get final result)
            let lastStatus = ''
            pollInterval = setInterval(async () => {
                // Check timeout
                if (Date.now() - startTime > timeoutMs) {
                    finish(false, 'Task timed out')
                    return
                }

                // Check if stopped (use ref to get fresh value)
                if (!isRunningRef.current) {
                    finish(false, 'Stopped by user')
                    return
                }

                try {
                    // Use REST API for task status
                    const response = await fetch(`${API_URL}/v1/opencode/tasks/${taskId}`)
                    if (!response.ok) return

                    const task = await response.json()

                    // Log status changes
                    if (task.status !== lastStatus) {
                        lastStatus = task.status
                        if (task.status === 'working' || task.status === 'running') {
                            addLog('info', `Worker executing task...`, storyId)
                        } else if (task.status === 'pending') {
                            addLog('waiting', `Queued, waiting for worker...`, storyId)
                        }
                    }

                    finalResult = task.result || ''

                    if (task.status === 'completed') {
                        const success = finalResult.includes('STORY_COMPLETE') || !finalResult.includes('STORY_BLOCKED')
                        finish(success, finalResult)
                    } else if (task.status === 'failed') {
                        finish(false, task.error || 'Task failed')
                    } else if (task.status === 'cancelled') {
                        finish(false, 'Task cancelled')
                    }
                } catch {
                    // Ignore poll errors, will retry
                }
            }, 2000) // Poll every 2 seconds as backup
        })
    }

    // Run Ralph loop sequentially
    const runSequential = async () => {
        // Use ref to get current PRD (avoids stale closure)
        const currentPrd = prdRef.current
        if (!currentPrd) {
            addLog('error', 'No PRD available')
            return
        }

        addLog('info', `Processing ${currentPrd.userStories.length} stories...`)

        for (let i = 0; i < maxIterations; i++) {
            if (!isRunningRef.current) {
                addLog('info', 'Stopped by user')
                break
            }

            // Find next incomplete story from current PRD state
            const currentStories = prdRef.current?.userStories || []
            const story = currentStories.find(s => !s.passes)
            if (!story) {
                addLog('complete', 'All stories complete!')
                break
            }

            setRun(prev => prev ? {
                ...prev,
                currentIteration: i + 1,
                currentStoryId: story.id
            } : null)

            addLog('story_start', `Starting ${story.id}: ${story.title}`, story.id)

            try {
                // Create task
                addLog('info', `Creating A2A task for ${story.id}...`, story.id)
                const taskId = await createStoryTask(story, i + 1)

                // Update story with task ID (use functional update to get latest state)
                setPrd(prev => prev ? {
                    ...prev,
                    userStories: prev.userStories.map(s =>
                        s.id === story.id ? { ...s, taskId, taskStatus: 'pending' } : s
                    )
                } : null)

                addLog('info', `Task created: ${taskId}`, story.id)

                // Wait for completion with streaming updates
                const result = await waitForTask(taskId, story.id)

                if (result.success) {
                    addLog('story_pass', `${story.id} PASSED!`, story.id)
                    // Update story status (use functional update)
                    setPrd(prev => prev ? {
                        ...prev,
                        userStories: prev.userStories.map(s =>
                            s.id === story.id ? { ...s, passes: true, taskStatus: 'completed' } : s
                        )
                    } : null)
                } else {
                    addLog('story_fail', `${story.id} FAILED: ${result.result.slice(0, 200)}`, story.id)
                }

            } catch (err) {
                addLog('error', `Error on ${story.id}: ${err instanceof Error ? err.message : 'Unknown error'}`, story.id)
            }
        }
    }

    // Run Ralph loop in parallel
    const runParallel = async () => {
        if (!prd) return

        const incompleteStories = prd.userStories.filter(s => !s.passes)

        // Create all tasks
        addLog('info', `Creating ${incompleteStories.length} tasks in parallel (max ${maxParallel} concurrent)...`)

        const taskPromises: Promise<void>[] = []
        const semaphore = { count: 0 }

        for (const story of incompleteStories) {
            // Wait for semaphore
            while (semaphore.count >= maxParallel) {
                await new Promise(r => setTimeout(r, 1000))
            }

            semaphore.count++

            const runStory = async () => {
                try {
                    addLog('story_start', `Starting ${story.id}: ${story.title}`, story.id)
                    const taskId = await createStoryTask(story, 1)

                    // Update story
                    setPrd(prev => prev ? {
                        ...prev,
                        userStories: prev.userStories.map(s =>
                            s.id === story.id ? { ...s, taskId, taskStatus: 'running' } : s
                        )
                    } : null)

                    const result = await waitForTask(taskId, story.id)

                    if (result.success) {
                        addLog('story_pass', `${story.id} PASSED!`, story.id)
                        setPrd(prev => prev ? {
                            ...prev,
                            userStories: prev.userStories.map(s =>
                                s.id === story.id ? { ...s, passes: true, taskStatus: 'completed' } : s
                            )
                        } : null)
                    } else {
                        addLog('story_fail', `${story.id} FAILED`, story.id)
                    }
                } finally {
                    semaphore.count--
                }
            }

            taskPromises.push(runStory())
        }

        await Promise.all(taskPromises)
        addLog('complete', 'All parallel tasks finished!')
    }

    // Start Ralph
    const startRalph = async () => {
        if (!prd) return

        // Set both state and ref immediately (ref is used in async loops)
        setIsRunning(true)
        isRunningRef.current = true
        prdRef.current = prd
        setError(null)

        // Initialize run state
        const newRun: RalphRun = {
            id: generateUUID(),
            prd,
            status: 'running',
            currentIteration: 0,
            maxIterations,
            startedAt: new Date().toISOString(),
            logs: [],
            rlmCompressions: 0,
            tokensSaved: 0
        }
        setRun(newRun)

        addLog('info', `Starting Ralph loop for ${prd.project}`)
        addLog('info', `Branch: ${prd.branchName}`)
        addLog('info', `Stories: ${prd.userStories.length}`)
        addLog('info', `Mode: ${runMode}${runMode === 'parallel' ? ` (max ${maxParallel})` : ''}`)
        addLog('info', `Codebase: ${selectedCodebase}`)

        try {
            if (runMode === 'sequential') {
                await runSequential()
            } else {
                await runParallel()
            }
        } catch (err) {
            addLog('error', `Ralph failed: ${err instanceof Error ? err.message : 'Unknown error'}`)
            setError(err instanceof Error ? err.message : 'Unknown error')
        }

        setIsRunning(false)
        setRun(prev => prev ? {
            ...prev,
            status: 'completed',
            completedAt: new Date().toISOString()
        } : null)
    }

    // Stop Ralph
    const stopRalph = () => {
        setIsRunning(false)
        isRunningRef.current = false
        addLog('info', 'Ralph stopped by user')
        setRun(prev => prev ? { ...prev, status: 'paused' } : null)
    }

    // SSE connection for real-time server logs
    const eventSourceRef = useRef<EventSource | null>(null)
    
    const startServerLogStream = useCallback((runId: string) => {
        // Close any existing connection
        if (eventSourceRef.current) {
            eventSourceRef.current.close()
        }
        
        const streamUrl = `${API_URL}/v1/ralph/runs/${runId}/stream`
        const eventSource = new EventSource(streamUrl)
        eventSourceRef.current = eventSource
        setIsRunning(true)
        
        // Handle log events
        eventSource.addEventListener('log', (e) => {
            try {
                const log = JSON.parse(e.data)
                setRun(prev => {
                    if (!prev) return null
                    // Avoid duplicates
                    if (prev.logs.some(l => l.id === log.id)) return prev
                    return {
                        ...prev,
                        logs: [...prev.logs, {
                            id: log.id,
                            timestamp: log.timestamp,
                            type: log.type as RalphLogEntry['type'],
                            message: log.message,
                            storyId: log.story_id,
                        }],
                    }
                })
            } catch (err) {
                console.error('Failed to parse log event:', err)
            }
        })
        
        // Handle status events
        eventSource.addEventListener('status', (e) => {
            try {
                const data = JSON.parse(e.data)
                setRun(prev => prev ? { ...prev, status: data.status as RalphRun['status'] } : null)
            } catch (err) {
                console.error('Failed to parse status event:', err)
            }
        })
        
        // Handle story updates
        eventSource.addEventListener('story', (e) => {
            try {
                const storyResults = JSON.parse(e.data)
                if (prd) {
                    const updatedStories = prd.userStories.map(story => {
                        const result = storyResults.find((r: {story_id: string}) => r.story_id === story.id)
                        if (result) {
                            return {
                                ...story,
                                taskId: result.task_id,
                                taskStatus: result.status,
                                passes: result.status === 'passed'
                            }
                        }
                        return story
                    })
                    setPrd({ ...prd, userStories: updatedStories })
                }
            } catch (err) {
                console.error('Failed to parse story event:', err)
            }
        })
        
        // Handle real-time agent output
        eventSource.addEventListener('output', (e) => {
            try {
                const data = JSON.parse(e.data)
                const outputText = data.output?.trim()
                if (outputText) {
                    // Add agent output as a log entry
                    setRun(prev => {
                        if (!prev) return null
                        // Create a unique ID for this output chunk
                        const outputId = `output-${data.task_id}-${Date.now()}`
                        return {
                            ...prev,
                            logs: [...prev.logs, {
                                id: outputId,
                                timestamp: data.timestamp || new Date().toISOString(),
                                type: 'info' as RalphLogEntry['type'],
                                message: outputText,
                                storyId: data.story_id,
                            }],
                        }
                    })
                }
            } catch (err) {
                console.error('Failed to parse output event:', err)
            }
        })
        
        // Handle completion
        eventSource.addEventListener('done', (e) => {
            try {
                const data = JSON.parse(e.data)
                setRun(prev => prev ? { ...prev, status: data.status as RalphRun['status'] } : null)
                setIsRunning(false)
                eventSource.close()
                eventSourceRef.current = null
            } catch (err) {
                console.error('Failed to parse done event:', err)
            }
        })
        
        // Handle errors
        eventSource.addEventListener('error', () => {
            console.error('SSE connection error, falling back to polling')
            eventSource.close()
            eventSourceRef.current = null
            // Could implement polling fallback here
        })
        
    }, [prd, setPrd, setRun, setIsRunning])
    
    // Cleanup SSE on unmount
    useEffect(() => {
        return () => {
            if (eventSourceRef.current) {
                eventSourceRef.current.close()
            }
        }
    }, [])
    
    // Start server-side Ralph run (persisted, survives page reload)
    const [startingRun, setStartingRun] = useState(false)
    
    const startServerRalph = async () => {
        if (!prd) return
        
        setStartingRun(true)
        setError(null)
        
        // Initialize a run object to show logs FIRST
        const newRun: RalphRun = {
            id: 'pending',
            prd,
            status: 'running',
            currentIteration: 0,
            maxIterations,
            startedAt: new Date().toISOString(),
            logs: [{
                id: generateUUID(),
                timestamp: new Date().toISOString(),
                type: 'info',
                message: 'Starting Ralph run...',
            }],
            rlmCompressions: 0,
            tokensSaved: 0
        }
        setRun(newRun)
        
        try {
            const response = await fetch(`${API_URL}/v1/ralph/runs`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    prd: {
                        project: prd.project,
                        branchName: prd.branchName,
                        description: prd.description,
                        userStories: prd.userStories.map(s => ({
                            id: s.id,
                            title: s.title,
                            description: s.description,
                            acceptanceCriteria: s.acceptanceCriteria,
                            priority: s.priority,
                        })),
                    },
                    codebase_id: selectedCodebase === 'global' ? null : selectedCodebase,
                    model: selectedModel || null,
                    max_iterations: maxIterations,
                    run_mode: runMode,
                    max_parallel: maxParallel,
                })
            })

            if (response.ok) {
                const data = await response.json()
                addLog('info', `Ralph run started: ${data.id}`)
                // Update run ID and start SSE stream for real-time updates
                setRun(prev => prev ? { ...prev, id: data.id, status: 'running' } : null)
                startServerLogStream(data.id)
            } else {
                const err = await response.text()
                addLog('error', `Failed to start Ralph: ${err}`)
                setError(`Failed to start Ralph: ${err}`)
            }
        } catch (err) {
            const msg = err instanceof Error ? err.message : 'Unknown error'
            addLog('error', `Failed to start Ralph: ${msg}`)
            setError(`Failed to start Ralph: ${msg}`)
        } finally {
            setStartingRun(false)
        }
    }

    // Get status color
    const getStatusColor = (status: string) => {
        switch (status) {
            case 'completed': return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300'
            case 'running': return 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
            case 'failed': return 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300'
            case 'pending': return 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300'
            default: return 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'
        }
    }

    // Get log entry color
    const getLogColor = (type: RalphLogEntry['type']) => {
        switch (type) {
            case 'story_pass': return 'text-emerald-400'
            case 'story_fail': return 'text-red-400'
            case 'error': return 'text-red-400'
            case 'rlm': return 'text-pink-400'
            case 'complete': return 'text-emerald-400'
            case 'story_start': return 'text-yellow-400'
            case 'code': return 'text-cyan-400'
            case 'commit': return 'text-purple-400'
            case 'check': return 'text-green-400'
            case 'tool': return 'text-blue-400'
            case 'ai': return 'text-indigo-400'
            case 'waiting': return 'text-gray-500'
            default: return 'text-gray-400'
        }
    }

    const getLogIcon = (type: RalphLogEntry['type']) => {
        switch (type) {
            case 'story_pass': return '✅'
            case 'story_fail': return '❌'
            case 'error': return '⚠️'
            case 'rlm': return '🗜️'
            case 'complete': return '🎉'
            case 'story_start': return '📋'
            case 'code': return '💻'
            case 'commit': return '📦'
            case 'check': return '✓'
            case 'tool': return '🔧'
            case 'ai': return '🤖'
            case 'waiting': return '⏳'
            default: return '→'
        }
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Ralph Autonomous Loop</h1>
                    <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                        PRD-driven autonomous development with RLM context compression
                    </p>
                </div>
                <div className="flex items-center gap-3">
                    {!isRunning && (prd || run) && (
                        <button
                            onClick={() => {
                                if (confirm('Clear all Ralph state? This will reset PRD, logs, and run history.')) {
                                    reset()
                                }
                            }}
                            className="inline-flex items-center gap-2 rounded-lg bg-gray-600 px-4 py-2 text-sm font-medium text-white hover:bg-gray-500"
                        >
                            <TrashIcon className="h-4 w-4" />
                            Clear State
                        </button>
                    )}
                    {isRunning ? (
                        <button
                            onClick={stopRalph}
                            className="inline-flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-500"
                        >
                            <StopIcon className="h-4 w-4" />
                            Stop
                        </button>
                    ) : (
                        <button
                            onClick={startServerRalph}
                            disabled={!prd || startingRun}
                            className="inline-flex items-center gap-2 rounded-lg bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-500 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {startingRun ? (
                                <>
                                    <RefreshIcon className="h-4 w-4 animate-spin" />
                                    Starting...
                                </>
                            ) : (
                                <>
                                    <PlayIcon className="h-4 w-4" />
                                    Start Ralph
                                </>
                            )}
                        </button>
                    )}
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* PRD Builder Modal */}
                {showPRDBuilder && (
                    <PRDBuilder
                        onPRDComplete={handlePRDFromBuilder}
                        onCancel={() => setShowPRDBuilder(false)}
                    />
                )}

                {/* PRD Input Panel */}
                <div className="lg:col-span-1 space-y-4">
                    {/* PRD JSON Input */}
                    <div className="rounded-lg bg-white shadow-sm dark:bg-gray-800 dark:ring-1 dark:ring-white/10">
                        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
                            <h2 className="text-sm font-semibold text-gray-900 dark:text-white">PRD Configuration</h2>
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={() => setShowPRDBuilder(true)}
                                    disabled={isRunning}
                                    className="text-xs bg-purple-100 dark:bg-purple-900 text-purple-700 dark:text-purple-300 px-2 py-1 rounded hover:bg-purple-200 dark:hover:bg-purple-800 disabled:opacity-50"
                                >
                                    + Create PRD
                                </button>
                                <button
                                    onClick={loadExample}
                                    disabled={isRunning}
                                    className="text-xs text-purple-600 hover:text-purple-500 dark:text-purple-400 disabled:opacity-50"
                                >
                                    Load Example
                                </button>
                            </div>
                        </div>
                        <div className="p-4">
                            <textarea
                                value={prdJson}
                                onChange={(e) => handlePrdChange(e.target.value)}
                                placeholder='Paste your prd.json here or click "Create PRD" to use the builder...'
                                className="w-full h-64 p-3 text-xs font-mono bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg resize-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                                disabled={isRunning}
                            />
                            {error && (
                                <p className="mt-2 text-xs text-red-500">{error}</p>
                            )}
                        </div>
                    </div>

                    {/* Settings */}
                    <div className="rounded-lg bg-white shadow-sm dark:bg-gray-800 dark:ring-1 dark:ring-white/10">
                        <div className="p-4 border-b border-gray-200 dark:border-gray-700">
                            <h2 className="text-sm font-semibold text-gray-900 dark:text-white">Settings</h2>
                        </div>
                        <div className="p-4 space-y-4">
                            <div>
                                <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Codebase</label>
                                <select
                                    value={selectedCodebase}
                                    onChange={(e) => setSelectedCodebase(e.target.value)}
                                    disabled={isRunning}
                                    className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900"
                                >
                                    <option value="global">Global (Any Worker)</option>
                                    {codebases.map((cb: { id: string; name: string }) => (
                                        <option key={cb.id} value={cb.id}>{cb.name}</option>
                                    ))}
                                </select>
                            </div>
                            <div>
                                <div className="flex items-center justify-between mb-1">
                                    <label className="block text-xs text-gray-500 dark:text-gray-400">Model</label>
                                    <button
                                        onClick={loadAgents}
                                        disabled={loadingAgents || isRunning}
                                        className="text-xs text-purple-600 hover:text-purple-500 dark:text-purple-400 disabled:opacity-50"
                                    >
                                        {loadingAgents ? 'Loading...' : 'Refresh'}
                                    </button>
                                </div>
                                <select
                                    value={selectedModel}
                                    onChange={(e) => setSelectedModel(e.target.value)}
                                    disabled={isRunning || loadingAgents}
                                    className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900"
                                >
                                    <option value="">Any available model</option>
                                    {availableModels.map((model, idx) => (
                                        <option key={`${model}-${idx}`} value={model}>{model}</option>
                                    ))}
                                </select>
                                {availableModels.length === 0 && !loadingAgents && (
                                    <p className="mt-1 text-xs text-gray-500">No workers with models registered</p>
                                )}
                                {selectedModel && (
                                    <p className="mt-1 text-xs text-purple-500 dark:text-purple-400">
                                        Tasks will route to workers supporting: {selectedModel}
                                    </p>
                                )}
                            </div>
                            <div>
                                <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Max Iterations</label>
                                <input
                                    type="number"
                                    value={maxIterations}
                                    onChange={(e) => setMaxIterations(parseInt(e.target.value) || 10)}
                                    disabled={isRunning}
                                    min={1}
                                    max={50}
                                    className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900"
                                />
                            </div>
                            <div>
                                <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Run Mode</label>
                                <div className="flex gap-2">
                                    <button
                                        onClick={() => setRunMode('sequential')}
                                        disabled={isRunning}
                                        className={`flex-1 px-3 py-2 text-xs font-medium rounded-lg transition-colors ${
                                            runMode === 'sequential'
                                                ? 'bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300'
                                                : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'
                                        }`}
                                    >
                                        Sequential
                                    </button>
                                    <button
                                        onClick={() => setRunMode('parallel')}
                                        disabled={isRunning}
                                        className={`flex-1 px-3 py-2 text-xs font-medium rounded-lg transition-colors ${
                                            runMode === 'parallel'
                                                ? 'bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300'
                                                : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'
                                        }`}
                                    >
                                        Parallel
                                    </button>
                                </div>
                            </div>
                            {runMode === 'parallel' && (
                                <div>
                                    <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Max Parallel Workers</label>
                                    <input
                                        type="number"
                                        value={maxParallel}
                                        onChange={(e) => setMaxParallel(parseInt(e.target.value) || 3)}
                                        disabled={isRunning}
                                        min={1}
                                        max={10}
                                        className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900"
                                    />
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Stories Panel - Enhanced with Review/Feedback */}
                    {prd && (
                        <div className="rounded-lg bg-white shadow-sm dark:bg-gray-800 dark:ring-1 dark:ring-white/10">
                            <div className="p-4 border-b border-gray-200 dark:border-gray-700">
                                <div className="flex items-center justify-between">
                                    <h2 className="text-sm font-semibold text-gray-900 dark:text-white">User Stories</h2>
                                    <div className="flex items-center gap-2">
                                        <span className="text-xs text-gray-500 dark:text-gray-400">
                                            {passedCount}/{totalCount} passed
                                        </span>
                                        {!isRunning && passedCount < totalCount && (
                                            <button
                                                onClick={startRalph}
                                                className="text-xs px-2 py-1 bg-purple-600 text-white rounded hover:bg-purple-500"
                                            >
                                                Resume
                                            </button>
                                        )}
                                    </div>
                                </div>
                            </div>
                            <div className="divide-y divide-gray-200 dark:divide-gray-700 max-h-96 overflow-y-auto">
                                {prd.userStories.map((story) => (
                                    <StoryCard
                                        key={story.id}
                                        story={story}
                                        isActive={run?.currentStoryId === story.id}
                                        isRunning={isRunning}
                                        onRetry={async () => {
                                            // Reset story and retry
                                            setPrd(prev => prev ? {
                                                ...prev,
                                                userStories: prev.userStories.map(s =>
                                                    s.id === story.id ? { ...s, passes: false, taskId: undefined, taskStatus: undefined } : s
                                                )
                                            } : null)
                                            addLog('info', `Retrying ${story.id}...`, story.id)
                                        }}
                                        onViewTask={async () => {
                                            if (story.taskId) {
                                                // Fetch and show task details
                                                try {
                                                    const response = await fetch(`${API_URL}/v1/opencode/tasks/${story.taskId}`)
                                                    if (response.ok) {
                                                        const task = await response.json()
                                                        // Show result in logs
                                                        addLog('info', `--- ${story.id} Result ---`, story.id)
                                                        addLog('info', task.result?.slice(0, 500) || 'No result', story.id)
                                                    }
                                                } catch (e) {
                                                    addLog('error', `Failed to fetch task: ${e}`, story.id)
                                                }
                                            }
                                        }}
                                    />
                                ))}
                            </div>
                        </div>
                    )}
                </div>

                {/* Execution Panel */}
                <div className="lg:col-span-2">
                    <div className="rounded-lg bg-gray-900 shadow-sm overflow-hidden h-full flex flex-col">
                        {/* Terminal Header */}
                        <div className="flex items-center justify-between px-4 py-3 bg-gray-800 border-b border-gray-700">
                            <div className="flex items-center gap-2">
                                <div className="flex gap-1.5">
                                    <div className="h-3 w-3 rounded-full bg-red-500" />
                                    <div className="h-3 w-3 rounded-full bg-yellow-500" />
                                    <div className="h-3 w-3 rounded-full bg-green-500" />
                                </div>
                                <span className="ml-3 text-sm text-gray-400 font-mono">
                                    Ralph + RLM Loop
                                    {prd && ` — ${prd.project}`}
                                </span>
                            </div>
                            <div className="flex items-center gap-4">
                                {isRunning && (
                                    <div className="flex items-center gap-2 text-xs text-purple-400">
                                        <div className="h-2 w-2 rounded-full bg-purple-500 animate-pulse" />
                                        Running iteration {run?.currentIteration || 0}/{maxIterations}
                                    </div>
                                )}
                                {run && !isRunning && (
                                    <span className={`text-xs px-2 py-1 rounded ${getStatusColor(run.status)}`}>
                                        {run.status}
                                    </span>
                                )}
                            </div>
                        </div>

                        {/* Stats Bar */}
                        {run && (
                            <div className="flex items-center gap-6 px-4 py-2 bg-gray-800/50 border-b border-gray-700 text-xs font-mono">
                                <div>
                                    <span className="text-gray-500">Iteration: </span>
                                    <span className="text-purple-400">{run.currentIteration}/{run.maxIterations}</span>
                                </div>
                                <div>
                                    <span className="text-gray-500">Passed: </span>
                                    <span className="text-emerald-400">{passedCount}/{totalCount}</span>
                                </div>
                                <div>
                                    <span className="text-gray-500">RLM: </span>
                                    <span className="text-pink-400">
                                        {run.rlmCompressions > 0 ? `${run.rlmCompressions} compressions` : 'standby'}
                                    </span>
                                </div>
                                {run.startedAt && (
                                    <div>
                                        <span className="text-gray-500">Duration: </span>
                                        <span className="text-cyan-400">
                                            {Math.round((Date.now() - new Date(run.startedAt).getTime()) / 1000)}s
                                        </span>
                                    </div>
                                )}
                            </div>
                        )}

                        {/* Logs */}
                        <div ref={logsRef} className="flex-1 overflow-y-auto p-4 min-h-[400px] max-h-[600px]">
                            {!run && (
                                <div className="flex flex-col items-center justify-center h-full text-gray-500 text-sm">
                                    <p>Paste a prd.json and click &quot;Start Ralph&quot;</p>
                                    <p className="text-xs mt-2 text-gray-600">
                                        Ralph will create A2A tasks for each story and monitor their completion
                                    </p>
                                </div>
                            )}
                            {run?.logs.map((log) => (
                                <div key={log.id} className="flex gap-2 py-1 font-mono text-xs">
                                    <span className="text-gray-600 shrink-0">
                                        {new Date(log.timestamp).toLocaleTimeString()}
                                    </span>
                                    <span className={getLogColor(log.type)}>
                                        {getLogIcon(log.type)}
                                    </span>
                                    <span className={getLogColor(log.type)}>
                                        {log.storyId && <span className="text-gray-500">[{log.storyId}] </span>}
                                        {log.message}
                                    </span>
                                </div>
                            ))}
                            {isRunning && (
                                <div className="flex items-center gap-2 py-2 text-purple-400 text-xs font-mono">
                                    <div className="flex gap-1">
                                        <span className="h-2 w-2 rounded-full bg-purple-500 animate-pulse" />
                                    </div>
                                    <span>Live streaming from worker...</span>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>

            {/* Server-Side Ralph Runs */}
            <ServerRalphRuns />

            {/* Active Tasks */}
            {tasks.length > 0 && (
                <div className="rounded-lg bg-white shadow-sm dark:bg-gray-800 dark:ring-1 dark:ring-white/10">
                    <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
                        <h2 className="text-sm font-semibold text-gray-900 dark:text-white">Ralph Tasks</h2>
                        <button
                            onClick={loadTasks}
                            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
                        >
                            <RefreshIcon className="h-4 w-4" />
                        </button>
                    </div>
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead className="bg-gray-50 dark:bg-gray-700">
                                <tr>
                                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400">Task</th>
                                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400">Story</th>
                                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400">Status</th>
                                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400">Created</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                                {tasks.slice(0, 10).map((task) => (
                                    <tr key={task.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                                        <td className="px-4 py-2 text-gray-900 dark:text-white font-mono text-xs">
                                            {task.id.slice(0, 8)}...
                                        </td>
                                        <td className="px-4 py-2 text-gray-600 dark:text-gray-400">
                                            {task.title?.replace('Ralph: ', '') || 'Unknown'}
                                        </td>
                                        <td className="px-4 py-2">
                                            <span className={`px-2 py-0.5 text-xs rounded-full ${getStatusColor(task.status)}`}>
                                                {task.status}
                                            </span>
                                        </td>
                                        <td className="px-4 py-2 text-gray-500 dark:text-gray-400 text-xs">
                                            {new Date(task.created_at).toLocaleTimeString()}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}
        </div>
    )
}

// ============================================================================
// Server-Side Ralph Runs Component
// ============================================================================

interface ServerRalphRun {
    id: string
    prd: {
        project: string
        branchName: string
        userStories: Array<{ id: string; title: string }>
    }
    status: string
    current_iteration: number
    max_iterations: number
    story_results: Array<{ story_id: string; status: string }>
    created_at: string
    started_at?: string
    completed_at?: string
    error?: string
}

function ServerRalphRuns() {
    const [runs, setRuns] = useState<ServerRalphRun[]>([])
    const [loading, setLoading] = useState(false)
    const [expanded, setExpanded] = useState<string | null>(null)
    const [logs, setLogs] = useState<Record<string, Array<{id: string; timestamp: string; type: string; message: string; story_id?: string}>>>({})
    const [loadingLogs, setLoadingLogs] = useState<string | null>(null)

    const loadRuns = useCallback(async () => {
        setLoading(true)
        try {
            const response = await fetch(`${API_URL}/v1/ralph/runs?limit=20`)
            if (response.ok) {
                const data = await response.json()
                setRuns(data)
            }
        } catch (err) {
            console.error('Failed to load Ralph runs:', err)
        } finally {
            setLoading(false)
        }
    }, [])

    // Load logs for a specific run
    const loadLogs = useCallback(async (runId: string) => {
        setLoadingLogs(runId)
        try {
            const response = await fetch(`${API_URL}/v1/ralph/runs/${runId}/logs?limit=50`)
            if (response.ok) {
                const data = await response.json()
                setLogs(prev => ({ ...prev, [runId]: data }))
            }
        } catch (err) {
            console.error('Failed to load logs:', err)
        } finally {
            setLoadingLogs(null)
        }
    }, [])

    // Cancel a running run
    const cancelRun = useCallback(async (runId: string) => {
        try {
            const response = await fetch(`${API_URL}/v1/ralph/runs/${runId}/cancel`, { method: 'POST' })
            if (response.ok) {
                loadRuns()
            }
        } catch (err) {
            console.error('Failed to cancel run:', err)
        }
    }, [loadRuns])

    // Delete a run
    const deleteRun = useCallback(async (runId: string) => {
        if (!confirm('Delete this Ralph run? This cannot be undone.')) return
        try {
            const response = await fetch(`${API_URL}/v1/ralph/runs/${runId}`, { method: 'DELETE' })
            if (response.ok) {
                loadRuns()
            }
        } catch (err) {
            console.error('Failed to delete run:', err)
        }
    }, [loadRuns])

    useEffect(() => {
        loadRuns()
    }, [loadRuns])

    // Auto-refresh when there are running tasks
    useEffect(() => {
        const hasRunning = runs.some(r => r.status === 'running' || r.status === 'pending')
        if (hasRunning) {
            const interval = setInterval(loadRuns, 5000)
            return () => clearInterval(interval)
        }
    }, [runs, loadRuns])

    // Load logs when expanding a run
    useEffect(() => {
        if (expanded && !logs[expanded]) {
            loadLogs(expanded)
        }
    }, [expanded, logs, loadLogs])

    const getRunStatusColor = (status: string) => {
        switch (status) {
            case 'completed': return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300'
            case 'running': return 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
            case 'failed': return 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300'
            case 'cancelled': return 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'
            case 'pending': return 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300'
            default: return 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'
        }
    }

    const getProgress = (run: ServerRalphRun) => {
        const passed = run.story_results?.filter(r => r.status === 'passed').length || 0
        const total = run.prd?.userStories?.length || 0
        return { passed, total }
    }

    return (
        <div className="rounded-lg bg-white shadow-sm dark:bg-gray-800 dark:ring-1 dark:ring-white/10">
            <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
                <h2 className="text-sm font-semibold text-gray-900 dark:text-white">
                    Ralph Run History
                </h2>
                <button
                    onClick={loadRuns}
                    disabled={loading}
                    className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 disabled:opacity-50"
                >
                    <RefreshIcon className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                </button>
            </div>
            {runs.length === 0 ? (
                <div className="p-8 text-center text-gray-500 dark:text-gray-400">
                    <p className="text-sm">No Ralph runs yet</p>
                    <p className="text-xs mt-1">Configure a PRD above and click "Start Ralph" to begin</p>
                </div>
            ) : (
            <div className="divide-y divide-gray-200 dark:divide-gray-700">
                {runs.map((run) => {
                    const { passed, total } = getProgress(run)
                    const isExpanded = expanded === run.id
                    
                    return (
                        <div key={run.id} className="p-4">
                            <div 
                                className="flex items-center justify-between cursor-pointer"
                                onClick={() => setExpanded(isExpanded ? null : run.id)}
                            >
                                <div className="flex items-center gap-3">
                                    <span className="text-lg">
                                        {run.status === 'completed' && passed === total ? '✅' : 
                                         run.status === 'running' ? '⏳' :
                                         run.status === 'failed' ? '❌' :
                                         run.status === 'cancelled' ? '🛑' : '○'}
                                    </span>
                                    <div>
                                        <div className="font-medium text-gray-900 dark:text-white">
                                            {run.prd?.project || 'Unknown Project'}
                                        </div>
                                        <div className="text-xs text-gray-500 dark:text-gray-400">
                                            {run.prd?.branchName} • {passed}/{total} stories
                                        </div>
                                    </div>
                                </div>
                                <div className="flex items-center gap-3">
                                    <span className={`px-2 py-1 text-xs rounded-full ${getRunStatusColor(run.status)}`}>
                                        {run.status}
                                    </span>
                                    <span className="text-xs text-gray-500 dark:text-gray-400">
                                        {new Date(run.created_at).toLocaleString()}
                                    </span>
                                    <svg 
                                        className={`w-4 h-4 text-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                                        fill="none" viewBox="0 0 24 24" stroke="currentColor"
                                    >
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                    </svg>
                                </div>
                            </div>
                            
                            {isExpanded && (
                                <div className="mt-3 pl-9 space-y-3">
                                    <div className="flex items-center justify-between">
                                        <div className="text-xs text-gray-600 dark:text-gray-400">
                                            <span className="font-medium">Run ID:</span> {run.id}
                                        </div>
                                        <div className="flex items-center gap-2">
                                            {(run.status === 'running' || run.status === 'pending') && (
                                                <button
                                                    onClick={(e) => { e.stopPropagation(); cancelRun(run.id) }}
                                                    className="text-xs px-2 py-1 bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300 rounded hover:bg-yellow-200 dark:hover:bg-yellow-800"
                                                >
                                                    Cancel
                                                </button>
                                            )}
                                            <button
                                                onClick={(e) => { e.stopPropagation(); deleteRun(run.id) }}
                                                className="text-xs px-2 py-1 bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300 rounded hover:bg-red-200 dark:hover:bg-red-800"
                                            >
                                                Delete
                                            </button>
                                        </div>
                                    </div>
                                    {run.error && (
                                        <div className="text-xs text-red-600 dark:text-red-400">
                                            <span className="font-medium">Error:</span> {run.error}
                                        </div>
                                    )}
                                    
                                    {/* Stories */}
                                    <div className="text-xs font-medium text-gray-700 dark:text-gray-300">Stories:</div>
                                    <div className="space-y-1">
                                        {run.prd?.userStories?.map((story) => {
                                            const result = run.story_results?.find(r => r.story_id === story.id)
                                            return (
                                                <div key={story.id} className="flex items-center gap-2 text-xs">
                                                    <span>
                                                        {result?.status === 'passed' ? '✅' :
                                                         result?.status === 'failed' ? '❌' :
                                                         result?.status === 'running' ? '⏳' : '○'}
                                                    </span>
                                                    <span className="font-mono text-gray-600 dark:text-gray-400">{story.id}</span>
                                                    <span className="text-gray-700 dark:text-gray-300">{story.title}</span>
                                                </div>
                                            )
                                        })}
                                    </div>
                                    
                                    {/* Logs Section */}
                                    <div className="mt-3">
                                        <div className="flex items-center justify-between mb-2">
                                            <div className="text-xs font-medium text-gray-700 dark:text-gray-300">Logs:</div>
                                            <button
                                                onClick={(e) => { e.stopPropagation(); loadLogs(run.id) }}
                                                disabled={loadingLogs === run.id}
                                                className="text-xs text-purple-600 hover:text-purple-500 dark:text-purple-400 disabled:opacity-50"
                                            >
                                                {loadingLogs === run.id ? 'Loading...' : 'Refresh'}
                                            </button>
                                        </div>
                                        <div className="bg-gray-900 rounded p-2 max-h-48 overflow-y-auto font-mono text-xs">
                                            {(!logs[run.id] || logs[run.id].length === 0) ? (
                                                <div className="text-gray-500">No logs yet</div>
                                            ) : (
                                                logs[run.id].map((log) => (
                                                    <div key={log.id} className="flex gap-2 py-0.5">
                                                        <span className="text-gray-600 shrink-0">
                                                            {new Date(log.timestamp).toLocaleTimeString()}
                                                        </span>
                                                        <span className={
                                                            log.type === 'story_pass' ? 'text-emerald-400' :
                                                            log.type === 'story_fail' || log.type === 'error' ? 'text-red-400' :
                                                            log.type === 'complete' ? 'text-emerald-400' :
                                                            log.type === 'story_start' ? 'text-yellow-400' :
                                                            'text-gray-400'
                                                        }>
                                                            {log.story_id && <span className="text-gray-500">[{log.story_id}] </span>}
                                                            {log.message}
                                                        </span>
                                                    </div>
                                                ))
                                            )}
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    )
                })}
            </div>
            )}
        </div>
    )
}
