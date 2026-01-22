'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useRalphStore, useAvailableModels, type PRD, type UserStory } from './store'

// ============================================================================
// Types
// ============================================================================

interface ChatMessage {
    id: string
    role: 'user' | 'assistant' | 'system'
    content: string
    timestamp: string
    status?: 'sending' | 'sent' | 'error'
}

interface AIPRDBuilderProps {
    onPRDComplete: (prd: PRD) => void
    onCancel: () => void
    onSwitchToManual: () => void
}

interface GeneratedPRD {
    project: string
    branchName: string
    description: string
    userStories: Array<{
        id: string
        title: string
        description: string
        acceptanceCriteria: string[]
        priority: number
    }>
}

// ============================================================================
// Icons
// ============================================================================

function SendIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
        </svg>
    )
}

function SparklesIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
        </svg>
    )
}

function CloseIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
    )
}

function DocumentIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
    )
}

function CheckCircleIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
    )
}

function EditIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
        </svg>
    )
}

// ============================================================================
// Loading Dots Component
// ============================================================================

function LoadingDots() {
    return (
        <div className="flex space-x-1.5 items-center">
            <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce [animation-delay:-0.3s]" />
            <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce [animation-delay:-0.15s]" />
            <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" />
        </div>
    )
}

// ============================================================================
// API Configuration
// ============================================================================

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.codetether.run'

// System prompt for the AI assistant
const PRD_ASSISTANT_PROMPT = `You are a helpful product requirements document (PRD) assistant. Your job is to help users create well-structured PRDs by asking them questions about their feature.

IMPORTANT: You are having a conversation with the user. Ask questions ONE AT A TIME to gather information. Be conversational and friendly.

Your goal is to gather enough information to create a PRD with:
1. Project name
2. Feature description
3. Branch name (auto-generated from project name, like "ralph/feature-name")
4. User stories with acceptance criteria

Start by asking what feature they want to build. Then progressively ask about:
- Who is the target user/persona?
- What problem does this solve?
- What are the key user actions/workflows?
- What are the technical requirements?

After gathering enough information (usually 4-6 exchanges), offer to generate the PRD.

When the user confirms they want to generate the PRD, respond with ONLY a JSON block in this exact format:
\`\`\`json
{
  "type": "prd",
  "project": "ProjectName",
  "branchName": "ralph/feature-name",
  "description": "Brief description of the feature",
  "userStories": [
    {
      "id": "US-001",
      "title": "Story title",
      "description": "As a [user], I want to [action] so that [benefit]",
      "acceptanceCriteria": ["Criterion 1", "Criterion 2", "Typecheck passes"],
      "priority": 1
    }
  ]
}
\`\`\`

Always include "Typecheck passes" as the last acceptance criterion for every story.
Order stories by dependency - database changes first, then API, then UI.
Keep stories small and focused - each should be completable in one iteration.`

// ============================================================================
// UUID Generator
// ============================================================================

function generateUUID(): string {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
        return crypto.randomUUID()
    }
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
        const r = Math.random() * 16 | 0
        const v = c === 'x' ? r : (r & 0x3 | 0x8)
        return v.toString(16)
    })
}

// ============================================================================
// API Functions
// ============================================================================

interface TaskResponse {
    id: string
    task_id?: string
    title: string
    status: string
    result?: string
}

async function createTask(prompt: string, conversationHistory: ChatMessage[]): Promise<TaskResponse> {
    // Build conversation context
    const context = conversationHistory
        .filter(m => m.role !== 'system')
        .map(m => `${m.role === 'user' ? 'User' : 'Assistant'}: ${m.content}`)
        .join('\n\n')

    const fullPrompt = `${PRD_ASSISTANT_PROMPT}

Previous conversation:
${context}

User's latest message: ${prompt}

Respond naturally to continue the conversation. If you have enough information and the user wants to generate the PRD, output the JSON block.`

    const response = await fetch(`${API_URL}/v1/opencode/tasks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            title: `PRD Builder: ${prompt.substring(0, 50)}${prompt.length > 50 ? '...' : ''}`,
            prompt: fullPrompt,
            agent_type: 'general',
        }),
    })

    if (!response.ok) {
        throw new Error(`Failed to create task: ${response.statusText}`)
    }

    return response.json()
}

async function getTask(taskId: string): Promise<TaskResponse> {
    const response = await fetch(`${API_URL}/v1/opencode/tasks/${taskId}`)
    if (!response.ok) {
        throw new Error(`Failed to get task: ${response.statusText}`)
    }
    return response.json()
}

// Parse OpenCode result to extract text
function parseOpenCodeResult(result: string): string {
    if (!result) return 'No response received'
    
    if (!result.trim().startsWith('{') && !result.includes('{"type":')) {
        return result
    }
    
    const textParts: string[] = []
    const lines = result.split('\n').filter(line => line.trim())
    
    for (const line of lines) {
        try {
            const parsed = JSON.parse(line)
            if (parsed.type === 'text' && parsed.part?.text) {
                textParts.push(parsed.part.text)
            } else if (parsed.type === 'assistant' && parsed.part?.text) {
                textParts.push(parsed.part.text)
            } else if (parsed.text) {
                textParts.push(parsed.text)
            } else if (parsed.content) {
                textParts.push(parsed.content)
            }
        } catch {
            if (!line.trim().startsWith('{')) {
                textParts.push(line)
            }
        }
    }
    
    if (textParts.length > 0) {
        return textParts.join('')
    }
    
    return result.length > 500 ? result.substring(0, 500) + '...' : result
}

async function pollForCompletion(taskId: string, maxAttempts = 120, intervalMs = 1000): Promise<TaskResponse> {
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
        const task = await getTask(taskId)
        if (task.status === 'completed' || task.status === 'failed' || task.status === 'cancelled') {
            return task
        }
        await new Promise(resolve => setTimeout(resolve, intervalMs))
    }
    throw new Error('Task polling timed out')
}

// ============================================================================
// PRD Parser
// ============================================================================

function extractPRDFromResponse(response: string): GeneratedPRD | null {
    // Try to find JSON block in the response
    const jsonMatch = response.match(/```json\s*([\s\S]*?)\s*```/)
    if (jsonMatch) {
        try {
            const parsed = JSON.parse(jsonMatch[1])
            if (parsed.type === 'prd' && parsed.project && parsed.userStories) {
                return parsed as GeneratedPRD
            }
        } catch {
            // JSON parsing failed
        }
    }
    
    // Try to find raw JSON object
    const jsonObjectMatch = response.match(/\{[\s\S]*"type"\s*:\s*"prd"[\s\S]*\}/)
    if (jsonObjectMatch) {
        try {
            const parsed = JSON.parse(jsonObjectMatch[0])
            if (parsed.project && parsed.userStories) {
                return parsed as GeneratedPRD
            }
        } catch {
            // JSON parsing failed
        }
    }
    
    return null
}

// ============================================================================
// Component
// ============================================================================

export function AIPRDBuilder({ onPRDComplete, onCancel, onSwitchToManual }: AIPRDBuilderProps) {
    const { selectedModel, setSelectedModel, loadingAgents } = useRalphStore()
    const availableModels = useAvailableModels()
    
    const [messages, setMessages] = useState<ChatMessage[]>([
        {
            id: generateUUID(),
            role: 'assistant',
            content: "Hi! I'm here to help you create a Product Requirements Document (PRD). Let's start with the basics - what feature or project would you like to build?",
            timestamp: new Date().toISOString(),
            status: 'sent'
        }
    ])
    const [input, setInput] = useState('')
    const [isLoading, setIsLoading] = useState(false)
    const [generatedPRD, setGeneratedPRD] = useState<GeneratedPRD | null>(null)
    const [showPreview, setShowPreview] = useState(false)
    
    const messagesEndRef = useRef<HTMLDivElement>(null)
    const inputRef = useRef<HTMLTextAreaElement>(null)

    // Auto-scroll to bottom
    const scrollToBottom = useCallback(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [])

    useEffect(() => {
        scrollToBottom()
    }, [messages, scrollToBottom])

    // Focus input on mount
    useEffect(() => {
        inputRef.current?.focus()
    }, [])

    const sendMessage = async (userMessage: string) => {
        if (!userMessage.trim() || isLoading) return

        const userMsgId = generateUUID()
        const userMsg: ChatMessage = {
            id: userMsgId,
            role: 'user',
            content: userMessage,
            timestamp: new Date().toISOString(),
            status: 'sent'
        }
        
        setMessages(prev => [...prev, userMsg])
        setInput('')
        setIsLoading(true)

        // Add placeholder for AI response
        const aiMsgId = generateUUID()
        const aiPlaceholder: ChatMessage = {
            id: aiMsgId,
            role: 'assistant',
            content: '',
            timestamp: new Date().toISOString(),
            status: 'sending'
        }
        setMessages(prev => [...prev, aiPlaceholder])

        try {
            const task = await createTask(userMessage, [...messages, userMsg])
            const taskId = task.id || task.task_id
            
            if (!taskId) {
                throw new Error('No task ID returned')
            }

            const completedTask = await pollForCompletion(taskId)
            const parsedResult = parseOpenCodeResult(completedTask.result || '')
            
            // Check if response contains a PRD
            const prd = extractPRDFromResponse(parsedResult)
            if (prd) {
                setGeneratedPRD(prd)
                setShowPreview(true)
            }
            
            // Update AI message with result
            setMessages(prev => prev.map(msg => 
                msg.id === aiMsgId
                    ? { ...msg, content: parsedResult, status: 'sent' }
                    : msg
            ))
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'An error occurred'
            setMessages(prev => prev.map(msg =>
                msg.id === aiMsgId
                    ? { ...msg, content: `Error: ${errorMessage}. Please try again.`, status: 'error' }
                    : msg
            ))
        } finally {
            setIsLoading(false)
        }
    }

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault()
        sendMessage(input)
    }

    const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            sendMessage(input)
        }
    }

    const handleUsePRD = () => {
        if (generatedPRD) {
            const prd: PRD = {
                project: generatedPRD.project,
                branchName: generatedPRD.branchName,
                description: generatedPRD.description,
                userStories: generatedPRD.userStories.map(story => ({
                    ...story,
                    passes: false
                }))
            }
            onPRDComplete(prd)
        }
    }

    const quickPrompts = [
        "I want to add user authentication",
        "I need a dashboard with analytics",
        "Create a REST API for products",
        "Build a notification system"
    ]

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
            <div className="w-full max-w-4xl max-h-[90vh] overflow-hidden rounded-xl bg-white dark:bg-gray-800 shadow-2xl flex flex-col">
                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700 bg-gradient-to-r from-purple-600 to-indigo-600">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-white/20 rounded-lg">
                            <SparklesIcon className="h-5 w-5 text-white" />
                        </div>
                        <div>
                            <h2 className="text-lg font-semibold text-white">AI PRD Assistant</h2>
                            <p className="text-sm text-purple-200">
                                Let me help you create your PRD
                            </p>
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={onSwitchToManual}
                            className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-white/80 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
                        >
                            <EditIcon className="h-4 w-4" />
                            Manual Mode
                        </button>
                        <button
                            onClick={onCancel}
                            className="p-1.5 text-white/80 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
                        >
                            <CloseIcon className="h-5 w-5" />
                        </button>
                    </div>
                </div>

                {/* Chat Area */}
                <div className="flex-1 overflow-y-auto p-4 bg-gray-50 dark:bg-gray-900 space-y-4">
                    {/* Quick prompts if no messages yet */}
                    {messages.length === 1 && (
                        <div className="mb-4">
                            <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">Quick start suggestions:</p>
                            <div className="flex flex-wrap gap-2">
                                {quickPrompts.map((prompt, i) => (
                                    <button
                                        key={i}
                                        onClick={() => sendMessage(prompt)}
                                        disabled={isLoading}
                                        className="px-3 py-1.5 text-xs bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-full text-gray-700 dark:text-gray-300 hover:border-purple-500 hover:text-purple-600 dark:hover:text-purple-400 transition-colors disabled:opacity-50"
                                    >
                                        {prompt}
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Messages */}
                    {messages.map((msg) => (
                        <div
                            key={msg.id}
                            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                        >
                            <div
                                className={`max-w-[80%] px-4 py-3 rounded-2xl text-sm ${
                                    msg.role === 'user'
                                        ? 'bg-purple-600 text-white rounded-br-md'
                                        : msg.status === 'error'
                                            ? 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 rounded-bl-md'
                                            : 'bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-bl-md shadow-sm border border-gray-100 dark:border-gray-700'
                                }`}
                            >
                                {msg.status === 'sending' ? (
                                    <LoadingDots />
                                ) : (
                                    <div className="whitespace-pre-wrap">{msg.content}</div>
                                )}
                            </div>
                        </div>
                    ))}
                    <div ref={messagesEndRef} />
                </div>

                {/* PRD Preview Panel */}
                <AnimatePresence>
                    {showPreview && generatedPRD && (
                        <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            className="border-t border-gray-200 dark:border-gray-700 bg-emerald-50 dark:bg-emerald-900/20"
                        >
                            <div className="p-4">
                                <div className="flex items-center justify-between mb-3">
                                    <div className="flex items-center gap-2">
                                        <CheckCircleIcon className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
                                        <span className="font-medium text-emerald-800 dark:text-emerald-300">PRD Generated!</span>
                                    </div>
                                    <button
                                        onClick={() => setShowPreview(false)}
                                        className="text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
                                    >
                                        Hide
                                    </button>
                                </div>
                                
                                <div className="bg-white dark:bg-gray-800 rounded-lg p-3 mb-3 border border-emerald-200 dark:border-emerald-800">
                                    <div className="flex items-center justify-between mb-2">
                                        <h4 className="font-medium text-gray-900 dark:text-white">{generatedPRD.project}</h4>
                                        <span className="text-xs font-mono text-cyan-600 dark:text-cyan-400">{generatedPRD.branchName}</span>
                                    </div>
                                    <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">{generatedPRD.description}</p>
                                    <div className="text-xs text-gray-500">
                                        {generatedPRD.userStories.length} user {generatedPRD.userStories.length === 1 ? 'story' : 'stories'}
                                    </div>
                                </div>

                                <div className="flex gap-2">
                                    <button
                                        onClick={handleUsePRD}
                                        className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-500 text-sm font-medium"
                                    >
                                        <DocumentIcon className="h-4 w-4" />
                                        Use This PRD
                                    </button>
                                    <button
                                        onClick={onSwitchToManual}
                                        className="px-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 text-sm"
                                    >
                                        Edit Manually
                                    </button>
                                </div>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Model Selection */}
                <div className="px-4 py-2 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
                    <div className="flex items-center gap-2">
                        <label className="text-xs text-gray-500 dark:text-gray-400">Model:</label>
                        <select
                            value={selectedModel}
                            onChange={(e) => setSelectedModel(e.target.value)}
                            disabled={loadingAgents}
                            className="text-xs px-2 py-1 border border-gray-200 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300"
                        >
                            <option value="">Any available</option>
                            {availableModels.map((model, idx) => (
                                <option key={`${model}-${idx}`} value={model}>{model}</option>
                            ))}
                        </select>
                    </div>
                </div>

                {/* Input Area */}
                <form onSubmit={handleSubmit} className="p-4 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
                    <div className="flex items-end gap-3">
                        <div className="flex-1 relative">
                            <textarea
                                ref={inputRef}
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyDown={handleKeyDown}
                                placeholder="Describe your feature or answer the question..."
                                disabled={isLoading}
                                rows={1}
                                className="w-full px-4 py-3 pr-12 border border-gray-200 dark:border-gray-600 rounded-xl bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent disabled:opacity-50 resize-none"
                                style={{ minHeight: '48px', maxHeight: '120px' }}
                            />
                        </div>
                        <button
                            type="submit"
                            disabled={!input.trim() || isLoading}
                            className="p-3 bg-purple-600 text-white rounded-xl hover:bg-purple-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                            <SendIcon className="h-5 w-5" />
                        </button>
                    </div>
                    <p className="mt-2 text-xs text-gray-400 dark:text-gray-500">
                        Press Enter to send, Shift+Enter for new line
                    </p>
                </form>
            </div>
        </div>
    )
}
