import { useState, useRef } from 'react'
import { API_URL, Session } from '../types'

interface UseSessionResumeProps {
    selectedCodebase: string
    selectedMode: string
    selectedModel: string
    onSessionUpdate: (sessionId: string) => void
    loadSessions: (codebaseId: string) => Promise<void>
    loadSessionMessages: (sessionId: string) => Promise<void>
}

const TIMEOUT_MS = 30000 // 30 second timeout
const MAX_RETRIES = 2

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

export function useSessionResume({ selectedCodebase, selectedMode, selectedModel, onSessionUpdate, loadSessions, loadSessionMessages }: UseSessionResumeProps) {
    const [loading, setLoading] = useState(false)
    const [actionStatus, setActionStatus] = useState<string | null>(null)
    const abortControllerRef = useRef<AbortController | null>(null)
    const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

    const resumeSession = async (session: Session, prompt: string | null) => {
        if (!selectedCodebase || !session?.id) return

        // Cancel any in-flight request and its timeout
        if (timeoutRef.current) {
            clearTimeout(timeoutRef.current)
            timeoutRef.current = null
        }
        if (abortControllerRef.current) {
            abortControllerRef.current.abort()
        }

        setLoading(true)
        setActionStatus(null)

        const url = `${API_URL}/v1/opencode/codebases/${selectedCodebase}/sessions/${session.id}/resume`
        const controller = new AbortController()
        abortControllerRef.current = controller
        timeoutRef.current = setTimeout(() => controller.abort(), TIMEOUT_MS)

        try {
            const body = { prompt: prompt || null, agent: selectedMode || session.agent || 'build', model: selectedModel?.trim() || null }
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
            await loadSessions(selectedCodebase)
            await loadSessionMessages(activeSessionId)
            setActionStatus(prompt ? 'Message sent (session resumed if needed).' : 'Session resumed.')
        } catch (error) {
            if (timeoutRef.current) {
                clearTimeout(timeoutRef.current)
                timeoutRef.current = null
            }
            console.error('[useSessionResume] Error:', error, { url, codebase: selectedCodebase, session: session.id })

            if (error instanceof Error) {
                if (error.name === 'AbortError') {
                    setActionStatus('Resume failed: Request timed out after 30s')
                } else if (error.message === 'Failed to fetch') {
                    // Log additional debug info
                    console.error('[useSessionResume] Failed to fetch after retries - possible causes: ad blocker, browser extension, VPN, or network issue')
                    console.error('[useSessionResume] Try: 1) Disable extensions 2) Check browser DevTools Network tab for blocked requests')
                    setActionStatus('Resume failed: Network error after retries. Check ad blockers or DevTools.')
                } else {
                    setActionStatus(`Resume failed: ${error.message}`)
                }
            } else {
                setActionStatus('Resume failed: Unknown error')
            }
        } finally {
            setLoading(false)
            abortControllerRef.current = null
            timeoutRef.current = null
        }
    }

    return { loading, actionStatus, setActionStatus, resumeSession }
}
