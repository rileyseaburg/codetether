import { ServerIcon } from '@/components/ui/ChatIcons2'

interface WorkspaceSelectorProps {
    selectedWorkspace: string
    workspaces: Array<{ id: string, name?: string }>
    onChange: (id: string) => void
}

export function WorkspaceSelector({ selectedWorkspace, workspaces, onChange }: WorkspaceSelectorProps) {
    return (
        <div className="flex items-center gap-2" data-cy="workspace-selector-wrapper">
            <ServerIcon className="h-4 w-4 text-gray-400" />
            <label className="text-xs text-gray-500 dark:text-gray-400">Workspace:</label>
            <select
                value={selectedWorkspace}
                onChange={(e) => onChange(e.target.value)}
                data-cy="workspace-selector"
                className="text-xs px-2 py-1 border border-gray-200 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 focus:ring-2 focus:ring-cyan-500"
            >
                <option value="">None (general task)</option>
                {workspaces.map((ws) => (
                    <option key={ws.id} value={ws.id}>{ws.name || ws.id}</option>
                ))}
            </select>
        </div>
    )
}

/** @deprecated Use WorkspaceSelector instead */
export const CodebaseSelector = WorkspaceSelector
