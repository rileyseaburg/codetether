'use client'

import { useState, useEffect, useMemo, useCallback } from 'react'
import type { Session } from './types'
import { useCodebases, useSessions, useSessionStream, useModelStorage, useSessionResume } from './hooks'
import { useChatItems } from './useChatItems'
import { useSuggestedModels } from './useSuggestedModels'
import { SessionList, ChatHeader, ChatMessages, ChatInput } from './components'

export default function SessionsPage() {
    const [selectedCodebase, setSelectedCodebase] = useState('')
    const [selectedSession, setSelectedSession] = useState<Session | null>(null)
    const [selectedMode, setSelectedMode] = useState('build')
    const [draftMessage, setDraftMessage] = useState('')

    const { codebases } = useCodebases()
    const { selectedModel, setSelectedModel } = useModelStorage()
    const { sessions, sessionMessages, loadSessions, loadSessionMessages, clearSessions } = useSessions(selectedCodebase)
    const selectedCodebaseMeta = useMemo(() => codebases.find((c) => c.id === selectedCodebase) || null, [codebases, selectedCodebase])
    const handleSessionUpdate = useCallback((id: string) => setSelectedSession((p) => p && p.id !== id ? { ...p, id } : p), [])
    const { loading, actionStatus, setActionStatus, resumeSession } = useSessionResume({ selectedCodebase, selectedMode, selectedModel, onSessionUpdate: handleSessionUpdate, loadSessions, loadSessionMessages })
    const handleIdle = useCallback(() => { if (selectedSession?.id) loadSessionMessages(selectedSession.id) }, [selectedSession?.id, loadSessionMessages])
    const { streamConnected, streamStatus, liveDraft, resetStream } = useSessionStream({ selectedCodebase, selectedCodebaseMeta, selectedSession, onIdle: handleIdle })
    const chatItems = useChatItems(sessionMessages)
    const suggestedModels = useSuggestedModels(chatItems)

    useEffect(() => { if (selectedCodebase) loadSessions(selectedCodebase) }, [selectedCodebase, loadSessions])
    useEffect(() => {
        console.log('[page] selectedSession effect:', { selectedSession: selectedSession?.id, selectedCodebase })
        if (selectedSession) loadSessionMessages(selectedSession.id)
    }, [selectedSession, loadSessionMessages])
    useEffect(() => { if (selectedSession) setSelectedMode((selectedSession.agent || 'build').toString()) }, [selectedSession])

    const onCodebaseChange = (id: string) => { setSelectedCodebase(id); setSelectedSession(null); clearSessions(); setActionStatus(null); resetStream() }
    const onSessionSelect = (s: Session) => {
        console.log('[page] onSessionSelect:', { sessionId: s.id, selectedCodebase })
        setSelectedSession(s)
        setSelectedMode((s.agent || 'build').toString())
    }
    const onSend = async () => { if (selectedSession && draftMessage.trim()) { await resumeSession(selectedSession, draftMessage.trim()); setDraftMessage('') } }

    return (
        <main aria-label="Chat sessions dashboard" className="flex flex-col min-h-0 h-screen overflow-hidden">
            {/* Skip link for keyboard users */}
            <div className="relative shrink-0">
                <a
                    href="#chat-message-input"
                    className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:bg-indigo-600 focus:text-white focus:px-4 focus:py-2 focus:rounded-md"
                >
                    Skip to message input
                </a>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-12 gap-4 flex-1 min-h-0 overflow-hidden px-4 pb-4">
                {/* Session sidebar */}
                <aside className="md:col-span-4 lg:col-span-3 min-h-0 flex flex-col h-full" aria-label="Session list sidebar">
                    <SessionList
                        codebases={codebases}
                        sessions={sessions}
                        selectedCodebase={selectedCodebase}
                        selectedSession={selectedSession}
                        onCodebaseChange={onCodebaseChange}
                        onSessionSelect={onSessionSelect}
                    />
                </aside>

                {/* Chat area */}
                <div className="md:col-span-8 lg:col-span-9 flex flex-col min-h-0 overflow-hidden">
                    <div
                        className="rounded-lg bg-white shadow-sm dark:bg-gray-800 dark:ring-1 dark:ring-white/10 flex flex-col overflow-hidden flex-1 min-h-0"
                        role="region"
                        aria-label={selectedSession ? `Chat: ${selectedSession.title || 'Untitled session'}` : 'Chat panel'}
                    >
                        <ChatHeader
                            selectedSession={selectedSession}
                            selectedMode={selectedMode}
                            selectedModel={selectedModel}
                            suggestedModels={suggestedModels}
                            streamConnected={streamConnected}
                            streamStatus={streamStatus}
                            loading={loading}
                            chatItemsCount={chatItems.length}
                            onModeChange={setSelectedMode}
                            onModelChange={setSelectedModel}
                            onResume={() => selectedSession && resumeSession(selectedSession, null)}
                            onRefresh={() => selectedSession && loadSessionMessages(selectedSession.id)}
                        />
                        <ChatMessages
                            chatItems={chatItems}
                            selectedSession={selectedSession}
                            loading={loading}
                            liveDraft={liveDraft}
                            selectedMode={selectedMode}
                        />
                        <ChatInput
                            draftMessage={draftMessage}
                            loading={loading}
                            actionStatus={actionStatus}
                            hasSession={!!selectedSession}
                            onDraftChange={setDraftMessage}
                            onSend={onSend}
                        />
                    </div>
                </div>
            </div>
        </main>
    )
}
