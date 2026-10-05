import { useState, useCallback, useRef, useEffect } from 'react'
import { Session, SessionMessageWithParts } from '../types'
import {
  listSessionsV1AgentWorkspacesWorkspaceIdSessionsGet,
  getSessionMessagesByIdV1AgentWorkspacesWorkspaceIdSessionsSessionIdMessagesGet,
} from '@/lib/api'

const SESSIONS_PAGE_SIZE = 30

export function useSessions(selectedWorkspace: string) {
  const listRequest = useRef(0)
  const messageRequest = useRef(0)
  const listBusy = useRef(false)
  const messageBusy = useRef(false)
  const [sessionsLoading, setSessionsLoading] = useState(false)
  const [sessionsError, setSessionsError] = useState<string | null>(null)
  const [sessions, setSessions] = useState<Session[]>([])
  const [sessionMessages, setSessionMessages] = useState<
    SessionMessageWithParts[]
  >([])
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
  const sessionsOffset = useRef<number>(0)
  const currentQuery = useRef<string>('')
  const INITIAL_LOAD_LIMIT = 20
  const LOAD_MORE_LIMIT = 20

  useEffect(
    () => () => {
      ++listRequest.current
      ++messageRequest.current
      latestLoadedSessionId.current = null
      listBusy.current = false
      messageBusy.current = false
    },
    [],
  )

  const loadSessions = useCallback(async (id: string, query?: string) => {
    const request = ++listRequest.current
    listBusy.current = true
    setLoadingMoreSessions(false)
    setSessionsError(null)
    if (!id) {
      setSessions([])
      setHasMoreSessions(true)
      setTotalSessions(0)
      sessionsOffset.current = 0
      currentQuery.current = ''
      sessionsOffset.current = 0
      listBusy.current = false
      setSessionsLoading(false)
      return
    }
    if (typeof query === 'string') {
      currentQuery.current = query.trim()
    }
    setSessionsLoading(true)
    setSessions([])
    sessionsOffset.current = 0
    try {
      const result = await listSessionsV1AgentWorkspacesWorkspaceIdSessionsGet({
        path: { workspace_id: id },
        query: {
          limit: SESSIONS_PAGE_SIZE,
          offset: 0,
          ...(currentQuery.current ? { q: currentQuery.current } : {}),
        },
      })

      if (request !== listRequest.current) return
      if (!result.error && result.data) {
        const data = result.data as any
        if (!Array.isArray(data.sessions))
          throw new Error('Invalid sessions response')
        const sessionsList = [...data.sessions]
        sessionsList.sort((a: Session, b: Session) => {
          const dateA = a.time?.updated || a.time?.created || 0
          const dateB = b.time?.updated || b.time?.created || 0
          return dateB - dateA
        })
        setSessions(sessionsList)
        setTotalSessions(data.total ?? sessionsList.length)
        setHasMoreSessions(data.hasMore ?? false)
      } else {
        setSessionsError('Failed to load sessions. Please retry.')
      }
    } catch (e) {
      if (request === listRequest.current)
        setSessionsError('Failed to load sessions. Please retry.')
    } finally {
      if (request === listRequest.current) {
        setSessionsLoading(false)
        listBusy.current = false
      }
    }
  }, [])

  const loadMoreSessions = useCallback(
    async (id: string) => {
      if (!id || listBusy.current || !hasMoreSessions) return
      const request = listRequest.current
      listBusy.current = true
      setSessionsError(null)
      setLoadingMoreSessions(true)
      const newOffset = sessionsOffset.current + SESSIONS_PAGE_SIZE
      try {
        const result =
          await listSessionsV1AgentWorkspacesWorkspaceIdSessionsGet({
            path: { workspace_id: id },
            query: {
              limit: SESSIONS_PAGE_SIZE,
              offset: newOffset,
              ...(currentQuery.current ? { q: currentQuery.current } : {}),
            },
          })

        if (request !== listRequest.current) return
        if (!result.error && result.data) {
          const data = result.data as any
          if (!Array.isArray(data.sessions))
            throw new Error('Invalid sessions response')
          const newSessions = data.sessions
          setSessions((prev) => {
            const ids = new Set(prev.map((session) => session.id))
            return [
              ...prev,
              ...newSessions.filter((session: Session) => !ids.has(session.id)),
            ]
          })
          setHasMoreSessions(data.hasMore ?? false)
          sessionsOffset.current = newOffset
        } else {
          setSessionsError('Failed to load more sessions. Please retry.')
        }
      } catch (e) {
        if (request === listRequest.current)
          setSessionsError('Failed to load more sessions. Please retry.')
      } finally {
        if (request === listRequest.current) {
          setLoadingMoreSessions(false)
          listBusy.current = false
        }
      }
    },
    [hasMoreSessions],
  )

  const loadSessionMessages = useCallback(
    async (
      sessionId: string,
      force?: boolean,
      limit: number = INITIAL_LOAD_LIMIT,
    ) => {
      if (!selectedWorkspace || !sessionId) {
        return
      }
      if (
        !force &&
        latestLoadedSessionId.current === `${selectedWorkspace}:${sessionId}`
      ) {
        return
      }
      const request = ++messageRequest.current
      messageBusy.current = true
      const requestedSessionId = `${selectedWorkspace}:${sessionId}`
      latestLoadedSessionId.current = requestedSessionId
      setTotalMessages(0)
      currentLimit.current = limit
      setLoading(true)
      setLoadingMore(false)
      setHasMore(true)
      setError(null)
      setSessionMessages([])
      try {
        const result =
          await getSessionMessagesByIdV1AgentWorkspacesWorkspaceIdSessionsSessionIdMessagesGet(
            {
              path: { workspace_id: selectedWorkspace, session_id: sessionId },
              query: { limit },
            },
          )

        if (request !== messageRequest.current) {
          return
        }

        if (!result.error && result.data) {
          const data = result.data as any
          if (!Array.isArray(data.messages))
            throw new Error('Invalid messages response')
          setSessionMessages(data.messages)
          setTotalMessages(data.total ?? data.messages?.length ?? 0)
          setHasMore(data.hasMore ?? false)
        } else {
          latestLoadedSessionId.current = null
          setError('Failed to load messages')
        }
      } catch (e) {
        if (request === messageRequest.current) {
          latestLoadedSessionId.current = null
          setError('Failed to load messages')
        }
      } finally {
        if (request === messageRequest.current) {
          messageBusy.current = false
          setLoading(false)
        }
      }
    },
    [selectedWorkspace],
  )

  const loadMoreMessages = useCallback(async () => {
    if (
      !selectedWorkspace ||
      !latestLoadedSessionId.current ||
      !latestLoadedSessionId.current.startsWith(`${selectedWorkspace}:`) ||
      messageBusy.current ||
      !hasMore
    ) {
      return
    }

    const sessionId = latestLoadedSessionId.current.slice(
      selectedWorkspace.length + 1,
    )
    const request = messageRequest.current
    const nextLimit =
      (currentLimit.current ?? INITIAL_LOAD_LIMIT) + LOAD_MORE_LIMIT
    messageBusy.current = true
    setLoadingMore(true)
    setError(null)
    try {
      const result =
        await getSessionMessagesByIdV1AgentWorkspacesWorkspaceIdSessionsSessionIdMessagesGet(
          {
            path: { workspace_id: selectedWorkspace, session_id: sessionId },
            // This endpoint supports a limit, not an offset: expand the window.
            query: { limit: nextLimit },
          },
        )

      if (request !== messageRequest.current) return
      if (!result.error && result.data) {
        const data = result.data as any
        if (!Array.isArray(data.messages))
          throw new Error('Invalid messages response')
        const messages = data.messages
        setSessionMessages(messages)
        currentLimit.current = nextLimit
        setTotalMessages(data.total ?? messages.length)
        setHasMore(data.hasMore ?? false)
      } else {
        setError('Failed to load older messages. Please retry.')
      }
    } catch (e) {
      if (request === messageRequest.current)
        setError('Failed to load older messages. Please retry.')
    } finally {
      if (request === messageRequest.current) {
        messageBusy.current = false
        setLoadingMore(false)
      }
    }
  }, [selectedWorkspace, hasMore])

  const clearSessions = useCallback(() => {
    ++listRequest.current
    ++messageRequest.current
    listBusy.current = false
    messageBusy.current = false
    setSessionsLoading(false)
    setSessionsError(null)
    setLoadingMoreSessions(false)
    setHasMoreSessions(false)
    setTotalSessions(0)
    setSessions([])
    setSessionMessages([])
    setLoading(false)
    setLoadingMore(false)
    setHasMore(true)
    setTotalMessages(0)
    setError(null)
    latestLoadedSessionId.current = null
    currentLimit.current = null
    currentQuery.current = ''
  }, [])

  return {
    sessionsLoading,
    sessionsError,
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
