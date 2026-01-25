import { useRef, useEffect } from 'react'
import type { ChatMessage } from '../../app/(dashboard)/dashboard/ralph/useAIPRDChat'
import { ChatMessage as ChatMessageUI } from '@/components/ui/ChatMessage'
import { QuickPrompts } from '@/components/ui/QuickPrompts'

interface ChatAreaProps {
    messages: ChatMessage[]
    isLoading: boolean
    quickPrompts: string[]
    onQuickPrompt: (prompt: string) => void
    restoredConversation?: boolean
}

export function ChatArea({ messages, isLoading, quickPrompts, onQuickPrompt, restoredConversation }: ChatAreaProps) {
    const messagesEndRef = useRef<HTMLDivElement>(null)

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }

    useEffect(() => { scrollToBottom() }, [messages])

    return (
        <div className="flex-1 overflow-y-auto p-4 bg-gray-50 dark:bg-gray-900 space-y-4">
            {/* Restored conversation banner */}
            {restoredConversation && messages.length > 1 && (
                <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg px-4 py-2 flex items-center gap-2">
                    <svg className="w-4 h-4 text-green-600 dark:text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    <span className="text-sm text-green-700 dark:text-green-300">
                        Conversation restored - continue where you left off
                    </span>
                </div>
            )}
            {messages.length === 1 && !restoredConversation && (
                <QuickPrompts prompts={quickPrompts} onSelect={onQuickPrompt} disabled={isLoading} />
            )}
            {messages.map((msg) => (
                <ChatMessageUI key={msg.id} role={msg.role} content={msg.content} status={msg.status} />
            ))}
            <div ref={messagesEndRef} />
        </div>
    )
}
