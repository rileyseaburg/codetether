import { useMemo, useState, useRef, useEffect } from 'react'
import type { Codebase, Session } from '../types'
import { ChatIcon } from './ChatIcon'
import { SessionItem } from './SessionItem'

interface Props {
    codebases: Codebase[]
    sessions: Session[]
    selectedCodebase: string
    selectedSession: Session | null
    onCodebaseChange: (id: string) => void
    onSessionSelect: (s: Session) => void
    onSearchChange?: (query: string) => void
    hasMoreSessions?: boolean
    loadingMoreSessions?: boolean
    onLoadMoreSessions?: () => void
    totalSessions?: number
}

export function SessionList({
    codebases,
    sessions,
    selectedCodebase,
    selectedSession,
    onCodebaseChange,
    onSessionSelect,
    onSearchChange,
    hasMoreSessions = false,
    loadingMoreSessions = false,
    onLoadMoreSessions,
    totalSessions,
}: Props) {
    const [filtersOpen, setFiltersOpen] = useState(false)
    const selectedCodebaseName = codebases.find(cb => cb.id === selectedCodebase)?.name || 'all codebases'
    const [query, setQuery] = useState('')
    const [sortOrder, setSortOrder] = useState<'recent' | 'oldest'>('recent')
    const normalizedQuery = query.trim().toLowerCase()
    const totalLabel = totalSessions && totalSessions > sessions.length
        ? `${sessions.length} of ${totalSessions}`
        : `${sessions.length}`

    useEffect(() => {
        setQuery('')
        setSortOrder('recent')
        if (onSearchChange) {
            onSearchChange('')
        }
        setFiltersOpen(!selectedCodebase)
    }, [selectedCodebase, onSearchChange])

    useEffect(() => {
        if (!onSearchChange) return
        const handle = setTimeout(() => {
            onSearchChange(query.trim())
        }, 300)
        return () => clearTimeout(handle)
    }, [query, onSearchChange])

    const filteredSessions = useMemo(() => {
        if (!normalizedQuery || onSearchChange) return sessions
        return sessions.filter((s) => {
            const haystack = `${s.title || ''} ${s.id}`.toLowerCase()
            return haystack.includes(normalizedQuery)
        })
    }, [sessions, normalizedQuery, onSearchChange])

    const sortedSessions = useMemo(() => {
        const withIndex = filteredSessions.map((session, index) => ({ session, index }))
        const getTimestamp = (session: Session) => {
            const time = session.time?.updated || session.time?.created || 0
            return Number.isFinite(time) ? time : 0
        }
        withIndex.sort((a, b) => {
            const aTime = getTimestamp(a.session)
            const bTime = getTimestamp(b.session)
            if (aTime === bTime) return a.index - b.index
            return sortOrder === 'recent' ? bTime - aTime : aTime - bTime
        })
        return withIndex.map(({ session }) => session)
    }, [filteredSessions, sortOrder])

    const hasQuery = normalizedQuery.length > 0
    const showEmpty = !hasQuery && sessions.length === 0
    const showFilteredEmpty = hasQuery && sortedSessions.length === 0

    // Infinite scroll: load more when sentinel comes into view
    const sentinelRef = useRef<HTMLDivElement>(null)
    const listRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        if (!hasMoreSessions || !onLoadMoreSessions || loadingMoreSessions) return
        const sentinel = sentinelRef.current
        if (!sentinel) return

        const observer = new IntersectionObserver(
            (entries) => {
                if (entries[0]?.isIntersecting) {
                    onLoadMoreSessions()
                }
            },
            { root: listRef.current, rootMargin: '100px', threshold: 0 }
        )
        observer.observe(sentinel)
        return () => observer.disconnect()
    }, [hasMoreSessions, onLoadMoreSessions, loadingMoreSessions])

    return (
        <nav
            aria-label="Chat sessions"
            className="flex h-full min-h-0 max-h-full flex-col overflow-hidden rounded-lg bg-white shadow-sm dark:bg-gray-800 dark:ring-1 dark:ring-white/10"
        >
            <div className="shrink-0 border-b border-gray-200 p-2 dark:border-gray-700 sm:p-4">
                <div className="flex items-start justify-between gap-3">
                    <div>
                        <h2 id="sessions-heading" className="text-base font-semibold text-gray-900 dark:text-white">Sessions</h2>
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                            {selectedCodebaseName} - {totalLabel} total
                        </p>
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="rounded-full bg-gray-100 px-2 py-1 text-[10px] font-medium text-gray-600 dark:bg-gray-700 dark:text-gray-200">
                            {filteredSessions.length}
                        </span>
                        <button
                            type="button"
                            onClick={() => setFiltersOpen((prev) => !prev)}
                            aria-expanded={filtersOpen}
                            aria-controls="session-filters"
                            className="rounded-full border border-gray-200 px-2 py-1 text-[10px] font-medium text-gray-600 transition-colors hover:bg-gray-50 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-700 sm:hidden"
                        >
                            {filtersOpen ? 'Hide filters' : 'Filters'}
                        </button>
                    </div>
                </div>
                <div
                    id="session-filters"
                    className={`mt-2 grid gap-2 ${filtersOpen ? 'grid' : 'hidden'} sm:grid`}
                >
                    <div className="flex flex-col">
                        <label htmlFor="codebase-select" className="sr-only">Select codebase</label>
                        <select
                            id="codebase-select"
                            value={selectedCodebase}
                            onChange={(e) => onCodebaseChange(e.target.value)}
                            className="min-w-0 rounded-md border-gray-300 bg-white text-sm text-gray-900 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                            aria-describedby="codebase-hint"
                        >
                            <option value="">Select codebase...</option>
                            {codebases.map((cb) => <option key={cb.id} value={cb.id}>{cb.name}</option>)}
                        </select>
                        <span id="codebase-hint" className="sr-only">Choose a codebase to filter sessions</span>
                    </div>
                    <div className="relative">
                        <label htmlFor="session-search" className="sr-only">Search sessions</label>
                        <input
                            id="session-search"
                            type="text"
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            placeholder="Search sessions..."
                            className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 pr-10 text-sm text-gray-900 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                        />
                        {query && (
                            <button
                                type="button"
                                onClick={() => setQuery('')}
                                className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-600 dark:hover:text-gray-200"
                                aria-label="Clear search"
                            >
                                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        )}
                    </div>
                    <div className="flex items-center justify-between gap-2">
                        <label htmlFor="session-sort" className="text-xs font-medium text-gray-400">
                            Sort
                        </label>
                        <select
                            id="session-sort"
                            value={sortOrder}
                            onChange={(e) => setSortOrder(e.target.value as 'recent' | 'oldest')}
                            className="min-w-[140px] rounded-md border border-gray-300 bg-white px-2 py-1 text-xs text-gray-700 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200"
                        >
                            <option value="recent">Most recent</option>
                            <option value="oldest">Oldest first</option>
                        </select>
                    </div>
                </div>
            </div>
            <div
                ref={listRef}
                role="listbox"
                aria-labelledby="sessions-heading"
                aria-activedescendant={selectedSession?.id ? `session-${selectedSession.id}` : undefined}
                className="flex min-h-0 flex-1 basis-0 flex-col divide-y divide-gray-200 overflow-y-auto overflow-x-hidden dark:divide-gray-700"
                tabIndex={0}
            >
                {showEmpty && (
                    <div className="p-6 text-center text-gray-500 sm:p-8" role="status" aria-live="polite">
                        <ChatIcon className="mx-auto h-10 w-10 sm:h-12 sm:w-12 text-gray-400" aria-hidden="true" />
                        <p className="mt-2 text-sm">{selectedCodebase ? 'No sessions found' : 'Select a codebase'}</p>
                    </div>
                )}
                {showFilteredEmpty && (
                    <div className="p-6 text-center text-gray-500 sm:p-8" role="status" aria-live="polite">
                        <ChatIcon className="mx-auto h-10 w-10 text-gray-400" aria-hidden="true" />
                        <p className="mt-2 text-sm">No matches for "{query}".</p>
                        <p className="mt-1 text-xs text-gray-400">Try clearing filters or changing codebase.</p>
                    </div>
                )}
                {!showEmpty && !showFilteredEmpty && (
                    <>
                        <p className="sr-only" role="status" aria-live="polite">
                            {sortedSessions.length} session{sortedSessions.length !== 1 ? 's' : ''} available in {selectedCodebaseName}
                        </p>
                        {sortedSessions.map((s) => (
                            <SessionItem
                                key={s.id}
                                session={s}
                                isSelected={selectedSession?.id === s.id}
                                onSelect={onSessionSelect}
                            />
                        ))}
                        {/* Infinite scroll sentinel */}
                        {hasMoreSessions && (
                            <div ref={sentinelRef} className="p-4 text-center">
                                {loadingMoreSessions ? (
                                    <div className="flex items-center justify-center gap-2 text-sm text-gray-500">
                                        <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                        </svg>
                                        Loading more...
                                    </div>
                                ) : (
                                    <span className="text-xs text-gray-400">
                                        {totalSessions ? `${sessions.length} of ${totalSessions}` : 'Scroll for more'}
                                    </span>
                                )}
                            </div>
                        )}
                    </>
                )}
            </div>
        </nav>
    )
}
