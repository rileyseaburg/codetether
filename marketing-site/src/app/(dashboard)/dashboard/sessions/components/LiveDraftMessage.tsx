import { MarkdownMessage } from './MarkdownMessage'

interface LiveDraftMessageProps {
    liveDraft: string
    selectedMode: string
    sessionAgent?: string
}

export function LiveDraftMessage({
    liveDraft,
    selectedMode,
    sessionAgent,
}: LiveDraftMessageProps) {
    if (!liveDraft) return null

    const agentMode = selectedMode || sessionAgent || 'build'

    return (
        <article
            className="flex justify-start"
            aria-label="Agent is typing a response"
            aria-live="polite"
            aria-atomic="false"
        >
            <div className="max-w-[85%] text-left">
                <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-medium text-gray-600 dark:text-gray-300">
                        Agent
                    </span>
                    <span className="text-[10px] text-gray-400 dark:text-gray-500">
                        <span className="sr-only">Status: </span>
                        streaming
                        <span aria-hidden="true"> * </span>
                        <span className="sr-only">, Mode: </span>
                        {agentMode}
                    </span>
                </div>
                <div
                    className="rounded-2xl px-4 py-3 shadow-sm ring-1 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 ring-gray-200 dark:ring-white/10"
                    role="status"
                >
                    <MarkdownMessage text={liveDraft} />
                </div>
            </div>
        </article>
    )
}
