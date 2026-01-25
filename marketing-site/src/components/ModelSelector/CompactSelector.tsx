import { SearchableDropdown } from './SearchableDropdown'

export function CompactSelector(p: { selectedModel: string, setSelectedModel: (val: string) => void, availableModels: string[], loadingAgents: boolean, label: string, className: string }) {
    return (
        <div className={`flex flex-col gap-1 ${p.className}`}>
            <div className="flex items-center gap-2"><label className="text-xs text-gray-500 dark:text-gray-400">{p.label}:</label></div>
            <SearchableDropdown value={p.selectedModel} onChange={p.setSelectedModel} options={p.availableModels} placeholder="Any available" disabled={p.loadingAgents} className="text-xs" searchPlaceholder="Search..." />
        </div>
    )
}
