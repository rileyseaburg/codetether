// WorkspaceCard Component
// Individual workspace display card

import { FolderIcon, XIcon } from './Icons'
import { buildVmSshCommand } from '../utils'
import type { Workspace } from '../types'

interface WorkspaceCardProps {
    workspace: Workspace
    onUnregister: (id: string) => void
    onTrigger: (id: string) => void
}

export function WorkspaceCard({ workspace, onUnregister, onTrigger }: WorkspaceCardProps) {
    const sshCommand = buildVmSshCommand(workspace)
    const isVm = workspace.runtime === 'vm'

    return (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
            <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                    <FolderIcon className="w-5 h-5 text-indigo-500" />
                    <div>
                        <h4 className="font-medium text-gray-900 dark:text-white">
                            {workspace.name}
                        </h4>
                        <p className="text-sm text-gray-500 dark:text-gray-400">
                            {workspace.path}
                        </p>
                    </div>
                </div>
                <button
                    onClick={() => onUnregister(workspace.id)}
                    className="text-gray-400 hover:text-red-500"
                    title="Unregister workspace"
                >
                    <XIcon className="w-4 h-4" />
                </button>
            </div>

            {workspace.description && (
                <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">
                    {workspace.description}
                </p>
            )}

            <div className="mt-3 flex items-center gap-2">
                <span className={`px-2 py-1 text-xs rounded-full ${
                    workspace.status === 'ready'
                        ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'
                        : 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300'
                }`}>
                    {workspace.status}
                </span>
                {isVm && workspace.vm_status && (
                    <span className="px-2 py-1 text-xs rounded-full bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300">
                        VM: {workspace.vm_status}
                    </span>
                )}
            </div>

            {isVm && sshCommand && (
                <div className="mt-3 p-2 bg-gray-50 dark:bg-gray-900 rounded text-xs font-mono">
                    {sshCommand}
                </div>
            )}

            <button
                onClick={() => onTrigger(workspace.id)}
                className="mt-3 w-full py-2 px-4 bg-indigo-600 text-white rounded-md hover:bg-indigo-500 text-sm font-medium"
            >
                Trigger Agent
            </button>
        </div>
    )
}
