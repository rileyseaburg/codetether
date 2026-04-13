// WorkerList Component
// List of available workers

import { ServerIcon } from './Icons'
import type { Worker } from '../types'

interface WorkerListProps {
    workers: Worker[]
    onSelect: (workerId: string) => void
    selectedId: string
}

export function WorkerList({ workers, onSelect, selectedId }: WorkerListProps) {
    const formatLastSeen = (lastSeen?: string) => {
        if (!lastSeen) return 'Never'
        const date = new Date(lastSeen)
        const now = new Date()
        const diffMs = now.getTime() - date.getTime()
        const diffMins = Math.floor(diffMs / 60000)
        if (diffMins < 1) return 'Just now'
        if (diffMins < 60) return `${diffMins}m ago`
        const diffHours = Math.floor(diffMins / 60)
        if (diffHours < 24) return `${diffHours}h ago`
        return date.toLocaleDateString()
    }

    return (
        <div className="space-y-2">
            {workers.length === 0 ? (
                <p className="text-sm text-gray-500 dark:text-gray-400">No workers available</p>
            ) : (
                workers.map(worker => (
                    <button
                        key={worker.worker_id}
                        onClick={() => onSelect(worker.worker_id)}
                        className={`w-full text-left p-3 rounded-lg border ${
                            selectedId === worker.worker_id
                                ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/20'
                                : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                        }`}
                    >
                        <div className="flex items-center gap-3">
                            <ServerIcon className="w-4 h-4 text-gray-400" />
                            <div className="flex-1 min-w-0">
                                <p className="font-medium text-gray-900 dark:text-white truncate">
                                    {worker.name}
                                </p>
                                <p className="text-xs text-gray-500 dark:text-gray-400">
                                    {worker.hostname || worker.worker_id}
                                </p>
                            </div>
                            <div className="text-right">
                                <span className={`px-2 py-1 text-xs rounded-full ${
                                    worker.status === 'connected'
                                        ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'
                                        : 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
                                }`}>
                                    {worker.status}
                                </span>
                                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                                    {formatLastSeen(worker.last_seen)}
                                </p>
                            </div>
                        </div>
                    </button>
                ))
            )}
        </div>
    )
}
