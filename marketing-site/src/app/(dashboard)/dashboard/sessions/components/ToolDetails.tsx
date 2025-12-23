'use client'

import { useState } from 'react'
import type { ToolEntry as ToolEntryType } from '../types'
import { ToolEntry } from './ToolEntry'

interface ToolDetailsProps {
    tools: ToolEntryType[]
    isUser: boolean
}

export function ToolDetails({ tools, isUser }: ToolDetailsProps) {
    const [isOpen, setIsOpen] = useState(false)

    if (!tools.length) return null

    const toolNames = tools.map(t => t.tool).join(', ')
    const id = `tools-${Math.random().toString(36).substr(2, 9)}`

    return (
        <details
            className={`mt-3 rounded-lg ${isUser ? 'bg-indigo-500/20' : 'bg-gray-100 dark:bg-gray-900/30'} p-3`}
            onToggle={(e) => setIsOpen((e.target as HTMLDetailsElement).open)}
        >
            <summary
                className="cursor-pointer select-none text-xs font-medium text-gray-700 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 rounded"
                aria-expanded={isOpen}
                aria-controls={id}
            >
                <span className="sr-only">{isOpen ? 'Hide' : 'Show'} </span>
                Tools ({tools.length})
                <span className="sr-only">: {toolNames}</span>
            </summary>
            <div id={id} className="mt-2 space-y-2" role="list" aria-label="Tool calls">
                {tools.map((t, idx) => (
                    <div key={`${t.tool}-${idx}`} role="listitem">
                        <ToolEntry tool={t} />
                    </div>
                ))}
            </div>
        </details>
    )
}
