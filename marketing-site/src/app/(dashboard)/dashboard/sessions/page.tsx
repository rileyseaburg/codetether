'use client'

import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import type { ChatItem, Session } from './types'
import {
  useCodebases,
  useSessions,
  useSessionStream,
  useModelStorage,
  useSessionResume,
  useRlmFromHistory,
} from './hooks'
import { useChatItems } from './useChatItems'
import { useSuggestedModels } from './useSuggestedModels'
import {
  SessionList,
  ChatHeader,
  ChatMessages,
  ChatInput,
  ErrorBoundary,
} from './components'
import { RLMExecutionPane } from './components/RLMExecutionPane'

export default function SessionsPage() {
  const [selectedCodebase, setSelectedCodebase] = useState('')
  const [selectedSession, setSelectedSession] = useState<Session | null>(null)
  const [selectedMode, setSelectedMode] = useState('code')
  const [draftMessage, setDraftMessage] = useState('')
  const [awaitingResponse, setAwaitingResponse] = useState(false)
  const [optimisticMessages, setOptimisticMessages] = useState<ChatItem[]>([])
  const [showRLMPane, setShowRLMPane] = useState(false)
  const [mobilePane, setMobilePane] = useState<'sessions' | 'chat'>('sessions')
  const [sessionQuery, setSessionQuery] = useState('')
  const latestLoadingSessionId = useRef<string | null>(null)
  const prevSelectedSessionIdRef = useRef<string | null>(null)
  const pendingResponseKeyRef = useRef<string | null>(null)

  const { codebases } = useCodebases()
  const { selectedModel, setSelectedModel } = useModelStorage()
  const {
    sessions,
    sessionMessages,
    loadSessions,
    loadMoreSessions,
    loadSessionMessages,
    loadMoreMessages,
    clearSessions,
    loading,
    loadingMore,
    loadingMoreSessions,
    hasMore,
    hasMoreSessions,
    totalMessages,
    totalSessions,
    error,
  } = useSessions(selectedCodebase)
  const selectedCodebaseMeta = useMemo(
    () => codebases.find((c) => c.id === selectedCodebase) || null,
    [codebases, selectedCodebase],
  )
  const handleSessionUpdate = useCallback(
    (id: string) =>
      setSelectedSession((p) => (p && p.id !== id ? { ...p, id } : p)),
    [],
  )
  const {
    loading: resumeLoading,
    actionStatus,
    setActionStatus,
    resumeSession,
  } = useSessionResume({
    selectedCodebase,
    selectedMode,
    selectedModel,
    onSessionUpdate: handleSessionUpdate,
    loadSessions,
    loadSessionMessages,
  })
  const handleIdle = useCallback(() => {
    if (selectedSession?.id) loadSessionMessages(selectedSession.id)
  }, [selectedSession?.id, loadSessionMessages])
  const { streamConnected, streamStatus, liveDraft, rlmSteps, rlmStats, resetStream } =
    useSessionStream({
      selectedCodebase,
      selectedCodebaseMeta,
      selectedSession,
      onIdle: handleIdle,
    })
  const chatItems = useChatItems(sessionMessages)
  const lastChatItem = chatItems[chatItems.length - 1]
  const lastChatKey = lastChatItem?.key ?? null
  const lastChatRole = lastChatItem?.role
  const displayChatItems = useMemo(() => {
    if (optimisticMessages.length === 0) return chatItems
    return [...chatItems, ...optimisticMessages]
  }, [chatItems, optimisticMessages])
  const suggestedModels = useSuggestedModels(chatItems)

  // Extract RLM data from historical messages and combine with live data
  const { steps: historyRlmSteps, stats: historyRlmStats } = useRlmFromHistory(chatItems)
  const combinedRlmSteps = useMemo(() =>
    rlmSteps.length > 0 ? rlmSteps : historyRlmSteps,
    [rlmSteps, historyRlmSteps]
  )
  const combinedRlmStats = useMemo(() =>
    (rlmStats.tokens > 0 || rlmStats.chunks > 0 || rlmStats.subcalls.total > 0) ? rlmStats : historyRlmStats,
    [rlmStats, historyRlmStats]
  )

  const layoutClass = showRLMPane
    ? 'md:grid-cols-[minmax(260px,320px)_minmax(0,1fr)] lg:grid-cols-[minmax(260px,320px)_minmax(0,1fr)_minmax(280px,360px)]'
    : 'md:grid-cols-[minmax(260px,320px)_minmax(0,1fr)]'
  const handleLoadMoreSessions = useCallback(
    () => loadMoreSessions(selectedCodebase),
    [loadMoreSessions, selectedCodebase],
  )

  useEffect(() => {
    if (selectedCodebase) loadSessions(selectedCodebase, sessionQuery)
  }, [selectedCodebase, sessionQuery, loadSessions])
  useEffect(() => {
    if (!selectedSession) return
    const sessionId = selectedSession.id
    if (latestLoadingSessionId.current === sessionId) return
    latestLoadingSessionId.current = sessionId
    loadSessionMessages(sessionId)
    return () => {
      if (latestLoadingSessionId.current === sessionId)
        latestLoadingSessionId.current = null
    }
  }, [selectedSession, loadSessionMessages])

  useEffect(() => {
    const currentId = selectedSession?.id ?? null
    const prevId = prevSelectedSessionIdRef.current
    if (prevId === currentId) return
    prevSelectedSessionIdRef.current = currentId
    if (typeof window === 'undefined') return
    if (!window.matchMedia('(max-width: 767px)').matches) return
    setMobilePane(currentId ? 'chat' : 'sessions')
  }, [selectedSession?.id])

  useEffect(() => {
    setAwaitingResponse(false)
    pendingResponseKeyRef.current = null
    setOptimisticMessages([])
  }, [selectedSession?.id])

  useEffect(() => {
    if (!chatItems.length) return
    setOptimisticMessages((prev) => {
      if (!prev.length) return prev
      const matchesOptimistic = (optimistic: ChatItem, item: ChatItem) => {
        if (item.role !== 'user') return false
        if (item.text.trim() !== optimistic.text.trim()) return false
        if (!optimistic.createdAt || !item.createdAt) return true
        const optimisticTime = Date.parse(optimistic.createdAt)
        const itemTime = Date.parse(item.createdAt)
        if (!Number.isFinite(optimisticTime) || !Number.isFinite(itemTime)) {
          return true
        }
        const timeDiff = Math.abs(itemTime - optimisticTime)
        return timeDiff < 2 * 60 * 1000
      }

      return prev.filter(
        (optimistic) =>
          !chatItems.some((item) => matchesOptimistic(optimistic, item)),
      )
    })
  }, [chatItems])

  useEffect(() => {
    if (!awaitingResponse) return
    if (liveDraft) {
      setAwaitingResponse(false)
      return
    }
    if (actionStatus?.toLowerCase().includes('failed')) {
      setAwaitingResponse(false)
      return
    }
    if (!lastChatKey) return
    if (pendingResponseKeyRef.current && lastChatKey === pendingResponseKeyRef.current) {
      return
    }
    if (lastChatRole === 'assistant') {
      setAwaitingResponse(false)
    }
  }, [awaitingResponse, liveDraft, actionStatus, lastChatKey, lastChatRole])

  const onCodebaseChange = useCallback(
    (id: string) => {
      setSelectedCodebase(id)
      setSelectedSession(null)
      setMobilePane('sessions')
      setSessionQuery('')
      clearSessions()
      setActionStatus(null)
      setAwaitingResponse(false)
      pendingResponseKeyRef.current = null
      setOptimisticMessages([])
      resetStream()
    },
    [clearSessions, setActionStatus, resetStream],
  )

  const onSessionSelect = useCallback((s: Session) => {
    setSelectedSession(s)
    setSelectedMode('code')
    setMobilePane('chat')
  }, [])

  const onSend = useCallback(async () => {
    if (resumeLoading) return
    if (selectedSession && draftMessage.trim()) {
      const messageText = draftMessage.trim()
      const optimistic: ChatItem = {
        key: `optimistic-${Date.now()}-${Math.random().toString(16).slice(2)}`,
        role: 'user',
        label: 'You',
        text: messageText,
        createdAt: new Date().toISOString(),
      }

      setOptimisticMessages((prev) => [...prev, optimistic])
      pendingResponseKeyRef.current = lastChatKey
      setAwaitingResponse(true)
      setDraftMessage('')
      try {
        await resumeSession(selectedSession, messageText)
      } catch (e) {
        setAwaitingResponse(false)
        setOptimisticMessages((prev) =>
          prev.filter((item) => item.key !== optimistic.key),
        )
        setDraftMessage(messageText)
        console.error('Failed to send message:', e)
      }
    }
  }, [selectedSession, draftMessage, resumeSession, lastChatKey, resumeLoading])

  return (
    <div
      aria-label="Chat sessions dashboard"
      className="flex h-full min-h-0 flex-col overflow-hidden"
    >
      {/* Skip link for keyboard users */}
      <a
        href="#chat-message-input"
        className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:rounded-md focus:bg-cyan-600 focus:px-4 focus:py-2 focus:text-white"
      >
        Skip to message input
      </a>

      <div
        className={`grid min-h-0 flex-1 grid-cols-1 gap-3 overflow-hidden px-0.5 md:gap-4 ${layoutClass}`}
      >
        {/* Session sidebar */}
        <aside
          id="sessions-pane"
          className={`h-full min-h-0 overflow-hidden ${mobilePane === 'sessions' ? '' : 'hidden'} md:block`}
          aria-label="Session list sidebar"
        >
          <ErrorBoundary>
            <SessionList
              codebases={codebases}
              sessions={sessions}
              selectedCodebase={selectedCodebase}
              selectedSession={selectedSession}
              onCodebaseChange={onCodebaseChange}
              onSessionSelect={onSessionSelect}
              onSearchChange={setSessionQuery}
              hasMoreSessions={hasMoreSessions}
              loadingMoreSessions={loadingMoreSessions}
              onLoadMoreSessions={handleLoadMoreSessions}
              totalSessions={totalSessions}
            />
          </ErrorBoundary>
        </aside>

        {/* Chat area */}
        <div
          id="chat-pane"
          className={`flex h-full min-h-0 flex-col overflow-hidden ${mobilePane === 'chat' ? '' : 'hidden'} md:flex`}
        >
          <div
            className="flex h-full min-h-0 flex-col overflow-hidden rounded-lg bg-white shadow-sm dark:bg-gray-800 dark:ring-1 dark:ring-white/10"
            role="region"
            aria-label={
              selectedSession
                ? `Chat: ${selectedSession.title || 'Untitled session'}`
                : 'Chat panel'
            }
          >
            <ErrorBoundary>
              <ChatHeader
                selectedSession={selectedSession}
                selectedCodebase={selectedCodebase}
                selectedCodebaseName={selectedCodebaseMeta?.name}
                selectedMode={selectedMode}
                selectedModel={selectedModel}
                suggestedModels={suggestedModels}
                streamConnected={streamConnected}
                streamStatus={streamStatus}
                loading={loading || resumeLoading}
                awaitingResponse={awaitingResponse}
                chatItemsCount={displayChatItems.length}
                showBackButton={mobilePane === 'chat'}
                onBackToSessions={() => setMobilePane('sessions')}
                onModeChange={setSelectedMode}
                onModelChange={setSelectedModel}
                onResume={() =>
                  selectedSession && resumeSession(selectedSession, null)
                }
                onRefresh={() =>
                  selectedSession && loadSessionMessages(selectedSession.id)
                }
                showRLMPane={showRLMPane}
                onToggleRLMPane={() => setShowRLMPane(!showRLMPane)}
              />
              <ChatMessages
                chatItems={displayChatItems}
                selectedSession={selectedSession}
                loading={loading}
                loadingMore={loadingMore}
                hasMore={hasMore}
                totalMessages={totalMessages}
                error={error}
                liveDraft={liveDraft}
                awaitingResponse={awaitingResponse}
                onLoadMore={loadMoreMessages}
              />
              <ChatInput
                draftMessage={draftMessage}
                loading={loading || resumeLoading}
                actionStatus={actionStatus}
                hasSession={!!selectedSession}
                onDraftChange={setDraftMessage}
                onSend={onSend}
              />
            </ErrorBoundary>
          </div>
        </div>

        {showRLMPane && (
          <aside className="hidden h-full min-h-0 overflow-hidden rounded-lg bg-gray-950 shadow-lg ring-1 ring-white/10 lg:flex">
            <RLMExecutionPane
              isOpen={showRLMPane}
              onClose={() => setShowRLMPane(false)}
              sessionId={selectedSession?.id}
              liveDraft={liveDraft}
              steps={combinedRlmSteps}
              stats={combinedRlmStats}
              variant="dock"
            />
          </aside>
        )}
      </div>

      {/* RLM Execution Pane (mobile overlay) */}
      <RLMExecutionPane
        isOpen={showRLMPane}
        onClose={() => setShowRLMPane(false)}
        sessionId={selectedSession?.id}
        liveDraft={liveDraft}
        steps={combinedRlmSteps}
        stats={combinedRlmStats}
        variant="overlay"
        className="lg:hidden"
      />
    </div>
  )
}
