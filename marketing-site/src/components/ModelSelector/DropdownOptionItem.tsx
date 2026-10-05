import { forwardRef } from 'react'
import { parseModel, getProviderInfo, getCostIcon } from './utils'

function DropdownOptionItem(
  {
    id,
    option,
    isSelected,
    isFocused,
    onClick,
    onMouseEnter,
  }: {
    id?: string
    option: string
    isSelected: boolean
    isFocused?: boolean
    onClick: () => void
    onMouseEnter?: () => void
  },
  ref: React.Ref<HTMLButtonElement>,
) {
  const { provider, model } = parseModel(option)
  const info = getProviderInfo(provider)
  const cost = getCostIcon(info.costHint)
  return (
    <button
      ref={ref}
      id={id}
      type="button"
      role="option"
      tabIndex={-1}
      aria-selected={isSelected}
      onMouseDown={(event) => event.preventDefault()}
      onClick={onClick}
      onMouseEnter={onMouseEnter}
      className={`w-full px-3 py-2 text-left text-sm transition-colors hover:bg-gray-100 dark:hover:bg-gray-700 ${isFocused ? 'bg-cyan-50 ring-1 ring-cyan-500 dark:bg-cyan-900/20' : ''} ${isSelected ? 'bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-300' : 'text-gray-900 dark:text-white'}`}
    >
      <span className="flex items-center justify-between gap-2">
        <span className="truncate font-medium">{model || provider}</span>
        <span className="flex shrink-0 items-center gap-1">
          {cost && (
            <span className="text-[10px]" title={`Cost: ${info.costHint}`}>
              {cost}
            </span>
          )}
          <span
            className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] leading-none font-medium ${info.badgeColor}`}
          >
            {info.badge}
          </span>
        </span>
      </span>
      <span className="mt-0.5 block text-xs text-gray-500 dark:text-gray-400">
        via {info.label}
      </span>
    </button>
  )
}

export const DropdownOptionItemWithRef = forwardRef(DropdownOptionItem)
