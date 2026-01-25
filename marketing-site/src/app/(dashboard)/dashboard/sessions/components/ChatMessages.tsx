'use client'

import { useRef, useEffect, useState, useCallback, memo } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import { useDebouncedCallback } from 'use-debounce'
import type { ChatItem, Session } from '../types'
import { ChatMessage } from './ChatMessage'

interface Props {
  chatItems: ChatItem[]
  selectedSession: Session | null
  loading: boolean
  loadingMore: boolean
  hasMore: boolean
  totalMessages: number
  error: string | null
  liveDraft: string
  awaitingResponse: boolean
  onLoadMore: () => void
}

export function ChatMessages({
  chatItems,
  selectedSession,
  loading,
  loadingMore,
  hasMore,
  totalMessages,
  error,
  liveDraft,
  awaitingResponse,
  onLoadMore,
}: Props) {
  const parentRef = useRef<HTMLDivElement>(null)
  const [isAtBottom, setIsAtBottom] = useState(true)
  const [showScrollButton, setShowScrollButton] = useState(false)
  const [unreadCount, setUnreadCount] = useState(0)
  const [latestMessageKey, setLatestMessageKey] = useState<string | null>(null)
  const [showHistoryWhileStreaming, setShowHistoryWhileStreaming] = useState(false)
  const prevCountRef = useRef(chatItems.length)
  const prevSessionIdRef = useRef(selectedSession?.id)
  const loadingMoreRef = useRef(false)
  const clearHighlightRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const isStreaming = Boolean(liveDraft)
  // Always show history - hiding it causes jumpy UX when streaming completes
  // The live draft is appended at the bottom, separate from history
  const shouldHideHistory = false
  const visibleChatItems = chatItems
  const liveDraftMessage: ChatItem | null = liveDraft
    ? {
        key: `live-draft-${selectedSession?.id ?? 'session'}`,
        role: 'assistant',
        label: 'Agent',
        text: liveDraft,
      }
    : null

  const virtualizer = useVirtualizer({
    count: visibleChatItems.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 120,
    overscan: 3,
  })

  const scrollToBottom = useCallback((behavior: ScrollBehavior = 'smooth') => {
    if (parentRef.current) {
      parentRef.current.scrollTo({
        top: parentRef.current.scrollHeight,
        behavior,
      })
      setUnreadCount(0)
    }
  }, [])

  const scrollToTop = useCallback(() => {
    parentRef.current?.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

  useEffect(() => {
    const isSessionSwitch = prevSessionIdRef.current !== selectedSession?.id
    prevSessionIdRef.current = selectedSession?.id

    if (isSessionSwitch && parentRef.current) {
      parentRef.current.scrollTop = parentRef.current.scrollHeight
      setIsAtBottom(true)
      setUnreadCount(0)
      setShowHistoryWhileStreaming(false)
    }
  }, [selectedSession?.id])

  useEffect(() => {
    if (isAtBottom && chatItems.length > 0) {
      requestAnimationFrame(() => {
        parentRef.current?.scrollTo({
          top: parentRef.current.scrollHeight,
          behavior: liveDraft ? 'auto' : 'smooth',
        })
      })
    }
  }, [chatItems.length, isAtBottom, liveDraft])

  useEffect(() => {
    const diff = chatItems.length - prevCountRef.current
    if (diff > 0 && !isAtBottom) {
      setUnreadCount((prev) => prev + diff)
    }
    if (diff > 0) {
      const newestKey = chatItems[chatItems.length - 1]?.key
      if (newestKey) {
        setLatestMessageKey(newestKey)
        if (clearHighlightRef.current) clearTimeout(clearHighlightRef.current)
        clearHighlightRef.current = setTimeout(() => {
          setLatestMessageKey(null)
        }, 1400)
      }
    }
    prevCountRef.current = chatItems.length
  }, [chatItems.length, isAtBottom])

  // Debounced scroll handler to reduce unnecessary state updates
  const onScroll = useDebouncedCallback(() => {
    const el = parentRef.current
    if (!el) return

    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
    const atBottom = distanceFromBottom < 100

    setIsAtBottom(atBottom)
    setShowScrollButton(distanceFromBottom > 300)

    if (atBottom) setUnreadCount(0)

    const nearTopThreshold = el.scrollTop < 150

    if (nearTopThreshold && hasMore && !loadingMoreRef.current && !loading) {
      loadingMoreRef.current = true
      onLoadMore()
    }
  }, 16, { leading: true, trailing: true, maxWait: 100 }) // ~60fps with max 100ms delay

  useEffect(() => {
    loadingMoreRef.current = loadingMore
  }, [loadingMore])

  useEffect(() => {
    return () => {
      if (clearHighlightRef.current) clearTimeout(clearHighlightRef.current)
    }
  }, [])

  useEffect(() => {
    if (!prevSessionIdRef.current && chatItems.length > 0) {
      scrollToBottom('instant')
    }
  }, [chatItems.length, scrollToBottom])

  useEffect(() => {
    if (!liveDraft) {
      setShowHistoryWhileStreaming(false)
    }
  }, [liveDraft])

  if (!selectedSession) {
    return (
      <div className="flex flex-1 items-center justify-center bg-gray-50 dark:bg-gray-900">
        <p className="text-sm text-gray-500">
          Select a session to view the chat.
        </p>
      </div>
    )
  }

  const virtualItems = virtualizer.getVirtualItems()

  return (
    <section className="relative flex min-h-0 flex-1 flex-col bg-gray-50 dark:bg-gray-900">
      {visibleChatItems.length > 0 && (
        <div className="sticky top-0 z-10 hidden flex-shrink-0 items-center justify-between border-b border-gray-200 bg-white/80 px-3 py-2 text-xs text-gray-500 backdrop-blur dark:border-gray-700 dark:bg-gray-800/80 dark:text-gray-400 sm:flex">
          <span>
            {loadingMore
              ? 'Loading older messages...'
              : hasMore
                ? `${chatItems.length}/${totalMessages} messages`
                : `${totalMessages} messages`}
          </span>
          <div className="flex gap-1">
            <button
              onClick={scrollToTop}
              className="rounded p-1 hover:bg-gray-100 dark:hover:bg-gray-700"
              title="Top"
              aria-label="Scroll to top"
            >
              <svg
                className="h-3.5 w-3.5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 15l7-7 7 7"
                />
              </svg>
            </button>
            <button
              onClick={() => scrollToBottom()}
              className="rounded p-1 hover:bg-gray-100 dark:hover:bg-gray-700"
              title="Bottom"
              aria-label="Scroll to bottom"
            >
              <svg
                className="h-3.5 w-3.5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 9l-7 7-7-7"
                />
              </svg>
            </button>
          </div>
        </div>
      )}

      <div
        ref={parentRef}
        onScroll={onScroll}
        className="min-h-0 flex-1 overflow-y-auto"
        role="log"
        aria-label={`Chat: ${selectedSession.title || 'Untitled'}`}
      >
        {error && (
          <div className="m-3 rounded bg-red-50 p-3 text-sm text-red-600 dark:bg-red-900/20 dark:text-red-400">
            {error}
          </div>
        )}

        {visibleChatItems.length === 0 && !loading && !error && !liveDraft && (
          <div className="flex h-full flex-1 items-center justify-center">
            <p className="text-sm text-gray-500">No messages yet.</p>
          </div>
        )}

        {visibleChatItems.length > 0 && (
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
                const message = visibleChatItems[virtualRow.index]
                return (
                  <div
                    key={virtualRow.key}
                    data-index={virtualRow.index}
                    ref={virtualizer.measureElement}
                    className="py-2"
                  >
                    <ChatMessage
                      message={message}
                      messageIndex={virtualRow.index + 1}
                      isNew={message.key === latestMessageKey}
                    />
                  </div>
                )
              })}
            </div>
          </div>
        )}

        <div className="px-3 pb-3 sm:px-4">
          {loading && <LoadingIndicator />}
          {shouldHideHistory && (
            <div className="mb-2 flex items-center justify-between gap-2 rounded-full bg-gray-100 px-3 py-1 text-[11px] text-gray-600 dark:bg-gray-800 dark:text-gray-300">
              <span>Live response in progress. History hidden.</span>
              <button
                type="button"
                onClick={() => {
                  setShowHistoryWhileStreaming(true)
                  requestAnimationFrame(() => scrollToBottom('auto'))
                }}
                 className="text-cyan-600 hover:text-cyan-700 dark:text-cyan-300 dark:hover:text-cyan-200"
              >
                Show history
              </button>
            </div>
          )}
          {awaitingResponse && !liveDraftMessage && <LiveFeedbackIndicator />}
          {liveDraftMessage && (
            <div className="py-2" aria-live="polite" aria-atomic="false">
              <ChatMessage message={liveDraftMessage} />
            </div>
          )}
        </div>
      </div>

       {showScrollButton && (
        <button
            onClick={() => scrollToBottom()}
            className={`absolute bottom-4 right-4 flex items-center gap-1.5 rounded-full bg-cyan-600 px-3 py-2 text-sm font-medium text-white shadow-lg transition-all hover:bg-cyan-700 ${unreadCount > 0 ? 'animate-pulse' : ''}`}
          aria-label={
            unreadCount > 0 ? `${unreadCount} new messages` : 'Scroll to bottom'
          }
        >
          <svg
            className="h-4 w-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 14l-7 7m0 0l-7-7m7 7V3"
            />
          </svg>
          {unreadCount > 0 && (
                 <span className="min-w-[20px] rounded-full bg-white px-1.5 py-0.5 text-center text-xs font-bold text-cyan-600">
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
    <div className="flex items-center gap-2 rounded-2xl bg-white px-4 py-3 text-sm text-gray-600 ring-1 ring-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:ring-white/10">
      <div className="flex gap-1">
        <span
          className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400"
          style={{ animationDelay: '0ms' }}
        />
        <span
          className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400"
          style={{ animationDelay: '150ms' }}
        />
        <span
          className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400"
          style={{ animationDelay: '300ms' }}
        />
      </div>
      <span>Thinking...</span>
    </div>
  </div>
))
LoadingIndicator.displayName = 'LoadingIndicator'

const LiveFeedbackIndicator = memo(() => (
  <div className="flex justify-start py-2" role="status" aria-live="polite">
    <div className="max-w-[85%] text-left">
      <div className="mb-1 flex items-center gap-2">
        <span className="text-xs font-medium text-gray-600 dark:text-gray-300">
          Agent
        </span>
        <span className="text-[10px] text-gray-400 dark:text-gray-500">
          waiting
        </span>
        <span className="flex items-center gap-1 text-[10px] text-emerald-500">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500" />
          live
        </span>
      </div>
      <div className="rounded-2xl bg-white px-4 py-3 text-sm text-gray-600 shadow-sm ring-1 ring-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:ring-white/10">
        <div className="flex items-center gap-2">
          <span className="flex gap-1" aria-hidden="true">
            <span
              className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400"
              style={{ animationDelay: '0ms' }}
            />
            <span
              className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400"
              style={{ animationDelay: '150ms' }}
            />
            <span
              className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400"
              style={{ animationDelay: '300ms' }}
            />
          </span>
          <span>Waiting for response...</span>
        </div>
      </div>
    </div>
  </div>
))
LiveFeedbackIndicator.displayName = 'LiveFeedbackIndicator'
