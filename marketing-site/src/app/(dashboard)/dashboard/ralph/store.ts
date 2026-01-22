import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { useShallow } from 'zustand/react/shallow'

// ============================================================================
// Types
// ============================================================================

export interface UserStory {
    id: string
    title: string
    description: string
    acceptanceCriteria: string[]
    priority: number
    passes: boolean
    notes?: string
    taskId?: string
    taskStatus?: string
}

export interface PRD {
    project: string
    branchName: string
    description: string
    userStories: UserStory[]
}

export interface RalphLogEntry {
    id: string
    timestamp: string
    type: 'info' | 'story_start' | 'story_pass' | 'story_fail' | 'code' | 'check' | 'commit' | 'rlm' | 'error' | 'complete' | 'tool' | 'ai' | 'waiting'
    message: string
    storyId?: string
}

export interface RalphRun {
    id: string
    prd: PRD
    status: 'idle' | 'running' | 'paused' | 'completed' | 'failed'
    currentIteration: number
    maxIterations: number
    startedAt?: string
    completedAt?: string
    currentStoryId?: string
    logs: RalphLogEntry[]
    rlmCompressions: number
    tokensSaved: number
}

export interface Agent {
    name: string
    role: string
    instance_id?: string
    description?: string
    url?: string
    models_supported?: string[]
    last_seen?: string
}

export interface Task {
    id: string
    title?: string
    prompt?: string
    agent_type: string
    status: string
    created_at: string
    result?: string
    codebase_id?: string
    metadata?: Record<string, unknown>
}

// ============================================================================
// Store State
// ============================================================================

interface RalphState {
    // PRD
    prd: PRD | null
    prdJson: string
    
    // Run state
    run: RalphRun | null
    isRunning: boolean
    tasks: Task[]
    
    // Settings
    selectedCodebase: string
    selectedModel: string
    selectedAgentMode: 'build' | 'plan' | 'general' | 'explore'
    maxIterations: number
    runMode: 'sequential' | 'parallel'
    maxParallel: number
    
    // Agents/Models
    agents: Agent[]
    loadingAgents: boolean
    
    // UI state
    error: string | null
    showPRDBuilder: boolean
    
    // Actions
    setPrd: (prd: PRD | null | ((prev: PRD | null) => PRD | null)) => void
    setPrdJson: (json: string) => void
    setRun: (run: RalphRun | null | ((prev: RalphRun | null) => RalphRun | null)) => void
    setIsRunning: (running: boolean) => void
    setTasks: (tasks: Task[]) => void
    setSelectedCodebase: (codebase: string) => void
    setSelectedModel: (model: string) => void
    setSelectedAgentMode: (mode: 'build' | 'plan' | 'general' | 'explore') => void
    setMaxIterations: (iterations: number) => void
    setRunMode: (mode: 'sequential' | 'parallel') => void
    setMaxParallel: (max: number) => void
    setAgents: (agents: Agent[]) => void
    setLoadingAgents: (loading: boolean) => void
    setError: (error: string | null) => void
    setShowPRDBuilder: (show: boolean) => void
    
    // Complex actions
    addLog: (type: RalphLogEntry['type'], message: string, storyId?: string) => void
    updateStoryStatus: (storyId: string, updates: Partial<UserStory>) => void
    reset: () => void
}

// ============================================================================
// Initial State
// ============================================================================

const initialState = {
    prd: null,
    prdJson: '',
    run: null,
    isRunning: false,
    tasks: [],
    selectedCodebase: 'global',
    selectedModel: '',
    selectedAgentMode: 'build' as const,
    maxIterations: 10,
    runMode: 'sequential' as const,
    maxParallel: 3,
    agents: [],
    loadingAgents: false,
    error: null,
    showPRDBuilder: false,
}

// ============================================================================
// Store
// ============================================================================

// UUID generator
function generateUUID(): string {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
        return crypto.randomUUID()
    }
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
        const r = Math.random() * 16 | 0
        const v = c === 'x' ? r : (r & 0x3 | 0x8)
        return v.toString(16)
    })
}

export const useRalphStore = create<RalphState>()(
    persist(
        (set, get) => ({
            ...initialState,
    
            // Simple setters
            setPrd: (prdOrFn) => set((state) => ({
                prd: typeof prdOrFn === 'function' ? prdOrFn(state.prd) : prdOrFn
            })),
            setPrdJson: (prdJson) => set({ prdJson }),
            setRun: (runOrFn) => set((state) => ({
                run: typeof runOrFn === 'function' ? runOrFn(state.run) : runOrFn
            })),
            setIsRunning: (isRunning) => set({ isRunning }),
            setTasks: (tasks) => set({ tasks }),
            setSelectedCodebase: (selectedCodebase) => set({ selectedCodebase }),
            setSelectedModel: (selectedModel) => set({ selectedModel }),
            setSelectedAgentMode: (selectedAgentMode) => set({ selectedAgentMode }),
            setMaxIterations: (maxIterations) => set({ maxIterations }),
            setRunMode: (runMode) => set({ runMode }),
            setMaxParallel: (maxParallel) => set({ maxParallel }),
            setAgents: (agents) => set({ agents }),
            setLoadingAgents: (loadingAgents) => set({ loadingAgents }),
            setError: (error) => set({ error }),
            setShowPRDBuilder: (showPRDBuilder) => set({ showPRDBuilder }),
    
            // Add log entry
            addLog: (type, message, storyId) => {
                const entry: RalphLogEntry = {
            id: generateUUID(),
            timestamp: new Date().toISOString(),
            type,
            message,
            storyId
        }
        set((state) => ({
            run: state.run ? { ...state.run, logs: [...state.run.logs, entry] } : null
        }))
    },
    
    // Update story status
    updateStoryStatus: (storyId, updates) => {
        const { prd } = get()
        if (!prd) return
        
        set({
            prd: {
                ...prd,
                userStories: prd.userStories.map(s => 
                    s.id === storyId ? { ...s, ...updates } : s
                )
            }
        })
        },
    
            // Reset to initial state
            reset: () => set(initialState),
        }),
        {
            name: 'ralph-storage',
            // Only persist these fields (not transient state like loadingAgents)
            partialize: (state) => ({
                prd: state.prd,
                prdJson: state.prdJson,
                run: state.run,
                isRunning: state.isRunning,
                selectedCodebase: state.selectedCodebase,
                selectedModel: state.selectedModel,
                maxIterations: state.maxIterations,
                runMode: state.runMode,
                maxParallel: state.maxParallel,
            }),
        }
    )
)

// ============================================================================
// Selectors - use these with useShallow to prevent infinite loops
// ============================================================================

export const selectAvailableModels = (state: RalphState): string[] => {
    const modelSet = new Set<string>()
    for (const agent of state.agents) {
        if (agent.models_supported && Array.isArray(agent.models_supported)) {
            for (const model of agent.models_supported) {
                // Ensure model is a string, not an object
                if (typeof model === 'string' && model.trim()) {
                    modelSet.add(model)
                }
            }
        }
    }
    return Array.from(modelSet).sort()
}

export const selectPassedCount = (state: RalphState): number => {
    return state.prd?.userStories.filter(s => s.passes).length || 0
}

export const selectTotalCount = (state: RalphState): number => {
    return state.prd?.userStories.length || 0
}

// ============================================================================
// Hooks with shallow comparison (prevents infinite re-renders)
// ============================================================================

export const useAvailableModels = () => useRalphStore(useShallow(selectAvailableModels))
export const usePassedCount = () => useRalphStore(selectPassedCount)
export const useTotalCount = () => useRalphStore(selectTotalCount)
