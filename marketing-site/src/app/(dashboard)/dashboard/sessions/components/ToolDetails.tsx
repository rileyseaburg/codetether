'use client'

import { useState, useId } from 'react'
import type { ToolEntry as ToolEntryType } from '../types'
import { ToolEntry } from './ToolEntry'
import { MarkdownMessage } from './MarkdownMessage'

/** Extract the actual output string from RLM/task tool outputs (which may be objects with an `output` field) */
function getRlmOrTaskOutput(output: unknown): string {
    if (typeof output === 'string') return output
    if (output && typeof output === 'object' && 'output' in output) {
        const inner = (output as Record<string, unknown>).output
        if (typeof inner === 'string') return inner
    }
    return summarizeStructured(output)
}

function summarizeStructured(value: unknown): string {
    if (typeof value === 'string') return value
    if (typeof value === 'number' || typeof value === 'boolean') return String(value)
    if (value === null || value === undefined) return 'No data'
    if (Array.isArray(value)) return `Array (${value.length} item${value.length === 1 ? '' : 's'})`
    if (typeof value === 'object') {
        const keys = Object.keys(value as Record<string, unknown>).length
        return `Object (${keys} key${keys === 1 ? '' : 's'})`
    }
    return 'Structured data'
}

interface ToolDetailsProps {
    tools: ToolEntryType[]
    isUser: boolean
}

export function ToolDetails({ tools, isUser }: ToolDetailsProps) {
    const [isOpen, setIsOpen] = useState(false)
    const [expandedTools, setExpandedTools] = useState<Set<number>>(new Set())

    if (!tools.length) return null

    const toolNames = tools.slice(0, 3).map(t => t.tool).join(', ')
    const moreCount = tools.length > 3 ? tools.length - 3 : 0
    const id = useId()

    // Count successful vs failed tools
    const successCount = tools.filter(t => t.status === 'completed' || !t.status).length
    const failedCount = tools.filter(t => t.status === 'error' || t.status === 'failed').length

    const toggleTool = (idx: number) => {
        setExpandedTools(prev => {
            const next = new Set(prev)
            if (next.has(idx)) {
                next.delete(idx)
            } else {
                next.add(idx)
            }
            return next
        })
    }

    const expandAll = () => setExpandedTools(new Set(tools.map((_, i) => i)))
    const collapseAll = () => setExpandedTools(new Set())

    return (
        <details
            className={`mt-3 rounded-lg transition-shadow ${isUser ? 'bg-indigo-500/20' : 'bg-blue-50 dark:bg-blue-900/20 ring-1 ring-blue-200/50 dark:ring-blue-700/30'}`}
            onToggle={(e) => setIsOpen((e.target as HTMLDetailsElement).open)}
        >
            <summary
                className="cursor-pointer select-none p-3 text-xs font-medium text-blue-800 dark:text-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 rounded-lg flex items-center justify-between gap-2 transition-colors hover:bg-blue-100/50 dark:hover:bg-blue-900/40"
                aria-expanded={isOpen}
                aria-controls={id}
            >
                <div className="flex items-center gap-2">
                    <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                    <span>{tools.length} Tool{tools.length !== 1 ? 's' : ''}</span>
                    {successCount > 0 && (
                        <span className="px-1.5 py-0.5 rounded-full bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300 text-[10px]">
                            {successCount} done
                        </span>
                    )}
                    {failedCount > 0 && (
                        <span className="px-1.5 py-0.5 rounded-full bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300 text-[10px]">
                            {failedCount} failed
                        </span>
                    )}
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

            {/* Preview when collapsed */}
            {!isOpen && (
                <p className="px-3 pb-3 text-xs text-blue-700/70 dark:text-blue-300/50 truncate">
                    {toolNames}{moreCount > 0 ? ` +${moreCount} more` : ''}
                </p>
            )}

            <div id={id} className={`${isOpen ? 'p-3 pt-0' : 'hidden'}`}>
                {/* Expand/Collapse all controls */}
                {tools.length > 2 && (
                    <div className="flex items-center gap-2 mb-2 text-xs">
                        <button
                            onClick={(e) => { e.preventDefault(); expandAll() }}
                            className="text-blue-600 dark:text-blue-400 hover:underline"
                        >
                            Expand all
                        </button>
                        <span className="text-gray-300 dark:text-gray-600">|</span>
                        <button
                            onClick={(e) => { e.preventDefault(); collapseAll() }}
                            className="text-blue-600 dark:text-blue-400 hover:underline"
                        >
                            Collapse all
                        </button>
                    </div>
                )}

                <div className="space-y-2 max-h-96 overflow-y-auto" role="list" aria-label="Tool calls">
                    {tools.map((t, idx) => (
                        <ToolItem
                            key={`${t.tool}-${idx}`}
                            tool={t}
                            index={idx}
                            isExpanded={expandedTools.has(idx)}
                            onToggle={() => toggleTool(idx)}
                        />
                    ))}
                </div>
            </div>
        </details>
    )
}

interface ToolItemProps {
    tool: ToolEntryType
    index: number
    isExpanded: boolean
    onToggle: () => void
}

function ToolItem({ tool, index, isExpanded, onToggle }: ToolItemProps) {
    const statusColor = tool.status === 'error' || tool.status === 'failed'
        ? 'text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/30'
        : tool.status === 'running' || tool.status === 'pending'
        ? 'text-yellow-600 dark:text-yellow-400 bg-yellow-50 dark:bg-yellow-900/30'
        : 'text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/30'

    const hasDetails = tool.input || tool.output || tool.error

    return (
        <div
            className={`rounded-lg bg-white dark:bg-gray-800 ring-1 ring-gray-200 dark:ring-gray-700 overflow-hidden transition-shadow ${isExpanded ? 'shadow-md ring-indigo-200/60 dark:ring-indigo-600/40' : 'shadow-sm'}`}
            role="listitem"
        >
            <button
                onClick={onToggle}
                className="w-full text-left px-3 py-2 flex items-center justify-between gap-2 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
                aria-expanded={isExpanded}
            >
                <div className="flex items-center gap-2 min-w-0">
                    <span className="text-xs text-gray-400 dark:text-gray-500 font-mono">
                        {(index + 1).toString().padStart(2, '0')}
                    </span>
                    <code className="text-xs font-medium text-gray-900 dark:text-gray-100 truncate">
                        {tool.tool}
                    </code>
                    {tool.title && (
                        <span className="text-xs text-gray-500 dark:text-gray-400 truncate hidden sm:inline">
                            - {tool.title}
                        </span>
                    )}
                </div>
                <div className="flex items-center gap-2 shrink-0">
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${statusColor}`}>
                        {tool.status || 'done'}
                    </span>
                    {hasDetails ? (
                        <svg
                            className={`w-4 h-4 text-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                        >
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                        </svg>
                    ) : null}
                </div>
            </button>

            {isExpanded && hasDetails ? (
                <div className="px-3 pb-3 space-y-2 border-t border-gray-100 dark:border-gray-700 animate-fadeIn">
                    {tool.input ? (
                        <div className="mt-2">
                            <span className="text-[10px] font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">Input</span>
                            <pre className="mt-1 p-2 rounded bg-gray-50 dark:bg-gray-900/50 text-[11px] text-gray-700 dark:text-gray-300 overflow-x-auto max-h-32 overflow-y-auto">
                                {summarizeStructured(tool.input)}
                            </pre>
                        </div>
                    ) : null}
                    {tool.output ? (
                        <div>
                            <span className="text-[10px] font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">Output</span>
                            {/* Render rlm and task outputs as markdown, others as pre */}
                            {(tool.tool === 'rlm' || tool.tool === 'task') ? (
                                <div className="mt-1 p-2 rounded bg-gray-50 dark:bg-gray-900/50 text-sm text-gray-700 dark:text-gray-300 overflow-x-auto max-h-96 overflow-y-auto prose prose-sm dark:prose-invert max-w-none">
                                    <MarkdownMessage text={getRlmOrTaskOutput(tool.output)} />
                                </div>
                            ) : (
                                <pre className="mt-1 p-2 rounded bg-gray-50 dark:bg-gray-900/50 text-[11px] text-gray-700 dark:text-gray-300 overflow-x-auto max-h-32 overflow-y-auto">
                                    {summarizeStructured(tool.output)}
                                </pre>
                            )}
                        </div>
                    ) : null}
                    {tool.error ? (
                        <div>
                            <span className="text-[10px] font-medium text-red-500 dark:text-red-400 uppercase tracking-wide">Error</span>
                            <pre className="mt-1 p-2 rounded bg-red-50 dark:bg-red-900/30 text-[11px] text-red-700 dark:text-red-300 overflow-x-auto max-h-32 overflow-y-auto">
                                {summarizeStructured(tool.error)}
                            </pre>
                        </div>
                    ) : null}
                </div>
            ) : null}
        </div>
    )
}
