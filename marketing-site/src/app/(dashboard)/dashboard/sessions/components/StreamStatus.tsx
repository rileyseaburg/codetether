interface StreamStatusProps {
    connected: boolean
    status: string
}

export function StreamStatus({ connected, status }: StreamStatusProps) {
    const displayStatus = status || (connected ? 'Live' : 'Offline')
    const connectionLabel = connected ? 'Connected to live stream' : 'Not connected to live stream'

    return (
        <div
            className="hidden sm:flex items-center gap-2"
            role="status"
            aria-live="polite"
            aria-label={`Stream status: ${displayStatus}. ${connectionLabel}`}
        >
            <span
                className={`h-2.5 w-2.5 rounded-full ${connected ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`}
                aria-hidden="true"
            />
            <span className="text-xs text-gray-500 dark:text-gray-400">
                {displayStatus}
            </span>
        </div>
    )
}
