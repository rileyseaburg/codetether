import { useId } from 'react'
import { SearchableDropdown } from './SearchableDropdown'

export function CardSelector(p: {
  selectedModel: string
  setSelectedModel: (val: string) => void
  availableModels: string[]
  loadingAgents: boolean
  showSelectedInfo: boolean
  showEmptyState: boolean
  label: string
  className: string
  disabled?: boolean
}) {
  const modelId = useId()
  return (
    <div
      className={`rounded-lg border border-cyan-200 bg-cyan-50 p-4 dark:border-cyan-800 dark:bg-cyan-900/20 ${p.className}`}
    >
      <h4 className="mb-3 text-sm font-medium text-cyan-800 dark:text-cyan-300">
        Execution Settings
      </h4>
      <div className="space-y-3">
        <div>
          <label
            htmlFor={modelId}
            className="mb-1 block text-xs text-cyan-700 dark:text-cyan-400"
          >
            {p.label}
          </label>
          <SearchableDropdown
            id={modelId}
            label={p.label}
            loading={p.loadingAgents}
            value={p.selectedModel}
            onChange={p.setSelectedModel}
            options={p.availableModels}
            placeholder="Any available model"
            disabled={p.loadingAgents || p.disabled}
            className="w-full"
            searchPlaceholder="Search by provider or model..."
          />
          {p.showSelectedInfo && p.selectedModel && (
            <p className="mt-1 text-xs text-cyan-600 dark:text-cyan-400">
              Tasks will route to workers supporting: {p.selectedModel}
            </p>
          )}
          {p.showEmptyState &&
            p.availableModels.length === 0 &&
            !p.loadingAgents && (
              <p className="mt-1 text-xs text-cyan-500">
                No workers with models registered
              </p>
            )}
        </div>
      </div>
    </div>
  )
}
