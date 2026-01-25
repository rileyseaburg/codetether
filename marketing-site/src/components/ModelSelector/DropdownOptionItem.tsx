import { forwardRef } from 'react'
import { parseModel } from './utils'

function DropdownOptionItem({ option, isSelected, isFocused, onClick, onMouseEnter }: { option: string, isSelected: boolean, isFocused?: boolean, onClick: () => void, onMouseEnter?: () => void }, ref: React.Ref<HTMLButtonElement>) {
    const { provider, model } = parseModel(option)
    return (
        <button ref={ref} onClick={onClick} onMouseEnter={onMouseEnter} className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors ${isFocused ? 'ring-1 ring-cyan-500 bg-cyan-50 dark:bg-cyan-900/20' : ''} ${isSelected ? 'bg-cyan-100 dark:bg-cyan-900/30 text-cyan-700 dark:text-cyan-300' : 'text-gray-900 dark:text-white'}`}>
            <div className="font-medium">{provider}</div>
            <div className="text-xs text-gray-500 dark:text-gray-400">{model}</div>
        </button>
    )
}

export const DropdownOptionItemWithRef = forwardRef(DropdownOptionItem)
