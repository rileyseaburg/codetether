import { useRef, useEffect, useState } from 'react'
import type { ChatItem, Session } from '../types'
import { ChatMessage } from './ChatMessage'
import { LiveDraftMessage } from './LiveDraftMessage'

interface Props { chatItems: ChatItem[]; selectedSession: Session | null; loading: boolean; error: string | null; liveDraft: string; selectedMode: string }

export function ChatMessages({ chatItems, selectedSession, loading, error, liveDraft, selectedMode }: Props) {
    const containerRef = useRef<HTMLDivElement>(null)
    const endRef = useRef<HTMLDivElement>(null)
    const autoScroll = useRef(true)
    const [newMessageCount, setNewMessageCount] = useState(0)
    const prevCountRef = useRef(chatItems.length)
    const prevSessionIdRef = useRef(selectedSession?.id)

    useEffect(() => {
        const currentSessionId = selectedSession?.id
        const isSessionSwitch = prevSessionIdRef.current !== currentSessionId
        prevSessionIdRef.current = currentSessionId

        if (containerRef.current) {
            if (isSessionSwitch) {
                containerRef.current.scrollTop = 0
            } else if (autoScroll.current && (chatItems.length > 0 || liveDraft)) {
                containerRef.current.scrollTop = containerRef.current.scrollHeight
            }
        }
    }, [selectedSession?.id, chatItems, liveDraft])

    useEffect(() => {
        const diff = chatItems.length - prevCountRef.current
        if (diff > 0) {
            setNewMessageCount(diff)
            const timeout = setTimeout(() => setNewMessageCount(0), 1000)
            return () => clearTimeout(timeout)
        }
        prevCountRef.current = chatItems.length
    }, [chatItems.length])

    const onScroll = () => {
        const el = containerRef.current
        if (el) autoScroll.current = el.scrollHeight - el.scrollTop - el.clientHeight < 140
    }

    if (!selectedSession) return <Empty msg="Select a session to view the chat." />

    return (
        <section
            ref={containerRef}
            onScroll={onScroll}
            className="flex-1 min-h-0 overflow-y-auto bg-gray-50 dark:bg-gray-900 p-3 sm:p-4"
            aria-label={`Chat messages for session: ${selectedSession.title || 'Untitled'}`}
            role="log"
            aria-live="polite"
            aria-relevant="additions"
        >
            <div className="sr-only" role="status" aria-live="assertive" aria-atomic="true">
                {newMessageCount > 0 && `${newMessageCount} new message${newMessageCount !== 1 ? 's' : ''} received`}
            </div>

            {error && (
                <div className="mb-4 p-3 rounded bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-sm" role="alert">
                    {error}
                </div>
            )}

            {chatItems.length === 0 && !loading && !error && (
                <Empty msg="No messages yet." />
            )}

            <ol className="space-y-4" aria-label="Message list">
                {chatItems.map((m, index) => (
                    <li key={m.key}>
                        <ChatMessage message={m} messageIndex={index + 1} totalMessages={chatItems.length} />
                    </li>
                ))}
                {loading && <li><Loading /></li>}
                {liveDraft && (
                    <li aria-label="Agent is typing">
                        <LiveDraftMessage liveDraft={liveDraft} selectedMode={selectedMode} sessionAgent={selectedSession.agent} />
                    </li>
                )}
            </ol>
            <div ref={endRef} aria-hidden="true" />
        </section>
    )
}

const Empty = ({ msg }: { msg: string }) => (
    <div className="flex-1 min-h-0 overflow-hidden flex items-center justify-center bg-gray-50 dark:bg-gray-900" role="status">
        <p className="text-sm text-gray-500">{msg}</p>
    </div>
)

const Loading = () => (
    <div className="flex justify-start" role="status" aria-label="Agent is thinking">
        <div className="rounded-2xl px-4 py-3 bg-white dark:bg-gray-800 ring-1 ring-gray-200 dark:ring-white/10 text-sm text-gray-600 dark:text-gray-300">
            <span aria-hidden="true">Thinking...</span>
            <span className="sr-only">Agent is processing your request</span>
        </div>
    </div>
)
