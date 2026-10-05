'use client'

import { RalphRefreshIcon } from '../ui/RalphIcons'

interface RalphSettingsPanelProps {
    workspaces?: Array<{ id: string; name: string }>
    selectedWorkspace?: string
    selectedModel: string
    maxIterations: number
    runMode: 'sequential' | 'parallel'
    maxParallel: number
    availableModels: string[]
    loadingAgents: boolean
    isRunning: boolean
    onSetSelectedWorkspace?: (v: string) => void
    onSetSelectedModel: (v: string) => void
    onSetMaxIterations: (v: number) => void
    onSetRunMode: (m: 'sequential' | 'parallel') => void
    onSetMaxParallel: (v: number) => void
    onRefreshAgents: () => void
    // Backward-compat props while migration completes.
    codebases?: Array<{ id: string; name: string }>
    selectedCodebase?: string
    onSetSelectedCodebase?: (v: string) => void
}

export function RalphSettingsPanel({
    workspaces,
    selectedWorkspace,
    selectedModel,
    maxIterations,
    runMode,
    maxParallel,
    availableModels,
    loadingAgents,
    isRunning,
    onSetSelectedWorkspace,
    onSetSelectedModel,
    onSetMaxIterations,
    onSetRunMode,
    onSetMaxParallel,
    onRefreshAgents,
    codebases,
    selectedCodebase,
    onSetSelectedCodebase,
}: RalphSettingsPanelProps) {
    const workspaceOptions = workspaces ?? codebases ?? []
    const activeWorkspace = selectedWorkspace ?? selectedCodebase ?? 'global'
    const setWorkspace = onSetSelectedWorkspace ?? onSetSelectedCodebase

    return (
        <div className="rounded-lg bg-white shadow-sm dark:bg-gray-800 dark:ring-1 dark:ring-white/10" data-cy="ralph-settings-panel">
            <div className="p-4 border-b"><h2 className="text-sm font-semibold" data-cy="ralph-settings-title">Settings</h2></div>
            <div className="p-4 space-y-4">
                <div>
                    <label className="block text-xs mb-1">Workspace</label>
                    <select value={activeWorkspace} onChange={(e) => setWorkspace?.(e.target.value)} disabled={isRunning} data-cy="ralph-workspace-select" className="w-full px-3 py-2 text-sm border rounded-lg bg-white dark:bg-gray-900">
                        <option value="global">Global workspace</option>
                        {workspaceOptions.map(cb => <option key={cb.id} value={cb.id}>{cb.name}</option>)}
                    </select>
                </div>
                <div>
                    <div className="flex justify-between mb-1">
                        <label className="block text-xs">Model</label>
                        <button onClick={onRefreshAgents} disabled={loadingAgents || isRunning} data-cy="ralph-refresh-models-btn" className="text-xs text-purple-600">{loadingAgents ? 'Loading...' : 'Refresh'}</button>
                    </div>
                    <select value={selectedModel} onChange={(e) => onSetSelectedModel(e.target.value)} disabled={isRunning || loadingAgents} data-cy="ralph-model-select" className="w-full px-3 py-2 text-sm border rounded-lg bg-white dark:bg-gray-900">
                        <option value="">Any</option>
                        {availableModels.map((m, i) => <option key={`${m}-${i}`} value={m}>{m}</option>)}
                    </select>
                </div>
                <div>
                    <label className="block text-xs mb-1">Max Iterations</label>
                    <input type="number" value={maxIterations} onChange={(e) => onSetMaxIterations(parseInt(e.target.value) || 10)} disabled={isRunning} min={1} max={50} data-cy="ralph-max-iterations-input" className="w-full px-3 py-2 text-sm border rounded-lg bg-white dark:bg-gray-900" />
                </div>
                <div>
                    <label className="block text-xs mb-1">Run Mode</label>
                    <div className="flex gap-2">
                        <button onClick={() => onSetRunMode('sequential')} disabled={isRunning} data-cy="ralph-sequential-btn" className={`flex-1 px-3 py-2 text-xs rounded ${runMode === 'sequential' ? 'bg-purple-100 text-purple-700' : 'bg-gray-100'}`}>Sequential</button>
                        <button onClick={() => onSetRunMode('parallel')} disabled={isRunning} data-cy="ralph-parallel-btn" className={`flex-1 px-3 py-2 text-xs rounded ${runMode === 'parallel' ? 'bg-purple-100 text-purple-700' : 'bg-gray-100'}`}>Parallel</button>
                    </div>
                </div>
                {runMode === 'parallel' && <div>
                    <label className="block text-xs mb-1">Max Parallel Workers</label>
                    <input type="number" value={maxParallel} onChange={(e) => onSetMaxParallel(parseInt(e.target.value) || 3)} disabled={isRunning} min={1} max={10} data-cy="ralph-max-parallel-input" className="w-full px-3 py-2 text-sm border rounded-lg bg-white dark:bg-gray-900" />
                </div>}
            </div>
        </div>
    )
}
