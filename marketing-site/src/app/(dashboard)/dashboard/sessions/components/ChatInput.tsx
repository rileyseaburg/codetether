interface ChatInputProps {
    draftMessage: string
    loading: boolean
    actionStatus: string | null
    hasSession: boolean
    onDraftChange: (value: string) => void
    onSend: () => void
}

export function ChatInput({ draftMessage, loading, actionStatus, hasSession, onDraftChange, onSend }: ChatInputProps) {
    if (!hasSession) {
        return (
            <div className="border-t border-gray-200 dark:border-gray-700 p-3 sm:p-4" role="status">
                <p className="text-sm text-gray-500 dark:text-gray-400">Select a session to start chatting.</p>
            </div>
        )
    }

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            onSend()
        }
    }

    const canSend = !loading && draftMessage.trim().length > 0
    const characterCount = draftMessage.length

    return (
        <footer className="border-t border-gray-200 dark:border-gray-700 p-3 sm:p-4" aria-label="Message input">
            <form
                onSubmit={(e) => { e.preventDefault(); onSend() }}
                className="space-y-2"
            >
                <div className="flex gap-2 items-end">
                    <div className="flex-1 relative">
                        <label htmlFor="chat-message-input" className="sr-only">
                            Type your message to the agent
                        </label>
                        <textarea
                            id="chat-message-input"
                            value={draftMessage}
                            onChange={(e) => onDraftChange(e.target.value)}
                            onKeyDown={handleKeyDown}
                            rows={2}
                            placeholder="Message... (Enter to send)"
                            className="w-full resize-none rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                            aria-describedby="input-hints"
                            aria-busy={loading}
                            disabled={loading}
                        />
                        <span id="input-hints" className="sr-only">
                            Press Enter to send, Shift+Enter for new line. {characterCount} characters typed.
                        </span>
                    </div>
                    <button
                        type="submit"
                        disabled={!canSend}
                        className="rounded-md bg-indigo-600 px-3 sm:px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
                        aria-label={loading ? 'Sending message...' : 'Send message'}
                        aria-busy={loading}
                    >
                        {loading ? 'Sending...' : 'Send'}
                    </button>
                </div>
                <div className="flex items-center justify-between gap-3">
                    <span className="text-xs text-gray-500 dark:text-gray-400 hidden sm:block" aria-hidden="true">
                        Tip: Scroll up to pause auto-scroll.
                    </span>
                    {actionStatus && (
                        <span
                            className="text-xs text-gray-500 dark:text-gray-400"
                            role="status"
                            aria-live="polite"
                        >
                            {actionStatus}
                        </span>
                    )}
                </div>
            </form>
        </footer>
    )
}
