import type { ComponentPropsWithoutRef } from 'react'
import React from 'react'
import { Components } from 'react-markdown'

type MarkdownAnchorProps = ComponentPropsWithoutRef<'a'>
type MarkdownCodeProps = ComponentPropsWithoutRef<'code'> & {
    inline?: boolean
    children?: React.ReactNode
}
type MarkdownPreProps = ComponentPropsWithoutRef<'pre'> & {
    children?: React.ReactNode
}
type MarkdownParagraphProps = ComponentPropsWithoutRef<'p'>
type MarkdownUnorderedListProps = ComponentPropsWithoutRef<'ul'>
type MarkdownOrderedListProps = ComponentPropsWithoutRef<'ol'>
type MarkdownCodeElementProps = {
    children?: React.ReactNode
    className?: string
}

 export const MarkdownComponents: Components = {
    a: ({ children, ...props }: MarkdownAnchorProps) => (
        <a {...props} className="text-cyan-600 hover:underline dark:text-cyan-400" target="_blank" rel="noreferrer">{children}</a>
    ),
    code: ({ inline, children, className, ...props }: MarkdownCodeProps) => {
        if (inline) {
            return (
                <code {...props} className={`rounded bg-gray-100 dark:bg-gray-700/60 px-1 py-0.5 font-mono text-[0.9em] ${className || ''}`}>
                    {children}
                </code>
            )
        }
        return (
            <code {...props} className={`font-mono text-[0.9em] ${className || ''}`}>
                {children}
            </code>
        )
    },
    pre: ({ children, ...props }: MarkdownPreProps) => {
        const child = Array.isArray(children) ? children[0] : children
        if (React.isValidElement<MarkdownCodeElementProps>(child)) {
            const raw = child.props?.children
            const className = child.props?.className
            const text = Array.isArray(raw) ? raw.join('') : String(raw || '')
            if (looksLikeDiff(text, className)) {
                return <DiffBlock text={text} />
            }
        }
        return (
            <pre {...props} className="my-2 overflow-x-auto rounded-lg bg-gray-900/90 p-3 text-xs text-gray-100">
                {children}
            </pre>
        )
    },
    p: ({ children, ...props }: MarkdownParagraphProps) => <p {...props} className="mb-2 last:mb-0">{children}</p>,
    ul: ({ children, ...props }: MarkdownUnorderedListProps) => <ul {...props} className="mb-2 list-disc pl-5 last:mb-0">{children}</ul>,
    ol: ({ children, ...props }: MarkdownOrderedListProps) => <ol {...props} className="mb-2 list-decimal pl-5 last:mb-0">{children}</ol>,
}

export function looksLikeDiff(text: string, className?: string): boolean {
    if (className && /language-(diff|patch)/i.test(className)) return true
    const lines = text.trim().split('\n')
    if (lines.length < 2) return false
    let headers = 0
    let changes = 0
    for (const line of lines) {
        if (DIFF_HEADER_PATTERN.test(line)) headers += 1
        if (line.startsWith('+') && !line.startsWith('+++')) changes += 1
        if (line.startsWith('-') && !line.startsWith('---')) changes += 1
    }
    return headers > 0 && changes > 0
}

 export function diffLineClass(line: string): string {
    if (line.startsWith('diff --git') || line.startsWith('index ') || line.startsWith('*** ')) {
        return 'text-gray-300/80'
    }
    if (line.startsWith('@@')) {
        return 'bg-cyan-500/10 text-cyan-200'
    }
    if (line.startsWith('+++') || line.startsWith('---')) {
        return 'text-gray-300'
    }
    if (line.startsWith('+')) {
        return 'bg-emerald-500/10 text-emerald-200'
    }
    if (line.startsWith('-')) {
        return 'bg-red-500/10 text-red-200'
    }
    return 'text-gray-100'
}

export function DiffBlock({ text }: { text: string }) {
    const lines = text.replace(/\n$/, '').split('\n')
    return (
        <pre className="my-2 overflow-x-auto rounded-lg bg-gray-900/90 p-3 text-xs text-gray-100 ring-1 ring-white/10">
            <code className="block font-mono">
                {lines.map((line, i) => (
                    <span
                        key={`${i}-${line.slice(0, 12)}`}
                        className={`block whitespace-pre px-2 -mx-2 ${diffLineClass(line)}`}
                    >
                        {line || ' '}
                    </span>
                ))}
            </code>
        </pre>
    )
}

export const DIFF_HEADER_PATTERN = /^(diff --git|index\s|@@|\+\+\+|---|\*\*\* Begin Patch|\*\*\* End Patch)/i
