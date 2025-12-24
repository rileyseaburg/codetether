import type { Session } from '../types'
import { formatDate } from '../utils'

interface SessionItemProps {
    session: Session
    isSelected: boolean
    onSelect: (session: Session) => void
}

export function SessionItem({ session, isSelected, onSelect }: SessionItemProps) {
    const sessionTitle = session.title || 'Untitled Session'
    const agentName = session.agent || 'build'
    const messageCount = session.messageCount || 0
    const dateText = formatDate(session.updated || session.created || '')
    const descriptionId = `session-desc-${session.id}`

    return (
        <button
            id={`session-${session.id}`}
            type="button"
            role="option"
            aria-selected={isSelected}
            aria-describedby={descriptionId}
            className={`w-full text-left p-3 sm:p-4 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors focus:outline-none focus:ring-2 focus:ring-inset focus:ring-indigo-500 ${isSelected ? 'bg-indigo-50 dark:bg-indigo-900/20' : ''}`}
            onClick={() => onSelect(session)}
        >
            <div className="flex items-start justify-between gap-2 sm:gap-3">
                <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                        {sessionTitle}
                    </p>
                    <p id={descriptionId} className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 sm:mt-1">
                        <span className="sr-only">Agent: </span>{agentName}
                        <span aria-hidden="true"> * </span>
                        <span className="sr-only">, </span>
                        {messageCount} message{messageCount !== 1 ? 's' : ''}
                    </p>
                    <p className="text-xs text-gray-400 dark:text-gray-500">
                        <span className="sr-only">Last updated: </span>
                        <time dateTime={session.updated || session.created || ''}>{dateText}</time>
                    </p>
                </div>
                <span className="text-xs text-gray-400 dark:text-gray-500 shrink-0" aria-hidden="true">{'>'}</span>
            </div>
        </button>
    )
}
