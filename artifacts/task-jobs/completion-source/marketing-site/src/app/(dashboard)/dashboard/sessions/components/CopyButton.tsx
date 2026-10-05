'use client'

import { useState, useEffect } from 'react'

interface CopyButtonProps {
    text: string
    label: string
    iconOnly?: boolean
    className?: string
}

export function CopyButton({ text, label, iconOnly = false, className = '' }: CopyButtonProps) {
    const [copied, setCopied] = useState(false)

    useEffect(() => {
        if (!copied) return
        const timer = window.setTimeout(() => setCopied(false), 1400)
        return () => window.clearTimeout(timer)
    }, [copied])

    const handleCopy = async () => {
        try {
            await navigator.clipboard.writeText(text)
            setCopied(true)
        } catch {
            setCopied(false)
        }
    }

    return (
        <button
            onClick={(e) => {
                e.preventDefault()
                handleCopy()
            }}
            className={`inline-flex items-center gap-1 rounded-md border border-gray-200 dark:border-gray-700 bg-white/80 dark:bg-gray-900/40 px-2 py-1 text-[10px] font-medium text-gray-600 dark:text-gray-300 transition-all hover:text-gray-900 dark:hover:text-white hover:border-gray-300 dark:hover:border-gray-500 active:scale-[0.98] ${iconOnly ? 'px-1.5 py-1' : ''} ${className}`}
            aria-label={label}
            title={label}
            type="button"
        >
            <svg className="h-3 w-3" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                <path d="M6 2a2 2 0 00-2 2v8a2 2 0 002 2h1V4a1 1 0 011-1h6V2H6z" />
                <path d="M9 6a2 2 0 012-2h5a2 2 0 012 2v9a2 2 0 01-2 2h-5a2 2 0 01-2-2V6z" />
            </svg>
            {!iconOnly && <span>{copied ? 'Copied' : label}</span>}
        </button>
    )
}
