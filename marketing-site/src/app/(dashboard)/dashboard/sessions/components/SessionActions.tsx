interface SessionActionsProps {
    loading: boolean
    onResume: () => void
    onRefresh: () => void
    sessionTitle?: string
}

export function SessionActions({ loading, onResume, onRefresh, sessionTitle = 'session' }: SessionActionsProps) {
    return (
        <div role="group" aria-label="Session actions">
            <button
                type="button"
                onClick={onResume}
                disabled={loading}
                className="rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-xs font-medium text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50 focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 mr-2"
                aria-label={`Resume ${sessionTitle}`}
                aria-busy={loading}
            >
                Resume
                <span className="sr-only"> session</span>
            </button>
            <button
                type="button"
                onClick={onRefresh}
                disabled={loading}
                className="rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-xs font-medium text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50 focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
                aria-label={`Refresh messages for ${sessionTitle}`}
                aria-busy={loading}
            >
                Refresh
                <span className="sr-only"> messages</span>
            </button>
        </div>
    )
}
