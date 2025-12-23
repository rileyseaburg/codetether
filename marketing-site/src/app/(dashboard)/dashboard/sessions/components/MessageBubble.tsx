'use client'

import { useState } from 'react'
import type { ChatItem } from '../types'
import { formatCost, formatTokens } from '../utils'
import { MarkdownMessage } from './MarkdownMessage'
import { ToolDetails } from './ToolDetails'

interface Props { message: ChatItem; isUser: boolean }

export function MessageBubble({ message: m, isUser }: Props) {
    const tokenInfo = formatTokens(m.usage?.tokens)
    const costText = formatCost(m.usage?.cost)
    const bubbleClass = isUser ? 'bg-indigo-600 text-white ring-indigo-700/40' : 'bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 ring-gray-200 dark:ring-white/10'

    return (
        <div className={`rounded-2xl px-4 py-3 shadow-sm ring-1 ${bubbleClass}`}>
            {m.text ? (
                <div aria-label="Message content">
                    <MarkdownMessage text={m.text} />
                </div>
            ) : (
                <div className="text-sm opacity-70" aria-label="Empty message">
                    {isUser ? '(empty)' : '(no content)'}
                </div>
            )}
            {m.reasoning && <Reasoning text={m.reasoning} isUser={isUser} />}
            {m.tools?.length ? <ToolDetails tools={m.tools} isUser={isUser} /> : null}
            {(tokenInfo || costText) && <Usage tokenInfo={tokenInfo} costText={costText} isUser={isUser} />}
            {m.rawDetails && <Details text={m.rawDetails} isUser={isUser} />}
        </div>
    )
}

const Reasoning = ({ text, isUser }: { text: string; isUser: boolean }) => {
    const [isOpen, setIsOpen] = useState(false)
    const id = `reasoning-${Math.random().toString(36).substr(2, 9)}`

    return (
        <details
            className={`mt-3 rounded-lg p-3 ${isUser ? 'bg-indigo-500/20' : 'bg-gray-100 dark:bg-gray-900/30'}`}
            onToggle={(e) => setIsOpen((e.target as HTMLDetailsElement).open)}
        >
            <summary
                className="cursor-pointer text-xs font-medium text-gray-700 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 rounded"
                aria-expanded={isOpen}
                aria-controls={id}
            >
                <span className="sr-only">{isOpen ? 'Hide' : 'Show'} </span>
                Thinking
                <span className="sr-only"> process</span>
            </summary>
            <div id={id} className="mt-2">
                <MarkdownMessage text={text} />
            </div>
        </details>
    )
}

const Usage = ({ tokenInfo, costText, isUser }: { tokenInfo: { summary: string; detail?: string } | null; costText: string; isUser: boolean }) => (
    <div
        className={`mt-3 flex flex-wrap gap-x-3 text-[11px] ${isUser ? 'text-indigo-100/90' : 'text-gray-500 dark:text-gray-400'}`}
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

const Details = ({ text, isUser }: { text: string; isUser: boolean }) => {
    const [isOpen, setIsOpen] = useState(false)
    const id = `details-${Math.random().toString(36).substr(2, 9)}`

    return (
        <details
            className="mt-3"
            onToggle={(e) => setIsOpen((e.target as HTMLDetailsElement).open)}
        >
            <summary
                className={`cursor-pointer text-xs ${isUser ? 'text-indigo-100/90' : 'text-gray-600 dark:text-gray-300'} focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 rounded`}
                aria-expanded={isOpen}
                aria-controls={id}
            >
                <span className="sr-only">{isOpen ? 'Hide' : 'Show'} </span>
                Details
                <span className="sr-only"> (raw JSON)</span>
            </summary>
            <pre
                id={id}
                className="mt-2 overflow-x-auto rounded bg-gray-900/90 p-3 text-[11px] text-gray-100"
                tabIndex={0}
                aria-label="Raw message details"
            >
                {text}
            </pre>
        </details>
    )
}
