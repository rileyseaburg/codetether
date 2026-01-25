import { SearchableDropdown } from './SearchableDropdown'

export function SessionsSelector(p: { selectedModel: string, setSelectedModel: (val: string) => void, availableModels: string[], loadingAgents: boolean, showSelectedInfo: boolean, showEmptyState: boolean, hasCountBadge: boolean, label: string, className: string }) {
    return (
        <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
                <label className="text-xs font-medium text-gray-700 dark:text-gray-300" htmlFor="ct-model">{p.label}</label>
                {p.hasCountBadge && <span className="rounded-full bg-cyan-100 dark:bg-cyan-900/30 px-2 py-0.5 text-[10px] font-medium text-cyan-700 dark:text-cyan-300">{p.availableModels.length} available</span>}
            </div>
            <SearchableDropdown value={p.selectedModel} onChange={p.setSelectedModel} options={p.availableModels} placeholder="Any available model" disabled={p.loadingAgents} className="w-full min-w-[180px] sm:w-[220px]" searchPlaceholder="Search by provider or model..." />
            {p.showSelectedInfo && p.selectedModel && <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">Tasks will route to workers supporting: {p.selectedModel}</p>}
            {p.hasCountBadge && p.availableModels.length > 0 && p.selectedModel === '' && <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{p.availableModels.length} worker{p.availableModels.length !== 1 ? 's' : ''} registered</p>}
            {p.showEmptyState && p.availableModels.length === 0 && !p.loadingAgents && <p className="mt-1 text-xs text-gray-500">No workers with models registered</p>}
        </div>
    )
}
