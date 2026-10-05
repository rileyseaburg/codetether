import { useMemo, useState, useRef, useEffect } from 'react'
import type { Workspace, Session } from '../types'
import { ChatIcon } from './ChatIcon'
import { SessionItem } from './SessionItem'

interface Props {
  workspaces: Workspace[]
  sessions: Session[]
  selectedWorkspace: string
  selectedSession: Session | null
  onWorkspaceChange: (id: string) => void
  onSessionSelect: (s: Session) => void
  onSearchChange?: (query: string) => void
  hasMoreSessions?: boolean
  loadingMoreSessions?: boolean
  onLoadMoreSessions?: () => void
  totalSessions?: number
  loading?: boolean
  loadingLabel?: string
  error?: string | null
  onRetry?: () => void
}

export function SessionList({
  workspaces,
  sessions,
  selectedWorkspace,
  selectedSession,
  onWorkspaceChange,
  onSessionSelect,
  onSearchChange,
  hasMoreSessions = false,
  loadingMoreSessions = false,
  onLoadMoreSessions,
  totalSessions,
  loading = false,
  loadingLabel = 'Loading sessions…',
  error = null,
  onRetry,
}: Props) {
  const [query, setQuery] = useState('')
  const [sortOrder, setSortOrder] = useState<'recent' | 'oldest'>('recent')
  const normalizedQuery = query.trim().toLowerCase()
  const workspaceName =
    workspaces.find((workspace) => workspace.id === selectedWorkspace)?.name ||
    'this workspace'
  const sentinelRef = useRef<HTMLDivElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setQuery('')
    setSortOrder('recent')
    onSearchChange?.('')
  }, [selectedWorkspace, onSearchChange])

  useEffect(() => {
    if (!onSearchChange) return
    const timer = setTimeout(() => onSearchChange(query.trim()), 300)
    return () => clearTimeout(timer)
  }, [query, onSearchChange])

  const sortedSessions = useMemo(() => {
    const filtered =
      normalizedQuery && !onSearchChange
        ? sessions.filter((session) =>
            `${session.title || ''} ${session.id}`
              .toLowerCase()
              .includes(normalizedQuery),
          )
        : sessions
    const timestamp = (session: Session) => {
      const value = session.time?.updated || session.time?.created || 0
      return Number.isFinite(value) ? value : 0
    }
    return filtered
      .map((session, index) => ({ session, index }))
      .sort((a, b) => {
        const delta = timestamp(a.session) - timestamp(b.session)
        return delta === 0
          ? a.index - b.index
          : sortOrder === 'recent'
            ? -delta
            : delta
      })
      .map((item) => item.session)
  }, [sessions, normalizedQuery, onSearchChange, sortOrder])

  useEffect(() => {
    if (
      !hasMoreSessions ||
      !onLoadMoreSessions ||
      loadingMoreSessions ||
      loading ||
      error ||
      typeof IntersectionObserver === 'undefined'
    )
      return
    const sentinel = sentinelRef.current
    if (!sentinel) return
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) onLoadMoreSessions()
      },
      { root: listRef.current, rootMargin: '100px', threshold: 0 },
    )
    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [hasMoreSessions, onLoadMoreSessions, loadingMoreSessions, loading, error])

  const showEmpty = !loading && !error && sortedSessions.length === 0
  return (
    <nav
      aria-label="Chat sessions"
      className="flex h-full min-h-0 flex-col bg-gray-50 dark:bg-gray-950"
    >
      <div className="shrink-0 space-y-4 border-b border-gray-200 p-4 sm:p-5 dark:border-gray-800">
        <div>
          <h1
            id="sessions-heading"
            className="text-xl font-semibold tracking-tight text-gray-950 dark:text-white"
          >
            Sessions
          </h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Pick up a conversation.
          </p>
        </div>
        <div>
          <label
            htmlFor="workspace-select"
            className="mb-1.5 block text-xs font-medium text-gray-600 dark:text-gray-300"
          >
            Workspace
          </label>
          <select
            id="workspace-select"
            aria-label="Select workspace"
            value={selectedWorkspace}
            onChange={(event) => onWorkspaceChange(event.target.value)}
            className="min-h-11 w-full min-w-0 rounded-lg border-gray-300 bg-white text-sm text-gray-900 focus:border-cyan-600 focus:ring-cyan-600 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
          >
            <option value="">Select workspace…</option>
            {workspaces.map((workspace) => (
              <option key={workspace.id} value={workspace.id}>
                {workspace.name}
              </option>
            ))}
          </select>
        </div>
        {selectedWorkspace && (
          <div className="space-y-2">
            <div className="relative">
              <label htmlFor="session-search" className="sr-only">
                Search sessions
              </label>
              <input
                id="session-search"
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Find a session…"
                className="min-h-11 w-full rounded-lg border-gray-300 bg-white pr-16 text-sm text-gray-900 focus:border-cyan-600 focus:ring-cyan-600 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
              />
              {query && (
                <button
                  type="button"
                  onClick={() => setQuery('')}
                  aria-label="Clear search"
                  className="absolute inset-y-0 right-2 rounded px-2 text-xs text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white"
                >
                  Clear
                </button>
              )}
            </div>
            <details>
              <summary className="w-fit cursor-pointer rounded py-1 text-xs text-gray-500 focus-visible:outline-2 focus-visible:outline-cyan-600 dark:text-gray-400">
                Sort & list details
              </summary>
              <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
                <label htmlFor="session-sort">Sort</label>
                <select
                  id="session-sort"
                  value={sortOrder}
                  onChange={(event) =>
                    setSortOrder(event.target.value as 'recent' | 'oldest')
                  }
                  className="min-h-10 rounded-lg border-gray-300 bg-white text-xs text-gray-700 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200"
                >
                  <option value="recent">Most recent</option>
                  <option value="oldest">Oldest first</option>
                </select>
                {!loading && !error && (
                  <span>
                    {totalSessions && totalSessions > sessions.length
                      ? `${sessions.length} of ${totalSessions}`
                      : sessions.length}{' '}
                    sessions
                  </span>
                )}
              </div>
            </details>
          </div>
        )}
      </div>
      <div
        ref={listRef}
        role="group"
        aria-labelledby="sessions-heading"
        aria-busy={loading || loadingMoreSessions}
        className="min-h-0 flex-1 overflow-y-auto overscroll-contain"
      >
        {loading && (
          <p
            className="p-6 text-sm text-gray-500 dark:text-gray-400"
            role="status"
          >
            {loadingLabel}
          </p>
        )}
        {error && (
          <div
            className="m-4 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/30 dark:text-red-200"
            role="alert"
          >
            <p>{error}</p>
            <button
              type="button"
              onClick={onRetry}
              disabled={loading || loadingMoreSessions}
              className="mt-3 min-h-10 rounded-lg border border-current px-3 py-2 text-xs font-medium disabled:opacity-50"
            >
              Retry sessions
            </button>
          </div>
        )}
        {showEmpty && (
          <div className="px-5 py-10 text-center" role="status">
            <ChatIcon
              className="mx-auto h-8 w-8 text-gray-400"
              aria-hidden="true"
            />
            <p className="mt-3 text-sm font-medium text-gray-700 dark:text-gray-200">
              {normalizedQuery
                ? `No matches for “${query}”.`
                : selectedWorkspace
                  ? 'No sessions found'
                  : workspaces.length
                    ? 'Select a workspace'
                    : 'No workspaces available'}
            </p>
            <p className="mt-2 text-sm leading-6 text-gray-500 dark:text-gray-400">
              {normalizedQuery
                ? 'Try another search or clear the filter.'
                : selectedWorkspace
                  ? 'Conversations from this workspace will appear here.'
                  : 'Choose where you want to work to see its conversations.'}
            </p>
            {normalizedQuery && (
              <button
                type="button"
                onClick={() => setQuery('')}
                className="mt-3 min-h-10 rounded-lg px-3 text-sm font-medium text-cyan-700 dark:text-cyan-300"
              >
                Show all sessions
              </button>
            )}
            {!selectedWorkspace && !workspaces.length && (
              <a
                href="/dashboard/getting-started"
                className="mt-4 inline-block rounded-lg px-3 py-2 text-sm font-medium text-cyan-700 underline dark:text-cyan-300"
              >
                Connect a workspace
              </a>
            )}
          </div>
        )}
        {!loading && sortedSessions.length > 0 && (
          <div className="divide-y divide-gray-200 dark:divide-gray-800">
            <p className="sr-only" role="status">
              {sortedSessions.length} sessions available in {workspaceName}
            </p>
            {sortedSessions.map((session) => (
              <SessionItem
                key={session.id}
                session={session}
                isSelected={selectedSession?.id === session.id}
                onSelect={onSessionSelect}
              />
            ))}
            {hasMoreSessions && (
              <div ref={sentinelRef} className="p-4 text-center">
                <button
                  type="button"
                  onClick={onLoadMoreSessions}
                  disabled={loadingMoreSessions || loading || !!error || !onLoadMoreSessions}
                  className="min-h-11 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 disabled:opacity-50 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200"
                >
                  {loadingMoreSessions ? 'Loading more…' : 'Load more sessions'}
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </nav>
  )
}