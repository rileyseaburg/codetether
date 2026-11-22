'use client'

import { useMemo, useState } from 'react'

interface WorkspaceChoice {
  id: string
  name: string
  path: string
  description?: string
  status: string
  worker_id?: string
  runtime: 'container' | 'vm'
}

export function WorkspaceBrowser({
  workspaces,
  selectedId,
  onSelect,
  onRegister,
  statusLabel,
  connectedWorkerIds = [],
  loading = false,
  error,
  onRetry,
}: {
  workspaces: WorkspaceChoice[]
  selectedId: string
  onSelect: (id: string) => void
  onRegister: () => void
  statusLabel: (status: string) => string
  connectedWorkerIds?: string[]
  loading?: boolean
  error?: string | null
  onRetry?: () => void
}) {
  const [query, setQuery] = useState('')
  const [runtime, setRuntime] = useState('all')
  const [visible, setVisible] = useState(8)
  const [connectedOnly, setConnectedOnly] = useState(false)
  const connected = useMemo(
    () => new Set(connectedWorkerIds),
    [connectedWorkerIds],
  )
  const filtered = useMemo(() => {
    const search = query.trim().toLowerCase()
    return workspaces
      .filter(
        (workspace) =>
          (runtime === 'all' || workspace.runtime === runtime) &&
          (!connectedOnly || connected.has(workspace.worker_id || '')) &&
          [
            workspace.name,
            workspace.path,
            workspace.description,
            workspace.id,
          ].some((value) => value?.toLowerCase().includes(search)),
      )
      .sort(
        (a, b) =>
          Number(connected.has(b.worker_id || '')) -
          Number(connected.has(a.worker_id || '')),
      )
  }, [workspaces, query, runtime, connectedOnly, connected])
  const selected = workspaces.find((workspace) => workspace.id === selectedId)

  return (
    <section
      aria-labelledby="workspace-discovery-title"
      className="overflow-hidden rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900"
    >
      <div className="border-b border-gray-100 p-4 sm:p-5 dark:border-gray-800">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2
            id="workspace-discovery-title"
            className="text-base font-semibold text-gray-900 dark:text-white"
          >
            <span
              className="mr-2 inline-flex h-6 w-6 items-center justify-center rounded-full bg-gray-100 text-xs text-gray-600 dark:bg-gray-800 dark:text-gray-300"
              aria-hidden="true"
            >
              1
            </span>
            Choose a workspace
          </h2>
          <span className="text-xs text-gray-500 dark:text-gray-400">
            {loading
              ? 'Loading…'
              : `${filtered.length} of ${workspaces.length}`}
          </span>
        </div>
        <div className="mt-4 flex flex-col gap-3 sm:flex-row">
          <div className="min-w-0 flex-1">
            <label htmlFor="workspace-home-search" className="sr-only">
              Search workspaces
            </label>
            <input
              id="workspace-home-search"
              type="search"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value)
                setVisible(8)
              }}
              placeholder="Search by name or path…"
              className="w-full rounded-lg border border-gray-300 bg-white px-4 py-2.5 text-sm text-gray-900 focus:border-cyan-600 focus:ring-cyan-600 dark:border-gray-700 dark:bg-gray-950 dark:text-white"
            />
          </div>
          <div>
            <label htmlFor="workspace-home-runtime" className="sr-only">
              Filter workspaces by runtime
            </label>
            <select
              id="workspace-home-runtime"
              value={runtime}
              onChange={(event) => {
                setRuntime(event.target.value)
                setVisible(8)
              }}
              className="w-full rounded-lg border border-gray-300 bg-white py-2.5 pr-9 pl-3 text-sm text-gray-700 focus:border-cyan-600 focus:ring-cyan-600 sm:w-auto dark:border-gray-700 dark:bg-gray-950 dark:text-gray-200"
            >
              <option value="all">All runtimes</option>
              <option value="container">Containers</option>
              <option value="vm">Virtual machines</option>
            </select>
          </div>
        </div>
        <label className="mt-3 flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
          <input
            type="checkbox"
            checked={connectedOnly}
            onChange={(event) => {
              setConnectedOnly(event.target.checked)
              setVisible(8)
            }}
            className="rounded border-gray-300 text-cyan-700 focus:ring-cyan-600 dark:border-gray-600"
          />
          Connected workers only
        </label>
        <p className="mt-2 text-xs text-gray-400 dark:text-gray-500">
          Connected workers appear first. Other registrations may be stale.
        </p>
      </div>

      {error && (
        <div
          role="alert"
          className="m-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-900 dark:bg-amber-950/40 dark:text-amber-200"
        >
          {error}{' '}
          {onRetry && (
            <button type="button" onClick={onRetry} className="ml-2 underline">
              Retry
            </button>
          )}
        </div>
      )}
      {loading && (
        <p
          role="status"
          className="px-6 py-10 text-center text-sm text-gray-500 dark:text-gray-400"
        >
          Loading your workspaces…
        </p>
      )}
      {!loading && !error && workspaces.length === 0 ? (
        <div className="px-6 py-10 text-center">
          <h3 className="font-medium text-gray-900 dark:text-white">
            Start with your code
          </h3>
          <p className="mx-auto mt-2 max-w-md text-sm text-gray-500 dark:text-gray-400">
            Add a local folder, connect a Git repository, or attach an external
            workspace.
          </p>
          <button
            type="button"
            onClick={onRegister}
            className="mt-5 rounded-lg bg-cyan-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-cyan-800"
          >
            Add a workspace
          </button>
          <p className="mt-3 text-xs text-gray-500 dark:text-gray-400">
            You can also launch below to create one automatically.
          </p>
        </div>
      ) : !loading && filtered.length === 0 && !error ? (
        <div role="status" className="px-6 py-8 text-center">
          <p className="text-sm text-gray-600 dark:text-gray-300">
            No workspaces match these filters.
          </p>
          <button
            type="button"
            onClick={() => {
              setQuery('')
              setRuntime('all')
              setConnectedOnly(false)
              setVisible(8)
            }}
            className="mt-3 text-sm font-medium text-cyan-700 underline dark:text-cyan-400"
          >
            Clear filters
          </button>
        </div>
      ) : (
        <ul
          aria-label="Available workspaces"
          className="grid max-h-[14rem] grid-cols-1 gap-2 overflow-y-auto p-3 sm:max-h-[26rem] sm:p-4"
        >
          {filtered.slice(0, visible).map((workspace) => {
            const active = workspace.id === selectedId
            return (
              <li key={workspace.id} className="min-w-0">
                <button
                  type="button"
                  aria-pressed={active}
                  aria-controls="workspace-launcher"
                  onClick={() => onSelect(workspace.id)}
                  className={`w-full rounded-xl border p-4 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-600 ${active ? 'border-cyan-600 bg-cyan-50/60 dark:border-cyan-500 dark:bg-cyan-950/40' : 'border-transparent bg-gray-50 hover:border-gray-300 hover:bg-gray-100 dark:bg-gray-800/50 dark:hover:border-gray-600 dark:hover:bg-gray-800'}`}
                >
                  <span className="flex items-start justify-between gap-3">
                    <span className="truncate text-sm font-semibold text-gray-900 dark:text-white">
                      {workspace.name}
                    </span>
                    {active && (
                      <span className="shrink-0 text-xs font-medium text-cyan-700 dark:text-cyan-300">
                        Selected
                      </span>
                    )}
                  </span>
                  <span
                    className="mt-1 block truncate text-xs text-gray-500 dark:text-gray-400"
                    title={workspace.path}
                  >
                    {workspace.path || 'No source path configured'}
                  </span>
                  <span className="mt-3 flex items-center justify-between gap-2 text-xs text-gray-500 dark:text-gray-400">
                    <span>
                      {workspace.runtime === 'vm'
                        ? 'Virtual machine'
                        : 'Container'}
                    </span>
                    <span>{statusLabel(workspace.status)}</span>
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
      {filtered.length > visible && (
        <div className="border-t border-gray-100 px-5 py-3 dark:border-gray-800">
          <button
            type="button"
            onClick={() => setVisible((count) => count + 8)}
            className="text-sm font-medium text-cyan-700 hover:underline dark:text-cyan-400"
          >
            Show more workspaces ({filtered.length - visible} remaining)
          </button>
        </div>
      )}
      {selected && (
        <div className="border-t border-gray-100 px-5 py-3 dark:border-gray-800">
          <a
            href="#workspace-launcher"
            className="text-sm font-medium text-cyan-700 hover:underline dark:text-cyan-400"
          >
            Continue with {selected.name} →
          </a>
          {!filtered
            .slice(0, visible)
            .some((workspace) => workspace.id === selectedId) && (
            <button
              type="button"
              onClick={() => {
                setQuery(selected.id)
                setRuntime('all')
                setConnectedOnly(false)
                setVisible(8)
              }}
              className="mt-1 block text-xs text-gray-500 underline dark:text-gray-400"
            >
              Show selected workspace
            </button>
          )}
        </div>
      )}
      <p role="status" aria-live="polite" className="sr-only">
        {filtered.length} matching workspaces.
        {selected ? ` Selected: ${selected.name}.` : ''}
      </p>
      {selected &&
        !filtered.some((workspace) => workspace.id === selectedId) && (
          <p className="border-t border-gray-100 px-5 py-3 text-sm text-gray-500 dark:border-gray-800 dark:text-gray-400">
            Still selected:{' '}
            <strong className="font-medium">{selected.name}</strong>. Filtering
            does not change your selection.
          </p>
        )}
    </section>
  )
}