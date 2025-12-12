'use client'

import { useState, useEffect, useCallback } from 'react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.codetether.run'

interface Codebase {
    id: string
    name: string
    path: string
    status: string
}

interface Session {
    id: string
    title?: string
    agent?: string
    messageCount?: number
    created?: string
    updated?: string
}

interface SessionMessage {
    info?: {
        role?: string
        model?: string
        content?: string
    }
    role?: string
    model?: string
    content?: string
    parts?: Array<{
        type: string
        text?: string
    }>
}

function ChatIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
        </svg>
    )
}

export default function SessionsPage() {
    const [codebases, setCodebases] = useState<Codebase[]>([])
    const [selectedCodebase, setSelectedCodebase] = useState('')
    const [sessions, setSessions] = useState<Session[]>([])
    const [selectedSession, setSelectedSession] = useState<Session | null>(null)
    const [sessionMessages, setSessionMessages] = useState<SessionMessage[]>([])
    const [draftMessage, setDraftMessage] = useState('')
    const [loading, setLoading] = useState(false)
    const [actionStatus, setActionStatus] = useState<string | null>(null)

    const loadCodebases = useCallback(async () => {
        try {
            const response = await fetch(`${API_URL}/v1/opencode/codebases`)
            if (response.ok) {
                const data = await response.json()
                setCodebases(data)
            }
        } catch (error) {
            console.error('Failed to load codebases:', error)
        }
    }, [])

    const loadSessions = useCallback(async (codebaseId: string) => {
        if (!codebaseId) {
            setSessions([])
            return
        }
        try {
            const response = await fetch(`${API_URL}/v1/opencode/codebases/${codebaseId}/sessions`)
            if (response.ok) {
                const data = await response.json()
                setSessions(data.sessions || [])
            }
        } catch (error) {
            console.error('Failed to load sessions:', error)
        }
    }, [])

    const loadSessionMessages = useCallback(async (sessionId: string) => {
        if (!selectedCodebase || !sessionId) return
        try {
            const response = await fetch(`${API_URL}/v1/opencode/codebases/${selectedCodebase}/sessions/${sessionId}/messages`)
            if (response.ok) {
                const data = await response.json()
                setSessionMessages(data.messages || [])
            }
        } catch (error) {
            console.error('Failed to load session messages:', error)
        }
    }, [selectedCodebase])

    useEffect(() => {
        loadCodebases()
    }, [loadCodebases])

    useEffect(() => {
        if (selectedCodebase) {
            loadSessions(selectedCodebase)
        }
    }, [selectedCodebase, loadSessions])

    useEffect(() => {
        if (selectedSession) {
            loadSessionMessages(selectedSession.id)
        }
    }, [selectedSession, loadSessionMessages])

    const resumeSession = async (session: Session, prompt: string | null) => {
        if (!selectedCodebase || !session?.id) return
        setLoading(true)
        setActionStatus(null)
        try {
            const response = await fetch(
                `${API_URL}/v1/opencode/codebases/${selectedCodebase}/sessions/${session.id}/resume`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prompt: prompt || null, agent: session.agent || 'build' }),
                }
            )

            const data = await response.json().catch(() => ({}))
            if (!response.ok) {
                setActionStatus(`Resume failed: ${data?.detail || data?.message || response.statusText}`)
                return
            }

            const activeSessionId: string =
                data?.active_session_id || data?.new_session_id || data?.session_id || session.id

            // Keep UI focused on the active session (some backends may return a new session id)
            setSelectedSession((prev) => {
                const base = prev && prev.id === session.id ? prev : session
                return activeSessionId && base.id !== activeSessionId ? { ...base, id: activeSessionId } : base
            })

            // Refresh sidebar lists and message preview
            await loadSessions(selectedCodebase)
            await loadSessionMessages(activeSessionId)

            setActionStatus(prompt ? 'Message sent (session resumed if needed).' : 'Session resumed. You can reply below.')
        } catch (error) {
            console.error('Failed to resume session:', error)
            setActionStatus('Resume failed: network error')
        } finally {
            setLoading(false)
        }
    }

    const sendReply = async () => {
        if (!selectedSession) return
        const message = draftMessage.trim()
        if (!message) return
        await resumeSession(selectedSession, message)
        setDraftMessage('')
    }

    const formatDate = (dateStr: string) => {
        if (!dateStr) return ''
        const date = new Date(dateStr)
        const now = new Date()
        const diff = now.getTime() - date.getTime()

        if (diff < 60000) return 'Just now'
        if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`
        if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`
        return date.toLocaleDateString()
    }

    const extractContent = (msg: SessionMessage): string => {
        const info = (msg.info || msg) as {
            role?: string
            model?: string
            content?: unknown
        }
        const parts = msg.parts || []

        let content = ''
        for (const part of parts) {
            if (part.type === 'text' && part.text) {
                content += part.text
            }
        }
        if (!content && info.content) {
            content = typeof info.content === 'string' ? info.content : JSON.stringify(info.content)
        }
        return content
    }

    return (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            {/* Session List */}
            <div className="lg:col-span-2">
                <div className="rounded-lg bg-white shadow-sm dark:bg-gray-800 dark:ring-1 dark:ring-white/10">
                    <div className="p-4 border-b border-gray-200 dark:border-gray-700">
                        <div className="flex items-center justify-between">
                            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Session History</h2>
                            <select
                                value={selectedCodebase}
                                onChange={(e) => {
                                    setSelectedCodebase(e.target.value)
                                    setSelectedSession(null)
                                }}
                                className="rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white text-sm"
                            >
                                <option value="">Select codebase...</option>
                                {codebases.map((cb) => (
                                    <option key={cb.id} value={cb.id}>{cb.name}</option>
                                ))}
                            </select>
                        </div>
                    </div>
                    <div className="divide-y divide-gray-200 dark:divide-gray-700 max-h-[calc(100vh-350px)] overflow-y-auto">
                        {sessions.length === 0 ? (
                            <div className="p-8 text-center text-gray-500 dark:text-gray-400">
                                <ChatIcon className="mx-auto h-12 w-12 text-gray-400" />
                                <p className="mt-2 text-sm">
                                    {selectedCodebase ? 'No sessions found' : 'Select a codebase to view sessions'}
                                </p>
                            </div>
                        ) : (
                            sessions.map((session) => (
                                <div
                                    key={session.id}
                                    className={`p-4 hover:bg-gray-50 dark:hover:bg-gray-700/50 cursor-pointer ${selectedSession?.id === session.id ? 'bg-indigo-50 dark:bg-indigo-900/20' : ''}`}
                                    onClick={() => setSelectedSession(session)}
                                >
                                    <div className="flex items-start justify-between">
                                        <div className="min-w-0 flex-1">
                                            <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                                                {session.title || 'Untitled Session'}
                                            </p>
                                            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                                                {session.agent || 'build'} • {session.messageCount || 0} messages
                                            </p>
                                            <p className="text-xs text-gray-400 dark:text-gray-500">
                                                {formatDate(session.updated || session.created || '')}
                                            </p>
                                        </div>
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation()
                                                setSelectedSession(session)
                                                setDraftMessage('')
                                                void resumeSession(session, null)
                                            }}
                                            className="ml-2 text-xs text-indigo-600 dark:text-indigo-400 hover:underline"
                                        >
                                            ▶️ Resume
                                        </button>
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </div>
            </div>

            {/* Session Detail */}
            <div className="lg:col-span-1">
                <div className="rounded-lg bg-white shadow-sm dark:bg-gray-800 dark:ring-1 dark:ring-white/10 sticky top-24">
                    <div className="p-4 border-b border-gray-200 dark:border-gray-700">
                        <h3 className="text-sm font-semibold text-gray-900 dark:text-white">Session Messages</h3>
                    </div>
                    <div className="p-4">
                        {selectedSession ? (
                            <div className="space-y-4">
                                <div className="space-y-3 max-h-64 overflow-y-auto">
                                    {sessionMessages.slice(-20).map((msg, idx) => {
                                        const info = (msg.info || msg) as {
                                            role?: string
                                            model?: string
                                            content?: unknown
                                        }
                                        const role = info.role || 'unknown'
                                        const isUser = role === 'user' || role === 'human'
                                        const content = extractContent(msg)

                                        return (
                                            <div
                                                key={idx}
                                                className={`p-2 rounded-lg ${isUser ? 'bg-indigo-50 dark:bg-indigo-900/20' : 'bg-gray-50 dark:bg-gray-700/50'}`}
                                            >
                                                <div className="flex items-center gap-2 mb-1">
                                                    <span className={`text-xs font-medium ${isUser ? 'text-indigo-700 dark:text-indigo-300' : 'text-gray-700 dark:text-gray-300'}`}>
                                                        {isUser ? '👤 User' : '🤖 Assistant'}
                                                    </span>
                                                    {info.model && <span className="text-xs text-gray-400">{info.model}</span>}
                                                </div>
                                                <p className="text-sm text-gray-800 dark:text-gray-200 line-clamp-4">
                                                    {content.substring(0, 500)}
                                                </p>
                                            </div>
                                        )
                                    })}
                                </div>
                                <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
                                    <div className="space-y-2">
                                        <div className="flex gap-2">
                                            <input
                                                type="text"
                                                value={draftMessage}
                                                onChange={(e) => setDraftMessage(e.target.value)}
                                                onKeyDown={(e) => {
                                                    if (e.key === 'Enter') {
                                                        e.preventDefault()
                                                        void sendReply()
                                                    }
                                                }}
                                                placeholder="Reply to this session…"
                                                className="flex-1 rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white text-sm"
                                            />
                                            <button
                                                onClick={() => void sendReply()}
                                                disabled={loading || !draftMessage.trim()}
                                                className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
                                            >
                                                {loading ? '...' : 'Send'}
                                            </button>
                                        </div>
                                        <div className="flex items-center justify-between">
                                            <button
                                                type="button"
                                                onClick={() => void resumeSession(selectedSession, null)}
                                                disabled={loading}
                                                className="text-xs text-gray-600 dark:text-gray-300 hover:underline disabled:opacity-50"
                                            >
                                                Resume without sending
                                            </button>
                                            {actionStatus ? (
                                                <span className="text-xs text-gray-500 dark:text-gray-400">{actionStatus}</span>
                                            ) : null}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-8">
                                Select a session to view messages
                            </p>
                        )}
                    </div>
                </div>
            </div>
        </div>
    )
}
