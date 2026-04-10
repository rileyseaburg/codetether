'use client'

import React, { useState, useEffect } from 'react'
import { useSession } from 'next-auth/react'
import { useRalphStore, useAvailableModels, usePassedCount, useTotalCount } from './store'
import { useWorkspaces } from '../sessions/hooks/useWorkspaces'
import { RalphHeader } from '@/components/Ralph/RalphHeader'
import { RalphPRDConfigPanel } from '@/components/Ralph/RalphPRDConfigPanel'
import { RalphSettingsPanel } from '@/components/Ralph/RalphSettingsPanel'
import { RalphStoriesPanel } from '@/components/Ralph/RalphStoriesPanel'
import { RalphLogViewer } from '@/components/Ralph/RalphLogViewer'
import { ServerRalphRuns } from '@/components/Ralph/ServerRalphRuns'
import { RalphTasksTable } from '@/components/Ralph/RalphTasksTable'
import { PRDChatHistory } from './PRDChatHistory'
import { useRalphHooks } from './RalphPageHooks'
import { getTaskV1AgentTasksTaskIdGet, hasApiAuthToken } from '@/lib/api'

export default function RalphPage() {
    const store = useRalphStore()
    const { workspaces } = useWorkspaces()
    const availableModels = useAvailableModels()
    const passedCount = usePassedCount()
    const totalCount = useTotalCount()
    const [prdBuilderMode, setPrdBuilderMode] = useState<'ai' | 'manual'>('ai')
    const [startingRun, setStartingRun] = useState(false)
    const [resumeSession, setResumeSession] = useState<{ sessionId: string; title: string; messages: Array<{ role: 'user' | 'assistant'; content: string; timestamp: string }> } | null>(null)
    const { handlePrdChange, handlePRDFromBuilder, startServerRalph, loadAgents, loadTasks } = useRalphHooks(store)
    const { data: session } = useSession()

    // Load agents/models on mount (only once, after auth is ready)
    const loadAgentsRef = React.useRef(loadAgents)
    loadAgentsRef.current = loadAgents
    useEffect(() => {
        if (!session?.accessToken && !hasApiAuthToken()) return
        loadAgentsRef.current()
    }, [session?.accessToken])

    return (
        <div className="space-y-6">
            <RalphHeader isRunning={store.isRunning} hasPRDOrRun={!!(store.prd || store.run)} hasPRD={!!store.prd} startingRun={startingRun} onClear={store.reset} onStop={() => { store.setIsRunning(false); store.setRun(p => p ? { ...p, status: 'paused' } : null) }} onStart={startServerRalph} />
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-1 space-y-4">
                    <RalphPRDConfigPanel prdJson={store.prdJson} error={store.error} isRunning={store.isRunning} showBuilder={store.showPRDBuilder} builderMode={store.showPRDBuilder ? prdBuilderMode : 'manual'} prdBuilderMode={prdBuilderMode} resumeSession={resumeSession} onChange={handlePrdChange} onLoadExample={() => { const prd = { project: "MyApp", branchName: "ralph/new-feature", description: "Add feature", userStories: [{ id: "US-001", title: "Feature", description: "As user", acceptanceCriteria: ["Done"], priority: 1, passes: false }] }; store.setPrdJson(JSON.stringify(prd, null, 2)); store.setPrd(prd); store.setError(null) }} onBuilderComplete={handlePRDFromBuilder} onSetShowBuilder={store.setShowPRDBuilder} onSetBuilderMode={setPrdBuilderMode} onSetPrdBuilderMode={setPrdBuilderMode} onClearResumeSession={() => setResumeSession(null)} />
                    <RalphSettingsPanel workspaces={workspaces} selectedWorkspace={store.selectedCodebase} selectedModel={store.selectedModel} maxIterations={store.maxIterations} runMode={store.runMode} maxParallel={store.maxParallel} availableModels={availableModels} loadingAgents={store.loadingAgents} isRunning={store.isRunning} onSetSelectedWorkspace={store.setSelectedCodebase} onSetSelectedModel={store.setSelectedModel} onSetMaxIterations={store.setMaxIterations} onSetRunMode={store.setRunMode} onSetMaxParallel={store.setMaxParallel} onRefreshAgents={loadAgents} />
                    <PRDChatHistory onContinueSession={(sessionId, sessionTitle, messages) => {
                        setResumeSession({ sessionId, title: sessionTitle, messages })
                        setPrdBuilderMode('ai')
                        store.setShowPRDBuilder(true)
                    }} />
                    <RalphStoriesPanel prd={store.prd} run={store.run} passedCount={passedCount} totalCount={totalCount} isRunning={store.isRunning} onResume={startServerRalph} onRetryStory={(id) => store.setPrd(p => p ? { ...p, userStories: p.userStories.map(s => s.id === id ? { ...s, passes: false, taskId: undefined, taskStatus: undefined } : s) } : null)} onViewTask={async (id) => { const story = store.prd?.userStories.find(s => s.id === id); if (story?.taskId) { try { const { data: task } = await getTaskV1AgentTasksTaskIdGet({ path: { task_id: story.taskId } }); if (task) { const taskData = task as { result_summary?: string }; store.setRun(p => p ? { ...p, logs: [...p.logs, { id: crypto.randomUUID(), timestamp: new Date().toISOString(), type: 'info', message: `--- ${id} ---`, storyId: id }, { id: crypto.randomUUID(), timestamp: new Date().toISOString(), type: 'info', message: taskData.result_summary?.slice(0, 500) || 'No result', storyId: id }] } : null) } } catch { } } }} />
                </div>
                <div className="lg:col-span-2"><RalphLogViewer run={store.run} prd={store.prd} isRunning={store.isRunning} maxIterations={store.maxIterations} /></div>
            </div>
            <ServerRalphRuns />
            <RalphTasksTable tasks={store.tasks} onRefresh={loadTasks} />
        </div>
    )
}
