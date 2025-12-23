import { useState } from 'react'
import { API_URL, Session } from '../types'

interface UseSessionResumeProps {
    selectedCodebase: string
    selectedMode: string
    selectedModel: string
    onSessionUpdate: (sessionId: string) => void
    loadSessions: (codebaseId: string) => Promise<void>
    loadSessionMessages: (sessionId: string) => Promise<void>
}

export function useSessionResume({ selectedCodebase, selectedMode, selectedModel, onSessionUpdate, loadSessions, loadSessionMessages }: UseSessionResumeProps) {
    const [loading, setLoading] = useState(false)
    const [actionStatus, setActionStatus] = useState<string | null>(null)

    const resumeSession = async (session: Session, prompt: string | null) => {
        if (!selectedCodebase || !session?.id) return
        setLoading(true)
        setActionStatus(null)

        try {
            const response = await fetch(`${API_URL}/v1/opencode/codebases/${selectedCodebase}/sessions/${session.id}/resume`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt: prompt || null, agent: selectedMode || session.agent || 'build', model: selectedModel?.trim() || null }),
            })

            const data = await response.json().catch(() => ({}))
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
            console.error('Failed to resume session:', error)
            setActionStatus('Resume failed: network error')
        } finally {
            setLoading(false)
        }
    }

    return { loading, actionStatus, setActionStatus, resumeSession }
}
