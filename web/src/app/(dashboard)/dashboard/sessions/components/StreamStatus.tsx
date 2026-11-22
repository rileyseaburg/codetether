interface StreamStatusProps {
    connected: boolean
    status: string
}

export function StreamStatus({ connected, status }: StreamStatusProps) {
    const displayStatus = status || (connected ? 'Live' : 'Offline')
    const connectionLabel = connected ? 'Connected to live stream' : 'Not connected to live stream'

    return (
        <div
            className="hidden items-center gap-2 rounded-full border border-gray-200 bg-white px-3 py-1 text-xs text-gray-600 shadow-sm dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 sm:flex"
            role="status"
            aria-live="polite"
            aria-label={`Stream status: ${displayStatus}. ${connectionLabel}`}
        >
            <span
                className={`h-2.5 w-2.5 rounded-full ${connected ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`}
                aria-hidden="true"
            />
            <span>{displayStatus}</span>
        </div>
    )
}
