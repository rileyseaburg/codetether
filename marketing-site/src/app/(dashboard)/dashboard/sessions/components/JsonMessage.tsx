'use client'

import { useState } from 'react'
import { CopyButton } from './CopyButton'
import { JsonNode } from './JsonNode'
import { JsonExpandContext } from './JsonExpandContext'
import { getJsonSummary, parseJsonPayload, type ParsedJsonPayload } from './JsonHelpers'

interface JsonMessageProps {
    payload: ParsedJsonPayload
    rawText: string
}

export function JsonMessage({ payload, rawText }: JsonMessageProps) {
    const [showRaw, setShowRaw] = useState(false)
    const [expandSignal, setExpandSignal] = useState({
        action: null as 'expand' | 'collapse' | null,
        version: 0,
    })

    const triggerExpand = (action: 'expand' | 'collapse') => {
        setExpandSignal((prev) => ({ action, version: prev.version + 1 }))
    }

    const summary = payload.kind === 'lines'
        ? `${payload.value.length} event${payload.value.length === 1 ? '' : 's'}`
        : getJsonSummary(payload.value)

    return (
        <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white/70 dark:bg-gray-900/40 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-200 dark:border-gray-700 px-3 py-2">
                <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-gray-300">JSON</span>
                    <span className="text-[10px] text-gray-400 dark:text-gray-500">{summary}</span>
                </div>
                <div className="flex flex-wrap items-center gap-1.5">
                    <button
                        type="button"
                        onClick={() => setShowRaw((prev) => !prev)}
                        className={`rounded-md border px-2 py-1 text-[10px] font-medium transition-all hover:border-gray-300 dark:hover:border-gray-500 ${showRaw
                                ? 'border-cyan-300 bg-cyan-50 text-cyan-700 dark:border-cyan-700 dark:bg-cyan-900/40 dark:text-cyan-200'
                                : 'border-gray-200 bg-white/70 text-gray-600 dark:border-gray-700 dark:bg-gray-900/40 dark:text-gray-300'
                            }`}
                        aria-pressed={showRaw}
                    >
                        {showRaw ? 'Pretty' : 'Raw'}
                    </button>
                    <CopyButton text={rawText} label="Copy JSON" />
                    <button
                        type="button"
                        onClick={() => triggerExpand('expand')}
                        className="rounded-md border border-gray-200 dark:border-gray-700 px-2 py-1 text-[10px] font-medium text-gray-600 dark:text-gray-300 transition-all hover:border-gray-300 dark:hover:border-gray-500"
                    >
                        Expand all
                    </button>
                    <button
                        type="button"
                        onClick={() => triggerExpand('collapse')}
                        className="rounded-md border border-gray-200 dark:border-gray-700 px-2 py-1 text-[10px] font-medium text-gray-600 dark:text-gray-300 transition-all hover:border-gray-300 dark:hover:border-gray-500"
                    >
                        Collapse all
                    </button>
                </div>
            </div>
            <div className="max-h-112 overflow-y-auto p-2">
                {showRaw ? (
                    <pre className="rounded-md bg-gray-900/90 p-3 text-[11px] text-gray-100 overflow-x-auto">
                        {rawText}
                    </pre>
                ) : (
                    <JsonExpandContext.Provider value={expandSignal}>
                        {payload.kind === 'lines' ? (
                            <div className="space-y-2">
                                {payload.value.map((entry, index) => (
                                    <div
                                        key={`json-line-${index}`}
                                        className="rounded-md border border-gray-200 dark:border-gray-700 bg-white/80 dark:bg-gray-900/30"
                                    >
                                        <JsonNode
                                            name={`Event ${String(index + 1).padStart(2, '0')}`}
                                            value={entry}
                                            depth={0}
                                            path={`event.${index}`}
                                        />
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <JsonNode name="root" value={payload.value} depth={0} path="root" />
                        )}
                    </JsonExpandContext.Provider>
                )}
            </div>
        </div>
    )
}
