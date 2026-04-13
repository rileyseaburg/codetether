// SwarmMonitor Component
// Real-time swarm execution monitoring

import { PlayIcon, StopIcon } from './Icons'
import {
    getSwarmRunStatusClasses,
    getSwarmSubtaskStatusClasses,
    getSwarmSubtaskStatusLabel,
} from '../utils'
import type { SwarmMonitorState, SwarmSubtaskStatus } from '../types'

interface SwarmMonitorProps {
    monitor: SwarmMonitorState
    onStart: () => void
    onStop: () => void
}

export function SwarmMonitor({ monitor, onStart, onStop }: SwarmMonitorProps) {
    const isRunning = monitor.status === 'running'
    const isCompleted = monitor.status === 'completed'
    const isFailed = monitor.status === 'failed'

    return (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
            <div className="flex items-center justify-between mb-4">
                <h3 className="font-medium text-gray-900 dark:text-white">Swarm Monitor</h3>
                <div className="flex items-center gap-3">
                    <span className={`px-3 py-1 text-sm rounded-full ${getSwarmRunStatusClasses(monitor.status)}`}>
                        {monitor.status}
                    </span>
                    {!isRunning ? (
                        <button
                            onClick={onStart}
                            className="p-2 bg-green-600 text-white rounded hover:bg-green-500"
                        >
                            <PlayIcon className="w-4 h-4" />
                        </button>
                    ) : (
                        <button
                            onClick={onStop}
                            className="p-2 bg-red-600 text-white rounded hover:bg-red-500"
                        >
                            <StopIcon className="w-4 h-4" />
                        </button>
                    )}
                </div>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-4 gap-4 mb-4">
                <div className="text-center">
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">
                        {monitor.plannedSubtasks ?? '-'}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">Planned</p>
                </div>
                <div className="text-center">
                    <p className="text-2xl font-bold text-green-600">
                        {monitor.stageCompleted}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">Completed</p>
                </div>
                <div className="text-center">
                    <p className="text-2xl font-bold text-red-600">
                        {monitor.stageFailed}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">Failed</p>
                </div>
                <div className="text-center">
                    <p className="text-2xl font-bold text-blue-600">
                        {monitor.speedup ? `${monitor.speedup.toFixed(1)}x` : '-'}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">Speedup</p>
                </div>
            </div>

            {/* Routing info */}
            {monitor.routing && (
                <div className="mb-4 p-3 bg-gray-50 dark:bg-gray-900 rounded-lg">
                    <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">Routing</p>
                    <div className="flex flex-wrap gap-2">
                        {monitor.routing.complexity && (
                            <span className="px-2 py-1 text-xs bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300 rounded">
                                {monitor.routing.complexity}
                            </span>
                        )}
                        {monitor.routing.modelTier && (
                            <span className="px-2 py-1 text-xs bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300 rounded">
                                {monitor.routing.modelTier}
                            </span>
                        )}
                        {monitor.routing.targetAgentName && (
                            <span className="px-2 py-1 text-xs bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300 rounded">
                                {monitor.routing.targetAgentName}
                            </span>
                        )}
                    </div>
                </div>
            )}

            {/* Subtasks */}
            {Object.keys(monitor.subtasks).length > 0 && (
                <div className="mb-4">
                    <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">Subtasks</p>
                    <div className="space-y-1 max-h-40 overflow-y-auto">
                        {Object.values(monitor.subtasks).map(subtask => (
                            <div
                                key={subtask.id}
                                className={`flex items-center justify-between p-2 rounded text-sm ${
                                    subtask.status === 'failed' ? 'bg-red-50 dark:bg-red-900/20' : ''
                                }`}
                            >
                                <span className="font-mono text-gray-900 dark:text-white">
                                    {subtask.id}
                                </span>
                                <div className="flex items-center gap-2">
                                    {subtask.tool && (
                                        <span className="text-xs text-gray-500 dark:text-gray-400">
                                            {subtask.tool}
                                        </span>
                                    )}
                                    <span className={`px-2 py-0.5 text-xs rounded-full ${getSwarmSubtaskStatusClasses(subtask.status)}`}>
                                        {getSwarmSubtaskStatusLabel(subtask.status)}
                                    </span>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Recent lines */}
            {monitor.recentLines.length > 0 && (
                <div>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">Log</p>
                    <div className="bg-gray-900 text-gray-100 p-2 rounded text-xs font-mono max-h-32 overflow-y-auto">
                        {monitor.recentLines.slice(-10).map((line, i) => (
                            <div key={i} className="truncate">{line}</div>
                        ))}
                    </div>
                </div>
            )}

            {/* Error */}
            {monitor.error && (
                <div className="mt-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded">
                    <p className="text-sm text-red-700 dark:text-red-300">{monitor.error}</p>
                </div>
            )}
        </div>
    )
}
