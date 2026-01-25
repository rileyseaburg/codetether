import { useState } from 'react'
import { useAIPRDSessions, type PRDChatMessage } from './useAIPRDSessions'
import { useRalphStore } from './store'

const ChatIcon = (props: any) => (
  <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
  </svg>
)

const ArrowIcon = (props: any) => (
  <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
  </svg>
)

interface PRDChatHistoryProps {
  onContinueSession: (sessionId: string, sessionTitle: string, messages: PRDChatMessage[]) => void
}

export function PRDChatHistory({ onContinueSession }: PRDChatHistoryProps) {
  const { selectedCodebase } = useRalphStore()
  const { sessions, loading, error, loadSessionMessages } = useAIPRDSessions(selectedCodebase || undefined)
  const [loadingSessionId, setLoadingSessionId] = useState<string | null>(null)

  // Don't show anything if no codebase selected
  if (!selectedCodebase || selectedCodebase === 'global') {
    return null
  }

  // Loading state
  if (loading) {
    return (
      <div className="rounded-lg bg-white shadow-sm dark:bg-gray-800 dark:ring-1 dark:ring-white/10 p-4">
        <div className="flex items-center gap-3">
          <div className="animate-spin rounded-full h-5 w-5 border-2 border-purple-500 border-t-transparent" />
          <span className="text-sm text-gray-600 dark:text-gray-400">Loading your conversations...</span>
        </div>
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <div className="rounded-lg bg-red-50 dark:bg-red-900/20 p-4">
        <p className="text-sm text-red-600 dark:text-red-400">Could not load previous conversations. Please try again.</p>
      </div>
    )
  }

  // Empty state - no previous conversations
  if (sessions.length === 0) {
    return null // Don't show empty state, just hide the section
  }

  const formatTime = (timestamp: string | number) => {
    const date = new Date(typeof timestamp === 'string' ? timestamp : timestamp)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMins / 60)
    const diffDays = Math.floor(diffHours / 24)

    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins} min ago`
    if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`
    if (diffDays === 1) return 'Yesterday'
    if (diffDays < 7) return `${diffDays} days ago`
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }

  // Clean up title - remove "PRD Chat: " prefix if present
  const cleanTitle = (title: string) => {
    return title.replace(/^PRD Chat:\s*/i, '').trim() || 'Untitled conversation'
  }

  const handleResume = async (session: typeof sessions[0]) => {
    setLoadingSessionId(session.id)
    try {
      const messages = await loadSessionMessages(session.sessionId)
      onContinueSession(session.sessionId, session.title || 'Chat', messages)
    } finally {
      setLoadingSessionId(null)
    }
  }

  return (
    <div className="rounded-lg bg-white shadow-sm dark:bg-gray-800 dark:ring-1 dark:ring-white/10">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-white flex items-center gap-2">
          <ChatIcon className="w-4 h-4 text-purple-500" />
          Recent Conversations
        </h3>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
          Pick up where you left off
        </p>
      </div>

      {/* Session list */}
      <div className="divide-y divide-gray-100 dark:divide-gray-700">
        {sessions.slice(0, 5).map((session) => {
          const isLoading = loadingSessionId === session.id
          
          return (
            <button
              key={session.id}
              onClick={() => handleResume(session)}
              disabled={isLoading}
              className="w-full px-4 py-3 flex items-center gap-3 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors text-left disabled:opacity-60"
            >
              {/* Icon */}
              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center">
                {isLoading ? (
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-purple-500 border-t-transparent" />
                ) : (
                  <ChatIcon className="w-4 h-4 text-purple-600 dark:text-purple-400" />
                )}
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                  {cleanTitle(session.title || '')}
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                  {formatTime(session.lastUpdated)}
                  {(session.messageCount ?? 0) > 0 && (
                    <span> · {session.messageCount} message{session.messageCount !== 1 ? 's' : ''}</span>
                  )}
                </div>
              </div>

              {/* Arrow */}
              <ArrowIcon className="w-4 h-4 text-gray-400 flex-shrink-0" />
            </button>
          )
        })}
      </div>

      {/* Show more link if there are more than 5 */}
      {sessions.length > 5 && (
        <div className="px-4 py-2 border-t border-gray-100 dark:border-gray-700">
          <p className="text-xs text-gray-500 dark:text-gray-400 text-center">
            +{sessions.length - 5} more conversation{sessions.length - 5 !== 1 ? 's' : ''}
          </p>
        </div>
      )}
    </div>
  )
}
