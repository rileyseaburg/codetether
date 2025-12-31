import { useState, useCallback, useRef } from 'react'
import { API_URL, Session, SessionMessage } from '../types'

export function useSessions(selectedCodebase: string) {
    const [sessions, setSessions] = useState<Session[]>([])
    const [sessionMessages, setSessionMessages] = useState<SessionMessage[]>([])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const latestLoadedSessionId = useRef<string | null>(null)

    const loadSessions = useCallback(async (id: string) => {
        if (!id) { setSessions([]); return }
        setLoading(true)
        setError(null)
        try {
            const res = await fetch(`${API_URL}/v1/opencode/codebases/${id}/sessions`)
            if (res.ok) {
                const data = (await res.json()).sessions || []
                data.sort((a: Session, b: Session) => {
                    const dateA = new Date(a.updated || a.created || 0).getTime()
                    const dateB = new Date(b.updated || b.created || 0).getTime()
                    return dateB - dateA
                })
                setSessions(data)
            } else {
                setError('Failed to load sessions')
            }
        } catch (e) {
            setError('Failed to load sessions')
        } finally {
            setLoading(false)
        }
    }, [])

    const loadSessionMessages = useCallback(async (sessionId: string) => {
        if (!selectedCodebase || !sessionId) {
            return
        }
        if (latestLoadedSessionId.current === sessionId) {
            return
        }
        latestLoadedSessionId.current = sessionId
        setLoading(true)
        setError(null)
        setSessionMessages([])
        try {
            const url = `${API_URL}/v1/opencode/codebases/${selectedCodebase}/sessions/${sessionId}/messages`
            const res = await fetch(url)
            if (res.ok) {
                const data = await res.json()
                setSessionMessages(data.messages || [])
            } else {
                setError('Failed to load messages')
            }
        } catch (e) {
            setError('Failed to load messages')
        } finally {
            setLoading(false)
        }
    }, [selectedCodebase])

    const clearSessions = useCallback(() => {
        setSessions([])
        setSessionMessages([])
        setLoading(false)
        setError(null)
        latestLoadedSessionId.current = null
    }, [])

    return { sessions, sessionMessages, loadSessions, loadSessionMessages, clearSessions, loading, error }
}
