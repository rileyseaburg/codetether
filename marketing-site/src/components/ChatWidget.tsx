'use client'

import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import { useSession } from 'next-auth/react'
import { motion, AnimatePresence } from 'framer-motion'
import { useTenantApi } from '@/hooks/useTenantApi'
import { useWorkers, type Worker as TargetWorker } from '@/components/WorkerSelector'
import { createGlobalTaskV1AgentTasksPost, getTaskV1AgentTasksTaskIdGet } from '@/lib/api'

// Constants
const STORAGE_KEY = 'intercom-chat-messages'
const CONVERSATION_ID_KEY = 'intercom-chat-conversation-id'

// Types
interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  status?: 'sending' | 'sent' | 'error'
  taskId?: string
}

interface StoredMessages {
  messages: Message[]
  conversationId: string
}

interface TaskResponse {
  id: string
  task_id?: string
  title: string
  status: string
  result?: string
  description?: string
}

interface WorkspaceOption {
  id: string
  name: string
  path: string
  status?: string
  worker_id?: string | null
}

interface CreateTaskOptions {
  workerId?: string
  workspaceId?: string
  conversationId?: string
}

function getTaskId(response: TaskResponse): string {
  return response.id || response.task_id || ''
}

type RequestHeaders = Record<string, string> | undefined

function normalizeWorkspaceOptions(data: unknown): WorkspaceOption[] {
  const items = Array.isArray(data)
    ? data
    : Array.isArray((data as { workspaces?: unknown[] } | undefined)?.workspaces)
      ? (data as { workspaces: unknown[] }).workspaces
      : Array.isArray((data as { codebases?: unknown[] } | undefined)?.codebases)
        ? (data as { codebases: unknown[] }).codebases
        : Array.isArray((data as { data?: unknown[] } | undefined)?.data)
          ? (data as { data: unknown[] }).data
          : []

  return items
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object')
    .map((item) => ({
      id: String(item.id ?? ''),
      name: String(item.name ?? item.id ?? ''),
      path: String(item.path ?? ''),
      status: typeof item.status === 'string' ? item.status : undefined,
      worker_id: typeof item.worker_id === 'string' ? item.worker_id : null,
    }))
    .filter((item) => item.id)
}

function formatWorkerLabel(worker: TargetWorker): string {
  return (worker.name || worker.worker_id).trim()
}

function formatWorkspaceLabel(workspace: WorkspaceOption): string {
  const leaf = workspace.path.split('/').filter(Boolean).pop()
  const suffix = leaf && leaf !== workspace.name ? ` (${leaf})` : ''
  return `${workspace.name}${suffix}`
}

function normalizeTaskResponse(data: any): TaskResponse {
  const task = data?.task ?? data

  return {
    id: task?.id || task?.task_id || task?.taskId || '',
    task_id: task?.task_id || task?.taskId || task?.id,
    title: task?.title || '',
    status: task?.status || '',
    result: task?.result,
    description: task?.description || task?.detail,
  }
}

function extractErrorMessage(error: unknown): string | undefined {
  if (!error) return undefined
  if (typeof error === 'string') return error
  if (typeof error === 'object') {
    const value = error as Record<string, unknown>
    if (typeof value.detail === 'string') return value.detail
    if (typeof value.message === 'string') return value.message
    if (Array.isArray(value.detail)) {
      return value.detail
        .map((item) =>
          typeof item === 'string'
            ? item
            : typeof item === 'object' && item && 'msg' in item
              ? String((item as Record<string, unknown>).msg)
              : JSON.stringify(item)
        )
        .join('; ')
    }
  }
  return undefined
}

async function readResultPayload(result: any): Promise<any> {
  if (!result) return undefined

  if (
    typeof result === 'object' &&
    !('data' in result) &&
    !('error' in result) &&
    !('response' in result) &&
    !('request' in result)
  ) {
    return result
  }

  if (result.data !== undefined) {
    return result.data
  }

  const response = result.response
  if (!(response instanceof Response)) {
    return undefined
  }

  const contentType = response.headers.get('Content-Type') || ''
  if (contentType.includes('application/json')) {
    return response.clone().json().catch(() => undefined)
  }

  const text = await response.clone().text().catch(() => '')
  if (!text) {
    return undefined
  }

  try {
    return JSON.parse(text)
  } catch {
    return { result: text }
  }
}

// Shared icons
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
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
    </svg>
  )
}

function SendIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 12 3.269 3.125A59.769 59.769 0 0 1 21.485 12 59.768 59.768 0 0 1 3.27 20.875L5.999 12Zm0 0h7.5" />
    </svg>
  )
}

function LoadingDots() {
  return (
    <div className="flex space-x-1">
      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
    </div>
  )
}

function RetryIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" />
    </svg>
  )
}

function TrashIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" />
    </svg>
  )
}

// System context
const CODETETHER_CONTEXT = `You are a helpful assistant for CodeTether. Answer questions based on this documentation:

# CodeTether - Turn AI Agents into Production Systems

CodeTether is a **production-ready Agent-to-Agent (A2A) platform** that is **officially A2A Protocol v0.3 compliant**. Build AI agent systems that actually work in the real world.

## Key Features

### Ralph: Autonomous Development
Ralph implements entire PRDs with zero human intervention. Define user stories, Ralph writes the code, runs tests, and commits—autonomously iterating until all acceptance criteria pass.

### MCP Tool Integration
Connect to 100+ tools via Model Context Protocol. File systems, databases, APIs, and more.

### AI Coding at Scale
Deploy AI coding agents across your infrastructure using CodeTether. Automated code generation, refactoring, and testing.

### RLM (Recursive Language Models)
Process arbitrarily long contexts through recursive LLM calls. Analyze entire monorepos without context limits.

### Email Reply to Continue Tasks
Workers send email notifications when tasks complete. Reply directly to the email to continue the conversation.

### Zapier Integration
Connect CodeTether to 5,000+ apps with native Zapier integration. OAuth2 authentication, triggers, actions, and searches.

### Voice Agent
Real-time voice interactions with AI agents through LiveKit integration.

### Real-Time Streaming
Watch agents think in real-time with SSE streaming.

## Quick Start

\`\`\`bash
pip install codetether
codetether-worker --api-url https://api.codetether.run
codetether-server --host 0.0.0.0 --port 8000
\`\`\`

## Pricing
CodeTether is open source (Apache 2.0). The hosted API at api.codetether.run is free for development use.

Answer questions helpfully and concisely based on the above documentation.`

// API Functions using SDK
async function createTask(
  prompt: string,
  headers?: RequestHeaders,
  options: CreateTaskOptions = {}
): Promise<TaskResponse> {
  const metadata: Record<string, unknown> = {
    source: 'chat_widget',
    interactive: true,
  }

  if (options.workerId) {
    metadata.target_worker_id = options.workerId
  }

  if (options.conversationId) {
    metadata.conversation_id = options.conversationId
  }

  const result = await createGlobalTaskV1AgentTasksPost({
    body: {
      title: `Chat: ${prompt.substring(0, 50)}${prompt.length > 50 ? '...' : ''}`,
      prompt: `${CODETETHER_CONTEXT}\n\n---\n\nUser question: ${prompt}\n\nProvide a helpful, concise response.`,
      agent_type: 'general',
      ...(options.workspaceId ? { workspace_id: options.workspaceId } : {}),
      metadata,
    },
    headers,
  })

  const data = await readResultPayload(result)
  if (!data) {
    const detail = extractErrorMessage(result.error)
    if (detail) {
      throw new Error(`Failed to create task: ${detail}`)
    }
    if (result.response?.status) {
      throw new Error(
        `Failed to create task: HTTP ${result.response.status} ${result.response.statusText}`.trim()
      )
    }
    throw new Error('Failed to create task: No data returned')
  }

  return normalizeTaskResponse(data)
}

async function getTask(
  taskId: string,
  headers?: RequestHeaders
): Promise<TaskResponse> {
  const result = await getTaskV1AgentTasksTaskIdGet({
    path: { task_id: taskId },
    headers,
  })

  const data = await readResultPayload(result)
  if (!data) {
    const detail = extractErrorMessage(result.error)
    if (detail) {
      throw new Error(`Failed to get task: ${detail}`)
    }
    if (result.response?.status) {
      throw new Error(
        `Failed to get task: HTTP ${result.response.status} ${result.response.statusText}`.trim()
      )
    }
    throw new Error('Failed to get task: No data returned')
  }

  return normalizeTaskResponse(data)
}

function parseCodeTetherResult(result: string): string {
  if (!result) return 'No response received'
  if (!result.trim().startsWith('{')) return result

  const textParts: string[] = []
  for (const line of result.split('\n').filter(l => l.trim())) {
    try {
      const parsed = JSON.parse(line)
      if (parsed.text) textParts.push(parsed.text)
      if (parsed.content) textParts.push(parsed.content)
    } catch {
      if (!line.trim().startsWith('{')) textParts.push(line)
    }
  }

  return textParts.length ? textParts.join('') : result
}

async function pollForCompletion(
  taskId: string,
  onUpdate?: (task: TaskResponse) => void,
  maxAttempts = 60,
  intervalMs = 1000,
  headers?: RequestHeaders
): Promise<TaskResponse> {
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const task = await getTask(taskId, headers)

    if (onUpdate) onUpdate(task)

    if (task.status === 'completed' || task.status === 'failed' || task.status === 'cancelled') {
      return task
    }

    await new Promise(resolve => setTimeout(resolve, intervalMs))
  }

  throw new Error('Task polling timed out')
}

function generateConversationId(): string {
  return `conv-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`
}

function loadFromStorage(): StoredMessages | null {
  if (typeof window === 'undefined') return null
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (!stored) return null
    return JSON.parse(stored)
  } catch {
    return null
  }
}

function saveToStorage(messages: Message[], conversationId: string): void {
  if (typeof window === 'undefined') return
  try {
    const data: StoredMessages = { messages, conversationId }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
  } catch { }
}

function clearStorage(): void {
  if (typeof window === 'undefined') return
  try {
    localStorage.removeItem(STORAGE_KEY)
    localStorage.removeItem(CONVERSATION_ID_KEY)
  } catch { }
}

export function ChatWidget() {
  const { data: session } = useSession()
  const { tenantFetch } = useTenantApi()
  const typedSession = session as any
  const [isOpen, setIsOpen] = useState(false)
  const [message, setMessage] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [conversationId, setConversationId] = useState<string>('')
  const [selectedWorkerId, setSelectedWorkerId] = useState('')
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState('')
  const [workspaces, setWorkspaces] = useState<WorkspaceOption[]>([])
  const [workspacesLoading, setWorkspacesLoading] = useState(false)
  const [workspacesError, setWorkspacesError] = useState<string | null>(null)
  const [hasStoredAccessToken, setHasStoredAccessToken] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const hasRuntimeAccess = Boolean(
    typedSession?.accessToken || hasStoredAccessToken
  )
  const { workers, loading: workersLoading, error: workersError } = useWorkers(isOpen && hasRuntimeAccess)

  useEffect(() => {
    const stored = loadFromStorage()
    if (stored) {
      setMessages(stored.messages)
      setConversationId(stored.conversationId)
    } else {
      setConversationId(generateConversationId())
    }
  }, [])

  useEffect(() => {
    if (conversationId && messages.length > 0) {
      saveToStorage(messages, conversationId)
    }
  }, [messages, conversationId])

  useEffect(() => {
    if (typeof window === 'undefined') return
    setHasStoredAccessToken(Boolean(localStorage.getItem('a2a_token') || localStorage.getItem('access_token')))
  }, [typedSession?.accessToken])

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => { scrollToBottom() }, [messages, scrollToBottom])

  const clearChat = useCallback(() => {
    setMessages([])
    clearStorage()
    setConversationId(generateConversationId())
  }, [])

  const loadWorkspaces = useCallback(async () => {
    if (!isOpen || !hasRuntimeAccess) {
      setWorkspaces([])
      setWorkspacesError(null)
      setWorkspacesLoading(false)
      return
    }

    setWorkspacesLoading(true)
    setWorkspacesError(null)

    const { data, error } = await tenantFetch<unknown>('/v1/agent/workspaces/list')

    if (error) {
      setWorkspaces([])
      setWorkspacesError(error)
      setWorkspacesLoading(false)
      return
    }

    setWorkspaces(normalizeWorkspaceOptions(data))
    setWorkspacesLoading(false)
  }, [hasRuntimeAccess, isOpen, tenantFetch])

  useEffect(() => {
    loadWorkspaces()
  }, [loadWorkspaces])

  const getRequestHeaders = useCallback((): RequestHeaders => {
    const headers: Record<string, string> = {}
    const accessToken =
      typedSession?.accessToken ||
      (typeof window !== 'undefined'
        ? localStorage.getItem('a2a_token') ||
          localStorage.getItem('access_token') ||
          undefined
        : undefined)

    if (accessToken) {
      headers.Authorization = `Bearer ${accessToken}`
    }
    if (typedSession?.tenantId) {
      headers['X-Tenant-ID'] = typedSession.tenantId
    }

    return Object.keys(headers).length ? headers : undefined
  }, [typedSession?.accessToken, typedSession?.tenantId])

  const connectedWorkers = useMemo(
    () => workers.filter((worker) => worker.is_sse_connected),
    [workers]
  )

  const selectedWorker = useMemo(
    () => connectedWorkers.find((worker) => worker.worker_id === selectedWorkerId) || null,
    [connectedWorkers, selectedWorkerId]
  )

  const workerScopedWorkspaces = useMemo(() => {
    if (!selectedWorkerId) return []

    const assignedWorkspaceIds = new Set(selectedWorker?.codebases || [])

    return workspaces.filter((workspace) =>
      workspace.worker_id === selectedWorkerId || assignedWorkspaceIds.has(workspace.id)
    )
  }, [selectedWorker?.codebases, selectedWorkerId, workspaces])

  useEffect(() => {
    if (!selectedWorkerId) {
      setSelectedWorkspaceId('')
      return
    }

    if (!connectedWorkers.some((worker) => worker.worker_id === selectedWorkerId)) {
      setSelectedWorkerId('')
      setSelectedWorkspaceId('')
      return
    }

    if (!workerScopedWorkspaces.some((workspace) => workspace.id === selectedWorkspaceId)) {
      setSelectedWorkspaceId(workerScopedWorkspaces[0]?.id || '')
    }
  }, [connectedWorkers, selectedWorkerId, selectedWorkspaceId, workerScopedWorkspaces])

  const sendMessage = async (userMessage: string, isRetry = false, retryMsgId?: string) => {
    const userMsgId = isRetry ? retryMsgId! : `user-${Date.now()}`

    if (!isRetry) {
      const userMsg: Message = {
        id: userMsgId,
        role: 'user',
        content: userMessage,
        timestamp: new Date().toISOString(),
        status: 'sent',
      }
      setMessages(prev => [...prev, userMsg])
    }

    setIsLoading(true)

    if (isRetry && retryMsgId) {
      setMessages(prev => prev.filter(msg => msg.id !== retryMsgId))
    }

    try {
      const requestHeaders = getRequestHeaders()
      const task = await createTask(userMessage, requestHeaders, {
        workerId: selectedWorkerId || undefined,
        workspaceId: selectedWorkspaceId || undefined,
        conversationId,
      })
      const taskId = getTaskId(task)

      if (!taskId) {
        throw new Error('Failed to create task: no task ID returned')
      }

      const aiMsgId = `assistant-${Date.now()}`
      const aiMsg: Message = {
        id: aiMsgId,
        role: 'assistant',
        content: '',
        timestamp: new Date().toISOString(),
        status: 'sending',
        taskId: taskId,
      }
      setMessages(prev => [...prev, aiMsg])

      const completedTask = await pollForCompletion(
        taskId,
        undefined,
        60,
        1000,
        requestHeaders
      )
      const parsedResult = parseCodeTetherResult(completedTask.result || '')

      setMessages(prev =>
        prev.map(msg =>
          msg.id === aiMsgId
            ? { ...msg, content: parsedResult, status: 'sent' }
            : msg
        )
      )
    } catch (error) {
      const errorContent = error instanceof Error
        ? (error.message === 'Task polling timed out'
          ? 'Request timed out after 60 seconds. Please try again.'
          : error.message)
        : 'An error occurred'

      const errorMsg: Message = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: errorContent,
        timestamp: new Date().toISOString(),
        status: 'error',
      }
      setMessages(prev => [...prev, errorMsg])
    } finally {
      setIsLoading(false)
    }
  }

  const retryMessage = useCallback((errorMsgId: string) => {
    const errorIndex = messages.findIndex(m => m.id === errorMsgId)
    if (errorIndex === -1) return

    for (let i = errorIndex - 1; i >= 0; i--) {
      if (messages[i].role === 'user') {
        sendMessage(messages[i].content, true, errorMsgId)
        break
      }
    }
  }, [messages])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (selectedWorkerId && !selectedWorkspaceId) return
    if (message.trim() && !isLoading) {
      sendMessage(message.trim())
      setMessage('')
    }
  }

  const targetingSummary = useMemo(() => {
    if (!hasRuntimeAccess) return null
    if (!selectedWorkerId && !workersLoading && connectedWorkers.length === 0) {
      return 'No connected workers are available yet. This widget can still send a global task.'
    }
    if (!selectedWorkerId) {
      return 'Send as a global task, or choose a connected worker and one of its registered workspaces.'
    }
    if (workersLoading || workspacesLoading) {
      return 'Loading connected workers and workspaces...'
    }
    if (!selectedWorker) {
      return 'Selected worker is no longer connected.'
    }
    if (!workerScopedWorkspaces.length) {
      return 'This worker has no registered workspaces yet.'
    }
    const workspace = workerScopedWorkspaces.find((item) => item.id === selectedWorkspaceId)
    if (!workspace) {
      return 'Select a workspace registered to this worker.'
    }
    return `Tasks will run on ${formatWorkerLabel(selectedWorker)} in ${workspace.name}.`
  }, [
    hasRuntimeAccess,
    selectedWorkerId,
    connectedWorkers.length,
    workersLoading,
    workspacesLoading,
    selectedWorker,
    workerScopedWorkspaces,
    selectedWorkspaceId,
  ])

  return (
    <div className="fixed bottom-6 right-6 z-50">
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className="absolute bottom-[calc(60px+16px)] right-0 w-[400px] h-[560px] bg-white dark:bg-gray-900 rounded-2xl shadow-2xl border border-gray-200 dark:border-gray-700 flex flex-col overflow-hidden"
          >
            <div className="flex items-center justify-between px-4 py-3 bg-cyan-500 text-white">
              <h3 className="font-semibold text-base">Chat with AI</h3>
              <div className="flex items-center gap-2">
                {messages.length > 0 && (
                  <button onClick={clearChat} className="p-1 rounded-full hover:bg-white/20 transition-colors" aria-label="Clear chat" title="Clear chat history">
                    <TrashIcon className="w-5 h-5" />
                  </button>
                )}
                <button onClick={() => setIsOpen(false)} className="p-1 rounded-full hover:bg-white/20 transition-colors" aria-label="Close chat">
                  <CloseIcon className="w-5 h-5" />
                </button>
              </div>
            </div>

            {hasRuntimeAccess && (
              <div className="border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/80 px-3 py-3">
                <div className="space-y-2">
                  <div>
                    <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                      Worker
                    </label>
                    <select
                      value={selectedWorkerId}
                      onChange={(e) => setSelectedWorkerId(e.target.value)}
                      disabled={isLoading || workersLoading}
                      className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-cyan-500 disabled:opacity-50"
                    >
                      <option value="">Auto-select worker</option>
                      {connectedWorkers.map((worker) => (
                        <option key={worker.worker_id} value={worker.worker_id}>
                          {formatWorkerLabel(worker)}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                      Workspace
                    </label>
                    <select
                      value={selectedWorkspaceId}
                      onChange={(e) => setSelectedWorkspaceId(e.target.value)}
                      disabled={isLoading || !selectedWorkerId || workspacesLoading || workerScopedWorkspaces.length === 0}
                      className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-cyan-500 disabled:opacity-50"
                    >
                      <option value="">
                        {!selectedWorkerId
                          ? 'Select a worker first'
                          : workspacesLoading
                            ? 'Loading workspaces...'
                            : workerScopedWorkspaces.length === 0
                              ? 'No registered workspaces'
                              : 'Select workspace'}
                      </option>
                      {workerScopedWorkspaces.map((workspace) => (
                        <option key={workspace.id} value={workspace.id}>
                          {formatWorkspaceLabel(workspace)}
                        </option>
                      ))}
                    </select>
                  </div>

                  {(workersError || workspacesError || targetingSummary) && (
                    <p className={`text-[11px] ${workersError || workspacesError ? 'text-red-500 dark:text-red-400' : 'text-gray-500 dark:text-gray-400'}`}>
                      {workersError || workspacesError || targetingSummary}
                    </p>
                  )}
                </div>
              </div>
            )}

            <div className="flex-1 p-4 overflow-y-auto bg-gray-50 dark:bg-gray-800">
              {messages.length === 0 ? (
                <div className="text-center text-gray-500 dark:text-gray-400 text-sm mt-8">
                  <p>Welcome! How can I help you today?</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {messages.map(msg => (
                    <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                      <div className="flex flex-col items-start max-w-[80%]">
                        <div className={`px-4 py-2 rounded-2xl text-sm ${msg.role === 'user'
                            ? 'bg-cyan-500 text-white rounded-br-md'
                            : msg.status === 'error'
                              ? 'bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-200 rounded-bl-md'
                              : 'bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-gray-100 rounded-bl-md'
                          }`}>
                          {msg.status === 'sending' ? <LoadingDots /> : <p className="whitespace-pre-wrap">{msg.content}</p>}
                        </div>
                        {msg.status === 'error' && !isLoading && (
                          <button
                            onClick={() => retryMessage(msg.id)}
                            className="mt-1 flex items-center gap-1 text-xs text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 transition-colors"
                          >
                            <RetryIcon className="w-3 h-3" />
                            Retry
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>

            <form onSubmit={handleSubmit} className="p-3 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={message}
                  onChange={e => setMessage(e.target.value)}
                  placeholder={selectedWorkerId && selectedWorkspaceId ? 'Ask the selected worker...' : 'Type a message...'}
                  disabled={isLoading}
                  className="flex-1 px-4 py-2 rounded-full border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent disabled:opacity-50"
                />
                <button
                  type="submit"
                  disabled={!message.trim() || isLoading || Boolean(selectedWorkerId && !selectedWorkspaceId)}
                  className="p-2 rounded-full bg-cyan-500 text-white hover:bg-cyan-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  aria-label="Send message"
                >
                  <SendIcon className="w-5 h-5" />
                </button>
              </div>
            </form>
          </motion.div>
        )}
      </AnimatePresence>

      <motion.button
        onClick={() => setIsOpen(!isOpen)}
        className="w-[60px] h-[60px] rounded-full bg-cyan-500 text-white shadow-lg hover:bg-cyan-600 transition-colors flex items-center justify-center"
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        aria-label={isOpen ? 'Close chat' : 'Open chat'}
      >
        <AnimatePresence mode="wait">
          {isOpen ? (
            <motion.div key="close" initial={{ rotate: -90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: 90, opacity: 0 }} transition={{ duration: 0.15 }}>
              <CloseIcon className="w-7 h-7" />
            </motion.div>
          ) : (
            <motion.div key="chat" initial={{ rotate: 90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: -90, opacity: 0 }} transition={{ duration: 0.15 }}>
              <ChatIcon className="w-7 h-7" />
            </motion.div>
          )}
        </AnimatePresence>
      </motion.button>
    </div>
  )
}
