'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

// Types
interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  status?: 'sending' | 'sent' | 'error'
  taskId?: string
}

interface TaskResponse {
  task_id: string
  title: string
  status: string
  result?: string
  description?: string
}

// API Configuration
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

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

function LoadingIndicator() {
  return (
    <div className="flex items-center space-x-1.5 px-4 py-2">
      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.3s]" />
      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.15s]" />
      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
    </div>
  )
}

// API Functions
async function createTask(prompt: string): Promise<TaskResponse> {
  const response = await fetch(`${API_URL}/v1/opencode/tasks`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      title: `Chat: ${prompt.substring(0, 50)}${prompt.length > 50 ? '...' : ''}`,
      description: prompt,
      agent_type: 'build',
    }),
  })

  if (!response.ok) {
    throw new Error(`Failed to create task: ${response.statusText}`)
  }

  return response.json()
}

async function getTask(taskId: string): Promise<TaskResponse> {
  const response = await fetch(`${API_URL}/v1/opencode/tasks/${taskId}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  })

  if (!response.ok) {
    throw new Error(`Failed to get task: ${response.statusText}`)
  }

  return response.json()
}

async function pollForCompletion(
  taskId: string,
  onUpdate?: (task: TaskResponse) => void,
  maxAttempts = 60,
  intervalMs = 1000
): Promise<TaskResponse> {
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const task = await getTask(taskId)
    
    if (onUpdate) {
      onUpdate(task)
    }

    if (task.status === 'completed' || task.status === 'failed' || task.status === 'cancelled') {
      return task
    }

    await new Promise((resolve) => setTimeout(resolve, intervalMs))
  }

  throw new Error('Task polling timed out')
}

export function IntercomChat() {
  const [isOpen, setIsOpen] = useState(false)
  const [message, setMessage] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when messages change
  const scrollToBottom = useCallback(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, isLoading, scrollToBottom])

  const sendMessage = async (userMessage: string) => {
    const userMsgId = `user-${Date.now()}`
    const userMsg: Message = {
      id: userMsgId,
      role: 'user',
      content: userMessage,
      timestamp: new Date(),
      status: 'sent',
    }

    setMessages((prev) => [...prev, userMsg])
    setIsLoading(true)

    try {
      // Create task via POST /v1/opencode/tasks
      const task = await createTask(userMessage)

      // Add placeholder for AI response
      const aiMsgId = `assistant-${Date.now()}`
      const aiMsg: Message = {
        id: aiMsgId,
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        status: 'sending',
        taskId: task.task_id,
      }
      setMessages((prev) => [...prev, aiMsg])

      // Poll for completion
      const completedTask = await pollForCompletion(task.task_id)

      // Update AI message with result
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === aiMsgId
            ? {
                ...msg,
                content: completedTask.result || 'No response received',
                status: 'sent',
              }
            : msg
        )
      )
    } catch (error) {
      // Add error message
      const errorMsg: Message = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: error instanceof Error ? error.message : 'An error occurred',
        timestamp: new Date(),
        status: 'error',
      }
      setMessages((prev) => [...prev, errorMsg])
    } finally {
      setIsLoading(false)
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (message.trim() && !isLoading) {
      sendMessage(message.trim())
      setMessage('')
    }
  }

  // User message style: right-aligned with purple/cyan gradient
  const getUserMessageStyle = () => {
    return 'bg-gradient-to-r from-purple-500 to-cyan-500 text-white rounded-2xl rounded-br-md'
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
            <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-purple-500 to-cyan-500 text-white">
              <h3 className="font-semibold text-base">Chat with us</h3>
              <button
                onClick={() => setIsOpen(false)}
                className="p-1 rounded-full hover:bg-white/20 transition-colors"
                aria-label="Close chat"
              >
                <CloseIcon className="w-5 h-5" />
              </button>
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
                        className={`max-w-[80%] px-4 py-2 text-sm ${
                          msg.role === 'user'
                            ? getUserMessageStyle()
                            : getAIMessageStyle(msg.status)
                        }`}
                      >
                        {msg.status === 'sending' ? (
                          <LoadingIndicator />
                        ) : (
                          <p className="whitespace-pre-wrap">{msg.content}</p>
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
                  className="flex-1 px-4 py-2 rounded-full border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent disabled:opacity-50"
                />
                <button
                  type="submit"
                  disabled={!message.trim() || isLoading}
                  className="p-2 rounded-full bg-gradient-to-r from-purple-500 to-cyan-500 text-white hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-opacity"
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
        className="w-[60px] h-[60px] rounded-full bg-gradient-to-r from-purple-500 to-cyan-500 text-white shadow-lg hover:opacity-90 transition-opacity flex items-center justify-center"
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
