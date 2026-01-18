import { useState, useCallback, useRef } from 'react'
import { API_URL, Session, SessionMessage } from '../types'

export function useSessions(selectedCodebase: string) {
  const [sessions, setSessions] = useState<Session[]>([])
  const [sessionMessages, setSessionMessages] = useState<SessionMessage[]>([])
  const [loading, setLoading] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(true)
  const [totalMessages, setTotalMessages] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const latestLoadedSessionId = useRef<string | null>(null)
  const currentLimit = useRef<number | null>(null)
  const currentOffset = useRef<number | null>(null)
  const INITIAL_LOAD_LIMIT = 20
  const LOAD_MORE_LIMIT = 20

  const loadSessions = useCallback(async (id: string) => {
    if (!id) {
      setSessions([])
      return
    }
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

  const loadSessionMessages = useCallback(
    async (
      sessionId: string,
      force?: boolean,
      limit: number = INITIAL_LOAD_LIMIT,
      offset: number = 0,
    ) => {
      if (!selectedCodebase || !sessionId) {
        return
      }
      if (!force && latestLoadedSessionId.current === sessionId) {
        return
      }
      const requestedSessionId = sessionId
      latestLoadedSessionId.current = sessionId
      currentLimit.current = limit
      currentOffset.current = offset
      setLoading(true)
      setLoadingMore(false)
      setHasMore(true)
      setError(null)
      setSessionMessages([])
      try {
        const url = `${API_URL}/v1/opencode/codebases/${selectedCodebase}/sessions/${sessionId}/messages?limit=${limit}&offset=${offset}`
        const res = await fetch(url)
        if (latestLoadedSessionId.current !== requestedSessionId) {
          return
        }
        if (res.ok) {
          const data = await res.json()
          if (latestLoadedSessionId.current === requestedSessionId) {
            setSessionMessages(data.messages || [])
            setTotalMessages(data.total ?? data.messages?.length ?? 0)
            setHasMore(data.hasMore ?? false)
          }
        } else {
          setError('Failed to load messages')
        }
      } catch (e) {
        if (latestLoadedSessionId.current === requestedSessionId) {
          setError('Failed to load messages')
        }
      } finally {
        if (latestLoadedSessionId.current === requestedSessionId) {
          setLoading(false)
        }
      }
    },
    [selectedCodebase, INITIAL_LOAD_LIMIT],
  )

  const loadMoreMessages = useCallback(async () => {
    if (
      !selectedCodebase ||
      !latestLoadedSessionId.current ||
      loadingMore ||
      !hasMore
    ) {
      return
    }
    const sessionId = latestLoadedSessionId.current
    const offset = (currentOffset.current ?? 0) + (currentLimit.current ?? 0)
    setLoadingMore(true)
    try {
      const url = `${API_URL}/v1/opencode/codebases/${selectedCodebase}/sessions/${sessionId}/messages?limit=${LOAD_MORE_LIMIT}&offset=${offset}`
      const res = await fetch(url)
      if (res.ok) {
        const data = await res.json()
        setSessionMessages((prev) => [...(data.messages || []), ...prev])
        setTotalMessages(
          data.total ?? totalMessages + (data.messages?.length ?? 0),
        )
        setHasMore(data.hasMore ?? false)
        currentOffset.current = offset
      }
    } catch (e) {
      console.error('Failed to load more messages:', e)
    } finally {
      setLoadingMore(false)
    }
  }, [selectedCodebase, loadingMore, hasMore, LOAD_MORE_LIMIT, totalMessages])

  const clearSessions = useCallback(() => {
    setSessions([])
    setSessionMessages([])
    setLoading(false)
    setLoadingMore(false)
    setHasMore(true)
    setTotalMessages(0)
    setError(null)
    latestLoadedSessionId.current = null
    currentLimit.current = null
    currentOffset.current = null
  }, [])

  return {
    sessions,
    sessionMessages,
    loadSessions,
    loadSessionMessages,
    loadMoreMessages,
    clearSessions,
    loading,
    loadingMore,
    hasMore,
    totalMessages,
    error,
  }
}
