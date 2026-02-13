'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { useSession } from 'next-auth/react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.codetether.run'

interface Codebase {
    id: string
    name: string
    path: string
    status: string
}

interface OutputLine {
    type: 'text' | 'status' | 'error' | 'tool'
    content: string
    timestamp: Date
}

function TerminalIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
    )
}

export default function OutputPage() {
    const { data: session } = useSession()
    const [codebases, setCodebases] = useState<Codebase[]>([])
    const [selectedCodebase, setSelectedCodebase] = useState('')
    const [output, setOutput] = useState<OutputLine[]>([])
    const [connected, setConnected] = useState(false)
    const eventSourceRef = useRef<EventSource | null>(null)
    const outputEndRef = useRef<HTMLDivElement>(null)

    const loadCodebases = useCallback(async () => {
        try {
            const response = await fetch(`${API_URL}/v1/opencode/codebases/list`)
            if (response.ok) {
                const data = await response.json()
                const items = Array.isArray(data) ? data : (data?.codebases ?? [])
                setCodebases(
                    (items as any[]).map((cb) => ({
                        id: String(cb?.id ?? ''),
                        name: String(cb?.name ?? cb?.id ?? ''),
                        path: String(cb?.path ?? ''),
                        status: String(cb?.status ?? 'unknown'),
                    })).filter((cb) => cb.id)
                )
            }
        } catch (error) {
            console.error('Failed to load codebases:', error)
        }
    }, [])

    useEffect(() => {
        loadCodebases()
    }, [loadCodebases])

    useEffect(() => {
        // Auto-scroll to bottom
        outputEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [output])

    const connectToCodebase = useCallback((codebaseId: string) => {
        // Close existing connection
        if (eventSourceRef.current) {
            eventSourceRef.current.close()
        }

        if (!codebaseId) {
            setOutput([])
            setConnected(false)
            return
        }

        setOutput([{ type: 'status', content: 'Connecting to event stream...', timestamp: new Date() }])

        const sseUrl = new URL(`${API_URL}/v1/opencode/codebases/${codebaseId}/events`)
        if (session?.accessToken) {
            sseUrl.searchParams.set('access_token', session.accessToken)
        }
        const eventSource = new EventSource(sseUrl.toString())
        eventSourceRef.current = eventSource

        eventSource.onopen = () => {
            setConnected(true)
            addOutput('status', 'Connected')
        }

        eventSource.onerror = () => {
            setConnected(false)
            addOutput('error', 'Event stream disconnected')
        }

        eventSource.addEventListener('connected', () => {
            addOutput('status', 'Connected to agent stream')
        })

        eventSource.addEventListener('message', (e) => {
            try {
                const data = JSON.parse(e.data)
                processEvent(data)
            } catch {
                if (e.data && e.data.trim()) {
                    addOutput('text', e.data)
                }
            }
        })

        eventSource.addEventListener('status', (e) => {
            const data = JSON.parse(e.data)
            addOutput('status', data.message || data.status)
        })

        return () => eventSource.close()
    }, [])

    useEffect(() => {
        if (selectedCodebase) {
            connectToCodebase(selectedCodebase)
        }
        return () => {
            if (eventSourceRef.current) {
                eventSourceRef.current.close()
            }
        }
    }, [selectedCodebase, connectToCodebase])

    const addOutput = (type: OutputLine['type'], content: string) => {
        setOutput((prev) => [...prev, { type, content, timestamp: new Date() }].slice(-500))
    }

    const processEvent = (event: Record<string, unknown>) => {
        const type = (event.type || event.event_type) as string
        const part = (event.part || {}) as Record<string, unknown>

        const getTextContent = (obj: Record<string, unknown> | string): string => {
            if (!obj) return ''
            if (typeof obj === 'string') return obj
            if (obj.text) return obj.text as string
            if (obj.content) {
                if (typeof obj.content === 'string') return obj.content
                if (Array.isArray(obj.content)) return obj.content.map(c => (c as Record<string, string>).text || c).join('')
            }
            return ''
        }

        switch (type) {
            case 'text':
            case 'part.text': {
                const text = getTextContent(part) || getTextContent(event as Record<string, unknown>)
                if (text) addOutput('text', text)
                break
            }
            case 'tool_use':
            case 'part.tool': {
                const stateInfo = (part.state || event.state || {}) as Record<string, unknown>
                const toolName = part.tool || part.tool_name || event.tool_name || 'Tool'
                const toolOutput = stateInfo.output || ''
                const toolTitle = stateInfo.title || ''
                addOutput('tool', `Tool: ${toolName}${toolTitle ? ' - ' + toolTitle : ''}\n${toolOutput}`)
                break
            }
            case 'step_start':
            case 'part.step-start':
                addOutput('status', '--- Step started ---')
                break
            case 'step_finish':
            case 'part.step-finish': {
                const tokens = (part.tokens || event.tokens) as Record<string, number> | undefined
                if (tokens) {
                    const total = (tokens.input || 0) + (tokens.output || 0)
                    addOutput('status', `Step finished (${total} tokens)`)
                } else {
                    addOutput('status', '--- Step finished ---')
                }
                break
            }
            case 'message':
            case 'message.updated': {
                const msgContent = getTextContent(event as Record<string, unknown>)
                if (msgContent) addOutput('text', msgContent)
                break
            }
            case 'status':
            case 'session.status':
                addOutput('status', (event.status || event.message || 'Status update') as string)
                break
            case 'error':
                addOutput('error', (event.error || event.message || 'Error occurred') as string)
                break
            default: {
                const fallbackText = getTextContent(event as Record<string, unknown>) || getTextContent(part)
                if (fallbackText) {
                    addOutput('text', fallbackText)
                }
            }
        }
    }

    const getOutputClasses = (type: OutputLine['type']) => {
        const classes: Record<string, string> = {
            text: 'text-gray-900 dark:text-gray-100',
            status: 'text-blue-600 dark:text-blue-400',
            error: 'text-red-600 dark:text-red-400',
            tool: 'text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/20 p-2 rounded',
        }
        return classes[type] || classes.text
    }

    const clearOutput = () => setOutput([])

    return (
        <div className="rounded-lg bg-white shadow-sm dark:bg-gray-800 dark:ring-1 dark:ring-white/10">
            <div className="p-4 border-b border-gray-200 dark:border-gray-700">
                <div className="flex items-center justify-between">
                    <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Agent Output</h2>
                    <div className="flex items-center gap-4">
                        <select
                            value={selectedCodebase}
                            onChange={(e) => setSelectedCodebase(e.target.value)}
                            className="rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white text-sm"
                        >
                            <option value="">Select codebase...</option>
                            {codebases.map((cb) => (
                                <option key={cb.id} value={cb.id}>{cb.name}</option>
                            ))}
                        </select>
                        <div className="flex items-center gap-2">
                            <span className={`h-2.5 w-2.5 rounded-full ${connected ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`} />
                            <span className="text-sm text-gray-600 dark:text-gray-300">
                                {connected ? 'Connected' : 'Disconnected'}
                            </span>
                        </div>
                        <button
                            onClick={clearOutput}
                            className="text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
                        >
                            Clear
                        </button>
                    </div>
                </div>
            </div>
            <div className="p-4 max-h-[calc(100vh-250px)] overflow-y-auto font-mono text-sm bg-gray-50 dark:bg-gray-900">
                {output.length === 0 ? (
                    <div className="text-center text-gray-500 dark:text-gray-400 py-8">
                        <TerminalIcon className="mx-auto h-12 w-12 text-gray-400" />
                        <p className="mt-2">Select a codebase to view agent output</p>
                    </div>
                ) : (
                    output.map((line, idx) => (
                        <div key={idx} className={`mb-2 whitespace-pre-wrap ${getOutputClasses(line.type)}`}>
                            {line.content}
                        </div>
                    ))
                )}
                <div ref={outputEndRef} />
            </div>
        </div>
    )
}
