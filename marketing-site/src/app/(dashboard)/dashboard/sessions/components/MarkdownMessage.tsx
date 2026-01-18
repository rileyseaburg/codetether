'use client'

import { memo, useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkBreaks from 'remark-breaks'
import remarkGfm from 'remark-gfm'

interface MarkdownMessageProps {
    text: string
}

// Memoize plugins array to prevent recreation on every render
const remarkPlugins = [remarkGfm, remarkBreaks]

// Memoize components object - this was causing re-renders
const markdownComponents = {
    a: ({ children, ...props }: any) => (
        <a {...props} className="text-indigo-600 hover:underline dark:text-indigo-400" target="_blank" rel="noreferrer">{children}</a>
    ),
    code: ({ children, className, ...props }: any) => (
        <code {...props} className={`rounded bg-gray-100 dark:bg-gray-700/60 px-1 py-0.5 font-mono text-[0.9em] ${className || ''}`}>{children}</code>
    ),
    pre: ({ children, ...props }: any) => (
        <pre {...props} className="my-2 overflow-x-auto rounded-lg bg-gray-900/90 p-3 text-xs text-gray-100">{children}</pre>
    ),
    p: ({ children, ...props }: any) => <p {...props} className="mb-2 last:mb-0">{children}</p>,
    ul: ({ children, ...props }: any) => <ul {...props} className="mb-2 list-disc pl-5 last:mb-0">{children}</ul>,
    ol: ({ children, ...props }: any) => <ol {...props} className="mb-2 list-decimal pl-5 last:mb-0">{children}</ol>,
}

function MarkdownMessageInner({ text }: MarkdownMessageProps) {
    // Memoize the markdown rendering - only re-render when text changes
    const content = useMemo(() => {
        if (!text) return null
        return (
            <ReactMarkdown 
                remarkPlugins={remarkPlugins} 
                components={markdownComponents}
            >
                {text}
            </ReactMarkdown>
        )
    }, [text])

    if (!content) return null
    
    return (
        <div className="text-sm leading-relaxed break-words">
            {content}
        </div>
    )
}

// Memoize the entire component - skip re-render if text hasn't changed
export const MarkdownMessage = memo(MarkdownMessageInner)
MarkdownMessage.displayName = 'MarkdownMessage'
