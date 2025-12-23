import { useState, useCallback } from 'react'
import { API_URL, Session, SessionMessage } from '../types'

export function useSessions(selectedCodebase: string) {
    const [sessions, setSessions] = useState<Session[]>([])
    const [sessionMessages, setSessionMessages] = useState<SessionMessage[]>([])

    const loadSessions = useCallback(async (id: string) => {
        if (!id) { setSessions([]); return }
        try {
            const res = await fetch(`${API_URL}/v1/opencode/codebases/${id}/sessions`)
            if (res.ok) setSessions((await res.json()).sessions || [])
        } catch (e) { console.error('Failed to load sessions:', e) }
    }, [])

    const loadSessionMessages = useCallback(async (sessionId: string) => {
        if (!selectedCodebase || !sessionId) {
            console.warn('[useSessions] loadSessionMessages skipped:', { selectedCodebase, sessionId })
            return
        }
        // Clear previous messages immediately to prevent stale data display
        setSessionMessages([])
        try {
            const url = `${API_URL}/v1/opencode/codebases/${selectedCodebase}/sessions/${sessionId}/messages`
            console.log('[useSessions] Fetching messages from:', url)
            const res = await fetch(url)
            if (res.ok) {
                const data = await res.json()
                console.log('[useSessions] Got messages:', data.messages?.length || 0, 'messages')
                setSessionMessages(data.messages || [])
            } else {
                console.error('[useSessions] Failed to fetch messages:', res.status, res.statusText)
            }
        } catch (e) { console.error('Failed to load messages:', e) }
    }, [selectedCodebase])

    const clearSessions = useCallback(() => { setSessions([]); setSessionMessages([]) }, [])

    return { sessions, sessionMessages, loadSessions, loadSessionMessages, clearSessions }
}
