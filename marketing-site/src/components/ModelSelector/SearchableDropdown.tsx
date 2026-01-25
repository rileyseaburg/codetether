import { useState, useMemo, useRef, useEffect, forwardRef } from 'react'
import { useDropdownPosition } from './useDropdownPosition'
import { useDropdownFilter } from './useDropdownFilter'
import { DropdownOptionItemWithRef } from './DropdownOptionItem'

export function SearchableDropdown({ value, onChange, options, placeholder, disabled, className, searchPlaceholder = "Search by provider or model..."
}: { value: string, onChange: (val: string) => void, options: string[], placeholder?: string, disabled?: boolean, className?: string, searchPlaceholder?: string }) {
    const [search, setSearch] = useState('')
    const [open, setOpen] = useState(false)
    const [isSearching, setIsSearching] = useState(false)
    const [focusedIndex, setFocusedIndex] = useState(-1)
    const inputRef = useRef<HTMLInputElement>(null)
    const menuRef = useRef<HTMLDivElement>(null)
    const pos = useDropdownPosition(open, inputRef)
    const filtered = useDropdownFilter(options, isSearching ? search : '')
    const displayOptions = isSearching ? filtered : options
    const selected = useMemo(() => options.find(o => o === value) || value, [options, value])
    const itemRefs = useRef<(HTMLButtonElement | null)[]>([])

    useEffect(() => {
        itemRefs.current = []
    }, [filtered.length, isSearching])

    useEffect(() => {
        if (focusedIndex >= 0 && itemRefs.current[focusedIndex] && menuRef.current) {
            const item = itemRefs.current[focusedIndex]
            const menu = menuRef.current
            if (item && menu) {
                const itemTop = item.offsetTop
                const itemBottom = itemTop + item.offsetHeight
                const menuTop = menu.scrollTop
                const menuBottom = menuTop + menu.clientHeight
                
                if (itemTop < menuTop) {
                    menu.scrollTop = itemTop
                } else if (itemBottom > menuBottom) {
                    menu.scrollTop = itemBottom - menu.clientHeight
                }
            }
        }
    }, [focusedIndex])

    const keyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === 'ArrowDown') {
            e.preventDefault()
            setFocusedIndex(prev => Math.min(prev + 1, displayOptions.length - 1))
        } else if (e.key === 'ArrowUp') {
            e.preventDefault()
            setFocusedIndex(prev => Math.max(prev - 1, 0))
        } else if (e.key === 'Backspace' && search === '' && !isSearching) {
            setIsSearching(true)
            setSearch(selected)
            e.preventDefault()
        } else if (e.key === 'Escape') {
            setOpen(false)
            setSearch('')
            setIsSearching(false)
            setFocusedIndex(-1)
        } else if (e.key === 'Enter') {
            e.preventDefault()
            if (focusedIndex >= 0 && displayOptions[focusedIndex]) {
                handleOptionClick(displayOptions[focusedIndex])
            } else if (filtered.length === 1) {
                handleOptionClick(filtered[0])
            }
        } else if (e.key === 'Tab') {
            if (focusedIndex >= 0 && displayOptions[focusedIndex]) {
                e.preventDefault()
                handleOptionClick(displayOptions[focusedIndex])
            }
        }
    }

    const handleFocus = () => {
        setOpen(true)
        if (value) {
            setIsSearching(false)
        }
    }

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const val = e.target.value
        setSearch(val)
        setIsSearching(true)
        setOpen(true)
        setFocusedIndex(-1)
    }

    const handleOptionClick = (opt: string) => {
        onChange(opt)
        setSearch('')
        setIsSearching(false)
        setOpen(false)
        setFocusedIndex(-1)
    }

    const displayValue = isSearching ? search : selected

    return (
        <div className={`relative ${className}`} data-cy="model-selector">
            <input ref={inputRef} type="text" placeholder={searchPlaceholder} value={displayValue} onChange={handleChange} onKeyDown={keyDown} onFocus={handleFocus} onBlur={() => setTimeout(() => setOpen(false), 200)} disabled={disabled} data-cy="model-selector-input" className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-white focus:ring-2 focus:ring-cyan-500" />
            {open && <DropdownMenuWithRef ref={menuRef} pos={pos} filtered={displayOptions} search={search} value={value} onChange={handleOptionClick} setOpen={setOpen} focusedIndex={focusedIndex} setFocusedIndex={setFocusedIndex} itemRefs={itemRefs} />}
        </div>
    )
}

function DropdownMenu({ pos, filtered, search, value, onChange, setOpen, focusedIndex, setFocusedIndex, itemRefs }: { pos: { top: number, left: number, width: number }, filtered: string[], search: string, value: string, onChange: (v: string) => void, setOpen: (b: boolean) => void, focusedIndex: number, setFocusedIndex: (i: number) => void, itemRefs: React.MutableRefObject<(HTMLButtonElement | null)[]> }, ref: React.Ref<HTMLDivElement>) {
    return (
        <div ref={ref} className="fixed z-50 mt-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-lg shadow-lg max-h-80 overflow-y-auto" style={{ top: pos.top, left: pos.left, width: pos.width }}>
            {!filtered.length ? <div className="px-3 py-2 text-sm text-gray-500 dark:text-gray-400">No models matching "{search}"</div> : filtered.map((opt, idx) => <DropdownOptionItemWithRef key={opt} option={opt} isSelected={opt === value} isFocused={idx === focusedIndex} onClick={() => { onChange(opt); setOpen(false) }} onMouseEnter={() => setFocusedIndex(idx)} ref={(el: HTMLButtonElement | null) => { itemRefs.current[idx] = el }} />)}
        </div>
    )
}

const DropdownMenuWithRef = forwardRef(DropdownMenu)
