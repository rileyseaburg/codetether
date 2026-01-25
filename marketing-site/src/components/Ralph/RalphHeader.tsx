'use client'

import { RalphPlayIcon, RalphStopIcon, RalphTrashIcon } from '../ui/RalphIcons'

interface RalphHeaderProps {
    isRunning: boolean
    hasPRDOrRun: boolean
    hasPRD: boolean
    startingRun: boolean
    onClear: () => void
    onStop: () => void
    onStart: () => void
}

export function RalphHeader({ isRunning, hasPRDOrRun, hasPRD, startingRun, onClear, onStop, onStart }: RalphHeaderProps) {
    return (
        <div className="flex items-center justify-between" data-cy="ralph-header">
            <div>
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white" data-cy="ralph-title">Ralph Autonomous Loop</h1>
                <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">PRD-driven autonomous development with RLM context compression</p>
            </div>
            <div className="flex items-center gap-3" data-cy="ralph-controls">
                {!isRunning && hasPRDOrRun && (
                    <button onClick={onClear} data-cy="ralph-clear-btn" className="inline-flex items-center gap-2 rounded-lg bg-gray-600 px-4 py-2 text-sm font-medium text-white hover:bg-gray-500">
                        <RalphTrashIcon className="h-4 w-4" />
                        Clear State
                    </button>
                )}
                {isRunning ? (
                    <button onClick={onStop} data-cy="ralph-stop-btn" className="inline-flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-500">
                        <RalphStopIcon className="h-4 w-4" />
                        Stop
                    </button>
                ) : (
                    <button onClick={onStart} disabled={!hasPRD || startingRun} data-cy="ralph-start-btn" className="inline-flex items-center gap-2 rounded-lg bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-500 disabled:opacity-50 disabled:cursor-not-allowed">
                        {startingRun ? <><RalphPlayIcon className="h-4 w-4" />Starting...</> : <><RalphPlayIcon className="h-4 w-4" />Start Ralph</>}
                    </button>
                )}
            </div>
        </div>
    )
}
