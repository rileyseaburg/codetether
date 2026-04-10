import { useState, useEffect, useRef, useCallback } from 'react'
import { API_URL, Workspace, Session } from '../types'

export interface RLMStep {
    id: string
    type: 'load' | 'code' | 'output' | 'subcall' | 'result' | 'error'
    content: string
    timestamp: Date
    status?: 'running' | 'completed' | 'error'
    duration?: number
}

export interface RLMStats {
    tokens: number
    chunks: number
    subcalls: { completed: number; total: number }
}

interface Props {
    selectedWorkspace: string
    selectedWorkspaceMeta: Workspace | null
    selectedSession: Session | null
    onIdle: () => void
}

const BACKOFF_MIN = 1000
const BACKOFF_MAX = 30000
const MAX_RECONNECT_ATTEMPTS = 10

// Note: RLM steps/stats are only populated from explicit RLM tool events (part.tool with tool_name='rlm',
// or rlm.step/rlm.stats/rlm.routing events), NOT from parsing text deltas which could be any tool output.

export function useSessionStream({ selectedWorkspace, selectedWorkspaceMeta, selectedSession, onIdle }: Props) {
    const [streamConnected, setStreamConnected] = useState(false)
    const [streamStatus, setStreamStatus] = useState('')
    const [liveDraft, setLiveDraft] = useState('')
    const [rlmSteps, setRlmSteps] = useState<RLMStep[]>([])
    const [rlmStats, setRlmStats] = useState<RLMStats>({ tokens: 0, chunks: 0, subcalls: { completed: 0, total: 0 } })
    const esRef = useRef<EventSource | null>(null)
    const attempts = useRef(0)
    const timeout = useRef<ReturnType<typeof setTimeout> | null>(null)
    // Use ref for onIdle to prevent infinite reconnection loops when callback changes
    const onIdleRef = useRef(onIdle)
    onIdleRef.current = onIdle

    const clearRLMState = useCallback(() => {
        setRlmSteps([])
        setRlmStats({ tokens: 0, chunks: 0, subcalls: { completed: 0, total: 0 } })
    }, [])

    useEffect(() => {
        esRef.current?.close()
        if (timeout.current) clearTimeout(timeout.current)
        setStreamConnected(false); setStreamStatus(''); setLiveDraft('')
        attempts.current = 0
        if (!selectedWorkspace || !selectedSession || !selectedWorkspaceMeta) return
        if (!selectedWorkspaceMeta.worker_id && !selectedWorkspaceMeta.agent_port) { setStreamStatus('Unavailable'); return }

        const connect = () => {
            // Handle relative API URLs by resolving against window.location
            const baseApiUrl = API_URL.startsWith('/') ? `${window.location.origin}${API_URL}` : API_URL
            const es = new EventSource(`${baseApiUrl}/v1/agent/workspaces/${selectedWorkspace}/events`)
            esRef.current = es

            es.onopen = () => {
                attempts.current = 0
                setStreamConnected(true)
                setStreamStatus('Live')
            }

            es.onerror = (err) => {
                console.error('EventSource error:', err)
                setStreamConnected(false)
                setStreamStatus('Disconnected')
                es.close()
                // Stop reconnecting after max attempts
                if (attempts.current >= MAX_RECONNECT_ATTEMPTS) {
                    setStreamStatus('Connection failed - max retries exceeded')
                    return
                }
                const delay = Math.min(BACKOFF_MIN * Math.pow(2, attempts.current), BACKOFF_MAX)
                attempts.current++
                timeout.current = setTimeout(connect, delay)
            }

            const handler = (e: MessageEvent) => {
                // Handle NDJSON (newline-delimited JSON) - multiple events can arrive in one message
                const lines = (e.data || '').split('\n').filter((line: string) => line.trim())

                for (const line of lines) {
                    try {
                        const d = JSON.parse(line)
                        processEvent(d)
                    } catch {
                        // Not valid JSON, skip this line
                        console.debug('[SSE] Skipping non-JSON line:', line.slice(0, 100))
                    }
                }
            }

            const processEvent = (d: Record<string, unknown>) => {
                try {
                    if (d?.session_id && selectedSession?.id && d.session_id !== selectedSession.id) return
                    if (d?.message || d?.status) setStreamStatus((d.message || d.status as string).toString())
                    if (d?.status === 'idle' || d?.event_type === 'idle') { onIdleRef.current(); setLiveDraft(''); clearRLMState() }
                    const t = (d?.event_type || d?.type || '') as string
                    // Debug: log event types we're receiving
                    if (t && !['status', 'connected'].includes(t)) {
                        console.debug('[SSE] Event type:', t)
                    }
                    // Clear live draft when a new step/response starts
                    // This ensures each message response is shown separately, not concatenated
                    if (t === 'step_start' || t === 'step-start') {
                        setLiveDraft('')
                        clearRLMState()
                    }
                    if (t === 'part.text' || t === 'text') {
                        // Extract text from various event formats:
                        // 1. CodeTether format: { part: { text: "..." } }
                        // 2. Direct delta: { delta: "..." }
                        // 3. Direct content: { content: "..." }
                        // 4. Direct text: { text: "..." }
                        const part = d?.part as Record<string, unknown> | undefined
                        const delta = (part && typeof part === 'object' ? part.text : null)
                            || d?.delta
                            || d?.content
                            || d?.text
                            || ''
                        if (!delta) return // Skip empty deltas
                        setLiveDraft((p) => p + delta)
                        // Note: RLM patterns are now only parsed from explicit RLM tool events,
                        // not from text deltas (which could be any tool output like Read/Grep)
                    }
                    // Handle RLM tool execution events (part.tool where tool_name is 'rlm')
                    if (t === 'part.tool' && d?.tool_name === 'rlm') {
                        const metadata = (d?.metadata || {}) as Record<string, unknown>
                        const status = (d?.status || 'running') as string

                        // Extract RLM stats from tool metadata
                        if (metadata.iteration !== undefined || metadata.totalSubcalls !== undefined) {
                            setRlmStats({
                                tokens: (metadata.totalSubcallTokens as number) || 0,
                                chunks: (metadata.maxIterations as number) || 0,
                                subcalls: {
                                    completed: (metadata.totalSubcalls as number) || 0,
                                    total: (metadata.maxIterations as number) || 20,
                                },
                            })
                        }

                        // Add step based on RLM execution state
                        if (status === 'running' && metadata.iteration) {
                            const stdout = metadata.stdout as string | undefined
                            const stepContent = stdout
                                ? stdout.slice(0, 500) + (stdout.length > 500 ? '...' : '')
                                : `Iteration ${metadata.iteration}/${metadata.maxIterations || 20}`

                            setRlmSteps(prev => {
                                const exists = prev.some(s => s.id === `rlm-iter-${metadata.iteration}`)
                                if (exists) return prev
                                return [...prev, {
                                    id: `rlm-iter-${metadata.iteration}`,
                                    type: 'subcall',
                                    content: stepContent,
                                    timestamp: new Date(),
                                    status: 'running',
                                }]
                            })
                        }

                        // Handle completed RLM tool
                        const output = d?.output as string | undefined
                        if (status === 'completed' && output) {
                            setRlmSteps(prev => {
                                // Mark all running as completed
                                const updated = prev.map(s => s.status === 'running' ? { ...s, status: 'completed' as const } : s)
                                return [...updated, {
                                    id: `rlm-result-${Date.now()}`,
                                    type: 'result',
                                    content: output.slice(0, 1000) + (output.length > 1000 ? '...' : ''),
                                    timestamp: new Date(),
                                    status: 'completed',
                                }]
                            })
                        }

                        // Handle error
                        const error = d?.error as string | undefined
                        if (status === 'error' && error) {
                            setRlmSteps(prev => [...prev, {
                                id: `rlm-error-${Date.now()}`,
                                type: 'error',
                                content: error,
                                timestamp: new Date(),
                                status: 'error',
                            }])
                        }
                    }

                    // Handle explicit RLM events from backend (if emitted)
                    if (t === 'rlm.step' || t === 'rlm_step') {
                        const step: RLMStep = {
                            id: (d.id as string) || `step-${Date.now()}`,
                            type: (d.step_type || d.rlm_type || 'output') as RLMStep['type'],
                            content: ((d.content || d.text) as string) || '',
                            timestamp: new Date((d.timestamp as number) || Date.now()),
                            status: (d.status as RLMStep['status']) || 'completed',
                            duration: d.duration as number | undefined,
                        }
                        setRlmSteps(prev => [...prev, step])
                    }
                    if (t === 'rlm.stats' || t === 'rlm_stats') {
                        setRlmStats({
                            tokens: (d.tokens as number) || 0,
                            chunks: (d.chunks as number) || 0,
                            subcalls: { completed: (d.subcalls_completed as number) || 0, total: (d.subcalls_total as number) || 0 },
                        })
                    }

                    // Handle RLM routing decision events
                    if (t === 'rlm.routing') {
                        const decision = d.decision as string // 'routed' or 'passthrough'
                        const reason = d.reason as string
                        const tokens = (d.estimated_tokens as number) || 0

                        // Add routing decision step to show in pane
                        if (decision === 'routed') {
                            setRlmSteps(prev => {
                                const exists = prev.some(s => s.id === `routing-${d.call_id}`)
                                if (exists) return prev
                                return [...prev, {
                                    id: `routing-${d.call_id || Date.now()}`,
                                    type: 'load',
                                    content: `RLM activated: ${d.tool} output (${tokens.toLocaleString()} tokens) exceeds threshold. Reason: ${reason}`,
                                    timestamp: new Date(),
                                    status: 'running',
                                }]
                            })
                            setRlmStats(prev => ({
                                ...prev,
                                tokens: Math.max(prev.tokens, tokens),
                            }))
                        }
                    }
                } catch (err) {
                    console.error('Failed to process event:', err)
                }
            }
                ;['status', 'idle', 'message', 'part.text', 'part.tool', 'rlm.routing'].forEach((e) => es.addEventListener(e, handler))
        }

        connect()

        return () => {
            esRef.current?.close()
            if (timeout.current) clearTimeout(timeout.current)
        }
        // onIdle is accessed via ref, so not needed in deps
    }, [selectedWorkspace, selectedWorkspaceMeta, selectedSession])

    return {
        streamConnected,
        streamStatus,
        liveDraft,
        rlmSteps,
        rlmStats,
        resetStream: () => { setStreamConnected(false); setStreamStatus(''); setLiveDraft(''); clearRLMState() }
    }
}
