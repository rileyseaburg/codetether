import type { Session } from '../types'
import { formatDate } from '../utils'

interface SessionItemProps {
    session: Session
    isSelected: boolean
    onSelect: (session: Session) => void
}

export function SessionItem({ session, isSelected, onSelect }: SessionItemProps) {
    const sessionTitle = session.title || 'Untitled Session'
    const summaryFiles = session.summary?.files
    const sessionTimestamp = session.time?.updated ?? session.time?.created
    const dateText = sessionTimestamp ? formatDate(new Date(sessionTimestamp).toISOString()) : ''
    const descriptionId = `session-desc-${session.id}`

    return (
        <button
            id={`session-${session.id}`}
            type="button"
            role="option"
            aria-selected={isSelected}
            aria-describedby={descriptionId}
            className={`group w-full text-left p-3 transition-colors focus:outline-none focus:ring-2 focus:ring-inset focus:ring-indigo-500 sm:p-4 ${isSelected ? 'bg-indigo-50 dark:bg-indigo-900/20' : 'hover:bg-gray-50 dark:hover:bg-gray-700/50'}`}
            onClick={() => onSelect(session)}
        >
            <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                    <div className="flex items-start justify-between gap-2">
                        <p className="truncate text-sm font-semibold text-gray-900 dark:text-white">
                            {sessionTitle}
                        </p>
                        {dateText && (
                            <time
                                dateTime={sessionTimestamp ? new Date(sessionTimestamp).toISOString() : ''}
                                className="shrink-0 text-[10px] text-gray-400 dark:text-gray-500"
                            >
                                {dateText}
                            </time>
                        )}
                    </div>
                    <div id={descriptionId} className="mt-2 flex flex-wrap items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
                        {typeof summaryFiles === 'number' && (
                            <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-600 dark:bg-gray-700 dark:text-gray-300">
                                {summaryFiles} file{summaryFiles !== 1 ? 's' : ''}
                            </span>
                        )}
                    </div>
                </div>
                <span className="mt-1 shrink-0 text-gray-300 transition-colors group-hover:text-gray-400 dark:text-gray-600 dark:group-hover:text-gray-400" aria-hidden="true">
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                </span>
            </div>
        </button>
    )
}
