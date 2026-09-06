'use client'

import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import type { ChatItem, Session } from './types'
import {
  useWorkspaces,
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
  const [selectedWorkspace, setSelectedWorkspace] = useState('')
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

  const {
    workspaces,
    loadWorkspaces,
    loading: workspacesLoading,
    error: workspacesError,
  } = useWorkspaces()
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
    sessionsLoading,
    sessionsError,
    loadingMore,
    loadingMoreSessions,
    hasMore,
    hasMoreSessions,
    totalMessages,
    totalSessions,
    error,
  } = useSessions(selectedWorkspace)
  const selectedWorkspaceMeta = useMemo(
    () => workspaces.find((c) => c.id === selectedWorkspace) || null,
    [workspaces, selectedWorkspace],
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
    selectedWorkspace,
    selectedMode,
    selectedModel,
    onSessionUpdate: handleSessionUpdate,
    loadSessions,
    loadSessionMessages,
  })
  const handleIdle = useCallback(() => {
    if (selectedSession?.id) loadSessionMessages(selectedSession.id)
  }, [selectedSession?.id, loadSessionMessages])
  const {
    streamConnected,
    streamStatus,
    liveDraft,
    rlmSteps,
    rlmStats,
    resetStream,
  } = useSessionStream({
    selectedWorkspace,
    selectedWorkspaceMeta: selectedWorkspaceMeta,
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
  const { steps: historyRlmSteps, stats: historyRlmStats } =
    useRlmFromHistory(chatItems)
  const combinedRlmSteps = useMemo(
    () => (rlmSteps.length > 0 ? rlmSteps : historyRlmSteps),
    [rlmSteps, historyRlmSteps],
  )
  const combinedRlmStats = useMemo(
    () =>
      rlmStats.tokens > 0 || rlmStats.chunks > 0 || rlmStats.subcalls.total > 0
        ? rlmStats
        : historyRlmStats,
    [rlmStats, historyRlmStats],
  )

  const layoutClass =
    'md:grid-cols-[18rem_minmax(0,1fr)] xl:grid-cols-[20rem_minmax(0,1fr)]'
  const handleLoadMoreSessions = useCallback(
    () => loadMoreSessions(selectedWorkspace),
    [loadMoreSessions, selectedWorkspace],
  )

  useEffect(() => {
    if (selectedWorkspace) loadSessions(selectedWorkspace, sessionQuery)
  }, [selectedWorkspace, sessionQuery, loadSessions])
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
    if (
      pendingResponseKeyRef.current &&
      lastChatKey === pendingResponseKeyRef.current
    ) {
      return
    }
    if (lastChatRole === 'assistant') {
      setAwaitingResponse(false)
    }
  }, [awaitingResponse, liveDraft, actionStatus, lastChatKey, lastChatRole])

  const onWorkspaceChange = useCallback(
    (id: string) => {
      setSelectedWorkspace(id)
      setSelectedSession(null)
      setShowRLMPane(false)
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
      className="flex h-full min-h-0 flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900"
    >
      {/* Skip link for keyboard users */}
      {selectedSession && (
        <a
          href="#chat-message-input"
          className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:rounded-md focus:bg-cyan-600 focus:px-4 focus:py-2 focus:text-white"
        >
          Skip to message input
        </a>
      )}

      <div
        className={`grid min-h-0 flex-1 grid-cols-1 overflow-hidden ${layoutClass}`}
      >
        {/* Session sidebar */}
        <aside
          id="sessions-pane"
          className={`h-full min-h-0 overflow-hidden border-gray-200 md:border-r dark:border-gray-800 ${mobilePane === 'sessions' ? '' : 'hidden'} md:block`}
          aria-label="Session list sidebar"
        >
          <ErrorBoundary>
            <SessionList
              workspaces={workspaces}
              sessions={sessions}
              selectedWorkspace={selectedWorkspace}
              selectedSession={selectedSession}
              onWorkspaceChange={onWorkspaceChange}
              onSessionSelect={onSessionSelect}
              onSearchChange={setSessionQuery}
              hasMoreSessions={hasMoreSessions}
              loadingMoreSessions={loadingMoreSessions}
              onLoadMoreSessions={handleLoadMoreSessions}
              totalSessions={totalSessions}
              loading={workspacesLoading || sessionsLoading}
              loadingLabel={
                workspacesLoading ? 'Loading workspaces…' : 'Loading sessions…'
              }
              error={workspacesError || sessionsError}
              onRetry={() => {
                if (workspacesError) void loadWorkspaces()
                else if (sessions.length)
                  void loadMoreSessions(selectedWorkspace)
                else void loadSessions(selectedWorkspace, sessionQuery)
              }}
            />
          </ErrorBoundary>
        </aside>

        {/* Chat area */}
        <div
          id="chat-pane"
          className={`flex h-full min-h-0 flex-col overflow-hidden ${mobilePane === 'chat' ? '' : 'hidden'} md:flex`}
        >
          <div
            className="mx-auto flex h-full min-h-0 w-full max-w-4xl flex-col overflow-hidden bg-white dark:bg-gray-900 [&_article_.wrap-break-word]:text-base [&_article_.wrap-break-word]:leading-7 [&_section>div.sticky]:border-0 [&_section>div.sticky]:bg-transparent [&_section>div.sticky]:py-1"
            role="region"
            aria-label={
              selectedSession
                ? `Chat: ${selectedSession.title || 'Untitled session'}`
                : 'Chat panel'
            }
          >
            <ErrorBoundary>
              {!selectedSession ? (
                <section
                  className="flex flex-1 flex-col items-center justify-center px-6 py-12 text-center"
                  aria-labelledby="conversation-empty-title"
                >
                  <span
                    aria-hidden="true"
                    className="mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-gray-100 text-2xl text-gray-400 dark:bg-gray-800"
                  >
                    ↖
                  </span>
                  <p className="text-xs font-medium tracking-widest text-gray-500 uppercase">
                    {selectedWorkspace
                      ? 'Next: choose a conversation'
                      : 'Start here'}
                  </p>
                  <h2
                    id="conversation-empty-title"
                    className="mt-3 text-2xl font-semibold tracking-tight text-gray-900 dark:text-white"
                  >
                    {selectedWorkspace
                      ? 'Choose a session'
                      : 'Choose a workspace'}
                  </h2>
                  <p className="mt-3 max-w-sm text-sm leading-7 text-gray-500 dark:text-gray-400">
                    {selectedWorkspace
                      ? 'Select a conversation from the list to read its messages and pick up where you left off.'
                      : 'Choose a workspace from the list. Its sessions will appear here, ready to continue.'}
                  </p>
                  <button
                    type="button"
                    onClick={() => {
                      setMobilePane('sessions')
                      requestAnimationFrame(() => {
                        const target = selectedWorkspace
                          ? document.querySelector<HTMLButtonElement>(
                              '#sessions-pane button[aria-controls="chat-pane"]',
                            )
                          : null
                        ;(
                          target || document.getElementById('workspace-select')
                        )?.focus()
                      })
                    }}
                    className="mt-6 min-h-11 rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 focus-visible:ring-2 focus-visible:ring-cyan-600 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800"
                  >
                    {selectedWorkspace ? 'View sessions' : 'Select workspace'}
                  </button>
                </section>
              ) : (
                <>
                  <ChatHeader
                    selectedSession={selectedSession}
                    selectedWorkspace={selectedWorkspace}
                    selectedWorkspaceName={selectedWorkspaceMeta?.name}
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
                    onRetry={() => {
                      if (sessionMessages.length) void loadMoreMessages()
                      else if (selectedSession)
                        void loadSessionMessages(selectedSession.id, true)
                    }}
                  />
                  <ChatInput
                    draftMessage={draftMessage}
                    loading={loading || resumeLoading}
                    actionStatus={actionStatus}
                    hasSession={!!selectedSession}
                    onDraftChange={setDraftMessage}
                    onSend={onSend}
                  />
                </>
              )}
            </ErrorBoundary>
          </div>
        </div>
      </div>

      {/* Execution detail is an optional overlay, never a third conversation column. */}
      <RLMExecutionPane
        isOpen={showRLMPane}
        onClose={() => setShowRLMPane(false)}
        sessionId={selectedSession?.id}
        liveDraft={liveDraft}
        steps={combinedRlmSteps}
        stats={combinedRlmStats}
        variant="overlay"
      />
    </div>
  )
}