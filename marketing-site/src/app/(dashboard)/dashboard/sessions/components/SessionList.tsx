import type { Codebase, Session } from '../types'
import { ChatIcon } from './ChatIcon'
import { SessionItem } from './SessionItem'

interface Props { codebases: Codebase[]; sessions: Session[]; selectedCodebase: string; selectedSession: Session | null; onCodebaseChange: (id: string) => void; onSessionSelect: (s: Session) => void }

export function SessionList({ codebases, sessions, selectedCodebase, selectedSession, onCodebaseChange, onSessionSelect }: Props) {
    const selectedCodebaseName = codebases.find(cb => cb.id === selectedCodebase)?.name || 'all codebases'

    return (
        <nav
            aria-label="Chat sessions"
            className="rounded-lg bg-white shadow-sm dark:bg-gray-800 dark:ring-1 dark:ring-white/10 flex flex-col overflow-hidden flex-1"
        >
            <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between gap-3 shrink-0">
                <h2 id="sessions-heading" className="text-lg font-semibold text-gray-900 dark:text-white">Sessions</h2>
                <div className="flex flex-col">
                    <label htmlFor="codebase-select" className="sr-only">Select codebase</label>
                    <select
                        id="codebase-select"
                        value={selectedCodebase}
                        onChange={(e) => onCodebaseChange(e.target.value)}
                        className="min-w-0 rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                        aria-describedby="codebase-hint"
                    >
                        <option value="">Select codebase...</option>
                        {codebases.map((cb) => <option key={cb.id} value={cb.id}>{cb.name}</option>)}
                    </select>
                    <span id="codebase-hint" className="sr-only">Choose a codebase to filter sessions</span>
                </div>
            </div>
            <div
                role="listbox"
                aria-labelledby="sessions-heading"
                aria-activedescendant={selectedSession?.id ? `session-${selectedSession.id}` : undefined}
                className="divide-y divide-gray-200 dark:divide-gray-700 overflow-y-auto flex-1 min-h-0"
                tabIndex={0}
            >
                {sessions.length === 0 ? (
                    <div className="p-8 text-center text-gray-500" role="status" aria-live="polite">
                        <ChatIcon className="mx-auto h-12 w-12 text-gray-400" aria-hidden="true" />
                        <p className="mt-2 text-sm">{selectedCodebase ? 'No sessions found' : 'Select a codebase'}</p>
                    </div>
                ) : (
                    <>
                        <p className="sr-only" role="status" aria-live="polite">
                            {sessions.length} session{sessions.length !== 1 ? 's' : ''} available in {selectedCodebaseName}
                        </p>
                        {sessions.map((s) => (
                            <SessionItem
                                key={s.id}
                                session={s}
                                isSelected={selectedSession?.id === s.id}
                                onSelect={onSessionSelect}
                            />
                        ))}
                    </>
                )}
            </div>
        </nav>
    )
}
