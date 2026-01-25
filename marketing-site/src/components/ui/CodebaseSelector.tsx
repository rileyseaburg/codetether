import { ServerIcon } from '@/components/ui/ChatIcons2'

interface CodebaseSelectorProps {
    selectedCodebase: string
    codebases: Array<{ id: string, name?: string }>
    onChange: (id: string) => void
}

export function CodebaseSelector({ selectedCodebase, codebases, onChange }: CodebaseSelectorProps) {
    return (
        <div className="flex items-center gap-2" data-cy="codebase-selector-wrapper">
            <ServerIcon className="h-4 w-4 text-gray-400" />
            <label className="text-xs text-gray-500 dark:text-gray-400">Codebase:</label>
            <select
                value={selectedCodebase}
                onChange={(e) => onChange(e.target.value)}
                data-cy="codebase-selector"
                className="text-xs px-2 py-1 border border-gray-200 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 focus:ring-2 focus:ring-cyan-500"
            >
                <option value="">None (general task)</option>
                {codebases.map((cb) => (
                    <option key={cb.id} value={cb.id}>{cb.name || cb.id}</option>
                ))}
            </select>
        </div>
    )
}
