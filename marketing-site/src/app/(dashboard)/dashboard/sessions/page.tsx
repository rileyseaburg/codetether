'use client'

import { useState, useEffect, useCallback, useMemo, useRef } from 'react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.codetether.run'

interface Codebase {
    id: string
    name: string
    path: string
    status: string
    worker_id?: string | null
    opencode_port?: number | null
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
    const [selectedMode, setSelectedMode] = useState('build')
    const [selectedModel, setSelectedModel] = useState('')
    const [loading, setLoading] = useState(false)
    const [actionStatus, setActionStatus] = useState<string | null>(null)
    const [streamConnected, setStreamConnected] = useState(false)
    const [streamStatus, setStreamStatus] = useState<string>('')
    const [liveDraft, setLiveDraft] = useState<string>('')
    const messagesContainerRef = useRef<HTMLDivElement | null>(null)
    const messagesEndRef = useRef<HTMLDivElement | null>(null)
    const shouldAutoScrollRef = useRef(true)
    const eventSourceRef = useRef<EventSource | null>(null)

    const MODEL_STORAGE_KEY = 'codetether.model.default'

    const loadCodebases = useCallback(async () => {
        try {
            const response = await fetch(`${API_URL}/v1/opencode/codebases/list`)
            if (response.ok) {
                const data = await response.json()
                const items = Array.isArray(data) ? data : (data?.codebases ?? [])
                setCodebases(
                    (items as any[])
                        .map((cb) => ({
                            id: String(cb?.id ?? ''),
                            name: String(cb?.name ?? cb?.id ?? ''),
                            path: String(cb?.path ?? ''),
                            status: String(cb?.status ?? 'unknown'),
                            worker_id: typeof cb?.worker_id === 'string' ? cb.worker_id : null,
                            opencode_port:
                                typeof cb?.opencode_port === 'number'
                                    ? cb.opencode_port
                                    : cb?.opencode_port
                                        ? Number(cb.opencode_port)
                                        : null,
                        }))
                        .filter((cb) => cb.id)
                )
            }
        } catch (error) {
            console.error('Failed to load codebases:', error)
        }
    }, [])

    const selectedCodebaseMeta = useMemo(() => {
        if (!selectedCodebase) return null
        return codebases.find((c) => c.id === selectedCodebase) || null
    }, [codebases, selectedCodebase])

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
        // Load persisted model override (per-browser) so users can switch models easily.
        try {
            const saved = window.localStorage.getItem(MODEL_STORAGE_KEY)
            if (saved) setSelectedModel(saved)
        } catch {
            // ignore
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [])

    useEffect(() => {
        // Persist model override.
        try {
            if (selectedModel) window.localStorage.setItem(MODEL_STORAGE_KEY, selectedModel)
            else window.localStorage.removeItem(MODEL_STORAGE_KEY)
        } catch {
            // ignore
        }
    }, [selectedModel])

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

    useEffect(() => {
        // Keep mode in sync with the selected session, but allow user override.
        if (!selectedSession) return
        const next = (selectedSession.agent || 'build').toString()
        setSelectedMode(next)
    }, [selectedSession])

    useEffect(() => {
        // Connect SSE stream for the selected codebase so we can show real-time output in the chat UI.
        // Only attempt SSE when the codebase is streamable.
        if (eventSourceRef.current) {
            eventSourceRef.current.close()
            eventSourceRef.current = null
        }

        setStreamConnected(false)
        setStreamStatus('')
        setLiveDraft('')

        if (!selectedCodebase || !selectedSession) return
        if (!selectedCodebaseMeta) return

        const canStream = Boolean(selectedCodebaseMeta.worker_id) || Boolean(selectedCodebaseMeta.opencode_port)
        if (!canStream) {
            setStreamStatus('Live stream unavailable (agent not running / no worker assigned)')
            return
        }

        const es = new EventSource(`${API_URL}/v1/opencode/codebases/${selectedCodebase}/events`)
        eventSourceRef.current = es

        es.onopen = () => {
            setStreamConnected(true)
            setStreamStatus('Live')
        }

        es.onerror = () => {
            setStreamConnected(false)
            setStreamStatus('Disconnected')
        }

        const onStatus = (e: MessageEvent) => {
            try {
                const data = JSON.parse(e.data)
                const sessionId = typeof data?.session_id === 'string' ? data.session_id : undefined
                if (sessionId && selectedSession?.id && sessionId !== selectedSession.id) return

                const msg = (data?.message || data?.status || '').toString()
                if (msg) setStreamStatus(msg)

                const statusValue = (data?.status || '').toString()
                const eventType = (data?.event_type || data?.type || '').toString()
                if ((statusValue === 'idle' || eventType === 'idle') && selectedSession?.id) {
                    void loadSessionMessages(selectedSession.id)
                    setLiveDraft('')
                }
            } catch {
                // ignore
            }
        }

        const onMessage = (e: MessageEvent) => {
            // We receive a mix of OpenCode-transformed events and remote-worker task streams.
            // If a session_id is present, filter to the selected session.
            try {
                const data = JSON.parse(e.data)
                const sessionId = typeof data?.session_id === 'string' ? data.session_id : undefined

                if (sessionId && selectedSession?.id && sessionId !== selectedSession.id) return

                const eventType = (data?.event_type || data?.type || '').toString()
                const isText =
                    eventType === 'part.text' ||
                    eventType === 'text' ||
                    data?.type === 'text'
                if (isText) {
                    const delta = typeof data?.delta === 'string' ? data.delta : ''
                    const content = typeof data?.content === 'string' ? data.content : ''
                    const text = typeof data?.text === 'string' ? data.text : ''
                    const next = delta || content || text
                    if (next) {
                        setLiveDraft((prev) => (prev ? prev + next : next))
                    }
                }
            } catch {
                // ignore
            }
        }

        es.addEventListener('status', onStatus)
        es.addEventListener('idle', onStatus)
        es.addEventListener('message', onMessage)
        es.addEventListener('part.text', onMessage)

        return () => {
            es.removeEventListener('status', onStatus)
            es.removeEventListener('idle', onStatus)
            es.removeEventListener('message', onMessage)
            es.removeEventListener('part.text', onMessage)
            es.close()
        }
    }, [selectedCodebase, selectedCodebaseMeta, selectedSession, loadSessionMessages])

    useEffect(() => {
        if (!selectedSession) return
        if (!shouldAutoScrollRef.current) return
        // Use 'auto' to avoid scroll-jank while messages stream in.
        messagesEndRef.current?.scrollIntoView({ behavior: 'auto' })
    }, [selectedSession, sessionMessages])

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
                    body: JSON.stringify({
                        prompt: prompt || null,
                        agent: selectedMode || session.agent || 'build',
                        model: selectedModel?.trim() ? selectedModel.trim() : null,
                    }),
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

    const chatMessages = useMemo(() => {
        return (sessionMessages || []).map((msg) => {
            const info = (msg.info || msg) as {
                role?: string
                model?: string
                content?: unknown
            }
            const role = (info.role || msg.role || 'unknown').toString()
            const normalizedRole = role === 'human' ? 'user' : role
            const content = extractContent(msg)
            return {
                role: normalizedRole,
                model: info.model || msg.model,
                content,
            }
        })
    }, [sessionMessages])

    const suggestedModels = useMemo(() => {
        const models = new Set<string>()
        for (const m of chatMessages) {
            if (m.model) models.add(String(m.model))
        }
        // Also allow a few common placeholders without being prescriptive.
        // (Users can type any provider/model supported by their worker/OpenCode.)
        ;[
            'anthropic/claude-sonnet-4-20250514',
            'anthropic/claude-3-5-sonnet-latest',
            'openai/gpt-4.1',
            'openai/gpt-4o',
        ].forEach((m) => models.add(m))
        return Array.from(models).sort()
    }, [chatMessages])

    const onMessagesScroll = () => {
        const el = messagesContainerRef.current
        if (!el) return
        const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
        // If user scrolls up more than a small threshold, stop auto-scroll.
        shouldAutoScrollRef.current = distanceFromBottom < 140
    }

    return (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
            {/* Left: Session list */}
            <div className="lg:col-span-4">
                <div className="rounded-lg bg-white shadow-sm dark:bg-gray-800 dark:ring-1 dark:ring-white/10">
                    <div className="p-4 border-b border-gray-200 dark:border-gray-700">
                        <div className="flex items-center justify-between gap-3">
                            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Sessions</h2>
                            <select
                                value={selectedCodebase}
                                onChange={(e) => {
                                    setSelectedCodebase(e.target.value)
                                    setSelectedSession(null)
                                    setSessionMessages([])
                                    setActionStatus(null)
                                    setStreamConnected(false)
                                    setStreamStatus('')
                                    setLiveDraft('')
                                }}
                                className="min-w-0 rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white text-sm"
                            >
                                <option value="">Select codebase...</option>
                                {codebases.map((cb) => (
                                    <option key={cb.id} value={cb.id}>{cb.name}</option>
                                ))}
                            </select>
                        </div>
                    </div>

                    <div className="divide-y divide-gray-200 dark:divide-gray-700 max-h-[calc(100vh-220px)] overflow-y-auto">
                        {sessions.length === 0 ? (
                            <div className="p-8 text-center text-gray-500 dark:text-gray-400">
                                <ChatIcon className="mx-auto h-12 w-12 text-gray-400" />
                                <p className="mt-2 text-sm">
                                    {selectedCodebase ? 'No sessions found' : 'Select a codebase to view sessions'}
                                </p>
                            </div>
                        ) : (
                            sessions.map((session) => (
                                <button
                                    type="button"
                                    key={session.id}
                                    className={`w-full text-left p-4 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors ${selectedSession?.id === session.id ? 'bg-indigo-50 dark:bg-indigo-900/20' : ''}`}
                                    onClick={() => {
                                        setSelectedSession(session)
                                        setSelectedMode((session.agent || 'build').toString())
                                    }}
                                >
                                    <div className="flex items-start justify-between gap-3">
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
                                        <span className="text-xs text-gray-400 dark:text-gray-500">→</span>
                                    </div>
                                </button>
                            ))
                        )}
                    </div>
                </div>
            </div>

            {/* Right: Chat */}
            <div className="lg:col-span-8">
                <div className="rounded-lg bg-white shadow-sm dark:bg-gray-800 dark:ring-1 dark:ring-white/10 h-[calc(100vh-160px)] flex flex-col">
                    <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between gap-3">
                        <div className="min-w-0">
                            <h3 className="text-sm font-semibold text-gray-900 dark:text-white truncate">
                                {selectedSession ? (selectedSession.title || 'Untitled Session') : 'Chat'}
                            </h3>
                            <p className="text-xs text-gray-500 dark:text-gray-400">
                                {selectedSession
                                    ? `Mode: ${selectedMode || selectedSession.agent || 'build'} • ${chatMessages.length} messages`
                                    : 'Select a session on the left'}
                            </p>
                        </div>
                        <div className="flex items-center gap-2">
                            <div className="hidden sm:flex items-center gap-2">
                                <span className={`h-2.5 w-2.5 rounded-full ${streamConnected ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`} />
                                <span className="text-xs text-gray-500 dark:text-gray-400">{streamStatus || (streamConnected ? 'Live' : 'Offline')}</span>
                            </div>

                            <select
                                value={selectedMode}
                                onChange={(e) => setSelectedMode(e.target.value)}
                                className="rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-xs px-2 py-2"
                                title="Agent mode"
                            >
                                <option value="build">build</option>
                                <option value="plan">plan</option>
                                <option value="explore">explore</option>
                                <option value="general">general</option>
                            </select>

                            <div className="hidden md:flex flex-col items-end">
                                <label className="text-[10px] text-gray-400 dark:text-gray-500" htmlFor="ct-model">
                                    Model (optional)
                                </label>
                                <input
                                    id="ct-model"
                                    value={selectedModel}
                                    onChange={(e) => setSelectedModel(e.target.value)}
                                    list="ct-model-options"
                                    placeholder="provider/model"
                                    className="w-[220px] rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-xs px-2 py-2"
                                    title="Override the model used when resuming/sending messages"
                                />
                                <datalist id="ct-model-options">
                                    {suggestedModels.map((m) => (
                                        <option key={m} value={m} />
                                    ))}
                                </datalist>
                            </div>

                            {selectedSession ? (
                                <>
                                    <button
                                        type="button"
                                        onClick={() => void resumeSession(selectedSession, null)}
                                        disabled={loading}
                                        className="rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-xs font-medium text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50"
                                    >
                                        Resume
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => void loadSessionMessages(selectedSession.id)}
                                        disabled={loading}
                                        className="rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-xs font-medium text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50"
                                    >
                                        Refresh
                                    </button>
                                </>
                            ) : null}
                        </div>
                    </div>

                    <div
                        ref={messagesContainerRef}
                        onScroll={onMessagesScroll}
                        className="flex-1 overflow-y-auto bg-gray-50 dark:bg-gray-900 p-4"
                    >
                        {!selectedSession ? (
                            <div className="h-full flex items-center justify-center">
                                <p className="text-sm text-gray-500 dark:text-gray-400">Select a session to view the chat.</p>
                            </div>
                        ) : chatMessages.length === 0 ? (
                            <div className="h-full flex items-center justify-center">
                                <p className="text-sm text-gray-500 dark:text-gray-400">No messages yet.</p>
                            </div>
                        ) : (
                            <div className="space-y-4">
                                {chatMessages.map((m, idx) => {
                                    const isUser = m.role === 'user'
                                    const label = isUser ? 'You' : 'Agent'
                                    return (
                                        <div
                                            key={idx}
                                            className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}
                                        >
                                            <div className={`max-w-[85%] ${isUser ? 'text-right' : 'text-left'}`}>
                                                <div className="flex items-center gap-2 mb-1">
                                                    {!isUser ? (
                                                        <span className="text-xs font-medium text-gray-600 dark:text-gray-300">{label}</span>
                                                    ) : null}
                                                    {m.model ? (
                                                        <span className="text-[10px] text-gray-400 dark:text-gray-500">{m.model}</span>
                                                    ) : null}
                                                    {isUser ? (
                                                        <span className="ml-auto text-xs font-medium text-gray-600 dark:text-gray-300">{label}</span>
                                                    ) : null}
                                                </div>
                                                <div
                                                    className={`rounded-2xl px-4 py-3 shadow-sm ring-1 ${isUser
                                                        ? 'bg-indigo-600 text-white ring-indigo-700/40'
                                                        : 'bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 ring-gray-200 dark:ring-white/10'
                                                        }`}
                                                >
                                                    <div className="whitespace-pre-wrap text-sm leading-relaxed">
                                                        {m.content || (isUser ? '(empty message)' : '(no content)')}
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    )
                                })}

                                {loading ? (
                                    <div className="flex justify-start">
                                        <div className="rounded-2xl px-4 py-3 bg-white dark:bg-gray-800 ring-1 ring-gray-200 dark:ring-white/10">
                                            <div className="text-sm text-gray-600 dark:text-gray-300">Thinking…</div>
                                        </div>
                                    </div>
                                ) : null}

                                {selectedSession && liveDraft ? (
                                    <div className="flex justify-start">
                                        <div className="max-w-[85%] text-left">
                                            <div className="flex items-center gap-2 mb-1">
                                                <span className="text-xs font-medium text-gray-600 dark:text-gray-300">Agent</span>
                                                <span className="text-[10px] text-gray-400 dark:text-gray-500">streaming • {selectedMode || selectedSession.agent || 'build'}</span>
                                            </div>
                                            <div className="rounded-2xl px-4 py-3 shadow-sm ring-1 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 ring-gray-200 dark:ring-white/10">
                                                <div className="whitespace-pre-wrap text-sm leading-relaxed">{liveDraft}</div>
                                            </div>
                                        </div>
                                    </div>
                                ) : null}
                            </div>
                        )}
                        <div ref={messagesEndRef} />
                    </div>

                    <div className="border-t border-gray-200 dark:border-gray-700 p-4">
                        {selectedSession ? (
                            <div className="space-y-2">
                                <div className="flex gap-2 items-end">
                                    <textarea
                                        value={draftMessage}
                                        onChange={(e) => setDraftMessage(e.target.value)}
                                        onKeyDown={(e) => {
                                            if (e.key === 'Enter' && !e.shiftKey) {
                                                e.preventDefault()
                                                void sendReply()
                                            }
                                        }}
                                        rows={2}
                                        placeholder="Message the agent… (Enter to send, Shift+Enter for newline)"
                                        className="flex-1 resize-none rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                                    />
                                    <button
                                        onClick={() => void sendReply()}
                                        disabled={loading || !draftMessage.trim()}
                                        className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
                                    >
                                        Send
                                    </button>
                                </div>

                                <div className="flex items-center justify-between gap-3">
                                    <span className="text-xs text-gray-500 dark:text-gray-400">
                                        Tip: Scroll up to pause auto-scroll.
                                    </span>
                                    {actionStatus ? (
                                        <span className="text-xs text-gray-500 dark:text-gray-400">{actionStatus}</span>
                                    ) : null}
                                </div>
                            </div>
                        ) : (
                            <p className="text-sm text-gray-500 dark:text-gray-400">Select a session to start chatting.</p>
                        )}
                    </div>
                </div>
            </div>
        </div>
    )
}
