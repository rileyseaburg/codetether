import { SearchableDropdown } from './SearchableDropdown'

export function CardSelector(p: { selectedModel: string, setSelectedModel: (val: string) => void, availableModels: string[], loadingAgents: boolean, showSelectedInfo: boolean, showEmptyState: boolean, label: string, className: string }) {
    return (
        <div className={`p-4 bg-cyan-50 dark:bg-cyan-900/20 rounded-lg border border-cyan-200 dark:border-cyan-800 ${p.className}`}>
            <h4 className="text-sm font-medium text-cyan-800 dark:text-cyan-300 mb-3">Execution Settings</h4>
            <div className="space-y-3">
                <div>
                    <label className="block text-xs text-cyan-700 dark:text-cyan-400 mb-1">{p.label}</label>
                    <SearchableDropdown value={p.selectedModel} onChange={p.setSelectedModel} options={p.availableModels} placeholder="Any available model" disabled={p.loadingAgents} className="w-full" searchPlaceholder="Search by provider or model..." />
                    {p.showSelectedInfo && p.selectedModel && <p className="mt-1 text-xs text-cyan-600 dark:text-cyan-400">Tasks will route to workers supporting: {p.selectedModel}</p>}
                    {p.showEmptyState && p.availableModels.length === 0 && !p.loadingAgents && <p className="mt-1 text-xs text-cyan-500">No workers with models registered</p>}
                </div>
            </div>
        </div>
    )
}
