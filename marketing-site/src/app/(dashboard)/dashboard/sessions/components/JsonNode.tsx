'use client'

import { useState, useEffect, useContext } from 'react'
import { CopyButton } from './CopyButton'
import { getJsonSummary } from './JsonHelpers'
import type { JsonValue } from './JsonHelpers'
import { JsonExpandContext } from './JsonExpandContext'

interface JsonNodeProps {
    name?: string
    value: JsonValue
    depth: number
    path: string
}

export function JsonNode({ name, value, depth, path }: JsonNodeProps) {
    const { action, version } = useContext(JsonExpandContext)
    const [isOpen, setIsOpen] = useState(depth < 1)
    const isArray = Array.isArray(value)
    const isObject = value !== null && typeof value === 'object' && !isArray

    useEffect(() => {
        if (action === 'expand') setIsOpen(true)
        if (action === 'collapse') setIsOpen(false)
    }, [action, version])

    const paddingStyle = { paddingLeft: `${depth * 12}px` }

    if (isArray || isObject) {
        const entries = isArray
            ? (value as JsonValue[]).map((item, index) => [String(index), item] as const)
            : Object.entries(value as { [key: string]: JsonValue })

        const label = name || (isArray ? 'Array' : 'Object')

        return (
            <div>
                <div
                    className="group flex items-center gap-2 rounded-md py-1 pr-2 transition-colors hover:bg-gray-50 dark:hover:bg-gray-800/60"
                    style={paddingStyle}
                >
                    <button
                        type="button"
                        onClick={() => setIsOpen((prev) => !prev)}
                        className="flex min-w-0 flex-1 items-center gap-2 text-left"
                        aria-expanded={isOpen}
                    >
                        <span
                            className={`flex h-4 w-4 items-center justify-center rounded-full border border-gray-200 dark:border-gray-700 text-gray-500 transition-transform ${isOpen ? 'rotate-90' : ''
                                }`}
                        >
                            <svg viewBox="0 0 20 20" fill="currentColor" className="h-2.5 w-2.5">
                                <path d="M6 6l5 4-5 4V6z" />
                            </svg>
                        </span>
                        <span className="truncate font-mono text-xs text-gray-600 dark:text-gray-300">{label}</span>
                        <span className="text-[10px] text-gray-400 dark:text-gray-500">{getJsonSummary(value)}</span>
                    </button>
                    <CopyButton
                        text={JSON.stringify(value, null, 2)}
                        label={`Copy ${label}`}
                        iconOnly
                        className="opacity-0 group-hover:opacity-100"
                    />
                </div>
                {isOpen && (
                    <div className="mt-1 space-y-1">
                        {entries.map(([key, child]) => (
                            <JsonNode
                                key={`${path}.${key}`}
                                name={isArray ? `[${key}]` : key}
                                value={child}
                                depth={depth + 1}
                                path={`${path}.${key}`}
                            />
                        ))}
                    </div>
                )}
            </div>
        )
    }

    const valueClass =
        typeof value === 'string'
            ? 'text-amber-700 dark:text-amber-300'
            : typeof value === 'number'
                ? 'text-sky-700 dark:text-sky-300'
                : typeof value === 'boolean'
                    ? 'text-violet-700 dark:text-violet-300'
                    : 'text-gray-500 dark:text-gray-400'

    return (
        <div
            className="group flex items-start gap-2 rounded-md py-1 pr-2 transition-colors hover:bg-gray-50 dark:hover:bg-gray-800/60"
            style={paddingStyle}
        >
            {name && (
                <span className="min-w-20 shrink-0 font-mono text-xs text-gray-500 dark:text-gray-400">{name}</span>
            )}
            <span className={`flex-1 wrap-break-word font-mono text-xs ${valueClass}`}>{formatJsonValue(value)}</span>
            <CopyButton
                text={String(value)}
                label="Copy value"
                iconOnly
                className="opacity-0 group-hover:opacity-100"
            />
        </div>
    )
}

function formatJsonValue(value: JsonValue) {
    if (typeof value === 'string') return `"${value}"`
    if (typeof value === 'number') return String(value)
    if (typeof value === 'boolean') return value ? 'true' : 'false'
    if (value === null) return 'null'
    return ''
}
