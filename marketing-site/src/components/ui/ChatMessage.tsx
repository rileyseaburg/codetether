import { LoadingDots } from './LoadingDots'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'

interface ChatMessageProps {
    role: 'user' | 'assistant' | 'system'
    content: string
    status?: 'sending' | 'sent' | 'error'
}

export function ChatMessage({ role, content, status = 'sent' }: ChatMessageProps) {
    return (
        <div className={`flex ${role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] px-4 py-3 rounded-2xl text-sm ${
                role === 'user'
                    ? 'bg-cyan-500 text-white rounded-br-md'
                    : status === 'error'
                        ? 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 rounded-bl-md'
                        : 'bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-bl-md shadow-sm border border-gray-100 dark:border-gray-700'
            }`}>
                {status === 'sending' ? <LoadingDots /> : (
                    <ReactMarkdown
                        remarkPlugins={[remarkGfm, remarkBreaks]}
                        components={{
                            p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                            ul: ({ children }) => <ul className="list-disc list-inside mb-2 ml-4">{children}</ul>,
                            ol: ({ children }) => <ol className="list-decimal list-inside mb-2 ml-4">{children}</ol>,
                            li: ({ children }) => <li className="mb-1 last:mb-0">{children}</li>,
                            h1: ({ children }) => <h1 className="text-lg font-bold mb-2">{children}</h1>,
                            h2: ({ children }) => <h2 className="text-base font-semibold mb-2">{children}</h2>,
                            h3: ({ children }) => <h3 className="text-sm font-semibold mb-2">{children}</h3>,
                            strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                            code: ({ children }) => <code className="bg-gray-100 dark:bg-gray-700 px-1 py-0.5 rounded text-xs font-mono">{children}</code>,
                            a: ({ href, children }) => <a href={href} className="text-cyan-500 hover:text-cyan-400 underline" target="_blank" rel="noopener noreferrer">{children}</a>,
                        }}
                    >
                        {content}
                    </ReactMarkdown>
                )}
            </div>
        </div>
    )
}
