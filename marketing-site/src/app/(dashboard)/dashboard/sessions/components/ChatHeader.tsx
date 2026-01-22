'use client'

import { useState } from 'react'
import type { Session } from '../types'
import { formatDate } from '../utils'
import { StreamStatus } from './StreamStatus'
import { ModeSelector } from './ModeSelector'
import { ModelSelector } from './ModelSelector'
import { SessionActions } from './SessionActions'

interface Props {
    selectedSession: Session | null
    selectedCodebase?: string
    selectedCodebaseName?: string
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

/**
 * ChatHeader component displays the header for a chat session.
 * Shows session title, ID, codebase info, message count, and update timestamp.
 * Provides controls for mode/model selection, session actions, RLM inspector toggle,
 * and mobile-friendly controls dialog.
 */
export function ChatHeader(p: Props) {
    const [mobileControlsOpen, setMobileControlsOpen] = useState(false)
    const [settingsOpen, setSettingsOpen] = useState(false)
    const sessionTitle = p.selectedSession ? p.selectedSession.title : 'Chat'
    const sessionTimestamp = p.selectedSession?.time?.updated ?? p.selectedSession?.time?.created
    const sessionUpdated = sessionTimestamp ? new Date(sessionTimestamp).toISOString() : ''
    const updatedLabel = sessionUpdated ? formatDate(sessionUpdated) : ''
    const sessionId = p.selectedSession?.id
    const sessionIdShort = sessionId ? sessionId.slice(0, 8) : ''
    const codebaseLabel = p.selectedCodebaseName || (p.selectedCodebase ? 'Unnamed codebase' : 'No codebase')
    const hasSession = !!p.selectedSession

    return (
        <header
            className="shrink-0 border-b border-gray-200 bg-white/80 p-1 backdrop-blur dark:border-gray-700 dark:bg-gray-800/80 sm:p-4"
            aria-label="Chat session header"
        >
            <div className="grid gap-1.5 sm:gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-start">
                <div className="min-w-0">
                    <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                            <div className="flex items-center gap-2">
                                {p.showBackButton && p.onBackToSessions && (
                                    <button
                                        type="button"
                                        onClick={p.onBackToSessions}
                                        className="inline-flex items-center justify-center rounded-full border border-gray-200 p-1 text-gray-600 transition-colors hover:bg-gray-50 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-700 md:hidden"
                                        aria-label="Back to sessions"
                                    >
                                        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                                        </svg>
                                    </button>
                                )}
                                <h2 id="chat-title" className="text-sm font-semibold text-gray-900 dark:text-white truncate sm:text-base">
                                    {sessionTitle}
                                </h2>
                                {hasSession && sessionIdShort && (
                                    <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-mono text-gray-600 dark:bg-gray-700 dark:text-gray-300">
                                        #{sessionIdShort}
                                    </span>
                                )}
                            </div>
                            <div className="mt-1 hidden flex-wrap items-center gap-2 text-xs text-gray-500 dark:text-gray-400 sm:flex">
                                <span className="inline-flex items-center gap-1">
                                    <span className="text-gray-400">Codebase</span>
                                    <span className="font-medium text-gray-700 dark:text-gray-200">{codebaseLabel}</span>
                                </span>
                                {hasSession && (
                                    <>
                                        <span className="h-1 w-1 rounded-full bg-gray-300 dark:bg-gray-600" aria-hidden="true" />
                                        <span>
                                            {p.chatItemsCount} message{p.chatItemsCount !== 1 ? 's' : ''}
                                        </span>
                                    </>
                                )}
                                {updatedLabel && (
                                    <>
                                        <span className="h-1 w-1 rounded-full bg-gray-300 dark:bg-gray-600" aria-hidden="true" />
                                        <span>
                                            Updated {updatedLabel}
                                        </span>
                                    </>
                                )}
                                {!hasSession && <span>Select a session to start.</span>}
                            </div>
                        </div>
                        <div className="flex items-center gap-1 md:hidden">
                            {/* Mobile Resume button removed - sending a message resumes the session implicitly */}
                            <button
                                type="button"
                                onClick={() => setMobileControlsOpen((prev) => !prev)}
                                aria-expanded={mobileControlsOpen}
                                aria-controls="chat-mobile-controls"
                                className={`inline-flex items-center justify-center rounded-full border p-1 text-gray-600 transition-colors ${
                                    mobileControlsOpen
                                        ? 'border-indigo-500 bg-indigo-50 text-indigo-700 dark:border-indigo-400 dark:bg-indigo-500/20 dark:text-indigo-200'
                                        : 'border-gray-200 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-700'
                                }`}
                                aria-label={mobileControlsOpen ? 'Close controls' : 'Open controls'}
                            >
                                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6h9M12 12h9M12 18h9M3 6h3m-3 6h3m-3 6h3" />
                                </svg>
                            </button>
                        </div>
                    </div>
                </div>
                <div
                    className="hidden flex-wrap items-center gap-2 md:flex md:justify-end"
                    role="toolbar"
                    aria-label="Chat controls"
                >
                    <StreamStatus connected={p.streamConnected} status={p.streamStatus} />
                    <button
                        type="button"
                        onClick={() => setSettingsOpen((prev) => !prev)}
                        aria-expanded={settingsOpen}
                        aria-controls="chat-settings-panel"
                        className={`hidden items-center gap-1 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors md:inline-flex ${
                            settingsOpen
                                ? 'border-indigo-500 bg-indigo-50 text-indigo-700 dark:border-indigo-400 dark:bg-indigo-500/20 dark:text-indigo-200'
                                : 'border-gray-200 text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-700'
                        }`}
                    >
                        Settings
                        <svg
                            className={`h-3.5 w-3.5 transition-transform ${settingsOpen ? 'rotate-180' : ''}`}
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                        >
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                        </svg>
                    </button>
                    {p.selectedSession && p.onToggleRLMPane && (
                        <button
                            onClick={p.onToggleRLMPane}
                            className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                                p.showRLMPane
                                    ? 'bg-cyan-600 text-white'
                                    : 'bg-cyan-100 text-cyan-700 hover:bg-cyan-200 dark:bg-cyan-900/30 dark:text-cyan-300 dark:hover:bg-cyan-900/50'
                            }`}
                            aria-pressed={p.showRLMPane}
                            aria-label="Toggle RLM execution view"
                            title="View RLM execution"
                        >
                            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                            </svg>
                            RLM Inspector
                        </button>
                    )}
                    {p.selectedSession && (
                        <SessionActions
                            loading={p.loading}
                            awaitingResponse={p.awaitingResponse}
                            onResume={p.onResume}
                            onRefresh={p.onRefresh}
                            sessionTitle={sessionTitle}
                            sessionId={p.selectedSession.id}
                            codebaseId={p.selectedCodebase}
                        />
                    )}
                </div>
                <div
                    id="chat-settings-panel"
                    className={`hidden flex-wrap items-center gap-3 md:col-span-2 ${settingsOpen ? 'md:flex' : 'md:hidden'}`}
                >
                    <ModeSelector value={p.selectedMode} onChange={p.onModeChange} />
                    <ModelSelector value={p.selectedModel} suggestions={p.suggestedModels} onChange={p.onModelChange} />
                </div>
            </div>

            {mobileControlsOpen && (
                <div
                    id="chat-mobile-controls"
                    className="fixed inset-0 z-50 md:hidden"
                    role="dialog"
                    aria-modal="true"
                    aria-label="Chat controls"
                >
                    <div
                        className="absolute inset-0 bg-gray-900/60"
                        onClick={() => setMobileControlsOpen(false)}
                        aria-hidden="true"
                    />
                    <div className="absolute inset-x-0 bottom-0 max-h-[75vh] overflow-y-auto rounded-t-2xl bg-white p-4 shadow-2xl dark:bg-gray-900">
                        <div className="flex items-center justify-between gap-2">
                            <div>
                                <p className="text-xs uppercase tracking-wide text-gray-400">Session controls</p>
                                <p className="text-sm font-semibold text-gray-900 dark:text-white truncate">
                                    {sessionTitle}
                                </p>
                            </div>
                            <button
                                type="button"
                                onClick={() => setMobileControlsOpen(false)}
                                className="inline-flex items-center justify-center rounded-full border border-gray-200 p-1.5 text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800"
                                aria-label="Close controls"
                            >
                                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>

                        <div className="mt-4 space-y-4">
                            {p.selectedSession && p.onToggleRLMPane && (
                                <button
                                    onClick={() => {
                                        p.onToggleRLMPane?.()
                                        setMobileControlsOpen(false)
                                    }}
                                    className={`inline-flex w-full items-center justify-center gap-2 rounded-full px-3 py-2 text-sm font-medium transition-colors ${
                                        p.showRLMPane
                                            ? 'bg-cyan-600 text-white'
                                            : 'bg-cyan-100 text-cyan-700 hover:bg-cyan-200 dark:bg-cyan-900/30 dark:text-cyan-300 dark:hover:bg-cyan-900/50'
                                    }`}
                                    aria-pressed={p.showRLMPane}
                                    aria-label="Toggle RLM execution view"
                                >
                                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                    </svg>
                                    {p.showRLMPane ? 'Hide RLM Inspector' : 'Show RLM Inspector'}
                                </button>
                            )}

                            {p.selectedSession && (
                                <SessionActions
                                    loading={p.loading}
                                    awaitingResponse={p.awaitingResponse}
                                    onResume={p.onResume}
                                    onRefresh={p.onRefresh}
                                    sessionTitle={sessionTitle}
                                    sessionId={p.selectedSession.id}
                                    codebaseId={p.selectedCodebase}
                                />
                            )}

                            <ModeSelector value={p.selectedMode} onChange={p.onModeChange} />
                            <ModelSelector value={p.selectedModel} suggestions={p.suggestedModels} onChange={p.onModelChange} />
                        </div>
                    </div>
                </div>
            )}
        </header>
    )
}
