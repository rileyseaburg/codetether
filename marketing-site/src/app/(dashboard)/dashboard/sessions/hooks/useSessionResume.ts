import { useState, useRef, useEffect, useCallback } from 'react'
import { API_URL, Session } from '../types'

interface UseSessionResumeProps {
    selectedWorkspace: string
    selectedMode: string
    selectedModel: string
    onSessionUpdate: (sessionId: string) => void
    loadSessions: (workspaceId: string) => Promise<void>
    loadSessionMessages: (sessionId: string, force?: boolean) => Promise<void>
}

const TIMEOUT_MS = 30000 // 30 second timeout
const MAX_RETRIES = 2
const POLL_INTERVAL_MS = 2000 // Poll every 2 seconds
const MAX_POLL_ATTEMPTS = 90 // 3 minutes max polling (90 * 2s)

type TaskStatus = 'pending' | 'running' | 'working' | 'completed' | 'failed' | 'cancelled'

interface TaskStatusResponse {
    id: string
    status: TaskStatus
    error?: string
    result?: unknown
}

async function fetchWithRetry(url: string, options: RequestInit, retries = MAX_RETRIES): Promise<Response> {
    let lastError: Error | null = null
    for (let attempt = 0; attempt <= retries; attempt++) {
        try {
            const response = await fetch(url, options)
            return response
        } catch (error) {
            lastError = error instanceof Error ? error : new Error(String(error))
            // Only retry on network errors (Failed to fetch), not on abort
            if (lastError.name === 'AbortError' || attempt === retries) {
                throw lastError
            }
            // Wait a bit before retrying (exponential backoff)
            await new Promise(r => setTimeout(r, 500 * Math.pow(2, attempt)))
            console.log(`[useSessionResume] Retry attempt ${attempt + 1}/${retries}`)
        }
    }
    throw lastError
}

export function useSessionResume({ selectedWorkspace, selectedMode, selectedModel, onSessionUpdate, loadSessions, loadSessionMessages }: UseSessionResumeProps) {
    const [loading, setLoading] = useState(false)
    const [actionStatus, setActionStatus] = useState<string | null>(null)
    const [taskStatus, setTaskStatus] = useState<TaskStatus | null>(null)
    const [activeTaskId, setActiveTaskId] = useState<string | null>(null)
    const abortControllerRef = useRef<AbortController | null>(null)
    const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
    const requestIdRef = useRef(0)
    const activeRequestIdRef = useRef<number | null>(null)
    const abortReasonsRef = useRef(new Map<number, 'timeout' | 'replaced'>())
    const pollAttemptsRef = useRef(0)

    // Cleanup on unmount to prevent memory leaks
    useEffect(() => {
        return () => {
            if (abortControllerRef.current) {
                const activeId = activeRequestIdRef.current
                if (typeof activeId === 'number') {
                    abortReasonsRef.current.set(activeId, 'replaced')
                }
                abortControllerRef.current.abort()
            }
            if (timeoutRef.current) {
                clearTimeout(timeoutRef.current)
            }
            if (pollIntervalRef.current) {
                clearInterval(pollIntervalRef.current)
            }
        }
    }, [])

    // Stop polling helper
    const stopPolling = useCallback(() => {
        if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current)
            pollIntervalRef.current = null
        }
        pollAttemptsRef.current = 0
    }, [])

    // Poll for task status
    const pollTaskStatus = useCallback(async (
        taskId: string,
        sessionId: string,
        workspaceId: string
    ): Promise<void> => {
        return new Promise((resolve, reject) => {
            pollAttemptsRef.current = 0

            const poll = async () => {
                pollAttemptsRef.current++

                if (pollAttemptsRef.current > MAX_POLL_ATTEMPTS) {
                    stopPolling()
                    setTaskStatus('failed')
                    setActionStatus('Task timed out - worker may be unavailable')
                    setLoading(false)
                    reject(new Error('Polling timeout'))
                    return
                }

                try {
                    const response = await fetch(`${API_URL}/v1/agent/tasks/${taskId}`)
                    if (!response.ok) {
                        console.warn('[useSessionResume] Failed to poll task status:', response.status)
                        return // Continue polling
                    }

                    const data: TaskStatusResponse = await response.json()
                    setTaskStatus(data.status)

                    if (data.status === 'pending') {
                        setActionStatus(`Waiting for worker... (${pollAttemptsRef.current}s)`)
                    } else if (data.status === 'working' || data.status === 'running') {
                        setActionStatus('Agent is processing...')
                    } else if (data.status === 'completed') {
                        stopPolling()
                        setActionStatus('Response received!')
                        // Reload messages to show the response
                        await loadSessionMessages(sessionId, true)
                        await loadSessions(workspaceId)
                        setLoading(false)
                        resolve()
                    } else if (data.status === 'failed') {
                        stopPolling()
                        setActionStatus(`Task failed: ${data.error || 'Unknown error'}`)
                        setLoading(false)
                        reject(new Error(data.error || 'Task failed'))
                    } else if (data.status === 'cancelled') {
                        stopPolling()
                        setActionStatus('Task was cancelled')
                        setLoading(false)
                        resolve()
                    }
                } catch (error) {
                    console.warn('[useSessionResume] Poll error:', error)
                    // Continue polling on network errors
                }
            }

            // Start polling
            poll() // Initial poll
            pollIntervalRef.current = setInterval(poll, POLL_INTERVAL_MS)
        })
    }, [stopPolling, loadSessionMessages, loadSessions])

    const resumeSession = async (session: Session, prompt: string | null) => {
        if (!selectedWorkspace || !session?.id) return

        // Skip empty resume calls if there's already a request in flight
        // This prevents the Resume button from interfering with message sends
        if (!prompt && activeRequestIdRef.current !== null) {
            console.log('[useSessionResume] Skipping empty resume - request already in flight')
            return
        }

        // Cancel any in-flight request and its timeout
        if (timeoutRef.current) {
            clearTimeout(timeoutRef.current)
            timeoutRef.current = null
        }
        if (abortControllerRef.current) {
            const activeId = activeRequestIdRef.current
            if (typeof activeId === 'number') {
                abortReasonsRef.current.set(activeId, 'replaced')
            }
            abortControllerRef.current.abort()
        }

        setLoading(true)
        setActionStatus(null)

        const requestId = ++requestIdRef.current
        activeRequestIdRef.current = requestId
        const url = `${API_URL}/v1/agent/workspaces/${selectedWorkspace}/sessions/${session.id}/resume`
        const controller = new AbortController()
        abortControllerRef.current = controller
        timeoutRef.current = setTimeout(() => {
            abortReasonsRef.current.set(requestId, 'timeout')
            controller.abort()
        }, TIMEOUT_MS)

        try {
            const body = { prompt: prompt || null, agent: selectedMode || 'build', model: selectedModel?.trim() || null }
            console.log('[useSessionResume] POST', url, body)

            const response = await fetchWithRetry(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
                signal: controller.signal,
            })

            if (timeoutRef.current) {
                clearTimeout(timeoutRef.current)
                timeoutRef.current = null
            }

            const data = await response.json().catch(() => ({}))
            console.log('[useSessionResume] Response:', response.status, data)

            if (!response.ok) {
                setActionStatus(`Resume failed: ${data?.detail || data?.message || response.statusText}`)
                return
            }

            const activeSessionId = data?.active_session_id || data?.new_session_id || data?.session_id || session.id
            onSessionUpdate(activeSessionId)

            // If we got a task_id, poll for completion
            if (data?.task_id) {
                setActiveTaskId(data.task_id)
                setTaskStatus('pending')
                setActionStatus('Task queued, waiting for worker...')

                // Start polling for task status (non-blocking)
                pollTaskStatus(data.task_id, activeSessionId, selectedWorkspace).catch((error) => {
                    console.warn('[useSessionResume] Task polling ended:', error?.message || error)
                })
                // Don't await - let it poll in background while showing intermediate state
                return
            }

            // Direct response (no task queued) - old behavior
            await loadSessions(selectedWorkspace)
            // Force reload messages since session ID may be the same but content changed
            await loadSessionMessages(activeSessionId, true)
            setActionStatus(prompt ? 'Message sent (session resumed if needed).' : 'Session resumed.')
        } catch (error) {
            if (timeoutRef.current) {
                clearTimeout(timeoutRef.current)
                timeoutRef.current = null
            }
            const abortReason = abortReasonsRef.current.get(requestId)

            if (error instanceof Error) {
                if (error.name === 'AbortError') {
                    if (abortReason === 'timeout') {
                        setActionStatus('Resume failed: Request timed out after 30s')
                    }
                    return
                } else if (error.message === 'Failed to fetch') {
                    // Log additional debug info
                    console.error('[useSessionResume] Failed to fetch after retries - possible causes: ad blocker, browser extension, VPN, or network issue')
                    console.error('[useSessionResume] Try: 1) Disable extensions 2) Check browser DevTools Network tab for blocked requests')
                    setActionStatus('Resume failed: Network error after retries. Check ad blockers or DevTools.')
                } else {
                    console.error('[useSessionResume] Error:', error, { url, workspace: selectedWorkspace, session: session.id })
                    setActionStatus(`Resume failed: ${error.message}`)
                }
            } else {
                console.error('[useSessionResume] Error:', error, { url, workspace: selectedWorkspace, session: session.id })
                setActionStatus('Resume failed: Unknown error')
            }
        } finally {
            setLoading(false)
            abortControllerRef.current = null
            timeoutRef.current = null
            abortReasonsRef.current.delete(requestId)
            if (activeRequestIdRef.current === requestId) {
                activeRequestIdRef.current = null
            }
        }
    }

    // Cancel any active polling when component unmounts or workspace changes
    const cancelPolling = useCallback(() => {
        stopPolling()
        setActiveTaskId(null)
        setTaskStatus(null)
    }, [stopPolling])

    return {
        loading,
        actionStatus,
        setActionStatus,
        resumeSession,
        taskStatus,
        activeTaskId,
        cancelPolling,
    }
}
