'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { createGlobalTaskV1AgentTasksPost, getTaskV1AgentTasksTaskIdGet } from '@/lib/api'

// Types
interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  status?: 'sending' | 'sent' | 'error'
  taskId?: string
  originalMessage?: string // For retry functionality - stores the original user message
}

interface TaskResponse {
  id: string
  task_id?: string // Some endpoints return task_id instead of id
  title: string
  status: string
  result?: string
  description?: string
}

// Helper to get task ID from response (handles both 'id' and 'task_id' fields)
function getTaskId(response: TaskResponse): string {
  return response.id || response.task_id || ''
}

// LocalStorage Keys
const STORAGE_KEY_MESSAGES = 'intercom-chat-messages'
const STORAGE_KEY_CONVERSATION_ID = 'intercom-chat-conversation-id'

// Timeout configuration
const TIMEOUT_MS = 60000 // 60 seconds timeout

// Serializable message type for localStorage (Date as string)
interface StoredMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  status?: 'sending' | 'sent' | 'error'
  taskId?: string
  originalMessage?: string
}

// Error types for better user messaging
type ErrorType = 'network' | 'timeout' | 'api' | 'unknown'

interface ErrorInfo {
  type: ErrorType
  message: string
  originalMessage?: string
}

function getErrorInfo(error: unknown, originalMessage?: string): ErrorInfo {
  if (error instanceof Error) {
    if (error.message === 'Request timed out after 60 seconds') {
      return {
        type: 'timeout',
        message: 'Request timed out after 60 seconds. Please try again.',
        originalMessage,
      }
    }
    if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) {
      return {
        type: 'network',
        message: 'Network error. Please check your connection and try again.',
        originalMessage,
      }
    }
    if (error.message.includes('Failed to create task') || error.message.includes('Failed to get task')) {
      return {
        type: 'api',
        message: `API error: ${error.message}`,
        originalMessage,
      }
    }
    return {
      type: 'unknown',
      message: error.message,
      originalMessage,
    }
  }
  return {
    type: 'unknown',
    message: 'An unexpected error occurred. Please try again.',
    originalMessage,
  }
}

function ChatIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={1.5}
      stroke="currentColor"
      className={className}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M8.625 12a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H8.25m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H12m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 0 1-2.555-.337A5.972 5.972 0 0 1 5.41 20.97a5.969 5.969 0 0 1-.474-.065 4.48 4.48 0 0 0 .978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25Z"
      />
    </svg>
  )
}

function CloseIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={1.5}
      stroke="currentColor"
      className={className}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M6 18 18 6M6 6l12 12"
      />
    </svg>
  )
}

function SendIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={1.5}
      stroke="currentColor"
      className={className}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M6 12 3.269 3.125A59.769 59.769 0 0 1 21.485 12 59.768 59.768 0 0 1 3.27 20.875L5.999 12Zm0 0h7.5"
      />
    </svg>
  )
}

function RetryIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={1.5}
      stroke="currentColor"
      className={className}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99"
      />
    </svg>
  )
}

function LoadingIndicator() {
  return (
    <div className="flex items-center space-x-1.5 px-4 py-2">
      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.3s]" />
      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.15s]" />
      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
    </div>
  )
}

async function createTask(prompt: string): Promise<TaskResponse> {
  const result = await createGlobalTaskV1AgentTasksPost({
    body: {
      title: `Chat: ${prompt.substring(0, 50)}${prompt.length > 50 ? '...' : ''}`,
      prompt: prompt,
      agent_type: 'build',
    },
  })

  if (!result.data) {
    throw new Error('Failed to create task: No data returned')
  }

  const data = result.data as any
  return {
    id: data.id,
    task_id: data.task_id,
    title: data.title,
    status: data.status,
    result: data.result,
    description: data.description,
  }
}

async function getTask(taskId: string): Promise<TaskResponse> {
  const result = await getTaskV1AgentTasksTaskIdGet({
    path: { task_id: taskId },
  })

  if (!result.data) {
    throw new Error('Failed to get task: No data returned')
  }

  const data = result.data as any
  return {
    id: data.id,
    task_id: data.task_id,
    title: data.title,
    status: data.status,
    result: data.result,
    description: data.description,
  }
}

async function pollForCompletion(
  taskId: string,
  onUpdate?: (task: TaskResponse) => void
): Promise<TaskResponse> {
  const startTime = Date.now()
  const intervalMs = 1000

  while (Date.now() - startTime < TIMEOUT_MS) {
    const task = await getTask(taskId)

    if (onUpdate) {
      onUpdate(task)
    }

    if (task.status === 'completed' || task.status === 'failed' || task.status === 'cancelled') {
      return task
    }

    await new Promise((resolve) => setTimeout(resolve, intervalMs))
  }

  throw new Error('Request timed out after 60 seconds')
}

export function IntercomChat() {
  const [isOpen, setIsOpen] = useState(false)
  const [message, setMessage] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [conversationId, setConversationId] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)

  // Restore messages and conversation ID from localStorage on mount
  useEffect(() => {
    try {
      const storedMessages = localStorage.getItem(STORAGE_KEY_MESSAGES)
      const storedConversationId = localStorage.getItem(STORAGE_KEY_CONVERSATION_ID)

      if (storedMessages) {
        const parsed: StoredMessage[] = JSON.parse(storedMessages)
        // Convert timestamp strings back to Date objects and filter out incomplete messages
        const restoredMessages: Message[] = parsed
          .filter((msg) => msg.status !== 'sending') // Don't restore messages that were sending
          .map((msg) => ({
            ...msg,
            timestamp: new Date(msg.timestamp),
          }))
        setMessages(restoredMessages)
      }

      if (storedConversationId) {
        setConversationId(storedConversationId)
      } else {
        // Generate a new conversation ID if none exists
        const newConversationId = `conv-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`
        setConversationId(newConversationId)
        localStorage.setItem(STORAGE_KEY_CONVERSATION_ID, newConversationId)
      }
    } catch (error) {
      console.error('Failed to restore chat history from localStorage:', error)
    }
  }, [])

  // Persist messages to localStorage whenever they change
  useEffect(() => {
    try {
      // Convert Date objects to strings for storage
      const messagesToStore: StoredMessage[] = messages.map((msg) => ({
        ...msg,
        timestamp: msg.timestamp.toISOString(),
      }))
      localStorage.setItem(STORAGE_KEY_MESSAGES, JSON.stringify(messagesToStore))
    } catch (error) {
      console.error('Failed to save chat history to localStorage:', error)
    }
  }, [messages])

  // Clear chat handler - resets localStorage and state
  const handleClearChat = useCallback(() => {
    setMessages([])
    localStorage.removeItem(STORAGE_KEY_MESSAGES)
    // Generate a new conversation ID for fresh threading
    const newConversationId = `conv-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`
    setConversationId(newConversationId)
    localStorage.setItem(STORAGE_KEY_CONVERSATION_ID, newConversationId)
  }, [])

  // Auto-scroll to bottom when messages change
  const scrollToBottom = useCallback(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, isLoading, scrollToBottom])

  const sendMessage = useCallback(async (userMessage: string, isRetry = false) => {
    // Don't send empty messages
    if (!userMessage.trim()) {
      return
    }

    // Only add user message if this is not a retry
    if (!isRetry) {
      const userMsgId = `user-${Date.now()}`
      const userMsg: Message = {
        id: userMsgId,
        role: 'user',
        content: userMessage,
        timestamp: new Date(),
        status: 'sent',
      }
      setMessages((prev) => [...prev, userMsg])
    }

    setIsLoading(true)

    // Add placeholder for AI response
    const aiMsgId = `assistant-${Date.now()}`
    const aiMsg: Message = {
      id: aiMsgId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      status: 'sending',
      originalMessage: userMessage, // Store for retry
    }
    setMessages((prev) => [...prev, aiMsg])

    try {
      // Create task via POST /v1/agent/tasks
      const task = await createTask(userMessage)
      const taskId = getTaskId(task)

      if (!taskId) {
        throw new Error('Failed to create task: no task ID returned')
      }

      // Update the placeholder with taskId
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === aiMsgId
            ? { ...msg, taskId: taskId }
            : msg
        )
      )

      // Poll for completion with timeout
      const completedTask = await pollForCompletion(taskId)

      // Update AI message with result
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === aiMsgId
            ? {
              ...msg,
              content: completedTask.result || 'No response received',
              status: 'sent',
              originalMessage: undefined, // Clear retry info on success
            }
            : msg
        )
      )
    } catch (error) {
      // Get detailed error info
      const errorInfo = getErrorInfo(error, userMessage)

      // Update the AI message placeholder to show error
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === aiMsgId
            ? {
              ...msg,
              content: errorInfo.message,
              status: 'error',
              originalMessage: userMessage, // Keep for retry
            }
            : msg
        )
      )
    } finally {
      setIsLoading(false)
    }
  }, [])

  // Retry handler for failed messages
  const handleRetry = useCallback((originalMessage: string, errorMessageId: string) => {
    // Remove the error message
    setMessages((prev) => prev.filter((msg) => msg.id !== errorMessageId))
    // Resend the message as a retry (don't add user message again)
    sendMessage(originalMessage, true)
  }, [sendMessage])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    // Don't send empty messages or while loading
    if (!message.trim() || isLoading) {
      return
    }
    sendMessage(message.trim())
    setMessage('')
  }

  // User message style: right-aligned with cyan gradient
  const getUserMessageStyle = () => {
    return 'bg-gradient-to-r from-cyan-600 to-cyan-500 text-white rounded-2xl rounded-br-md'
  }

  // AI message style: left-aligned with gray background
  const getAIMessageStyle = (status?: string) => {
    if (status === 'error') {
      return 'bg-red-100 dark:bg-red-900/50 text-red-700 dark:text-red-200 rounded-2xl rounded-bl-md'
    }
    return 'bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-gray-100 rounded-2xl rounded-bl-md'
  }

  return (
    <div className="fixed bottom-6 right-6 z-50">
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className="absolute bottom-[calc(60px+16px)] right-0 w-[400px] h-[500px] bg-white dark:bg-gray-900 rounded-2xl shadow-2xl border border-gray-200 dark:border-gray-700 flex flex-col overflow-hidden"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-cyan-600 to-cyan-500 text-white">
              <h3 className="font-semibold text-base">Chat with us</h3>
              <div className="flex items-center gap-2">
                {messages.length > 0 && (
                  <button
                    onClick={handleClearChat}
                    className="px-2 py-1 text-xs rounded-full hover:bg-white/20 transition-colors"
                    aria-label="Clear chat"
                  >
                    Clear
                  </button>
                )}
                <button
                  onClick={() => setIsOpen(false)}
                  className="p-1 rounded-full hover:bg-white/20 transition-colors"
                  aria-label="Close chat"
                >
                  <CloseIcon className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Message Area */}
            <div
              ref={messagesContainerRef}
              className="flex-1 p-4 overflow-y-auto bg-gray-50 dark:bg-gray-800"
            >
              {messages.length === 0 ? (
                <div className="text-center text-gray-500 dark:text-gray-400 text-sm mt-8">
                  <p>Welcome! How can I help you today?</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {messages.map((msg) => (
                    <div
                      key={msg.id}
                      className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div
                        className={`max-w-[80%] px-4 py-2 text-sm ${msg.role === 'user'
                            ? getUserMessageStyle()
                            : getAIMessageStyle(msg.status)
                          }`}
                      >
                        {msg.status === 'sending' ? (
                          <LoadingIndicator />
                        ) : (
                          <>
                            <p className="whitespace-pre-wrap">{msg.content}</p>
                            {/* Retry button for failed messages */}
                            {msg.status === 'error' && msg.originalMessage && (
                              <button
                                onClick={() => handleRetry(msg.originalMessage!, msg.id)}
                                disabled={isLoading}
                                className="mt-2 flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-red-600 dark:text-red-300 bg-red-50 dark:bg-red-900/30 hover:bg-red-100 dark:hover:bg-red-900/50 rounded-full transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                                aria-label="Retry sending message"
                              >
                                <RetryIcon className="w-3.5 h-3.5" />
                                Retry
                              </button>
                            )}
                          </>
                        )}
                      </div>
                    </div>
                  ))}
                  {/* Scroll anchor */}
                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>

            {/* Input Field */}
            <form onSubmit={handleSubmit} className="p-3 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="Type a message..."
                  disabled={isLoading}
                  className="flex-1 px-4 py-2 rounded-full border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent disabled:opacity-50"
                />
                <button
                  type="submit"
                  disabled={!message.trim() || isLoading}
                  className="p-2 rounded-full bg-gradient-to-r from-cyan-600 to-cyan-500 text-white hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-opacity"
                  aria-label="Send message"
                >
                  <SendIcon className="w-5 h-5" />
                </button>
              </div>
            </form>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Floating Button */}
      <motion.button
        onClick={() => setIsOpen(!isOpen)}
        className="w-[60px] h-[60px] rounded-full bg-gradient-to-r from-cyan-600 to-cyan-500 text-white shadow-lg hover:opacity-90 transition-opacity flex items-center justify-center"
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        aria-label={isOpen ? 'Close chat' : 'Open chat'}
      >
        <AnimatePresence mode="wait">
          {isOpen ? (
            <motion.div
              key="close"
              initial={{ rotate: -90, opacity: 0 }}
              animate={{ rotate: 0, opacity: 1 }}
              exit={{ rotate: 90, opacity: 0 }}
              transition={{ duration: 0.15 }}
            >
              <CloseIcon className="w-7 h-7" />
            </motion.div>
          ) : (
            <motion.div
              key="chat"
              initial={{ rotate: 90, opacity: 0 }}
              animate={{ rotate: 0, opacity: 1 }}
              exit={{ rotate: -90, opacity: 0 }}
              transition={{ duration: 0.15 }}
            >
              <ChatIcon className="w-7 h-7" />
            </motion.div>
          )}
        </AnimatePresence>
      </motion.button>
    </div>
  )
}
