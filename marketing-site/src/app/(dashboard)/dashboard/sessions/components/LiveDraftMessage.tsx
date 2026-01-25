import { useDeferredValue } from 'react'
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

    const agentMode = selectedMode || sessionAgent || 'code'
    const deferredDraft = useDeferredValue(liveDraft)

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
                    <span className="flex items-center gap-1 text-[10px] text-emerald-500">
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                        live
                    </span>
                </div>
                <div
                    className="rounded-2xl px-4 py-3 shadow-sm ring-1 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 ring-gray-200 dark:ring-white/10 transition-shadow"
                    role="status"
                >
                    <div className="inline">
                        <MarkdownMessage text={deferredDraft} />
                    </div>
                    <span className="ml-1 inline-block h-3 w-2 translate-y-[1px] rounded-sm bg-emerald-400/80 animate-pulse" aria-hidden="true" />
                </div>
            </div>
        </article>
    )
}
