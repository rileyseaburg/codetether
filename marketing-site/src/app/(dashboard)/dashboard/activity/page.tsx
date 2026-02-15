'use client'

import { useState, useEffect, useCallback } from 'react'
import { useSession } from 'next-auth/react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.codetether.run'

interface Message {
    type: string
    agent_name: string
    content: string
    timestamp: string
    metadata?: {
        conversation_id?: string
        [key: string]: unknown
    }
}

function BoltIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
    )
}

export default function ActivityPage() {
    const { data: session } = useSession()
    const [messages, setMessages] = useState<Message[]>([])
    const [connected, setConnected] = useState(false)

    const loadMessages = useCallback(async () => {
        try {
            const response = await fetch(`${API_URL}/v1/monitor/messages?limit=50`)
            if (response.ok) {
                const data = await response.json()
                setMessages(data)
            }
        } catch (error) {
            console.error('Failed to load messages:', error)
        }
    }, [])

    useEffect(() => {
        loadMessages()

        // Handle relative API URLs by resolving against window.location
        const baseApiUrl = API_URL.startsWith('/') ? `${window.location.origin}${API_URL}` : API_URL
        const sseUrl = new URL(`${baseApiUrl}/v1/monitor/stream`)
        if (session?.accessToken) {
            sseUrl.searchParams.set('access_token', session.accessToken)
        }
        const eventSource = new EventSource(sseUrl.toString())

        eventSource.onopen = () => setConnected(true)
        eventSource.onerror = () => setConnected(false)

        eventSource.onmessage = (e) => {
            try {
                const data = JSON.parse(e.data)
                if (data.type === 'connected') return

                setMessages((prev) => [{
                    type: data.type || 'agent',
                    agent_name: data.agent_name || 'System',
                    content: data.content || data.message || '',
                    timestamp: data.timestamp || new Date().toISOString(),
                    metadata: data.metadata
                }, ...prev].slice(0, 100))
            } catch {
                console.debug('Parse error:', e.data)
            }
        }

        return () => eventSource.close()
    }, [loadMessages])

    const getTypeIcon = (type: string) => {
        const icons: Record<string, string> = {
            agent: '🤖',
            human: '👤',
            system: '⚙️',
            tool: '🔧',
            error: '❌',
        }
        return icons[type] || '📝'
    }

    const formatTime = (timestamp: string) => {
        if (!timestamp) return ''
        return new Date(timestamp).toLocaleTimeString()
    }

    return (
        <div className="rounded-lg bg-white shadow-sm dark:bg-gray-800 dark:ring-1 dark:ring-white/10">
            <div className="p-4 border-b border-gray-200 dark:border-gray-700">
                <div className="flex items-center justify-between">
                    <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Activity Feed</h2>
                    <div className="flex items-center gap-2">
                        <span className={`h-2.5 w-2.5 rounded-full ${connected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
                        <span className="text-sm text-gray-600 dark:text-gray-300">
                            {connected ? 'Connected' : 'Disconnected'}
                        </span>
                    </div>
                </div>
            </div>
            <div className="divide-y divide-gray-200 dark:divide-gray-700 max-h-[calc(100vh-250px)] overflow-y-auto">
                {messages.length === 0 ? (
                    <div className="p-8 text-center text-gray-500 dark:text-gray-400">
                        <BoltIcon className="mx-auto h-12 w-12 text-gray-400" />
                        <p className="mt-2 text-sm">No recent activity</p>
                    </div>
                ) : (
                    messages.map((msg, idx) => (
                        <div key={idx} className="p-4 hover:bg-gray-50 dark:hover:bg-gray-700/50">
                            <div className="flex items-start gap-3">
                                <span className="text-lg">{getTypeIcon(msg.type)}</span>
                                <div className="min-w-0 flex-1">
                                    <div className="flex items-center gap-2">
                                        <span className="text-sm font-medium text-gray-900 dark:text-white">
                                            {msg.agent_name || 'Unknown'}
                                        </span>
                                        <span className="text-xs text-gray-500 dark:text-gray-400">
                                            {formatTime(msg.timestamp)}
                                        </span>
                                    </div>
                                    <p className="text-sm text-gray-600 dark:text-gray-300 mt-1 line-clamp-3">
                                        {typeof msg.content === 'string' ? msg.content.substring(0, 300) : JSON.stringify(msg.content)}
                                    </p>
                                    {msg.metadata?.conversation_id && (
                                        <span className="text-xs text-gray-400">
                                            Conv: {String(msg.metadata.conversation_id).substring(0, 8)}...
                                        </span>
                                    )}
                                </div>
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    )
}
