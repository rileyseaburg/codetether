import { useState, useRef, useEffect, useCallback } from 'react'
import { generateUUID } from './utils'
import { useRalphStore } from './store'
import { prdChatV1RalphChatPost, getTaskV1AgentTasksTaskIdGet } from '@/lib/api'

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
    const [messages, setMessages] = useState<ChatMessage[]>([])
    const [isLoading, setIsLoading] = useState(false)
    const [generatedPRD, setGeneratedPRD] = useState<GeneratedPRD | null>(null)
    const { messagesEndRef, scrollToBottom } = useChatScroll()
    const { selectedModel, selectedWorker } = useRalphStore()

    useEffect(() => { scrollToBottom() }, [messages, scrollToBottom])

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

            const { data: taskData } = await prdChatV1RalphChatPost({
                body: {
                    message: userMessage,
                    conversation_id: 'prd-builder',
                    history: history,
                    model: selectedModel || undefined,
                    worker_id: selectedWorker || undefined,
                    // Backend request key is still `codebase_id` for compatibility.
                    codebase_id: selectedWorkspace && selectedWorkspace !== 'global' ? selectedWorkspace : undefined,
                }
            })

            const taskId = (taskData as { task_id: string }).task_id

            // Poll for task completion
            let fullResponse = ''
            let attempts = 0
            const maxAttempts = 120 // 2 minutes max

            while (attempts < maxAttempts) {
                await new Promise(resolve => setTimeout(resolve, 1000))
                attempts++

                const statusResult = await getTaskV1AgentTasksTaskIdGet({
                    path: { task_id: taskId },
                })

                if (!statusResult.data) continue

                const data = statusResult.data as any
                const status = data.status

                if (status === 'completed') {
                    const rawResponse = data.result || data.output || 'Task completed but no response received.'
                    fullResponse = parseStreamingResponse(rawResponse)
                    break
                } else if (status === 'failed') {
                    throw new Error(data.error || 'Task failed')
                } else if (status === 'cancelled') {
                    throw new Error('Task was cancelled')
                }

                if (data.output) {
                    const parsedOutput = parseStreamingResponse(data.output)
                    setMessages(prev => prev.map(msg =>
                        msg.id === aiMsgId ? { ...msg, content: parsedOutput } : msg
                    ))
                }
            }

            if (!fullResponse && attempts >= maxAttempts) {
                throw new Error('Task timed out - no workers available to process request')
            }

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
