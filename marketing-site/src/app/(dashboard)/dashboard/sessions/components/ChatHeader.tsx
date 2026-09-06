'use client'

import type { Session } from '../types'
import { formatDate } from '../utils'
import { StreamStatus } from './StreamStatus'
import { ModeSelector } from './ModeSelector'
import { ModelSelector } from '@/components/ModelSelector'
import { SessionActions } from './SessionActions'
import VoiceChatButton from '../../components/voice/VoiceChatButton'

interface Props {
  selectedSession: Session | null
  selectedWorkspace?: string
  selectedWorkspaceName?: string
  selectedMode: string
  selectedModel: string
  suggestedModels: string[]
  streamConnected: boolean
  streamStatus: string
  loading: boolean
  awaitingResponse?: boolean
  chatItemsCount: number
  showBackButton?: boolean
  onBackToSessions?: () => void
  onModeChange: (mode: string) => void
  onModelChange: (model: string) => void
  onResume: () => void
  onRefresh: () => void
  showRLMPane?: boolean
  onToggleRLMPane?: () => void
}

/** Keep the conversation primary; operational controls live in one disclosure. */
export function ChatHeader(p: Props) {
  const title = p.selectedSession?.title || 'Untitled session'
  const timestamp =
    p.selectedSession?.time?.updated ?? p.selectedSession?.time?.created
  const date = timestamp ? new Date(timestamp) : null
  const updated =
    date && Number.isFinite(date.getTime())
      ? formatDate(date.toISOString())
      : 'Unknown'

  return (
    <header
      className="shrink-0 border-b border-gray-200 bg-white px-4 py-4 sm:px-6 dark:border-gray-800 dark:bg-gray-900"
      aria-label="Chat session header"
    >
      <div className="flex min-w-0 items-center gap-3">
        {p.showBackButton && p.onBackToSessions && (
          <button
            type="button"
            onClick={p.onBackToSessions}
            aria-label="Back to sessions"
            className="inline-flex min-h-11 shrink-0 items-center gap-1 rounded-lg px-2 text-sm font-medium text-gray-600 hover:bg-gray-100 focus-visible:ring-2 focus-visible:ring-cyan-600 md:hidden dark:text-gray-300 dark:hover:bg-gray-800"
          >
            <span aria-hidden="true">←</span> Sessions
          </button>
        )}
        <div className="min-w-0 flex-1">
          <h2
            id="chat-title"
            className="truncate text-base font-semibold text-gray-950 sm:text-lg dark:text-white"
            title={title}
          >
            {p.selectedSession ? title : 'Conversation'}
          </h2>
          <p
            className="mt-1 truncate text-sm text-gray-500 dark:text-gray-400"
            role={p.awaitingResponse ? 'status' : undefined}
          >
            {p.awaitingResponse
              ? 'The agent is responding…'
              : p.selectedWorkspaceName || 'Your conversation with the agent'}
          </p>
        </div>
      </div>
      {p.selectedSession && (
        <details className="group mt-3">
          <summary className="w-fit cursor-pointer rounded-md py-1 text-xs font-medium text-gray-500 hover:text-gray-900 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-cyan-600 dark:text-gray-400 dark:hover:text-white">
            Conversation settings & actions
          </summary>
          <div
            className="mt-3 max-h-[min(50dvh,24rem)] space-y-5 overflow-y-auto rounded-xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-800"
            aria-label="Conversation settings"
          >
            <div className="grid min-w-0 gap-4 sm:grid-cols-[minmax(0,1fr)_auto]">
              <ModelSelector
                visualVariant="default"
                label="Model"
                selectedModel={p.selectedModel}
                onSelectedModelChange={p.onModelChange}
                showSelectedInfo={false}
                disabled={p.loading}
              />
              <div className="min-w-0 self-end">
                <ModeSelector
                  value={p.selectedMode}
                  onChange={p.onModeChange}
                />
              </div>
            </div>
            <div
              className="flex flex-wrap items-center gap-3"
              aria-label="Session actions"
            >
              <SessionActions
                loading={p.loading}
                awaitingResponse={p.awaitingResponse}
                onResume={p.onResume}
                onRefresh={p.onRefresh}
                sessionTitle={title}
                sessionId={p.selectedSession.id}
                codebaseId={p.selectedWorkspace}
              />
              <VoiceChatButton
                codebaseId={p.selectedWorkspace}
                sessionId={p.selectedSession.id}
                mode="chat"
                compact
              />
              {p.onToggleRLMPane && (
                <button
                  type="button"
                  onClick={p.onToggleRLMPane}
                  aria-pressed={p.showRLMPane}
                  aria-label="Toggle RLM execution view"
                  className="min-h-10 rounded-lg border border-gray-300 px-3 py-2 text-xs font-medium text-gray-700 hover:bg-white focus-visible:ring-2 focus-visible:ring-cyan-600 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-700"
                >
                  {p.showRLMPane
                    ? 'Hide execution details'
                    : 'Show execution details'}
                </button>
              )}
            </div>
            <details className="border-t border-gray-200 pt-3 dark:border-gray-700">
              <summary className="w-fit cursor-pointer text-xs text-gray-500 focus-visible:outline-2 focus-visible:outline-cyan-600 dark:text-gray-400">
                Session information
              </summary>
              <dl className="mt-3 grid gap-2 text-xs text-gray-600 sm:grid-cols-2 dark:text-gray-300">
                <div>
                  <dt className="text-gray-500">Messages</dt>
                  <dd>{p.chatItemsCount}</dd>
                </div>
                <div>
                  <dt className="text-gray-500">Updated</dt>
                  <dd>{updated}</dd>
                </div>
                <div className="min-w-0 sm:col-span-2">
                  <dt className="text-gray-500">Session ID</dt>
                  <dd className="font-mono break-all">
                    {p.selectedSession.id}
                  </dd>
                </div>
                <div className="sm:col-span-2">
                  <dt className="sr-only">Connection</dt>
                  <dd>
                    <StreamStatus
                      connected={p.streamConnected}
                      status={p.streamStatus}
                    />
                  </dd>
                </div>
              </dl>
            </details>
          </div>
        </details>
      )}
    </header>
  )
}