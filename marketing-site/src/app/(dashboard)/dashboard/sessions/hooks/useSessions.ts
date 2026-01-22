import { useState, useCallback, useRef } from 'react'
import { API_URL, Session, SessionMessageWithParts } from '../types'

const SESSIONS_PAGE_SIZE = 30

export function useSessions(selectedCodebase: string) {
  const [sessions, setSessions] = useState<Session[]>([])
  const [sessionMessages, setSessionMessages] = useState<SessionMessageWithParts[]>([])
  const [loading, setLoading] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [loadingMoreSessions, setLoadingMoreSessions] = useState(false)
  const [hasMore, setHasMore] = useState(true)
  const [hasMoreSessions, setHasMoreSessions] = useState(true)
  const [totalMessages, setTotalMessages] = useState(0)
  const [totalSessions, setTotalSessions] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const latestLoadedSessionId = useRef<string | null>(null)
  const currentLimit = useRef<number | null>(null)
  const currentOffset = useRef<number | null>(null)
  const sessionsOffset = useRef<number>(0)
  const currentQuery = useRef<string>('')
  const INITIAL_LOAD_LIMIT = 20
  const LOAD_MORE_LIMIT = 20

  const loadSessions = useCallback(async (id: string, query?: string) => {
    if (!id) {
      setSessions([])
      setHasMoreSessions(true)
      setTotalSessions(0)
      sessionsOffset.current = 0
      currentQuery.current = ''
      return
    }
    if (typeof query === 'string') {
      currentQuery.current = query.trim()
    }
    setLoading(true)
    setError(null)
    sessionsOffset.current = 0
    try {
      const params = new URLSearchParams({
        limit: String(SESSIONS_PAGE_SIZE),
        offset: '0',
      })
      if (currentQuery.current) {
        params.set('q', currentQuery.current)
      }
      const res = await fetch(
        `${API_URL}/v1/opencode/codebases/${id}/sessions?${params.toString()}`,
      )
      if (res.ok) {
        const data = await res.json()
        const sessionsList = data.sessions || []
        // Backend now handles sorting, but keep client-side sort as fallback
        sessionsList.sort((a: Session, b: Session) => {
          const dateA = a.time?.updated || a.time?.created || 0
          const dateB = b.time?.updated || b.time?.created || 0
          return dateB - dateA
        })
        setSessions(sessionsList)
        setTotalSessions(data.total ?? sessionsList.length)
        setHasMoreSessions(data.hasMore ?? false)
      } else {
        setError('Failed to load sessions')
      }
    } catch (e) {
      setError('Failed to load sessions')
    } finally {
      setLoading(false)
    }
  }, [])

  const loadMoreSessions = useCallback(async (id: string) => {
    if (!id || loadingMoreSessions || !hasMoreSessions) return
    setLoadingMoreSessions(true)
    const newOffset = sessionsOffset.current + SESSIONS_PAGE_SIZE
    try {
      const params = new URLSearchParams({
        limit: String(SESSIONS_PAGE_SIZE),
        offset: String(newOffset),
      })
      if (currentQuery.current) {
        params.set('q', currentQuery.current)
      }
      const res = await fetch(
        `${API_URL}/v1/opencode/codebases/${id}/sessions?${params.toString()}`,
      )
      if (res.ok) {
        const data = await res.json()
        const newSessions = data.sessions || []
        setSessions(prev => [...prev, ...newSessions])
        setHasMoreSessions(data.hasMore ?? false)
        sessionsOffset.current = newOffset
      }
    } catch (e) {
      console.error('Failed to load more sessions:', e)
    } finally {
      setLoadingMoreSessions(false)
    }
  }, [loadingMoreSessions, hasMoreSessions])

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
    currentQuery.current = ''
  }, [])

  return {
    sessions,
    sessionMessages,
    loadSessions,
    loadMoreSessions,
    loadSessionMessages,
    loadMoreMessages,
    clearSessions,
    loading,
    loadingMore,
    loadingMoreSessions,
    hasMore,
    hasMoreSessions,
    totalMessages,
    totalSessions,
    error,
  }
}
