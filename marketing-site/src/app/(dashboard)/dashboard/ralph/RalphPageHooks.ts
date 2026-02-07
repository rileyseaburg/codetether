'use client'

import { useCallback } from 'react'
import {
    listWorkersV1AgentWorkersGet,
    createRalphRunV1RalphRunsPost,
    listAllTasksV1AgentTasksGet,
} from '@/lib/api'
import type { PRD, RalphState, Task as StoreTask } from './store'

interface WorkerModel {
    id?: string
    name?: string
    provider?: string
    provider_id?: string
    providerID?: string
    modelID?: string
}

interface Worker {
    name?: string
    worker_id?: string
    models?: (string | WorkerModel)[]
}

export function useRalphHooks(store: RalphState) {
    const handlePrdChange = useCallback((json: string) => {
        store.setPrdJson(json)
        store.setError(null)
        try {
            if (json.trim()) {
                const parsed = JSON.parse(json)
                if (!parsed.project || !parsed.branchName || !parsed.userStories) throw new Error('Invalid PRD')
                store.setPrd(parsed)
            } else {
                store.setPrd(null)
            }
        } catch {
            if (json.trim()) store.setError('Invalid JSON')
        }
    }, [store])

    const handlePRDFromBuilder = useCallback((newPrd: PRD) => {
        store.setPrd(newPrd)
        store.setPrdJson(JSON.stringify(newPrd, null, 2))
        store.setShowPRDBuilder(false)
        store.setError(null)
    }, [store])

    const loadAgents = useCallback(async () => {
        store.setLoadingAgents(true)
        try {
            const { data: workers } = await listWorkersV1AgentWorkersGet()
            if (workers && Array.isArray(workers)) {
                store.setAgents((workers as unknown as Worker[]).map((w: Worker) => ({
                    name: w.name || '',
                    role: 'worker',
                    instance_id: w.worker_id || '',
                    models_supported: (w.models || []).map((m: string | WorkerModel) => {
                        if (typeof m === 'string') return m
                        // Handle multiple API response formats
                        const provider = m.provider || m.provider_id || m.providerID || ''
                        const model = m.name || m.id || m.modelID || ''
                        return provider && model ? `${provider}:${model}` : model || provider || ''
                    }).filter(Boolean),
                })))
            }
        } finally {
            store.setLoadingAgents(false)
        }
    }, [store])

    const startServerRalph = useCallback(async () => {
        if (!store.prd) return
        try {
            const run = {
                id: 'pending',
                prd: store.prd,
                status: 'running' as const,
                currentIteration: 0,
                maxIterations: store.maxIterations,
                startedAt: new Date().toISOString(),
                logs: [{ id: crypto.randomUUID(), timestamp: new Date().toISOString(), type: 'info' as const, message: 'Starting...' }],
                rlmCompressions: 0,
                tokensSaved: 0,
            }
            store.setRun(run)
            
            const { data } = await createRalphRunV1RalphRunsPost({
                body: {
                    prd: {
                        project: store.prd.project,
                        branchName: store.prd.branchName,
                        description: store.prd.description,
                        userStories: store.prd.userStories.map((s) => ({
                            id: s.id,
                            title: s.title,
                            description: s.description,
                            acceptanceCriteria: s.acceptanceCriteria,
                            priority: s.priority,
                        })),
                    },
                    codebase_id: store.selectedCodebase === 'global' ? undefined : store.selectedCodebase,
                    model: store.selectedModel || undefined,
                    max_iterations: store.maxIterations,
                    run_mode: store.runMode,
                    max_parallel: store.maxParallel,
                },
            })
            
            if (data?.id) {
                store.setRun(p => p ? { ...p, id: data.id } : null)
            }
        } catch {
            store.setError('Failed to start Ralph')
        }
    }, [store])

    const loadTasks = useCallback(async () => {
        try {
            const { data: tasks } = await listAllTasksV1AgentTasksGet()
            if (tasks && Array.isArray(tasks)) {
                store.setTasks((tasks as unknown as StoreTask[]).filter((t: StoreTask) =>
                    (t.metadata as { ralph?: boolean })?.ralph || t.title?.startsWith('Ralph:')
                ))
            }
        } catch {}
    }, [store])

    return { handlePrdChange, handlePRDFromBuilder, loadAgents, startServerRalph, loadTasks }
}
