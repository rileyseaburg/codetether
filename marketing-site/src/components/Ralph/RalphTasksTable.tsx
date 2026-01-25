'use client'

import { RalphRefreshIcon } from '../ui/RalphIcons'

interface RalphTasksTableProps {
    tasks: Array<{ id: string; title?: string; status: string; created_at: string }>
    onRefresh: () => void
}

export function RalphTasksTable({ tasks, onRefresh }: RalphTasksTableProps) {
    if (tasks.length === 0) return null

    const getStatusColor = (status: string) => {
        const colors: Record<string, string> = { completed: 'bg-emerald-100 text-emerald-700', working: 'bg-blue-100 text-blue-700', failed: 'bg-red-100 text-red-700', pending: 'bg-yellow-100 text-yellow-700' }
        return colors[status] || 'bg-gray-100 text-gray-700'
    }

    return (
        <div className="rounded-lg bg-white shadow-sm dark:bg-gray-800 dark:ring-1 dark:ring-white/10">
            <div className="flex items-center justify-between p-4 border-b"><h2 className="text-sm font-semibold">Ralph Tasks</h2><button onClick={onRefresh}><RalphRefreshIcon className="h-4 w-4" /></button></div>
            <div className="overflow-x-auto">
                <table className="w-full text-sm"><thead className="bg-gray-50"><tr><th className="px-4 py-2 text-left text-xs">Task</th><th className="px-4 py-2 text-left text-xs">Story</th><th className="px-4 py-2 text-left text-xs">Status</th><th className="px-4 py-2 text-left text-xs">Created</th></tr></thead>
                    <tbody className="divide-y">{tasks.slice(0, 10).map((task) => (
                        <tr key={task.id} className="hover:bg-gray-50"><td className="px-4 py-2 font-mono text-xs">{task.id.slice(0, 8)}...</td><td className="px-4 py-2">{task.title?.replace('Ralph: ', '') || 'Unknown'}</td><td className="px-4 py-2"><span className={`px-2 py-0.5 text-xs rounded ${getStatusColor(task.status)}`}>{task.status}</span></td><td className="px-4 py-2 text-xs">{new Date(task.created_at).toLocaleTimeString()}</td></tr>
                    ))}</tbody>
                </table>
            </div>
        </div>
    )
}