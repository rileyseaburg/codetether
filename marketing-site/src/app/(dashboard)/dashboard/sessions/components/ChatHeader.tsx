import type { Session } from '../types'
import { StreamStatus } from './StreamStatus'
import { ModeSelector } from './ModeSelector'
import { ModelSelector } from './ModelSelector'
import { SessionActions } from './SessionActions'

interface Props {
    selectedSession: Session | null
    selectedCodebase?: string
    selectedMode: string
    selectedModel: string
    suggestedModels: string[]
    streamConnected: boolean
    streamStatus: string
    loading: boolean
    chatItemsCount: number
    onModeChange: (mode: string) => void
    onModelChange: (model: string) => void
    onResume: () => void
    onRefresh: () => void
}

export function ChatHeader(p: Props) {
    const sessionTitle = p.selectedSession?.title || 'Chat'

    return (
        <header
            className="shrink-0 p-3 sm:p-4 border-b border-gray-200 dark:border-gray-700 flex flex-col sm:flex-row sm:items-center justify-between gap-2 sm:gap-3"
            aria-label="Chat session header"
        >
            <div className="min-w-0 w-full sm:w-auto">
                <h2 id="chat-title" className="text-sm font-semibold text-gray-900 dark:text-white truncate">
                    {sessionTitle}
                </h2>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                    {p.selectedSession ? (
                        <>
                            <span className="sr-only">Current mode: </span>
                            <span>Mode: {p.selectedMode}</span>
                            <span aria-hidden="true"> * </span>
                            <span className="sr-only">, </span>
                            <span>{p.chatItemsCount} message{p.chatItemsCount !== 1 ? 's' : ''}</span>
                        </>
                    ) : (
                        'Select a session'
                    )}
                </p>
            </div>
            <div className="flex items-center gap-1 sm:gap-2 flex-wrap" role="toolbar" aria-label="Chat controls">
                <StreamStatus connected={p.streamConnected} status={p.streamStatus} />
                <ModeSelector value={p.selectedMode} onChange={p.onModeChange} />
                <ModelSelector value={p.selectedModel} suggestions={p.suggestedModels} onChange={p.onModelChange} />
                {p.selectedSession && (
                    <SessionActions
                        loading={p.loading}
                        onResume={p.onResume}
                        onRefresh={p.onRefresh}
                        sessionTitle={sessionTitle}
                        sessionId={p.selectedSession.id}
                        codebaseId={p.selectedCodebase}
                    />
                )}
            </div>
        </header>
    )
}
