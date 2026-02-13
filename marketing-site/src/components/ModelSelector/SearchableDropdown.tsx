import { useState, useMemo, useRef, useEffect, forwardRef } from 'react'
import { useDropdownPosition } from './useDropdownPosition'
import { useDropdownFilter } from './useDropdownFilter'
import { DropdownOptionItemWithRef } from './DropdownOptionItem'
import { parseModel, getProviderInfo, type RouteCategory } from './utils'

const CATEGORY_PILLS: { key: RouteCategory | 'all'; label: string; color: string }[] = [
    { key: 'all', label: 'All', color: 'bg-gray-200 text-gray-800 dark:bg-gray-600 dark:text-gray-200' },
    { key: 'direct', label: 'Direct', color: 'bg-emerald-200 text-emerald-800 dark:bg-emerald-800 dark:text-emerald-200' },
    { key: 'free', label: 'Free', color: 'bg-green-200 text-green-800 dark:bg-green-800 dark:text-green-200' },
    { key: 'cloud', label: 'Cloud', color: 'bg-purple-200 text-purple-800 dark:bg-purple-800 dark:text-purple-200' },
    { key: 'proxy', label: 'Proxy', color: 'bg-blue-200 text-blue-800 dark:bg-blue-800 dark:text-blue-200' },
    { key: 'enterprise', label: 'Infra', color: 'bg-indigo-200 text-indigo-800 dark:bg-indigo-800 dark:text-indigo-200' },
    { key: 'china', label: 'CN', color: 'bg-orange-200 text-orange-800 dark:bg-orange-800 dark:text-orange-200' },
    { key: 'community', label: 'Community', color: 'bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-300' },
]

/** Build a sorted list of { slug, label, count } for providers present in given options */
function buildProviderList(options: string[], categoryFilter: RouteCategory | 'all') {
    const counts = new Map<string, number>()
    for (const opt of options) {
        const { provider } = parseModel(opt)
        if (!provider) continue
        const info = getProviderInfo(provider)
        if (categoryFilter !== 'all' && info.category !== categoryFilter) continue
        counts.set(provider, (counts.get(provider) || 0) + 1)
    }
    return Array.from(counts.entries())
        .map(([slug, count]) => ({ slug, label: getProviderInfo(slug).label, count }))
        .sort((a, b) => b.count - a.count)
}

export function SearchableDropdown({ value, onChange, options, placeholder, disabled, className, searchPlaceholder = "Search by provider or model..."
}: { value: string, onChange: (val: string) => void, options: string[], placeholder?: string, disabled?: boolean, className?: string, searchPlaceholder?: string }) {
    const [search, setSearch] = useState('')
    const [open, setOpen] = useState(false)
    const [isSearching, setIsSearching] = useState(false)
    const [focusedIndex, setFocusedIndex] = useState(-1)
    const [categoryFilter, setCategoryFilter] = useState<RouteCategory | 'all'>('all')
    const [providerFilter, setProviderFilter] = useState<string | null>(null)
    const inputRef = useRef<HTMLInputElement>(null)
    const menuRef = useRef<HTMLDivElement>(null)
    const pos = useDropdownPosition(open, inputRef)
    const filtered = useDropdownFilter(options, isSearching ? search : '')

    // Available providers for the current category (computed from all options, not filtered by search)
    const availableProviders = useMemo(() => buildProviderList(options, categoryFilter), [options, categoryFilter])

    // Apply category + provider filter on top of text filter
    const categoryFiltered = useMemo(() => {
        const base = isSearching ? filtered : options
        return base.filter(opt => {
            const { provider } = parseModel(opt)
            if (providerFilter && provider !== providerFilter) return false
            if (categoryFilter === 'all') return true
            return getProviderInfo(provider).category === categoryFilter
        })
    }, [filtered, options, isSearching, categoryFilter, providerFilter])

    const displayOptions = categoryFiltered
    const selected = useMemo(() => options.find(o => o === value) || value, [options, value])
    const itemRefs = useRef<(HTMLButtonElement | null)[]>([])

    useEffect(() => {
        itemRefs.current = []
    }, [categoryFiltered.length, isSearching])

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

    const handleCategoryChange = (cat: RouteCategory | 'all') => {
        setCategoryFilter(cat)
        setProviderFilter(null)
        setFocusedIndex(-1)
    }

    const handleProviderChange = (slug: string | null) => {
        setProviderFilter(slug)
        setFocusedIndex(-1)
    }

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
            setCategoryFilter('all')
            setProviderFilter(null)
        } else if (e.key === 'Enter') {
            e.preventDefault()
            if (focusedIndex >= 0 && displayOptions[focusedIndex]) {
                handleOptionClick(displayOptions[focusedIndex])
            } else if (categoryFiltered.length === 1) {
                handleOptionClick(categoryFiltered[0])
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
        setCategoryFilter('all')
        setProviderFilter(null)
    }

    const displayValue = isSearching ? search : selected

    return (
        <div className={`relative ${className}`} data-cy="model-selector">
            <input ref={inputRef} type="text" placeholder={searchPlaceholder} value={displayValue} onChange={handleChange} onKeyDown={keyDown} onFocus={handleFocus} onBlur={() => setTimeout(() => setOpen(false), 200)} disabled={disabled} data-cy="model-selector-input" className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-white focus:ring-2 focus:ring-cyan-500" />
            {open && <DropdownMenuWithRef ref={menuRef} pos={pos} filtered={displayOptions} search={search} value={value} onChange={handleOptionClick} setOpen={setOpen} focusedIndex={focusedIndex} setFocusedIndex={setFocusedIndex} itemRefs={itemRefs} categoryFilter={categoryFilter} onCategoryChange={handleCategoryChange} providerFilter={providerFilter} onProviderChange={handleProviderChange} availableProviders={availableProviders} totalCount={options.length} />}
        </div>
    )
}

interface ProviderEntry { slug: string; label: string; count: number }

function DropdownMenu({ pos, filtered, search, value, onChange, setOpen, focusedIndex, setFocusedIndex, itemRefs, categoryFilter, onCategoryChange, providerFilter, onProviderChange, availableProviders, totalCount }: {
    pos: { top: number, left: number, width: number }
    filtered: string[]
    search: string
    value: string
    onChange: (v: string) => void
    setOpen: (b: boolean) => void
    focusedIndex: number
    setFocusedIndex: (i: number) => void
    itemRefs: React.MutableRefObject<(HTMLButtonElement | null)[]>
    categoryFilter: RouteCategory | 'all'
    onCategoryChange: (c: RouteCategory | 'all') => void
    providerFilter: string | null
    onProviderChange: (slug: string | null) => void
    availableProviders: ProviderEntry[]
    totalCount: number
}, ref: React.Ref<HTMLDivElement>) {
    return (
        <div ref={ref} className="fixed z-[90] mt-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-lg shadow-lg max-h-[28rem] flex flex-col" style={{ top: pos.top, left: pos.left, width: pos.width }}>
            {/* Category filter pills */}
            <div className="flex flex-wrap gap-1 px-2 py-1.5 border-b border-gray-200 dark:border-gray-600 shrink-0" onMouseDown={e => e.preventDefault()}>
                {CATEGORY_PILLS.map(pill => (
                    <button
                        key={pill.key}
                        onClick={() => onCategoryChange(pill.key)}
                        className={`px-2 py-0.5 rounded-full text-[10px] font-medium transition-all ${categoryFilter === pill.key
                            ? `${pill.color} ring-1 ring-current`
                            : 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600'
                            }`}
                    >
                        {pill.label}
                    </button>
                ))}
            </div>
            {/* Provider filter row */}
            {availableProviders.length > 0 && (
                <div className="flex flex-wrap gap-1 px-2 py-1 border-b border-gray-200 dark:border-gray-600 shrink-0 max-h-16 overflow-y-auto" onMouseDown={e => e.preventDefault()}>
                    <button
                        onClick={() => onProviderChange(null)}
                        className={`px-1.5 py-0.5 rounded text-[10px] font-medium transition-all ${providerFilter === null
                            ? 'bg-cyan-200 text-cyan-800 dark:bg-cyan-800 dark:text-cyan-200 ring-1 ring-cyan-400'
                            : 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600'
                            }`}
                    >
                        All providers
                    </button>
                    {availableProviders.map(p => (
                        <button
                            key={p.slug}
                            onClick={() => onProviderChange(providerFilter === p.slug ? null : p.slug)}
                            title={`${p.label} (${p.count} models)`}
                            className={`px-1.5 py-0.5 rounded text-[10px] font-medium transition-all ${providerFilter === p.slug
                                ? 'bg-cyan-200 text-cyan-800 dark:bg-cyan-800 dark:text-cyan-200 ring-1 ring-cyan-400'
                                : 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600'
                                }`}
                        >
                            {p.label} <span className="opacity-60">{p.count}</span>
                        </button>
                    ))}
                </div>
            )}
            {/* Count indicator */}
            <div className="px-3 py-1 text-[10px] text-gray-400 dark:text-gray-500 border-b border-gray-100 dark:border-gray-700 shrink-0">
                {filtered.length === totalCount ? `${totalCount} models` : `${filtered.length} of ${totalCount} models`}
                {providerFilter && <span className="ml-1 text-cyan-500">· {getProviderInfo(providerFilter).label}</span>}
            </div>
            {/* Model list */}
            <div className="overflow-y-auto flex-1">
                {!filtered.length ? <div className="px-3 py-2 text-sm text-gray-500 dark:text-gray-400">No models matching &quot;{search}&quot;</div> : filtered.map((opt, idx) => <DropdownOptionItemWithRef key={opt} option={opt} isSelected={opt === value} isFocused={idx === focusedIndex} onClick={() => { onChange(opt); setOpen(false) }} onMouseEnter={() => setFocusedIndex(idx)} ref={(el: HTMLButtonElement | null) => { itemRefs.current[idx] = el }} />)}
            </div>
        </div>
    )
}

const DropdownMenuWithRef = forwardRef(DropdownMenu)
