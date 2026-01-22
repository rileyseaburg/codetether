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
            <div className="shrink-0 border-t border-gray-200 p-3 dark:border-gray-700 sm:p-4" role="status">
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
        <footer className="shrink-0 border-t border-gray-200 p-1 dark:border-gray-700 sm:p-4" aria-label="Message input">
            <form
                onSubmit={(e) => { e.preventDefault(); onSend() }}
                className="space-y-1 sm:space-y-2"
            >
                <div className="flex items-end gap-2 rounded-xl border border-gray-200 bg-white p-1 shadow-sm focus-within:ring-2 focus-within:ring-indigo-500 dark:border-gray-700 dark:bg-gray-800 sm:p-2">
                    <div className="flex-1">
                        <label htmlFor="chat-message-input" className="sr-only">
                            Type your message to the agent
                        </label>
                        <textarea
                            id="chat-message-input"
                            value={draftMessage}
                            onChange={(e) => onDraftChange(e.target.value)}
                            onKeyDown={handleKeyDown}
                            rows={1}
                            placeholder="Message the agent..."
                            className="w-full min-h-[2rem] resize-none bg-transparent px-2 py-1 text-sm leading-tight text-gray-900 placeholder:text-gray-400 focus:outline-none focus:min-h-[4.5rem] dark:text-white sm:min-h-[3.25rem] sm:focus:min-h-[5.5rem] transition-[min-height]"
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
                        className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-2.5 py-1.5 text-xs font-medium text-white hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50 focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 sm:px-3 sm:py-2 sm:text-sm"
                        aria-label={loading ? 'Sending message...' : 'Send message'}
                        aria-busy={loading}
                    >
                        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M13 5l7 7-7 7" />
                        </svg>
                        <span className="hidden sm:inline">{loading ? 'Sending...' : 'Send'}</span>
                    </button>
                </div>
                {actionStatus && (
                    <div
                        className={`text-xs sm:hidden ${actionStatus.toLowerCase().includes('failed') ? 'text-red-600 dark:text-red-400' : 'text-gray-500 dark:text-gray-400'}`}
                        role="status"
                        aria-live="polite"
                    >
                        {actionStatus}
                    </div>
                )}
                <div className="hidden items-center justify-between gap-3 text-xs text-gray-500 dark:text-gray-400 sm:flex">
                    <span aria-hidden="true">Enter to send | Shift+Enter for new line.</span>
                    {actionStatus && (
                        <span
                            className={`${actionStatus.toLowerCase().includes('failed') ? 'text-red-600 dark:text-red-400' : ''}`}
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
