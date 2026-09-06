import { useId } from 'react'
import { SearchableDropdown } from './SearchableDropdown'

export function DefaultSelector(p: {
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
    <div className={p.className}>
      <label
        htmlFor={modelId}
        className="mb-2 block text-sm font-medium text-gray-700 dark:text-gray-300"
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
        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
          Tasks will route to workers supporting: {p.selectedModel}
        </p>
      )}
      {p.showEmptyState &&
        p.availableModels.length === 0 &&
        !p.loadingAgents && (
          <p className="mt-1 text-xs text-gray-500">
            No workers with models registered
          </p>
        )}
    </div>
  )
}
