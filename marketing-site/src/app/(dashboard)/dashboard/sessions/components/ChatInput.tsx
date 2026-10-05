interface ChatInputProps {
  draftMessage: string
  loading: boolean
  actionStatus: string | null
  hasSession: boolean
  onDraftChange: (value: string) => void
  onSend: () => void
}

export function ChatInput({
  draftMessage,
  loading,
  actionStatus,
  hasSession,
  onDraftChange,
  onSend,
}: ChatInputProps) {
  if (!hasSession) return null

  const handleKeyDown = (event: React.KeyboardEvent) => {
    // Enter confirms IME candidates; Safari can clear isComposing early.
    if (event.nativeEvent.isComposing || event.nativeEvent.keyCode === 229)
      return
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      onSend()
    }
  }
  const canSend = !loading && draftMessage.trim().length > 0

  return (
    <footer
      className="shrink-0 bg-white px-4 pt-3 pb-4 sm:px-6 sm:pb-5 dark:bg-gray-900"
      aria-label="Message input"
    >
      <form
        onSubmit={(event) => {
          event.preventDefault()
          onSend()
        }}
      >
        <div className="flex items-end gap-3 rounded-2xl border border-gray-300 bg-white p-3 shadow-sm focus-within:border-cyan-600 focus-within:ring-1 focus-within:ring-cyan-600 dark:border-gray-700 dark:bg-gray-800">
          <div className="min-w-0 flex-1">
            <label htmlFor="chat-message-input" className="sr-only">
              Type your message to the agent
            </label>
            <textarea
              id="chat-message-input"
              value={draftMessage}
              onChange={(event) => onDraftChange(event.target.value)}
              onKeyDown={handleKeyDown}
              rows={2}
              placeholder="Message the agent…"
              className="block max-h-40 min-h-14 w-full resize-y border-0 bg-transparent p-0 text-base leading-7 text-gray-900 placeholder:text-gray-400 focus:ring-0 focus:outline-none dark:text-white"
              aria-describedby="input-hints"
              aria-busy={loading}
              disabled={loading}
            />
          </div>
          <button
            type="submit"
            disabled={!canSend}
            aria-label={loading ? 'Sending message...' : 'Send message'}
            aria-busy={loading}
            className="inline-flex min-h-11 shrink-0 items-center justify-center rounded-xl bg-cyan-700 px-4 text-sm font-semibold text-white hover:bg-cyan-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-600 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {loading ? 'Sending…' : 'Send'}
          </button>
        </div>
        <div className="mt-2 flex min-h-5 flex-wrap items-center justify-between gap-x-4 gap-y-1 text-xs text-gray-500 dark:text-gray-400">
          <span id="input-hints">
            Enter to send · Shift+Enter for a new line
          </span>
          {actionStatus && (
            <span
              role="status"
              aria-live="polite"
              className={
                actionStatus.toLowerCase().includes('failed')
                  ? 'text-red-700 dark:text-red-300'
                  : ''
              }
            >
              {actionStatus}
            </span>
          )}
        </div>
      </form>
    </footer>
  )
}
