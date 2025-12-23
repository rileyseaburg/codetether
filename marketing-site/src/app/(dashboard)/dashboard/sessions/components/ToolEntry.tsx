'use client'

import { useState } from 'react'
import type { ToolEntry as ToolEntryType } from '../types'
import { safeJsonStringify } from '../utils'

interface ToolEntryProps {
    tool: ToolEntryType
}

export function ToolEntry({ tool }: ToolEntryProps) {
    const hasDetails = tool.input !== undefined || tool.output !== undefined || tool.error !== undefined
    const hasError = tool.error !== undefined

    return (
        <article
            className="rounded-md bg-white/60 dark:bg-gray-800/60 p-2 ring-1 ring-gray-200/70 dark:ring-white/10"
            aria-label={`Tool: ${tool.tool}${tool.status ? `, status: ${tool.status}` : ''}${hasError ? ' (has error)' : ''}`}
        >
            <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-semibold">{tool.tool}</span>
                {tool.status && (
                    <span
                        className="text-[10px] rounded-full bg-gray-200 px-2 py-0.5 text-gray-700 dark:bg-gray-700 dark:text-gray-200"
                        aria-label={`Status: ${tool.status}`}
                    >
                        {tool.status}
                    </span>
                )}
                {tool.title && (
                    <span className="text-[11px] text-gray-600 dark:text-gray-300">
                        {tool.title}
                    </span>
                )}
            </div>
            {hasDetails && <ToolIODetails tool={tool} />}
        </article>
    )
}

function ToolIODetails({ tool }: { tool: ToolEntryType }) {
    return (
        <div className="mt-2 space-y-2">
            {tool.input !== undefined && (
                <ExpandableDetail
                    label="Input"
                    content={safeJsonStringify(tool.input, 4000)}
                    variant="default"
                />
            )}
            {tool.output !== undefined && (
                <ExpandableDetail
                    label="Output"
                    content={safeJsonStringify(tool.output, 4000)}
                    variant="default"
                />
            )}
            {tool.error !== undefined && (
                <ExpandableDetail
                    label="Error"
                    content={safeJsonStringify(tool.error, 4000)}
                    variant="error"
                />
            )}
        </div>
    )
}

interface ExpandableDetailProps {
    label: string
    content: string
    variant: 'default' | 'error'
}

function ExpandableDetail({ label, content, variant }: ExpandableDetailProps) {
    const [isOpen, setIsOpen] = useState(false)
    const id = `tool-${label.toLowerCase()}-${Math.random().toString(36).substr(2, 9)}`
    const textColor = variant === 'error'
        ? 'text-red-600 dark:text-red-400'
        : 'text-gray-600 dark:text-gray-300'

    return (
        <details onToggle={(e) => setIsOpen((e.target as HTMLDetailsElement).open)}>
            <summary
                className={`cursor-pointer text-[11px] ${textColor} focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 rounded`}
                aria-expanded={isOpen}
                aria-controls={id}
            >
                <span className="sr-only">{isOpen ? 'Hide' : 'Show'} tool </span>
                {label}
            </summary>
            <pre
                id={id}
                className="mt-1 overflow-x-auto rounded bg-gray-900/90 p-2 text-[11px] text-gray-100"
                tabIndex={0}
                aria-label={`${label} data`}
            >
                {content}
            </pre>
        </details>
    )
}
