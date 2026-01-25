'use client'

import { useState, useMemo, useId, memo } from 'react'
import type { ChatItem } from '../types'
import { formatCost, formatTokens } from '../utils'
import { parseJsonPayload } from './JsonHelpers'
import { MarkdownMessage } from './MarkdownMessage'
import { ToolDetails } from './ToolDetails'

interface Props { message: ChatItem; isUser: boolean; isNew?: boolean }

// Thresholds for truncation
const TRUNCATE_CHARS = 1500
const TRUNCATE_LINES = 40

function MessageBubbleInner({ message: m, isUser, isNew = false }: Props) {
    const [isExpanded, setIsExpanded] = useState(false)
    const tokenInfo = formatTokens(m.usage?.tokens)
    const costText = formatCost(m.usage?.cost)
    const bubbleClass = isUser ? 'bg-cyan-600 text-white ring-cyan-700/40' : 'bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 ring-gray-200 dark:ring-white/10'
    const highlightClass = isNew ? 'ring-2 ring-cyan-400/30 shadow-[0_0_0_1px_rgba(34,211,238,0.2)]' : ''

    // Calculate if message should be truncated
    const { shouldTruncate, truncatedText, stats } = useMemo(() => {
        if (!m.text || isUser) return { shouldTruncate: false, truncatedText: m.text || '', stats: null }

        const hasStructuredPayload = !!parseJsonPayload(m.text)
        if (hasStructuredPayload) {
            return { shouldTruncate: false, truncatedText: m.text, stats: null }
        }
        
        const text = m.text
        const lines = text.split('\n')
        const charCount = text.length
        const lineCount = lines.length
        
        const needsTruncation = charCount > TRUNCATE_CHARS || lineCount > TRUNCATE_LINES
        
        if (!needsTruncation) {
            return { shouldTruncate: false, truncatedText: text, stats: null }
        }

        // Find a good truncation point (end of a line or sentence)
        let truncateAt = TRUNCATE_CHARS
        const lineEndIndex = text.lastIndexOf('\n', TRUNCATE_CHARS)
        const sentenceEnd = Math.max(
            text.lastIndexOf('. ', TRUNCATE_CHARS),
            text.lastIndexOf('.\n', TRUNCATE_CHARS)
        )
        
        if (lineEndIndex > TRUNCATE_CHARS * 0.7) {
            truncateAt = lineEndIndex
        } else if (sentenceEnd > TRUNCATE_CHARS * 0.7) {
            truncateAt = sentenceEnd + 1
        }

        return {
            shouldTruncate: true,
            truncatedText: text.slice(0, truncateAt),
            stats: {
                chars: charCount,
                lines: lineCount,
                hiddenChars: charCount - truncateAt,
                hiddenLines: lineCount - text.slice(0, truncateAt).split('\n').length
            }
        }
    }, [m.text, isUser])

    const displayText = shouldTruncate && !isExpanded ? truncatedText : m.text

    // Count tools and reasoning for summary
    const hasReasoning = !!m.reasoning
    const toolCount = m.tools?.length || 0
    const hasExtras = hasReasoning || toolCount > 0

    return (
        <div className={`rounded-2xl shadow-sm ring-1 ${bubbleClass} ${highlightClass} overflow-hidden`}>
            {/* Summary bar for complex messages */}
            {!isUser && hasExtras && (
                <div className="px-4 py-2 bg-gray-50 dark:bg-gray-900/50 border-b border-gray-100 dark:border-gray-700/50 flex items-center gap-3 text-xs text-gray-500 dark:text-gray-400">
                    {hasReasoning && (
                        <span className="flex items-center gap-1">
                            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                            </svg>
                            Thinking
                        </span>
                    )}
                    {toolCount > 0 && (
                        <span className="flex items-center gap-1">
                            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                            </svg>
                            {toolCount} tool{toolCount !== 1 ? 's' : ''}
                        </span>
                    )}
                    {stats && (
                        <span className="ml-auto">
                            {stats.lines} lines
                        </span>
                    )}
                </div>
            )}

            <div className="px-4 py-3">
                {/* Main text content */}
                {m.text ? (
                    <div aria-label="Message content">
                        <MarkdownMessage text={displayText || ''} />
                        
                        {/* Truncation controls */}
                        {shouldTruncate && (
                            <div className="mt-3 flex items-center gap-2">
                                {!isExpanded && (
                                    <div className="flex-1 h-px bg-gradient-to-r from-gray-200 dark:from-gray-700 to-transparent" />
                                )}
                                 <button
                                    onClick={() => setIsExpanded(!isExpanded)}
                                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-cyan-600 dark:text-cyan-400 hover:text-cyan-700 dark:hover:text-cyan-300 bg-cyan-50 dark:bg-cyan-900/30 rounded-full transition-colors"
                                    aria-expanded={isExpanded}
                                    aria-label={isExpanded ? 'Show less content' : `Show ${stats?.hiddenLines || 'more'} more lines`}
                                >
                                    {isExpanded ? (
                                        <>
                                            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                                            </svg>
                                            Show less
                                        </>
                                    ) : (
                                        <>
                                            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                            </svg>
                                            Show {stats?.hiddenLines || 'more'} more lines
                                        </>
                                    )}
                                </button>
                                {!isExpanded && (
                                    <div className="flex-1 h-px bg-gradient-to-l from-gray-200 dark:from-gray-700 to-transparent" />
                                )}
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="text-sm opacity-70" aria-label="Empty message">
                        {isUser ? '(empty)' : '(no content)'}
                    </div>
                )}

                {/* Reasoning section - collapsed by default */}
                {m.reasoning && <Reasoning text={m.reasoning} isUser={isUser} />}
                
                {/* Tools section - collapsed by default */}
                {m.tools?.length ? <ToolDetails tools={m.tools} isUser={isUser} /> : null}
                
                {/* Usage stats */}
                {(tokenInfo || costText) && <Usage tokenInfo={tokenInfo} costText={costText} isUser={isUser} />}
                

            </div>
        </div>
    )
}

    const Reasoning = ({ text, isUser }: { text: string; isUser: boolean }) => {
    const [isOpen, setIsOpen] = useState(false)
    const id = useId()
    
    const lines = text.split('\n').length
    const preview = text.slice(0, 100).replace(/\n/g, ' ')

    return (
        <details
            className={`mt-3 rounded-lg ${isUser ? 'bg-cyan-500/20' : 'bg-amber-50 dark:bg-amber-900/20 ring-1 ring-amber-200/50 dark:ring-amber-700/30'}`}
            onToggle={(e) => setIsOpen((e.target as HTMLDetailsElement).open)}
        >
            <summary
                className="cursor-pointer select-none p-3 text-xs font-medium text-amber-800 dark:text-amber-200 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2 rounded-lg flex items-center justify-between gap-2"
                aria-expanded={isOpen}
                aria-controls={id}
            >
                <div className="flex items-center gap-2">
                    <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                    <span>Thinking Process</span>
                    <span className="text-amber-600/70 dark:text-amber-300/70 font-normal">
                        ({lines} lines)
                    </span>
                </div>
                <svg 
                    className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} 
                    fill="none" 
                    stroke="currentColor" 
                    viewBox="0 0 24 24"
                >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
            </summary>
            {!isOpen && (
                <p className="px-3 pb-3 text-xs text-amber-700/70 dark:text-amber-300/50 truncate">
                    {preview}...
                </p>
            )}
            <div id={id} className={`${isOpen ? 'p-3 pt-0' : 'hidden'}`}>
                <div className="max-h-96 overflow-y-auto rounded-lg bg-white/50 dark:bg-gray-900/50 p-3">
                    <MarkdownMessage text={text} />
                </div>
            </div>
        </details>
    )
}

 const Usage = ({ tokenInfo, costText, isUser }: { tokenInfo: { summary: string; detail?: string } | null; costText: string; isUser: boolean }) => (
    <div
        className={`mt-3 flex flex-wrap gap-x-3 text-[11px] ${isUser ? 'text-cyan-100/90' : 'text-gray-500 dark:text-gray-400'}`}
        aria-label="Token usage and cost information"
    >
        {tokenInfo && (
            <span title={tokenInfo.detail} aria-label={tokenInfo.detail || tokenInfo.summary}>
                <span className="sr-only">Tokens: </span>
                {tokenInfo.summary}
            </span>
        )}
        {costText && (
            <span>
                <span className="sr-only">Estimated </span>
                Cost {costText}
            </span>
        )}
    </div>
)

// Memoize MessageBubble - only re-render when message content changes
export const MessageBubble = memo(MessageBubbleInner, (prev, next) => {
    return (
        prev.message.key === next.message.key &&
        prev.message.text === next.message.text &&
        prev.isUser === next.isUser &&
        prev.isNew === next.isNew
    )
})
MessageBubble.displayName = 'MessageBubble'
