import ReactMarkdown from 'react-markdown'
import remarkBreaks from 'remark-breaks'
import remarkGfm from 'remark-gfm'

interface MarkdownMessageProps {
    text: string
}

const components = {
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

export function MarkdownMessage({ text }: MarkdownMessageProps) {
    if (!text) return null
    return (
        <div className="text-sm leading-relaxed break-words">
            <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]} components={components}>{text}</ReactMarkdown>
        </div>
    )
}
