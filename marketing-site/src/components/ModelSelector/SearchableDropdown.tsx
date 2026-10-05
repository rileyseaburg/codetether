import {
  useState,
  useMemo,
  useRef,
  useEffect,
  useCallback,
  useId,
  forwardRef,
} from 'react'
import { useDropdownPosition } from './useDropdownPosition'
import { useDropdownFilter } from './useDropdownFilter'
import { DropdownOptionItemWithRef } from './DropdownOptionItem'
import { parseModel, getProviderInfo, type RouteCategory } from './utils'

const CATEGORY_PILLS: {
  key: RouteCategory | 'all'
  label: string
  color: string
}[] = [
  {
    key: 'all',
    label: 'All',
    color: 'bg-gray-200 text-gray-800 dark:bg-gray-600 dark:text-gray-200',
  },
  {
    key: 'direct',
    label: 'Direct',
    color:
      'bg-emerald-200 text-emerald-800 dark:bg-emerald-800 dark:text-emerald-200',
  },
  {
    key: 'free',
    label: 'Free',
    color: 'bg-green-200 text-green-800 dark:bg-green-800 dark:text-green-200',
  },
  {
    key: 'cloud',
    label: 'Cloud',
    color:
      'bg-purple-200 text-purple-800 dark:bg-purple-800 dark:text-purple-200',
  },
  {
    key: 'proxy',
    label: 'Proxy',
    color: 'bg-blue-200 text-blue-800 dark:bg-blue-800 dark:text-blue-200',
  },
  {
    key: 'enterprise',
    label: 'Infra',
    color:
      'bg-indigo-200 text-indigo-800 dark:bg-indigo-800 dark:text-indigo-200',
  },
  {
    key: 'china',
    label: 'CN',
    color:
      'bg-orange-200 text-orange-800 dark:bg-orange-800 dark:text-orange-200',
  },
  {
    key: 'community',
    label: 'Community',
    color: 'bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
  },
]

/** Build a sorted list of { slug, label, count } for providers present in given options */
function buildProviderList(
  options: string[],
  categoryFilter: RouteCategory | 'all',
) {
  const counts = new Map<string, number>()
  for (const opt of options) {
    const { provider } = parseModel(opt)
    if (!provider) continue
    const info = getProviderInfo(provider)
    if (categoryFilter !== 'all' && info.category !== categoryFilter) continue
    counts.set(provider, (counts.get(provider) || 0) + 1)
  }
  return Array.from(counts.entries())
    .map(([slug, count]) => ({
      slug,
      label: getProviderInfo(slug).label,
      count,
    }))
    .sort((a, b) => b.count - a.count)
}

export function SearchableDropdown({
  value,
  onChange,
  options,
  placeholder,
  disabled,
  loading = false,
  id,
  label,
  className,
  searchPlaceholder = 'Search by provider or model...',
}: {
  value: string
  onChange: (val: string) => void
  options: string[]
  placeholder?: string
  disabled?: boolean
  loading?: boolean
  id?: string
  label?: string
  className?: string
  searchPlaceholder?: string
}) {
  const generatedId = useId()
  const inputId = id || `${generatedId}-input`
  const listId = `${generatedId}-listbox`
  const statusId = `${generatedId}-status`
  const rootRef = useRef<HTMLDivElement>(null)
  const [search, setSearch] = useState('')
  const [open, setOpen] = useState(false)
  const [isSearching, setIsSearching] = useState(false)
  const [focusedOption, setFocusedOption] = useState<string | null>(null)
  const expanded = open && !disabled && !loading
  const [categoryFilter, setCategoryFilter] = useState<RouteCategory | 'all'>(
    'all',
  )
  const [providerFilter, setProviderFilter] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const pos = useDropdownPosition(expanded, inputRef)
  const filtered = useDropdownFilter(options, isSearching ? search : '')

  // Available providers for the current category (computed from all options, not filtered by search)
  const availableProviders = useMemo(
    () => buildProviderList(options, categoryFilter),
    [options, categoryFilter],
  )

  // Apply category + provider filter on top of text filter
  const categoryFiltered = useMemo(() => {
    const base = isSearching ? filtered : options
    return base.filter((opt) => {
      const { provider } = parseModel(opt)
      if (providerFilter && provider !== providerFilter) return false
      if (categoryFilter === 'all') return true
      return getProviderInfo(provider).category === categoryFilter
    })
  }, [filtered, options, isSearching, categoryFilter, providerFilter])

  const displayOptions = categoryFiltered
  const selected = useMemo(
    () => options.find((o) => o === value) || value,
    [options, value],
  )
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([])
  const focusedIndex =
    focusedOption === null ? -1 : displayOptions.indexOf(focusedOption)
  const setFocusedIndex = (index: number) =>
    setFocusedOption(displayOptions[index] ?? null)

  useEffect(() => {
    if (
      focusedIndex >= 0 &&
      itemRefs.current[focusedIndex] &&
      menuRef.current
    ) {
      const item = itemRefs.current[focusedIndex]
      const menu = menuRef.current
      if (item && menu) {
        // offsetTop includes the filter header's positioned ancestor. Compare
        // viewport rectangles so only the model list scrolls, not the page.
        const itemRect = item.getBoundingClientRect()
        const menuRect = menu.getBoundingClientRect()
        if (itemRect.top < menuRect.top) {
          menu.scrollTop += itemRect.top - menuRect.top
        } else if (itemRect.bottom > menuRect.bottom) {
          menu.scrollTop += itemRect.bottom - menuRect.bottom
        }
      }
    }
  }, [focusedIndex, displayOptions, expanded])

  const closeMenu = useCallback(() => {
    setOpen(false)
    setSearch('')
    setIsSearching(false)
    setFocusedOption(null)
    setCategoryFilter('all')
    setProviderFilter(null)
  }, [])

  useEffect(() => {
    if (!expanded) return
    const outside = (event: PointerEvent) => {
      if (
        event.target instanceof Node &&
        !rootRef.current?.contains(event.target)
      )
        closeMenu()
    }
    document.addEventListener('pointerdown', outside)
    return () => document.removeEventListener('pointerdown', outside)
  }, [expanded, closeMenu])

  // Reset interaction state when availability changes, not the controlled value.
  const unavailable = Boolean(disabled || loading)
  const [previousUnavailable, setPreviousUnavailable] = useState(unavailable)
  if (previousUnavailable !== unavailable) {
    setPreviousUnavailable(unavailable)
    if (unavailable) {
      setOpen(false)
      setSearch('')
      setIsSearching(false)
      setFocusedOption(null)
      setCategoryFilter('all')
      setProviderFilter(null)
    }
  }

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
    if (e.nativeEvent.isComposing || e.nativeEvent.keyCode === 229) return
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      setOpen(true)
      if (!displayOptions.length) return
      const selectedIndex = displayOptions.indexOf(value)
      if (!expanded || focusedIndex < 0) {
        setFocusedIndex(
          selectedIndex >= 0
            ? selectedIndex
            : e.key === 'ArrowDown'
              ? 0
              : displayOptions.length - 1,
        )
      } else {
        setFocusedIndex(
          e.key === 'ArrowDown'
            ? Math.min(focusedIndex + 1, displayOptions.length - 1)
            : Math.max(focusedIndex - 1, 0),
        )
      }
    } else if (
      expanded &&
      !isSearching &&
      (e.key === 'Home' || e.key === 'End')
    ) {
      e.preventDefault()
      setFocusedIndex(e.key === 'Home' ? 0 : displayOptions.length - 1)
    } else if (e.key === 'Backspace' && search === '' && !isSearching) {
      setIsSearching(true)
      setSearch(selected)
      e.preventDefault()
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (!expanded) {
        setOpen(true)
      } else if (focusedIndex >= 0 && displayOptions[focusedIndex]) {
        handleOptionClick(displayOptions[focusedIndex])
      } else if (categoryFiltered.length === 1) {
        handleOptionClick(categoryFiltered[0])
      }
    }
  }

  const handleFocus = () => {
    if (!expanded) {
      setOpen(true)
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
    if (unavailable) return
    inputRef.current?.focus({ preventScroll: true })
    closeMenu()
    onChange(opt)
  }

  const displayValue = isSearching ? search : selected
  const status = loading
    ? 'Loading models…'
    : !options.length
      ? 'No models available'
      : expanded && !displayOptions.length
        ? 'No models match your search or filters'
        : `${displayOptions.length} of ${options.length} models available`

  return (
    <div
      ref={rootRef}
      className={`relative ${className || ''}`}
      data-cy="model-selector"
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null))
          closeMenu()
      }}
      onKeyDown={(event) => {
        if (
          event.key === 'Escape' &&
          expanded &&
          !event.nativeEvent.isComposing
        ) {
          event.preventDefault()
          event.stopPropagation()
          inputRef.current?.focus({ preventScroll: true })
          closeMenu()
        }
      }}
    >
      <input
        ref={inputRef}
        id={inputId}
        type="text"
        role="combobox"
        aria-label={label || (id ? undefined : 'Model')}
        aria-autocomplete="list"
        aria-haspopup="listbox"
        aria-expanded={expanded}
        aria-controls={expanded ? listId : undefined}
        aria-activedescendant={
          expanded && focusedIndex >= 0
            ? `${listId}-${focusedIndex}`
            : undefined
        }
        aria-describedby={statusId}
        aria-busy={loading}
        autoComplete="off"
        placeholder={
          expanded ? searchPlaceholder : placeholder || searchPlaceholder
        }
        value={displayValue}
        onChange={handleChange}
        onKeyDown={keyDown}
        onFocus={handleFocus}
        onClick={() => setOpen(true)}
        disabled={unavailable}
        data-cy="model-selector-input"
        className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:ring-2 focus:ring-cyan-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
      />
      <p
        id={statusId}
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className={
          loading ? 'mt-1 text-xs text-gray-500 dark:text-gray-400' : 'sr-only'
        }
      >
        {status}
      </p>
      {expanded && (
        <DropdownMenuWithRef
          ref={menuRef}
          pos={pos}
          filtered={displayOptions}
          search={search}
          value={value}
          onChange={handleOptionClick}
          setOpen={setOpen}
          listId={listId}
          label={label || 'Models'}
          focusedIndex={focusedIndex}
          setFocusedIndex={setFocusedIndex}
          itemRefs={itemRefs}
          categoryFilter={categoryFilter}
          onCategoryChange={handleCategoryChange}
          providerFilter={providerFilter}
          onProviderChange={handleProviderChange}
          availableProviders={availableProviders}
          totalCount={options.length}
        />
      )}
    </div>
  )
}

interface ProviderEntry {
  slug: string
  label: string
  count: number
}

function DropdownMenu(
  {
    pos,
    filtered,
    search,
    value,
    onChange,
    setOpen,
    listId,
    label,
    focusedIndex,
    setFocusedIndex,
    itemRefs,
    categoryFilter,
    onCategoryChange,
    providerFilter,
    onProviderChange,
    availableProviders,
    totalCount,
  }: {
    pos: {
      top: number
      left: number
      width: number
      above?: boolean
      maxHeight?: number
    }
    filtered: string[]
    search: string
    value: string
    onChange: (v: string) => void
    setOpen: (b: boolean) => void
    listId: string
    label: string
    focusedIndex: number
    setFocusedIndex: (i: number) => void
    itemRefs: React.MutableRefObject<(HTMLButtonElement | null)[]>
    categoryFilter: RouteCategory | 'all'
    onCategoryChange: (c: RouteCategory | 'all') => void
    providerFilter: string | null
    onProviderChange: (slug: string | null) => void
    availableProviders: ProviderEntry[]
    totalCount: number
  },
  ref: React.Ref<HTMLDivElement>,
) {
  return (
    <div
      className="fixed z-[90] mt-1 flex max-h-[28rem] flex-col rounded-lg border border-gray-200 bg-white shadow-lg dark:border-gray-600 dark:bg-gray-800"
      style={{
        top: pos.top,
        left: pos.left,
        width: pos.width,
        maxHeight: pos.maxHeight,
        transform: pos.above ? 'translateY(-100%)' : undefined,
      }}
    >
      {/* Category filter pills */}
      <div
        className="flex shrink-0 flex-wrap gap-1 border-b border-gray-200 px-2 py-1.5 dark:border-gray-600"
        onMouseDown={(e) => e.preventDefault()}
      >
        {CATEGORY_PILLS.map((pill) => (
          <button
            key={pill.key}
            type="button"
            aria-pressed={categoryFilter === pill.key}
            onClick={() => onCategoryChange(pill.key)}
            className={`rounded-full px-2 py-0.5 text-[10px] font-medium transition-all ${
              categoryFilter === pill.key
                ? `${pill.color} ring-1 ring-current`
                : 'bg-gray-100 text-gray-500 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-400 dark:hover:bg-gray-600'
            }`}
          >
            {pill.label}
          </button>
        ))}
      </div>
      {/* Provider filter row */}
      {availableProviders.length > 0 && (
        <div
          className="flex max-h-16 shrink-0 flex-wrap gap-1 overflow-y-auto border-b border-gray-200 px-2 py-1 dark:border-gray-600"
          onMouseDown={(e) => e.preventDefault()}
        >
          <button
            onClick={() => onProviderChange(null)}
            type="button"
            aria-pressed={providerFilter === null}
            className={`rounded px-1.5 py-0.5 text-[10px] font-medium transition-all ${
              providerFilter === null
                ? 'bg-cyan-200 text-cyan-800 ring-1 ring-cyan-400 dark:bg-cyan-800 dark:text-cyan-200'
                : 'bg-gray-100 text-gray-500 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-400 dark:hover:bg-gray-600'
            }`}
          >
            All providers
          </button>
          {availableProviders.map((p) => (
            <button
              key={p.slug}
              type="button"
              aria-pressed={providerFilter === p.slug}
              onClick={() =>
                onProviderChange(providerFilter === p.slug ? null : p.slug)
              }
              title={`${p.label} (${p.count} models)`}
              className={`rounded px-1.5 py-0.5 text-[10px] font-medium transition-all ${
                providerFilter === p.slug
                  ? 'bg-cyan-200 text-cyan-800 ring-1 ring-cyan-400 dark:bg-cyan-800 dark:text-cyan-200'
                  : 'bg-gray-100 text-gray-500 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-400 dark:hover:bg-gray-600'
              }`}
            >
              {p.label} <span className="opacity-60">{p.count}</span>
            </button>
          ))}
        </div>
      )}
      {/* Count indicator */}
      <div
        aria-hidden="true"
        className="shrink-0 border-b border-gray-100 px-3 py-1 text-[10px] text-gray-400 dark:border-gray-700 dark:text-gray-500"
      >
        {filtered.length === totalCount
          ? `${totalCount} models`
          : `${filtered.length} of ${totalCount} models`}
        {providerFilter && (
          <span className="ml-1 text-cyan-500">
            · {getProviderInfo(providerFilter).label}
          </span>
        )}
      </div>
      {/* Model list */}
      <div
        ref={ref}
        id={listId}
        role="listbox"
        aria-label={label}
        className="min-h-0 flex-1 overflow-y-auto"
      >
        {!filtered.length ? (
          <div
            aria-hidden="true"
            className="px-3 py-2 text-sm text-gray-500 dark:text-gray-400"
          >
            {!totalCount
              ? 'No models available'
              : search
                ? `No models matching “${search}”`
                : 'No models match these filters'}
          </div>
        ) : (
          filtered.map((opt, idx) => (
            <DropdownOptionItemWithRef
              key={opt}
              id={`${listId}-${idx}`}
              option={opt}
              isSelected={opt === value}
              isFocused={idx === focusedIndex}
              onClick={() => {
                onChange(opt)
                setOpen(false)
              }}
              onMouseEnter={() => setFocusedIndex(idx)}
              ref={(el: HTMLButtonElement | null) => {
                itemRefs.current[idx] = el
              }}
            />
          ))
        )}
      </div>
    </div>
  )
}

const DropdownMenuWithRef = forwardRef(DropdownMenu)
