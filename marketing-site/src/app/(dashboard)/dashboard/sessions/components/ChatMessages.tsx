'use client'

import { useRef, useEffect, useState, useCallback, memo } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import type { ChatItem, Session } from '../types'
import { ChatMessage } from './ChatMessage'
import { LiveDraftMessage } from './LiveDraftMessage'

interface Props { 
    chatItems: ChatItem[]
    selectedSession: Session | null
    loading: boolean
    error: string | null
    liveDraft: string
    selectedMode: string 
}

// Memoized message component to prevent re-renders
const MemoizedChatMessage = memo(ChatMessage)

export function ChatMessages({ chatItems, selectedSession, loading, error, liveDraft, selectedMode }: Props) {
    const parentRef = useRef<HTMLDivElement>(null)
    const [isAtBottom, setIsAtBottom] = useState(true)
    const [showScrollButton, setShowScrollButton] = useState(false)
    const [unreadCount, setUnreadCount] = useState(0)
    const prevCountRef = useRef(chatItems.length)
    const prevSessionIdRef = useRef(selectedSession?.id)

    // Virtual list for performance - only render visible messages
    const virtualizer = useVirtualizer({
        count: chatItems.length,
        getScrollElement: () => parentRef.current,
        estimateSize: () => 120, // Estimated row height
        overscan: 3, // Render 3 extra items above/below viewport
    })

    const scrollToBottom = useCallback((behavior: ScrollBehavior = 'smooth') => {
        if (parentRef.current) {
            parentRef.current.scrollTo({
                top: parentRef.current.scrollHeight,
                behavior
            })
            setUnreadCount(0)
        }
    }, [])

    const scrollToTop = useCallback(() => {
        parentRef.current?.scrollTo({ top: 0, behavior: 'smooth' })
    }, [])

    // Handle session switch
    useEffect(() => {
        const isSessionSwitch = prevSessionIdRef.current !== selectedSession?.id
        prevSessionIdRef.current = selectedSession?.id

        if (isSessionSwitch && parentRef.current) {
            // Instant scroll on session switch
            parentRef.current.scrollTop = parentRef.current.scrollHeight
            setIsAtBottom(true)
            setUnreadCount(0)
        }
    }, [selectedSession?.id])

    // Auto-scroll when new messages arrive and user is at bottom
    useEffect(() => {
        if (isAtBottom && chatItems.length > 0) {
            // Use requestAnimationFrame for smoother scroll
            requestAnimationFrame(() => {
                parentRef.current?.scrollTo({
                    top: parentRef.current.scrollHeight,
                    behavior: 'smooth'
                })
            })
        }
    }, [chatItems.length, isAtBottom, liveDraft])

    // Track new messages
    useEffect(() => {
        const diff = chatItems.length - prevCountRef.current
        if (diff > 0 && !isAtBottom) {
            setUnreadCount(prev => prev + diff)
        }
        prevCountRef.current = chatItems.length
    }, [chatItems.length, isAtBottom])

    // Scroll position tracking
    const onScroll = useCallback(() => {
        const el = parentRef.current
        if (!el) return
        
        const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
        const atBottom = distanceFromBottom < 100
        
        setIsAtBottom(atBottom)
        setShowScrollButton(distanceFromBottom > 300)
        
        if (atBottom) setUnreadCount(0)
    }, [])

    if (!selectedSession) {
        return (
            <div className="flex-1 flex items-center justify-center bg-gray-50 dark:bg-gray-900">
                <p className="text-sm text-gray-500">Select a session to view the chat.</p>
            </div>
        )
    }

    const virtualItems = virtualizer.getVirtualItems()

    return (
        <section className="relative flex-1 min-h-0 flex flex-col bg-gray-50 dark:bg-gray-900">
            {/* Compact header */}
            {chatItems.length > 0 && (
                <div className="flex-shrink-0 flex items-center justify-between px-3 py-1.5 border-b border-gray-200 dark:border-gray-700 bg-white/80 dark:bg-gray-800/80 text-xs text-gray-500 dark:text-gray-400">
                    <span>{chatItems.length} messages</span>
                    <div className="flex gap-1">
                        <button onClick={scrollToTop} className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded" title="Top">
                            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                            </svg>
                        </button>
                        <button onClick={() => scrollToBottom()} className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded" title="Bottom">
                            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                            </svg>
                        </button>
                    </div>
                </div>
            )}

            {/* Virtualized messages container */}
            <div
                ref={parentRef}
                onScroll={onScroll}
                className="flex-1 min-h-0 overflow-y-auto"
                role="log"
                aria-label={`Chat: ${selectedSession.title || 'Untitled'}`}
            >
                {error && (
                    <div className="m-3 p-3 rounded bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-sm">
                        {error}
                    </div>
                )}

                {chatItems.length === 0 && !loading && !error && (
                    <div className="flex-1 flex items-center justify-center h-full">
                        <p className="text-sm text-gray-500">No messages yet.</p>
                    </div>
                )}

                {chatItems.length > 0 && (
                    <div
                        style={{ height: virtualizer.getTotalSize(), position: 'relative' }}
                        className="w-full"
                    >
                        <div
                            style={{
                                position: 'absolute',
                                top: 0,
                                left: 0,
                                width: '100%',
                                transform: `translateY(${virtualItems[0]?.start ?? 0}px)`,
                            }}
                            className="px-3 sm:px-4"
                        >
                            {virtualItems.map((virtualRow) => {
                                const message = chatItems[virtualRow.index]
                                return (
                                    <div
                                        key={virtualRow.key}
                                        data-index={virtualRow.index}
                                        ref={virtualizer.measureElement}
                                        className="py-2"
                                    >
                                        <MemoizedChatMessage
                                            message={message}
                                            messageIndex={virtualRow.index + 1}
                                            totalMessages={chatItems.length}
                                        />
                                    </div>
                                )
                            })}
                        </div>
                    </div>
                )}

                {/* Loading and live draft at the bottom */}
                <div className="px-3 sm:px-4 pb-3">
                    {loading && <LoadingIndicator />}
                    {liveDraft && (
                        <div className="py-2">
                            <LiveDraftMessage 
                                liveDraft={liveDraft} 
                                selectedMode={selectedMode} 
                                sessionAgent={selectedSession.agent} 
                            />
                        </div>
                    )}
                </div>
            </div>

            {/* Scroll to bottom FAB */}
            {showScrollButton && (
                <button
                    onClick={() => scrollToBottom()}
                    className="absolute bottom-4 right-4 flex items-center gap-1.5 px-3 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-full shadow-lg transition-colors"
                    aria-label={unreadCount > 0 ? `${unreadCount} new messages` : 'Scroll to bottom'}
                >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
                    </svg>
                    {unreadCount > 0 && (
                        <span className="bg-white text-indigo-600 px-1.5 py-0.5 rounded-full text-xs font-bold min-w-[20px] text-center">
                            {unreadCount > 99 ? '99+' : unreadCount}
                        </span>
                    )}
                </button>
            )}
        </section>
    )
}

const LoadingIndicator = memo(() => (
    <div className="flex justify-start py-2">
        <div className="rounded-2xl px-4 py-3 bg-white dark:bg-gray-800 ring-1 ring-gray-200 dark:ring-white/10 text-sm text-gray-600 dark:text-gray-300 flex items-center gap-2">
            <div className="flex gap-1">
                <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
            <span>Thinking...</span>
        </div>
    </div>
))
LoadingIndicator.displayName = 'LoadingIndicator'
