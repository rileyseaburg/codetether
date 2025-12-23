import type { ChatItem } from '../types'
import { formatDate } from '../utils'
import { MessageBubble } from './MessageBubble'

interface ChatMessageProps {
    message: ChatItem
    messageIndex?: number
    totalMessages?: number
}

export function ChatMessage({ message: m, messageIndex, totalMessages }: ChatMessageProps) {
    const positionLabel = messageIndex && totalMessages
        ? `Message ${messageIndex} of ${totalMessages}`
        : undefined

    if (m.role === 'system') {
        return (
            <div className="flex justify-center" role="status" aria-label="System message">
                <div className="max-w-[90%] rounded-full bg-gray-200/70 px-3 py-1 text-xs text-gray-700 dark:bg-gray-800 dark:text-gray-200">
                    {m.text || '-'}
                </div>
            </div>
        )
    }

    const isUser = m.role === 'user'
    const roleLabel = isUser ? 'You' : (m.label || 'Assistant')

    return (
        <article
            className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}
            aria-label={`${roleLabel}${positionLabel ? `, ${positionLabel}` : ''}`}
        >
            <div className={`max-w-[85%] ${isUser ? 'text-right' : 'text-left'}`}>
                <MessageHeader message={m} isUser={isUser} />
                <MessageBubble message={m} isUser={isUser} />
            </div>
        </article>
    )
}

function MessageHeader({ message: m, isUser }: { message: ChatItem; isUser: boolean }) {
    const dateText = m.createdAt ? formatDate(m.createdAt) : null

    return (
        <div className="flex items-center gap-2 mb-1" aria-hidden="false">
            {!isUser && (
                <span className="text-xs font-medium text-gray-600 dark:text-gray-300">
                    {m.label}
                </span>
            )}
            {m.model && (
                <span className="text-[10px] text-gray-400 dark:text-gray-500">
                    <span className="sr-only">Model: </span>
                    {m.model}
                </span>
            )}
            {dateText && (
                <time
                    dateTime={m.createdAt}
                    className="text-[10px] text-gray-400 dark:text-gray-500"
                    aria-label={`Sent at ${dateText}`}
                >
                    {dateText}
                </time>
            )}
            {isUser && (
                <span className="ml-auto text-xs font-medium text-gray-600 dark:text-gray-300">
                    {m.label}
                </span>
            )}
        </div>
    )
}
