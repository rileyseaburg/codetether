'use client'

import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import type { Session } from './types'
import {
  useCodebases,
  useSessions,
  useSessionStream,
  useModelStorage,
  useSessionResume,
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

export default function SessionsPage() {
  const [selectedCodebase, setSelectedCodebase] = useState('')
  const [selectedSession, setSelectedSession] = useState<Session | null>(null)
  const [selectedMode, setSelectedMode] = useState('build')
  const [draftMessage, setDraftMessage] = useState('')
  const latestLoadingSessionId = useRef<string | null>(null)

  const { codebases } = useCodebases()
  const { selectedModel, setSelectedModel } = useModelStorage()
  const {
    sessions,
    sessionMessages,
    loadSessions,
    loadSessionMessages,
    loadMoreMessages,
    clearSessions,
    loading,
    loadingMore,
    hasMore,
    totalMessages,
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
  const { actionStatus, setActionStatus, resumeSession } = useSessionResume({
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
  const { streamConnected, streamStatus, liveDraft, resetStream } =
    useSessionStream({
      selectedCodebase,
      selectedCodebaseMeta,
      selectedSession,
      onIdle: handleIdle,
    })
  const chatItems = useChatItems(sessionMessages)
  const suggestedModels = useSuggestedModels(chatItems)

  useEffect(() => {
    if (selectedCodebase) loadSessions(selectedCodebase)
  }, [selectedCodebase, loadSessions])
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

  const onCodebaseChange = useCallback(
    (id: string) => {
      setSelectedCodebase(id)
      setSelectedSession(null)
      clearSessions()
      setActionStatus(null)
      resetStream()
    },
    [clearSessions, setActionStatus, resetStream],
  )

  const onSessionSelect = useCallback((s: Session) => {
    setSelectedSession(s)
    setSelectedMode((s.agent || 'build').toString())
  }, [])

  const onSend = useCallback(async () => {
    if (selectedSession && draftMessage.trim()) {
      try {
        await resumeSession(selectedSession, draftMessage.trim())
        setDraftMessage('')
      } catch (e) {
        console.error('Failed to send message:', e)
      }
    }
  }, [selectedSession, draftMessage, resumeSession])

  return (
    <div
      aria-label="Chat sessions dashboard"
      className="flex h-full min-h-0 flex-col overflow-hidden"
    >
      {/* Skip link for keyboard users */}
      <a
        href="#chat-message-input"
        className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:rounded-md focus:bg-indigo-600 focus:px-4 focus:py-2 focus:text-white"
      >
        Skip to message input
      </a>

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 overflow-hidden px-0.5 md:grid-cols-12">
        {/* Session sidebar */}
        <aside
          className="h-full min-h-0 overflow-hidden md:col-span-4 lg:col-span-3"
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
            />
          </ErrorBoundary>
        </aside>

        {/* Chat area */}
        <div className="flex h-full min-h-0 flex-col overflow-hidden md:col-span-8 lg:col-span-9">
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
                selectedMode={selectedMode}
                selectedModel={selectedModel}
                suggestedModels={suggestedModels}
                streamConnected={streamConnected}
                streamStatus={streamStatus}
                loading={loading}
                chatItemsCount={chatItems.length}
                onModeChange={setSelectedMode}
                onModelChange={setSelectedModel}
                onResume={() =>
                  selectedSession && resumeSession(selectedSession, null)
                }
                onRefresh={() =>
                  selectedSession && loadSessionMessages(selectedSession.id)
                }
              />
              <ChatMessages
                chatItems={chatItems}
                selectedSession={selectedSession}
                loading={loading}
                loadingMore={loadingMore}
                hasMore={hasMore}
                totalMessages={totalMessages}
                error={error}
                liveDraft={liveDraft}
                selectedMode={selectedMode}
                onLoadMore={loadMoreMessages}
              />
              <ChatInput
                draftMessage={draftMessage}
                loading={loading}
                actionStatus={actionStatus}
                hasSession={!!selectedSession}
                onDraftChange={setDraftMessage}
                onSend={onSend}
              />
            </ErrorBoundary>
          </div>
        </div>
      </div>
    </div>
  )
}
