import VoiceChatButton from '../../components/voice/VoiceChatButton'

interface SessionActionsProps {
    loading: boolean
    awaitingResponse?: boolean
    onResume: () => void
    onRefresh: () => void
    sessionTitle?: string
    sessionId?: string
    codebaseId?: string
}

export function SessionActions({ loading, awaitingResponse, onResume, onRefresh, sessionTitle = 'session', sessionId, codebaseId }: SessionActionsProps) {
    return (
        <div role="group" aria-label="Session actions" className="flex flex-wrap items-center gap-2">
            <VoiceChatButton
                codebaseId={codebaseId}
                sessionId={sessionId}
                mode="chat"
            />
            {/* Hide Resume button when awaiting response - sending a message resumes implicitly */}
            {!awaitingResponse && (
                <button
                    type="button"
                    onClick={onResume}
                    disabled={loading}
                    className="rounded-lg border border-gray-300 px-3 py-2 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-700"
                    aria-label={`Resume ${sessionTitle}`}
                    aria-busy={loading}
                >
                    Resume
                    <span className="sr-only"> session</span>
                </button>
            )}
            <button
                type="button"
                onClick={onRefresh}
                disabled={loading}
                className="rounded-lg border border-gray-300 px-3 py-2 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-700"
                aria-label={`Refresh messages for ${sessionTitle}`}
                aria-busy={loading}
            >
                Refresh
                <span className="sr-only"> messages</span>
            </button>
        </div>
    )
}
