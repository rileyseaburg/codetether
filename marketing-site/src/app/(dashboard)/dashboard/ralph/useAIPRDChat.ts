import { useState, useRef, useEffect, useCallback } from 'react'
import { useSession } from 'next-auth/react'
import { generateUUID } from './utils'
import { useRalphStore } from './store'
import { useTenantApi } from '@/hooks/useTenantApi'

type Role = 'user' | 'assistant' | 'system'
type Status = 'sending' | 'sent' | 'error'

export interface ChatMessage {
    id: string
    role: Role
    content: string
    timestamp: string
    status?: Status
}

export interface GeneratedPRD {
    project: string
    branchName: string
    description: string
    userStories: Array<{ id: string, title: string, description: string, acceptanceCriteria: string[], priority: number }>
}

interface RalphChatTaskResponse {
    task_id?: string
    status?: string
}

interface RalphTaskState {
    status?: string
    result?: string
    output?: string
    error?: string
}

export function useChatScroll() {
    const messagesEndRef = useRef<HTMLDivElement>(null)
    const scrollToBottom = useCallback(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [])
    return { messagesEndRef, scrollToBottom }
}

/**
 * Parse streaming response that may contain JSON events like:
 * {"type":"step_start",...}
 * {"type":"text","part":{"text":"actual content"}}
 * {"type":"step_finish",...}
 * 
 * Returns only the actual text content.
 */
function parseStreamingResponse(response: string): string {
    if (!response) return ''
    
    // If it doesn't look like streaming JSON, return as-is
    if (!response.includes('"type"')) {
        return response
    }
    
    const textParts: string[] = []
    
    // Try to find and parse JSON objects in the response
    // They may be on separate lines or concatenated
    const jsonPattern = /\{[^{}]*"type"\s*:\s*"[^"]+(?:"[^{}]*\{[^{}]*\})*[^{}]*\}/g
    const matches = response.match(jsonPattern) || []
    
    for (const match of matches) {
        try {
            const parsed = JSON.parse(match)
            
            // Extract text from "text" type events
            if (parsed.type === 'text') {
                if (parsed.part?.text) {
                    textParts.push(parsed.part.text)
                } else if (typeof parsed.text === 'string') {
                    textParts.push(parsed.text)
                }
            }
        } catch {
            // Try nested parsing for complex objects
            try {
                // Look for text field in partial JSON
                const textMatch = match.match(/"text"\s*:\s*"((?:[^"\\]|\\.)*)"/)?.[1]
                if (textMatch && !match.includes('"type":"step_')) {
                    textParts.push(textMatch.replace(/\\n/g, '\n').replace(/\\"/g, '"').replace(/\\\\/g, '\\'))
                }
            } catch {
                // Ignore parsing errors
            }
        }
    }
    
    // If we extracted text parts, join them
    if (textParts.length > 0) {
        return textParts.join('')
    }
    
    // Fallback: try regex extraction for the "text" field in "type":"text" events
    // Match: "type":"text"...followed by..."text":"actual content"
    const regex = /"type"\s*:\s*"text"[^}]*?"text"\s*:\s*"((?:[^"\\]|\\.)*)"/g
    let match
    while ((match = regex.exec(response)) !== null) {
        if (match[1]) {
            textParts.push(match[1].replace(/\\n/g, '\n').replace(/\\"/g, '"').replace(/\\\\/g, '\\'))
        }
    }
    
    if (textParts.length > 0) {
        return textParts.join('')
    }
    
    // Last resort: return original (might be plain text)
    return response
}

function extractOutputText(payload: unknown): string {
    if (typeof payload === 'string') return payload
    if (!payload || typeof payload !== 'object') return ''

    const event = payload as Record<string, unknown>
    if (typeof event.output === 'string') return event.output
    if (typeof event.content === 'string') return event.content
    if (typeof event.message === 'string') return event.message
    if (typeof event.text === 'string') return event.text
    return ''
}

function buildTaskStreamUrl(baseApiUrl: string, taskId: string, accessToken?: string): string {
    const absoluteBaseApiUrl =
        baseApiUrl.startsWith('/') ? `${window.location.origin}${baseApiUrl}` : baseApiUrl
    const baseUrl = absoluteBaseApiUrl.replace(/\/+$/, '')
    const sseUrl = new URL(`${baseUrl}/v1/agent/tasks/${encodeURIComponent(taskId)}/output/stream`)

    if (accessToken) {
        sseUrl.searchParams.set('access_token', accessToken)
    }

    return sseUrl.toString()
}

const PRD_SYSTEM_PROMPT = `You are a helpful assistant that helps users create Product Requirements Documents (PRDs) for software development.

Your role is to:
1. Ask clarifying questions about the feature/project
2. Understand the user's requirements
3. Generate a structured PRD with user stories

When you have enough information, generate a PRD in this JSON format:
\`\`\`json
{
  "project": "Project Name",
  "branchName": "feature/branch-name",
  "description": "Brief description of the feature",
  "userStories": [
    {
      "id": "US-001",
      "title": "Story title",
      "description": "As a [user], I want [feature] so that [benefit]",
      "acceptanceCriteria": ["Criteria 1", "Criteria 2"],
      "priority": 1
    }
  ]
}
\`\`\`

Keep responses concise. Ask one or two questions at a time. When ready to generate the PRD, include the JSON block in your response.`

export function useAIPRDChat(selectedWorkspace: string) {
    const { data: session } = useSession()
    const typedSession = session as any
    const { tenantFetch, apiUrl, upstreamApiUrl } = useTenantApi()
    const [messages, setMessages] = useState<ChatMessage[]>([])
    const [isLoading, setIsLoading] = useState(false)
    const [generatedPRD, setGeneratedPRD] = useState<GeneratedPRD | null>(null)
    const { messagesEndRef, scrollToBottom } = useChatScroll()
    const { selectedModel, selectedWorker } = useRalphStore()
    const streamRef = useRef<EventSource | null>(null)

    useEffect(() => { scrollToBottom() }, [messages, scrollToBottom])

    const closeActiveStream = useCallback(() => {
        if (!streamRef.current) return
        streamRef.current.close()
        streamRef.current = null
    }, [])

    useEffect(() => () => {
        closeActiveStream()
    }, [closeActiveStream])

    const getAccessToken = useCallback(() => {
        if (typedSession?.accessToken) return typedSession.accessToken as string
        if (typeof window === 'undefined') return undefined
        return (
            localStorage.getItem('a2a_token') ||
            localStorage.getItem('access_token') ||
            undefined
        )
    }, [typedSession?.accessToken])

    const fetchTaskState = useCallback(async (taskId: string): Promise<RalphTaskState> => {
        const { data, error } = await tenantFetch<RalphTaskState>(`/v1/agent/tasks/${encodeURIComponent(taskId)}`)
        if (error || !data) {
            throw new Error(error || 'Failed to fetch task status')
        }
        return data
    }, [tenantFetch])

    const waitForTaskCompletion = useCallback(async (
        taskId: string,
        maxAttempts = 120,
        intervalMs = 1000
    ): Promise<RalphTaskState> => {
        for (let attempt = 0; attempt < maxAttempts; attempt++) {
            const task = await fetchTaskState(taskId)
            const status = task.status

            if (status === 'completed' || status === 'failed' || status === 'cancelled') {
                return task
            }

            await new Promise((resolve) => setTimeout(resolve, intervalMs))
        }

        throw new Error('Task timed out - no workers available to process request')
    }, [fetchTaskState])

    const streamTaskResponse = useCallback(async (taskId: string, aiMsgId: string): Promise<string> => {
        if (typeof window === 'undefined') {
            const task = await waitForTaskCompletion(taskId)
            return parseStreamingResponse(task.result || task.output || '')
        }

        closeActiveStream()

        const accessToken = getAccessToken()
        const streamBaseUrl =
            process.env.NEXT_PUBLIC_API_URL ||
            upstreamApiUrl ||
            apiUrl ||
            'https://api.codetether.run'

        return await new Promise<string>((resolve, reject) => {
            const source = new EventSource(buildTaskStreamUrl(streamBaseUrl, taskId, accessToken))
            const timeoutId = window.setTimeout(() => {
                finalizeWithTask(true, 'Task timed out - no workers available to process request')
            }, 120000)
            let rawOutput = ''
            let settled = false

            streamRef.current = source

            const cleanup = () => {
                window.clearTimeout(timeoutId)
                source.close()
                if (streamRef.current === source) {
                    streamRef.current = null
                }
            }

            const resolveFromTask = (task: RalphTaskState) => {
                const status = task.status
                if (status === 'failed') {
                    reject(new Error(task.error || 'Task failed'))
                    return
                }
                if (status === 'cancelled') {
                    reject(new Error('Task was cancelled'))
                    return
                }

                const rawResponse =
                    task.result ||
                    task.output ||
                    rawOutput ||
                    'Task completed but no response received.'
                resolve(parseStreamingResponse(rawResponse))
            }

            const finalizeWithTask = async (allowPollingFallback: boolean, fallbackMessage?: string) => {
                if (settled) return
                settled = true
                cleanup()

                try {
                    const task = allowPollingFallback
                        ? await waitForTaskCompletion(taskId)
                        : await fetchTaskState(taskId)
                    resolveFromTask(task)
                } catch (error) {
                    reject(
                        error instanceof Error
                            ? error
                            : new Error(fallbackMessage || 'Failed to stream task output')
                    )
                }
            }

            source.addEventListener('output', (rawEvent) => {
                const event = rawEvent as MessageEvent<string>
                if (!event.data) return

                let chunk = ''
                try {
                    chunk = extractOutputText(JSON.parse(event.data))
                } catch {
                    chunk = event.data
                }

                if (!chunk) return

                rawOutput += chunk
                const parsedOutput = parseStreamingResponse(rawOutput)
                const nextContent = parsedOutput || (!rawOutput.includes('"type"') ? rawOutput : '')
                if (!nextContent) return

                setMessages((prev) =>
                    prev.map((msg) =>
                        msg.id === aiMsgId
                            ? { ...msg, content: nextContent, status: 'sent' }
                            : msg
                    )
                )
            })

            source.addEventListener('done', () => {
                void finalizeWithTask(false)
            })

            source.onerror = () => {
                void finalizeWithTask(true, 'Live stream disconnected before completion.')
            }
        })
    }, [apiUrl, closeActiveStream, fetchTaskState, getAccessToken, upstreamApiUrl, waitForTaskCompletion])

    const initializeChat = (customMessage?: string) => {
        setMessages([{
            id: generateUUID(),
            role: 'assistant',
            content: customMessage || "Hi! I'm here to help you create a Product Requirements Document (PRD). What feature or project would you like to build?",
            timestamp: new Date().toISOString(),
            status: 'sent'
        }])
        setGeneratedPRD(null)
    }

    const loadSession = (sessionMessages: Array<{ role: 'user' | 'assistant'; content: string; timestamp: string }>) => {
        const loaded: ChatMessage[] = sessionMessages.map(m => ({
            id: generateUUID(),
            role: m.role,
            content: m.content,
            timestamp: m.timestamp,
            status: 'sent' as Status
        }))
        setMessages(loaded)
        
        // Try to extract PRD from the last assistant message
        const lastAssistant = [...loaded].reverse().find(m => m.role === 'assistant')
        if (lastAssistant?.content.includes('```json')) {
            try {
                const jsonMatch = lastAssistant.content.match(/```json\s*([\s\S]*?)\s*```/)
                if (jsonMatch) {
                    const prd = JSON.parse(jsonMatch[1])
                    setGeneratedPRD(prd)
                }
            } catch {
                // Ignore parse errors
            }
        }
    }

    const sendMessage = async (userMessage: string) => {
        if (!userMessage.trim() || isLoading) return

        const userMsgId = generateUUID()
        setMessages(prev => [...prev, {
            id: userMsgId, role: 'user', content: userMessage, timestamp: new Date().toISOString(), status: 'sent'
        }])

        const aiMsgId = generateUUID()
        setMessages(prev => [...prev, {
            id: aiMsgId, role: 'assistant', content: '', timestamp: new Date().toISOString(), status: 'sending'
        }])
        setIsLoading(true)

        try {
            // Build conversation history for the chat endpoint
            const history = messages.map(m => ({
                role: m.role,
                content: m.content
            }))

            const { data: taskData, error: taskError } = await tenantFetch<RalphChatTaskResponse>('/v1/ralph/chat', {
                method: 'POST',
                body: JSON.stringify({
                    message: userMessage,
                    conversation_id: 'prd-builder',
                    history: history,
                    model: selectedModel || undefined,
                    worker_id: selectedWorker || undefined,
                    // Backend request key is still `codebase_id` for compatibility.
                    codebase_id: selectedWorkspace && selectedWorkspace !== 'global' ? selectedWorkspace : undefined,
                }),
            })

            if (taskError || !taskData?.task_id) {
                throw new Error(taskError || 'Failed to create PRD chat task')
            }

            const fullResponse = await streamTaskResponse(taskData.task_id, aiMsgId)

            setMessages(prev => prev.map(msg => 
                msg.id === aiMsgId ? { ...msg, content: fullResponse, status: 'sent' } : msg
            ))

            // Try to extract PRD JSON if present
            if (fullResponse.includes('```json')) {
                try {
                    const jsonMatch = fullResponse.match(/```json\s*([\s\S]*?)\s*```/)
                    if (jsonMatch) {
                        const prd = JSON.parse(jsonMatch[1])
                        setGeneratedPRD(prd)
                    }
                } catch {
                    // Ignore JSON parse errors
                }
            }
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'An error occurred'
            setMessages(prev => prev.map(msg => 
                msg.id === aiMsgId ? { ...msg, content: 'Error: ' + errorMessage, status: 'error' } : msg
            ))
        } finally {
            setIsLoading(false)
        }
    }

    return { messages, isLoading, generatedPRD, setGeneratedPRD, sendMessage, initializeChat, loadSession, messagesEndRef }
}
