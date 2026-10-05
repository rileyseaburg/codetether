import { forwardRef } from 'react'
import { parseModel, getProviderInfo, getCostIcon } from './utils'

function DropdownOptionItem({ option, isSelected, isFocused, onClick, onMouseEnter }: { option: string, isSelected: boolean, isFocused?: boolean, onClick: () => void, onMouseEnter?: () => void }, ref: React.Ref<HTMLButtonElement>) {
    const { provider, model } = parseModel(option)
    const info = getProviderInfo(provider)
    const cost = getCostIcon(info.costHint)
    return (
        <button ref={ref} onClick={onClick} onMouseEnter={onMouseEnter} className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors ${isFocused ? 'ring-1 ring-cyan-500 bg-cyan-50 dark:bg-cyan-900/20' : ''} ${isSelected ? 'bg-cyan-100 dark:bg-cyan-900/30 text-cyan-700 dark:text-cyan-300' : 'text-gray-900 dark:text-white'}`}>
            <div className="flex items-center justify-between gap-2">
                <span className="font-medium truncate">{model || provider}</span>
                <span className="flex items-center gap-1 shrink-0">
                    {cost && <span className="text-[10px]" title={`Cost: ${info.costHint}`}>{cost}</span>}
                    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium leading-none ${info.badgeColor}`}>
                        {info.badge}
                    </span>
                </span>
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                via {info.label}
            </div>
        </button>
    )
}

export const DropdownOptionItemWithRef = forwardRef(DropdownOptionItem)
