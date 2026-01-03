import { useRef, useEffect, useState, useCallback } from 'react'
import type { ChatItem, Session } from '../types'
import { ChatMessage } from './ChatMessage'
import { LiveDraftMessage } from './LiveDraftMessage'

interface Props { chatItems: ChatItem[]; selectedSession: Session | null; loading: boolean; error: string | null; liveDraft: string; selectedMode: string }

export function ChatMessages({ chatItems, selectedSession, loading, error, liveDraft, selectedMode }: Props) {
    const containerRef = useRef<HTMLDivElement>(null)
    const endRef = useRef<HTMLDivElement>(null)
    const [isAtBottom, setIsAtBottom] = useState(true)
    const [showScrollButton, setShowScrollButton] = useState(false)
    const [newMessageCount, setNewMessageCount] = useState(0)
    const [unreadCount, setUnreadCount] = useState(0)
    const prevCountRef = useRef(chatItems.length)
    const prevSessionIdRef = useRef(selectedSession?.id)
    const [collapsedGroups, setCollapsedGroups] = useState<Set<number>>(new Set())

    // Group messages by conversation turns (user message + agent response)
    const messageGroups = groupMessages(chatItems)

    const scrollToBottom = useCallback((behavior: ScrollBehavior = 'smooth') => {
        if (containerRef.current) {
            containerRef.current.scrollTo({
                top: containerRef.current.scrollHeight,
                behavior
            })
            setUnreadCount(0)
        }
    }, [])

    const scrollToTop = useCallback(() => {
        if (containerRef.current) {
            containerRef.current.scrollTo({
                top: 0,
                behavior: 'smooth'
            })
        }
    }, [])

    // Handle session switch and auto-scroll
    useEffect(() => {
        const currentSessionId = selectedSession?.id
        const isSessionSwitch = prevSessionIdRef.current !== currentSessionId
        prevSessionIdRef.current = currentSessionId

        if (containerRef.current) {
            if (isSessionSwitch) {
                // On session switch, scroll to bottom instantly
                containerRef.current.scrollTop = containerRef.current.scrollHeight
                setIsAtBottom(true)
                setUnreadCount(0)
                setCollapsedGroups(new Set())
            } else if (isAtBottom && (chatItems.length > 0 || liveDraft)) {
                // Auto-scroll when at bottom
                scrollToBottom('smooth')
            }
        }
    }, [selectedSession?.id, chatItems, liveDraft, isAtBottom, scrollToBottom])

    // Track new messages for notification
    useEffect(() => {
        const diff = chatItems.length - prevCountRef.current
        if (diff > 0) {
            setNewMessageCount(diff)
            if (!isAtBottom) {
                setUnreadCount(prev => prev + diff)
            }
            const timeout = setTimeout(() => setNewMessageCount(0), 1000)
            return () => clearTimeout(timeout)
        }
        prevCountRef.current = chatItems.length
    }, [chatItems.length, isAtBottom])

    // Handle scroll position tracking
    const onScroll = useCallback(() => {
        const el = containerRef.current
        if (el) {
            const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
            const atBottom = distanceFromBottom < 100
            setIsAtBottom(atBottom)
            setShowScrollButton(distanceFromBottom > 300)
            if (atBottom) {
                setUnreadCount(0)
            }
        }
    }, [])

    const toggleGroup = useCallback((groupIndex: number) => {
        setCollapsedGroups(prev => {
            const next = new Set(prev)
            if (next.has(groupIndex)) {
                next.delete(groupIndex)
            } else {
                next.add(groupIndex)
            }
            return next
        })
    }, [])

    const collapseAllGroups = useCallback(() => {
        setCollapsedGroups(new Set(messageGroups.map((_, i) => i).slice(0, -1))) // Keep last group open
    }, [messageGroups])

    const expandAllGroups = useCallback(() => {
        setCollapsedGroups(new Set())
    }, [])

    if (!selectedSession) return <Empty msg="Select a session to view the chat." />

    const hasMultipleGroups = messageGroups.length > 3

    return (
        <section className="relative flex-1 min-h-0 flex flex-col bg-gray-50 dark:bg-gray-900">
            {/* Header with message count and controls */}
            {chatItems.length > 0 && (
                <div className="flex-shrink-0 flex items-center justify-between px-3 py-2 border-b border-gray-200 dark:border-gray-700 bg-white/80 dark:bg-gray-800/80 backdrop-blur-sm">
                    <span className="text-xs text-gray-500 dark:text-gray-400">
                        {chatItems.length} message{chatItems.length !== 1 ? 's' : ''}
                        {messageGroups.length > 1 && ` in ${messageGroups.length} turns`}
                    </span>
                    <div className="flex items-center gap-2">
                        {hasMultipleGroups && (
                            <>
                                <button
                                    onClick={collapseAllGroups}
                                    className="text-xs text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 px-2 py-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                                    title="Collapse all conversation turns"
                                >
                                    Collapse
                                </button>
                                <button
                                    onClick={expandAllGroups}
                                    className="text-xs text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 px-2 py-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                                    title="Expand all conversation turns"
                                >
                                    Expand
                                </button>
                            </>
                        )}
                        <button
                            onClick={scrollToTop}
                            className="text-xs text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                            title="Scroll to top"
                            aria-label="Scroll to top"
                        >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                            </svg>
                        </button>
                        <button
                            onClick={() => scrollToBottom()}
                            className="text-xs text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                            title="Scroll to bottom"
                            aria-label="Scroll to bottom"
                        >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                            </svg>
                        </button>
                    </div>
                </div>
            )}

            {/* Messages container */}
            <div
                ref={containerRef}
                onScroll={onScroll}
                className="flex-1 min-h-0 overflow-y-auto p-3 sm:p-4 scroll-smooth"
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

                {/* Render message groups */}
                <div className="space-y-2" aria-label="Message list">
                    {messageGroups.map((group, groupIndex) => (
                        <MessageGroup
                            key={`group-${groupIndex}`}
                            group={group}
                            groupIndex={groupIndex}
                            totalGroups={messageGroups.length}
                            isCollapsed={collapsedGroups.has(groupIndex)}
                            onToggle={() => toggleGroup(groupIndex)}
                            showCollapseControls={hasMultipleGroups}
                        />
                    ))}
                    {loading && (
                        <div className="py-2">
                            <Loading />
                        </div>
                    )}
                    {liveDraft && (
                        <div className="py-2" aria-label="Agent is typing">
                            <LiveDraftMessage liveDraft={liveDraft} selectedMode={selectedMode} sessionAgent={selectedSession.agent} />
                        </div>
                    )}
                </div>
                <div ref={endRef} aria-hidden="true" />
            </div>

            {/* Floating scroll-to-bottom button */}
            {showScrollButton && (
                <button
                    onClick={() => scrollToBottom()}
                    className="absolute bottom-4 right-4 flex items-center gap-2 px-3 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-full shadow-lg transition-all duration-200 hover:scale-105 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
                    aria-label={unreadCount > 0 ? `Scroll to bottom, ${unreadCount} unread messages` : 'Scroll to bottom'}
                >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
                    </svg>
                    {unreadCount > 0 && (
                        <span className="bg-white text-indigo-600 px-1.5 py-0.5 rounded-full text-xs font-bold">
                            {unreadCount > 99 ? '99+' : unreadCount}
                        </span>
                    )}
                </button>
            )}
        </section>
    )
}

// Group messages by conversation turns
function groupMessages(items: ChatItem[]): ChatItem[][] {
    if (items.length === 0) return []
    
    const groups: ChatItem[][] = []
    let currentGroup: ChatItem[] = []
    
    for (const item of items) {
        if (item.role === 'user' && currentGroup.length > 0) {
            groups.push(currentGroup)
            currentGroup = []
        }
        currentGroup.push(item)
    }
    
    if (currentGroup.length > 0) {
        groups.push(currentGroup)
    }
    
    return groups
}

interface MessageGroupProps {
    group: ChatItem[]
    groupIndex: number
    totalGroups: number
    isCollapsed: boolean
    onToggle: () => void
    showCollapseControls: boolean
}

function MessageGroup({ group, groupIndex, totalGroups, isCollapsed, onToggle, showCollapseControls }: MessageGroupProps) {
    const userMessage = group.find(m => m.role === 'user')
    const assistantMessages = group.filter(m => m.role !== 'user')
    const isLastGroup = groupIndex === totalGroups - 1
    
    // Get preview of user message
    const userPreview = userMessage?.text?.slice(0, 60) + (userMessage?.text && userMessage.text.length > 60 ? '...' : '') || 'User message'
    
    // Don't collapse the last group or single messages
    if (!showCollapseControls || isLastGroup || group.length === 1) {
        return (
            <div className="space-y-3">
                {group.map((m, index) => (
                    <ChatMessage 
                        key={m.key} 
                        message={m} 
                        messageIndex={groupIndex * 10 + index + 1} 
                        totalMessages={totalGroups} 
                    />
                ))}
            </div>
        )
    }

    if (isCollapsed) {
        return (
            <button
                onClick={onToggle}
                className="w-full text-left p-3 rounded-lg bg-white dark:bg-gray-800 ring-1 ring-gray-200 dark:ring-gray-700 hover:ring-indigo-300 dark:hover:ring-indigo-600 transition-all duration-150 group"
                aria-expanded="false"
                aria-label={`Expand conversation turn ${groupIndex + 1}: ${userPreview}`}
            >
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3 min-w-0">
                        <div className="flex-shrink-0 w-6 h-6 rounded-full bg-indigo-100 dark:bg-indigo-900/30 flex items-center justify-center">
                            <span className="text-xs font-medium text-indigo-600 dark:text-indigo-400">{groupIndex + 1}</span>
                        </div>
                        <div className="min-w-0">
                            <p className="text-sm text-gray-900 dark:text-gray-100 truncate">{userPreview}</p>
                            <p className="text-xs text-gray-500 dark:text-gray-400">
                                {group.length} message{group.length !== 1 ? 's' : ''} in this turn
                            </p>
                        </div>
                    </div>
                    <svg 
                        className="w-5 h-5 text-gray-400 group-hover:text-indigo-500 transition-colors flex-shrink-0" 
                        fill="none" 
                        stroke="currentColor" 
                        viewBox="0 0 24 24"
                    >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                </div>
            </button>
        )
    }

    return (
        <div className="relative">
            {/* Collapse handle */}
            <button
                onClick={onToggle}
                className="absolute -left-1 top-0 bottom-0 w-6 flex items-start pt-4 opacity-0 hover:opacity-100 transition-opacity group z-10"
                aria-expanded="true"
                aria-label={`Collapse conversation turn ${groupIndex + 1}`}
            >
                <div className="w-1 h-full bg-gray-200 dark:bg-gray-700 rounded group-hover:bg-indigo-400 dark:group-hover:bg-indigo-500 transition-colors" />
            </button>
            
            {/* Turn indicator */}
            <div className="flex items-center gap-2 mb-2 ml-1">
                <div className="flex-shrink-0 w-5 h-5 rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center ring-1 ring-gray-200 dark:ring-gray-700">
                    <span className="text-[10px] font-medium text-gray-500 dark:text-gray-400">{groupIndex + 1}</span>
                </div>
                <button
                    onClick={onToggle}
                    className="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
                >
                    Collapse
                </button>
            </div>
            
            <div className="space-y-3 ml-1 pl-4 border-l-2 border-gray-100 dark:border-gray-800">
                {group.map((m, index) => (
                    <ChatMessage 
                        key={m.key} 
                        message={m} 
                        messageIndex={groupIndex * 10 + index + 1} 
                        totalMessages={totalGroups} 
                    />
                ))}
            </div>
        </div>
    )
}

const Empty = ({ msg }: { msg: string }) => (
    <div className="flex-1 min-h-0 overflow-hidden flex items-center justify-center" role="status">
        <p className="text-sm text-gray-500">{msg}</p>
    </div>
)

const Loading = () => (
    <div className="flex justify-start" role="status" aria-label="Agent is thinking">
        <div className="rounded-2xl px-4 py-3 bg-white dark:bg-gray-800 ring-1 ring-gray-200 dark:ring-white/10 text-sm text-gray-600 dark:text-gray-300 flex items-center gap-2">
            <div className="flex gap-1">
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
            <span aria-hidden="true">Thinking...</span>
            <span className="sr-only">Agent is processing your request</span>
        </div>
    </div>
)
