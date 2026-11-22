import { useState, useEffect, useCallback } from 'react'
import { getSessionMessagesByIdV1AgentWorkspacesWorkspaceIdSessionsSessionIdMessagesGet } from '@/lib/api'

export interface PRDChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
}

interface PRDChatSession {
  id: string
  sessionId: string  // The actual CodeTether session ID for loading messages
  messages: PRDChatMessage[]
  lastUpdated: string | number
  title?: string
  messageCount?: number
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'https://api.codetether.run'

export function useAIPRDSessions(workspaceId: string | undefined) {
  const [sessions, setSessions] = useState<PRDChatSession[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadSessions = async () => {
    // Skip loading for 'global' or undefined workspace.
    if (!workspaceId || workspaceId === 'global') {
      setSessions([])
      return
    }

    setLoading(true)
    setError(null)

    try {
      // Use direct fetch until SDK is regenerated with new endpoint
      const response = await fetch(`${API_BASE}/v1/ralph/chat/sessions/${workspaceId}`)
      
      if (!response.ok) {
        setSessions([])
        return
      }
      
      const sessionsData = await response.json()
      // Get PRD chat sessions for this workspace
      const allSessions = (sessionsData.sessions || []).map((s: any) => ({
        id: s.id,
        sessionId: s.session_id,  // The CodeTether session ID
        title: s.title || 'PRD Chat',
        lastUpdated: s.updated_at || s.created_at || 0,
        messages: [],
        messageCount: s.message_count || 0,
      }))

      setSessions(allSessions)
    } catch (e) {
      setError('Failed to load PRD sessions')
    } finally {
      setLoading(false)
    }
  }

  const deleteSession = async (_sessionId: string) => {
    throw new Error('Delete session not implemented')
  }

  const loadSessionMessages = useCallback(async (openCodeSessionId: string): Promise<PRDChatMessage[]> => {
    if (!workspaceId || workspaceId === 'global') {
      return []
    }

    try {
      const { data, error: apiError } = await getSessionMessagesByIdV1AgentWorkspacesWorkspaceIdSessionsSessionIdMessagesGet({
        path: { workspace_id: workspaceId, session_id: openCodeSessionId }
      })

      if (apiError || !data) {
        return []
      }

      const messagesData = data as any
      const messages = messagesData.messages || []
      
      // Normalize message format from API
      return messages.map((m: any) => ({
        role: m.role || m.info?.role || 'assistant',
        content: m.content || m.info?.content || '',
        timestamp: m.time?.created || m.created_at || new Date().toISOString(),
      })).filter((m: PRDChatMessage) => m.content) // Filter out empty messages
    } catch (e) {
      console.error('Failed to load session messages:', e)
      return []
    }
  }, [workspaceId])

  useEffect(() => {
    loadSessions()
  }, [workspaceId])

  return { sessions, loading, error, loadSessions, deleteSession, loadSessionMessages }
}
