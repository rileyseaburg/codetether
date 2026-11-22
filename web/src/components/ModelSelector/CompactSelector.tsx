import { useId } from 'react'
import { SearchableDropdown } from './SearchableDropdown'

export function CompactSelector(p: {
  selectedModel: string
  setSelectedModel: (val: string) => void
  availableModels: string[]
  loadingAgents: boolean
  label: string
  className: string
  disabled?: boolean
}) {
  const modelId = useId()
  return (
    <div className={`flex flex-col gap-1 ${p.className}`}>
      <div className="flex items-center gap-2">
        <label
          htmlFor={modelId}
          className="text-xs text-gray-500 dark:text-gray-400"
        >
          {p.label}:
        </label>
      </div>
      <SearchableDropdown
        id={modelId}
        label={p.label}
        loading={p.loadingAgents}
        value={p.selectedModel}
        onChange={p.setSelectedModel}
        options={p.availableModels}
        placeholder="Any available"
        disabled={p.loadingAgents || p.disabled}
        className="text-xs"
        searchPlaceholder="Search..."
      />
    </div>
  )
}
