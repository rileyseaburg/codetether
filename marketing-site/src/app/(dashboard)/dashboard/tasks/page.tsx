'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { useSession } from 'next-auth/react'
import {
  Dialog,
  DialogBackdrop,
  DialogPanel,
  DialogTitle,
} from '@headlessui/react'
import { useWorkspaces } from '../sessions/hooks/useWorkspaces'
import {
  getTaskOutputV1AgentTasksTaskIdOutputGet,
  listAllTasksV1AgentTasksGet,
} from '@/lib/api'
import { useTenantApi } from '@/hooks/useTenantApi'
import { getApiAuth } from '@/lib/auth-token'
import { readTaskQueue, taskRequestError } from '@/lib/task-queue-response'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'

interface Task {
  id: string
  title?: string
  prompt?: string
  agent_type: string
  status: string
  created_at: string
  result?: string
  codebase_id?: string
  workspace_id?: string | null
  priority?: number
  started_at?: string
  completed_at?: string
  error?: string
  worker_id?: string
  metadata?: Record<string, unknown>
}

interface DispatchTaskRequest {
  title: string
  description: string
  agent_type?: string
  model?: string
  priority?: number
  metadata?: Record<string, unknown>
}

interface DispatchTaskResponse {
  task_id: string
  status: string
  event_id?: string
  dispatched_via_knative: boolean
}

type SwarmSubtaskStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'timed_out'
  | 'cancelled'
  | 'unknown'

interface SwarmSubtaskState {
  id: string
  status: SwarmSubtaskStatus
  tool?: string
  error?: string
  updatedAt: number
}

interface SwarmMonitorState {
  connected: boolean
  status: 'idle' | 'running' | 'completed' | 'failed'
  plannedSubtasks: number | null
  currentStage: number | null
  stageCompleted: number
  stageFailed: number
  speedup: number | null
  subtasks: Record<string, SwarmSubtaskState>
  recentLines: string[]
  lastUpdatedAt: number | null
  error?: string
}

const INITIAL_SWARM_MONITOR: SwarmMonitorState = {
  connected: false,
  status: 'idle',
  plannedSubtasks: null,
  currentStage: null,
  stageCompleted: 0,
  stageFailed: 0,
  speedup: null,
  subtasks: {},
  recentLines: [],
  lastUpdatedAt: null,
}

const normalizeSwarmStatus = (raw: string): SwarmSubtaskStatus => {
  const normalized = raw.trim().toLowerCase().replace(/\s+/g, '_')
  if (
    normalized === 'pending' ||
    normalized === 'running' ||
    normalized === 'completed' ||
    normalized === 'failed' ||
    normalized === 'timed_out' ||
    normalized === 'cancelled'
  ) {
    return normalized
  }
  if (normalized === 'timedout') {
    return 'timed_out'
  }
  return 'unknown'
}

const applySwarmLine = (
  state: SwarmMonitorState,
  line: string,
): SwarmMonitorState => {
  const trimmed = line.trim()
  if (!trimmed.toLowerCase().includes('[swarm]')) {
    return state
  }

  const now = Date.now()
  const next: SwarmMonitorState = {
    ...state,
    lastUpdatedAt: now,
    recentLines: [...state.recentLines, trimmed].slice(-180),
  }

  const startedMatch = trimmed.match(/started\b.*planned_subtasks=(\d+)/i)
  if (startedMatch) {
    const planned = Number(startedMatch[1])
    next.status = 'running'
    next.plannedSubtasks = Number.isFinite(planned) ? planned : null
    next.error = undefined
    return next
  }

  const stageMatch =
    trimmed.match(/stage=(\d+)\s+completed=(\d+)\s+failed=(\d+)/i) ||
    trimmed.match(
      /stage\s+(\d+)\s+complete:\s+(\d+)\s+succeeded,\s+(\d+)\s+failed/i,
    )
  if (stageMatch) {
    next.currentStage = Number(stageMatch[1]) || 0
    next.stageCompleted = Number(stageMatch[2]) || 0
    next.stageFailed = Number(stageMatch[3]) || 0
    return next
  }

  const subtaskStatusMatch =
    trimmed.match(
      /subtask(?:\s+id=|\s+)([A-Za-z0-9_-]+)\s+status=([A-Za-z_]+)/i,
    ) || trimmed.match(/subtask\s+([A-Za-z0-9_-]+)\s+->\s+([A-Za-z_]+)/i)
  if (subtaskStatusMatch) {
    const id = subtaskStatusMatch[1]
    const status = normalizeSwarmStatus(subtaskStatusMatch[2])
    next.subtasks = {
      ...next.subtasks,
      [id]: {
        ...(next.subtasks[id] ?? { id, updatedAt: now }),
        id,
        status,
        updatedAt: now,
      },
    }
    return next
  }

  const toolMatch =
    trimmed.match(
      /subtask(?:\s+id=|\s+)([A-Za-z0-9_-]+)\s+tool(?:=|:\s*)(.+)$/i,
    ) || trimmed.match(/\[swarm\]\s+([A-Za-z0-9_-]+)\s+tool:\s+(.+)$/i)
  if (toolMatch) {
    const id = toolMatch[1]
    const tool = toolMatch[2].trim()
    next.subtasks = {
      ...next.subtasks,
      [id]: {
        ...(next.subtasks[id] ?? {
          id,
          status: 'running' as SwarmSubtaskStatus,
          updatedAt: now,
        }),
        id,
        status: next.subtasks[id]?.status ?? 'running',
        tool,
        updatedAt: now,
      },
    }
    return next
  }

  const subtaskErrorMatch =
    trimmed.match(
      /subtask(?:\s+id=|\s+)([A-Za-z0-9_-]+)\s+error(?:=|:\s*)(.+)$/i,
    ) || trimmed.match(/\[swarm\]\s+([A-Za-z0-9_-]+)\s+error:\s+(.+)$/i)
  if (subtaskErrorMatch) {
    const id = subtaskErrorMatch[1]
    const error = subtaskErrorMatch[2].trim()
    next.subtasks = {
      ...next.subtasks,
      [id]: {
        ...(next.subtasks[id] ?? { id, updatedAt: now }),
        id,
        status: 'failed',
        error,
        updatedAt: now,
      },
    }
    next.status = 'failed'
    return next
  }

  const completeMatch = trimmed.match(
    /complete(?::|\s)+success=(true|false)\s+subtasks=(\d+)\s+speedup=([0-9.]+)/i,
  )
  if (completeMatch) {
    const success = completeMatch[1].toLowerCase() === 'true'
    const parsedSubtasks = Number(completeMatch[2])
    const parsedSpeedup = Number(completeMatch[3])
    next.status = success ? 'completed' : 'failed'
    next.plannedSubtasks = Number.isFinite(parsedSubtasks)
      ? parsedSubtasks
      : next.plannedSubtasks
    next.speedup = Number.isFinite(parsedSpeedup) ? parsedSpeedup : null
    return next
  }

  const swarmErrorMatch = trimmed.match(/error(?:\s+message=|:\s*)(.+)$/i)
  if (swarmErrorMatch) {
    next.status = 'failed'
    next.error = swarmErrorMatch[1].trim()
    return next
  }

  return next
}

const getSwarmRunStatusClasses = (status: SwarmMonitorState['status']) => {
  if (status === 'completed')
    return 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'
  if (status === 'failed')
    return 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300'
  if (status === 'running')
    return 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
  return 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
}

const getSwarmSubtaskStatusClasses = (status: SwarmSubtaskStatus) => {
  if (status === 'completed')
    return 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'
  if (status === 'failed' || status === 'timed_out' || status === 'cancelled')
    return 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300'
  if (status === 'running')
    return 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
  return 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
}

const isSwarmTask = (task?: Task | null) => {
  if (!task?.agent_type) return false
  const normalized = task.agent_type.toLowerCase()
  return (
    normalized === 'swarm' ||
    normalized === 'parallel' ||
    normalized === 'multi-agent'
  )
}

function ClipboardIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
  return (
    <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1}
        d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
      />
    </svg>
  )
}

function PlusIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
  return (
    <svg
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
      {...props}
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
    </svg>
  )
}

function XIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
  return (
    <svg
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
      {...props}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M6 18L18 6M6 6l12 12"
      />
    </svg>
  )
}

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [filter, setFilter] = useState('all')
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)
  const { workspaces } = useWorkspaces()
  const { data: session, status: authStatus } = useSession()
  const { token } = getApiAuth(session)
  const [isLoading, setIsLoading] = useState(true)
  const [hasLoaded, setHasLoaded] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [dispatchNotice, setDispatchNotice] = useState('')
  const loadController = useRef<AbortController | null>(null)
  const dispatchLock = useRef(false)
  const titleInput = useRef<HTMLInputElement>(null)
  const descriptionInput = useRef<HTMLTextAreaElement>(null)
  const detailsHeading = useRef<HTMLHeadingElement>(null)
  const selectedTaskButton = useRef<HTMLButtonElement | null>(null)
  const [mobileDetailOpen, setMobileDetailOpen] = useState(false)
  const { apiUrl } = useTenantApi()
  const [selectedWorkspace, setSelectedWorkspace] = useState<string>('all')
  const [taskSwarmMonitors, setTaskSwarmMonitors] = useState<
    Record<string, SwarmMonitorState>
  >({})
  const taskStreamRef = useRef<EventSource | null>(null)

  // New task creation state
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [newTaskTitle, setNewTaskTitle] = useState('')
  const [newTaskDescription, setNewTaskDescription] = useState('')
  const [newTaskAgentType, setNewTaskAgentType] = useState('build')
  const [isDispatching, setIsDispatching] = useState(false)
  const [dispatchError, setDispatchError] = useState<string | null>(null)

  const updateTaskSwarmMonitor = useCallback(
    (
      taskId: string,
      updater: (prev: SwarmMonitorState) => SwarmMonitorState,
    ) => {
      setTaskSwarmMonitors((prev) => ({
        ...prev,
        [taskId]: updater(prev[taskId] ?? INITIAL_SWARM_MONITOR),
      }))
    },
    [],
  )

  const ingestSwarmLineForTask = useCallback(
    (taskId: string, line: string) => {
      if (!line.trim()) return
      updateTaskSwarmMonitor(taskId, (prev) => applySwarmLine(prev, line))
    },
    [updateTaskSwarmMonitor],
  )

  const ingestTaskOutputPayload = useCallback(
    (taskId: string, payload: unknown) => {
      const ingestText = (text: string) => {
        text
          .split(/\r?\n/)
          .map((line) => line.trim())
          .filter(Boolean)
          .forEach((line) => ingestSwarmLineForTask(taskId, line))
      }

      if (typeof payload === 'string') {
        ingestText(payload)
        return
      }

      if (payload && typeof payload === 'object') {
        const event = payload as Record<string, unknown>
        const output =
          typeof event.output === 'string'
            ? event.output
            : typeof event.content === 'string'
              ? event.content
              : typeof event.message === 'string'
                ? event.message
                : undefined
        if (output) {
          ingestText(output)
        }
      }
    },
    [ingestSwarmLineForTask],
  )

  const loadTasks = useCallback(
    async (announce = false) => {
      if (loadController.current) return
      if (!token) {
        setLoadError('Sign in to load your tasks.')
        setIsLoading(false)
        return
      }
      const controller = new AbortController()
      loadController.current = controller
      if (announce) setIsLoading(true)
      const timeout = setTimeout(() => controller.abort(), 20000)
      try {
        const { data, error } = await listAllTasksV1AgentTasksGet({
          headers: { Authorization: `Bearer ${token}` },
          signal: controller.signal,
        })
        if (loadController.current !== controller) return
        if (error)
          throw new Error(
            taskRequestError(
              error,
              'The task service is unavailable. Please retry.',
            ),
          )
        const nextTasks: Task[] = readTaskQueue(data).map((row) => ({
          ...row,
          id: String(row.id),
          status: String(row.status),
          agent_type:
            typeof row.agent_type === 'string' ? row.agent_type : 'Unknown',
          created_at: String(row.created_at),
        }))
        setTasks(nextTasks)
        setHasLoaded(true)
        setLoadError(null)
        setSelectedTask((current) =>
          current
            ? (nextTasks.find((task) => task.id === current.id) ?? null)
            : null,
        )
      } catch (error) {
        if (loadController.current === controller) {
          setLoadError(
            controller.signal.aborted
              ? 'Loading tasks timed out. Please retry.'
              : taskRequestError(
                  error,
                  'The task service is unavailable. Please retry.',
                ),
          )
        }
      } finally {
        clearTimeout(timeout)
        if (loadController.current === controller) {
          loadController.current = null
          setIsLoading(false)
        }
      }
    },
    [token],
  )

  const dispatchTask = useCallback(
    async (
      request: DispatchTaskRequest,
    ): Promise<DispatchTaskResponse | null> => {
      if (dispatchLock.current) return null
      dispatchLock.current = true
      const controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), 20000)
      setIsDispatching(true)
      setDispatchError(null)
      try {
        const headers: Record<string, string> = {
          'Content-Type': 'application/json',
        }
        if (!token) throw new Error('Sign in before dispatching a task.')
        headers['Authorization'] = `Bearer ${token}`

        const response = await fetch(`${apiUrl}/v1/tasks/dispatch`, {
          method: 'POST',
          headers,
          body: JSON.stringify(request),
          signal: controller.signal,
        })

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          if (response.status >= 500) {
            // The live dispatcher can commit a task before queueing fails.
            // A server error is not proof that nothing was submitted.
            void loadTasks(true)
            throw new Error(
              `Dispatch could not be confirmed (HTTP ${response.status}). The task may already exist. Check the queue before submitting again.`,
            )
          }
          throw new Error(
            taskRequestError(
              errorData,
              `Failed to dispatch task: ${response.status}`,
            ),
          )
        }

        const result: DispatchTaskResponse = await response.json().catch(() => {
          throw new Error(
            'The service did not confirm a task ID. Check the queue before submitting again.',
          )
        })
        if (
          !result ||
          typeof result.task_id !== 'string' ||
          !result.task_id.trim()
        ) {
          throw new Error(
            'The service did not confirm a task ID. Check the queue before submitting again.',
          )
        }

        // A refresh failure must not turn an accepted dispatch into a failure.
        void loadTasks(true)

        return result
      } catch (error) {
        const message = controller.signal.aborted
          ? 'Dispatch confirmation timed out. Check the queue before submitting again.'
          : error instanceof TypeError
            ? 'Dispatch could not be confirmed. Check the queue before submitting again.'
            : taskRequestError(
                error,
                'Dispatch could not be confirmed. Check the queue before submitting again.',
              )
        setDispatchError(message)
        console.error('Failed to dispatch task:', error)
        return null
      } finally {
        clearTimeout(timeout)
        dispatchLock.current = false
        setIsDispatching(false)
      }
    },
    [apiUrl, token, loadTasks],
  )

  const handleCreateTask = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (dispatchLock.current) return
    if (!newTaskTitle.trim() || !newTaskDescription.trim()) {
      setDispatchError('Title and description are required')
      if (!newTaskTitle.trim()) titleInput.current?.focus()
      else descriptionInput.current?.focus()
      return
    }

    const result = await dispatchTask({
      title: newTaskTitle.trim(),
      description: newTaskDescription.trim(),
      agent_type: newTaskAgentType,
    })

    if (result) {
      setDispatchNotice(
        `Task ${result.task_id} was submitted. It may take a moment to appear in the queue.`,
      )
      setShowCreateModal(false)
      setNewTaskTitle('')
      setNewTaskDescription('')
      setNewTaskAgentType('build')
    }
  }

  useEffect(() => {
    if (authStatus === 'loading') return
    void loadTasks(true)
    const interval = token
      ? setInterval(() => void loadTasks(), 5000)
      : undefined
    return () => {
      clearInterval(interval)
      loadController.current?.abort()
      loadController.current = null
    }
  }, [loadTasks, token, authStatus])

  const selectedTaskId = selectedTask?.id ?? null
  const selectedTaskStatus = selectedTask?.status ?? null
  const selectedTaskAgentType = selectedTask?.agent_type ?? null

  useEffect(() => {
    if (taskStreamRef.current) {
      taskStreamRef.current.close()
      taskStreamRef.current = null
    }

    if (!selectedTaskId || !selectedTaskAgentType) {
      return
    }

    const normalizedAgentType = selectedTaskAgentType.toLowerCase()
    if (
      normalizedAgentType !== 'swarm' &&
      normalizedAgentType !== 'parallel' &&
      normalizedAgentType !== 'multi-agent'
    ) {
      return
    }

    const taskId = selectedTaskId
    updateTaskSwarmMonitor(taskId, (prev) => ({ ...prev, connected: false }))

    let cancelled = false

    const hydrateFromCurrentOutput = async () => {
      try {
        const { data, error } = await getTaskOutputV1AgentTasksTaskIdOutputGet({
          path: { task_id: taskId },
        })
        if (cancelled || error || !data) return

        const response = data as any
        const outputs = Array.isArray(response?.outputs) ? response.outputs : []
        for (const chunk of outputs) {
          ingestTaskOutputPayload(taskId, chunk)
        }
      } catch (error) {
        console.error('Failed to hydrate task output stream:', error)
      }
    }

    hydrateFromCurrentOutput()

    const isActive =
      selectedTaskStatus === 'pending' || selectedTaskStatus === 'running'
    if (!isActive) {
      return () => {
        cancelled = true
      }
    }

    // Handle relative API URLs by resolving against window.location
    const baseApiUrl = apiUrl.startsWith('/')
      ? `${window.location.origin}${apiUrl}`
      : apiUrl
    const baseUrl = baseApiUrl.replace(/\/+$/, '')
    const sseUrl = new URL(
      `${baseUrl}/v1/agent/tasks/${encodeURIComponent(taskId)}/output/stream`,
    )
    if (session?.accessToken) {
      sseUrl.searchParams.set('access_token', session.accessToken)
    }
    const eventSource = new EventSource(sseUrl.toString())
    taskStreamRef.current = eventSource

    eventSource.onopen = () => {
      updateTaskSwarmMonitor(taskId, (prev) => ({ ...prev, connected: true }))
    }

    eventSource.onerror = () => {
      updateTaskSwarmMonitor(taskId, (prev) => ({ ...prev, connected: false }))
    }

    eventSource.addEventListener('output', (rawEvent) => {
      const event = rawEvent as MessageEvent<string>
      if (!event.data) return
      try {
        ingestTaskOutputPayload(taskId, JSON.parse(event.data))
      } catch {
        ingestTaskOutputPayload(taskId, event.data)
      }
    })

    eventSource.addEventListener('done', (rawEvent) => {
      const event = rawEvent as MessageEvent<string>
      let status = selectedTaskStatus ?? 'completed'
      if (event.data) {
        try {
          const done = JSON.parse(event.data) as { status?: string }
          if (done?.status) {
            status = done.status
          }
        } catch {
          // ignore parse errors for done payload
        }
      }
      updateTaskSwarmMonitor(taskId, (prev) => ({
        ...prev,
        connected: false,
        status: status === 'failed' ? 'failed' : 'completed',
      }))
    })

    return () => {
      cancelled = true
      eventSource.close()
      if (taskStreamRef.current === eventSource) {
        taskStreamRef.current = null
      }
    }
  }, [
    apiUrl,
    ingestTaskOutputPayload,
    selectedTaskAgentType,
    selectedTaskId,
    selectedTaskStatus,
    updateTaskSwarmMonitor,
  ])

  const filteredTasks = tasks.filter((task: Task) => {
    const statusMatch = filter === 'all' || task.status === filter
    const workspaceMatch =
      selectedWorkspace === 'all' ||
      (task.workspace_id || task.codebase_id) === selectedWorkspace
    return statusMatch && workspaceMatch
  })

  const getStatusClasses = (status: string) => {
    const classes: Record<string, string> = {
      pending:
        'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300',
      running: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300',
      completed:
        'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300',
      failed: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300',
    }
    return classes[status] || classes.pending
  }

  const getPriorityBadge = (priority?: number) => {
    switch (priority) {
      case 4:
        return (
          <span className="rounded-full bg-red-100 px-2 py-1 text-xs text-red-800">
            Urgent
          </span>
        )
      case 3:
        return (
          <span className="rounded-full bg-orange-100 px-2 py-1 text-xs text-orange-800">
            High
          </span>
        )
      case 1:
        return (
          <span className="rounded-full bg-blue-100 px-2 py-1 text-xs text-blue-800">
            Low
          </span>
        )
      default:
        return (
          <span className="rounded-full bg-gray-100 px-2 py-1 text-xs text-gray-800">
            Normal
          </span>
        )
    }
  }

  const parseTaskResult = (result: string) => {
    try {
      const lines = result.split('\n').filter((l) => l.trim())
      const output: string[] = []
      for (const line of lines) {
        try {
          const event = JSON.parse(line)
          if (event.type === 'text' && event.part?.text) {
            output.push(event.part.text)
          } else if (event.type === 'tool_use') {
            output.push(
              `[Tool: ${event.part?.tool}] ${event.part?.state?.output || ''}`,
            )
          }
        } catch {
          output.push(line)
        }
      }
      return output.join('\n\n')
    } catch {
      return result
    }
  }

  const selectedTaskSwarmMonitor = selectedTask
    ? taskSwarmMonitors[selectedTask.id]
    : undefined
  const showSwarmMonitor =
    isSwarmTask(selectedTask) ||
    Boolean(selectedTaskSwarmMonitor?.recentLines.length)
  const swarmSubtasks = selectedTaskSwarmMonitor
    ? Object.values(selectedTaskSwarmMonitor.subtasks).sort(
        (a, b) => b.updatedAt - a.updatedAt,
      )
    : []
  const swarmCounts = swarmSubtasks.reduce(
    (acc, task) => {
      if (task.status === 'completed') acc.completed += 1
      else if (task.status === 'running') acc.running += 1
      else if (
        task.status === 'failed' ||
        task.status === 'timed_out' ||
        task.status === 'cancelled'
      )
        acc.failed += 1
      else acc.pending += 1
      return acc
    },
    { pending: 0, running: 0, completed: 0, failed: 0 },
  )
  const recentSwarmLines =
    selectedTaskSwarmMonitor?.recentLines.slice(-20) ?? []

  return (
    <div className="mx-auto w-full max-w-7xl space-y-6">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-gray-950 sm:text-3xl dark:text-white">
            Tasks
          </h1>
          <p className="mt-2 max-w-xl text-sm leading-6 text-gray-600 dark:text-gray-400">
            Follow work in progress and read the results, all in one place.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            setDispatchError(null)
            setShowCreateModal(true)
          }}
          disabled={!token || authStatus === 'loading'}
          className="inline-flex shrink-0 items-center justify-center gap-2 rounded-lg bg-cyan-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-cyan-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-600 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <PlusIcon className="h-4 w-4" />
          New Task
        </button>
      </header>
      <div
        role="status"
        className={
          dispatchNotice
            ? 'rounded-lg border border-green-200 bg-green-50 p-3 text-sm break-words text-green-800 dark:border-green-900 dark:bg-green-950/30 dark:text-green-200'
            : 'sr-only'
        }
      >
        {dispatchNotice}
      </div>
      <div className="grid min-w-0 grid-cols-1 items-start gap-5 lg:grid-cols-[minmax(17rem,0.85fr)_minmax(0,1.8fr)]">
        {/* Task List */}
        <div
          className={`${mobileDetailOpen ? 'hidden' : 'block'} min-w-0 lg:sticky lg:top-0 lg:block`}
        >
          <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
            <div className="border-b border-gray-200 p-4 dark:border-gray-700">
              <div className="space-y-6">
                <div className="flex items-center justify-between gap-3">
                  <h2 className="text-sm font-semibold text-gray-950 dark:text-white">
                    Task queue
                  </h2>
                  {hasLoaded && (
                    <span className="text-xs text-gray-500 tabular-nums dark:text-gray-400">
                      {filteredTasks.length} shown
                    </span>
                  )}
                </div>
                <div className="space-y-3">
                  <select
                    aria-label="Filter tasks by workspace"
                    value={selectedWorkspace}
                    onChange={(e) => setSelectedWorkspace(e.target.value)}
                    className="block w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-700 focus:border-cyan-600 focus:ring-cyan-600 dark:border-gray-700 dark:bg-gray-950 dark:text-gray-300"
                  >
                    <option value="all">All Workspaces</option>
                    {workspaces.map((cb: any) => (
                      <option key={cb.id} value={cb.id}>
                        {cb.name}
                      </option>
                    ))}
                  </select>
                  <div
                    role="group"
                    aria-label="Task status"
                    className="flex flex-wrap gap-1"
                  >
                    {['all', 'pending', 'running', 'completed', 'failed'].map(
                      (f) => (
                        <button
                          key={f}
                          aria-pressed={filter === f}
                          onClick={() => setFilter(f)}
                          className={`rounded-md px-2.5 py-2 text-xs font-medium transition-colors ${
                            filter === f
                              ? 'bg-cyan-50 text-cyan-800 ring-1 ring-cyan-200 ring-inset dark:bg-cyan-950 dark:text-cyan-200 dark:ring-cyan-900'
                              : 'text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800'
                          }`}
                        >
                          {f.charAt(0).toUpperCase() + f.slice(1)}
                        </button>
                      ),
                    )}
                  </div>
                </div>
              </div>
            </div>
            {loadError && (
              <div
                role="alert"
                className="m-4 rounded-md bg-red-50 p-3 text-sm text-red-800 dark:bg-red-900/20 dark:text-red-200"
              >
                <p>{loadError}</p>
                {hasLoaded && tasks.length > 0 && (
                  <p>
                    Previously loaded tasks are shown; their status may be out
                    of date.
                  </p>
                )}
                {token ? (
                  <button
                    type="button"
                    disabled={isLoading}
                    onClick={() => void loadTasks(true)}
                    className="mt-2 underline disabled:opacity-50"
                  >
                    Retry loading tasks
                  </button>
                ) : (
                  <a
                    href="/login?callbackUrl=%2Fdashboard%2Ftasks"
                    className="mt-2 inline-block underline"
                  >
                    Sign in
                  </a>
                )}
              </div>
            )}
            {isLoading && (
              <p
                role="status"
                className="p-4 text-sm text-gray-600 dark:text-gray-300"
              >
                {hasLoaded ? 'Refreshing tasks…' : 'Loading tasks…'}
              </p>
            )}
            <div
              role="region"
              aria-label="Task queue"
              aria-busy={isLoading}
              className="divide-y divide-gray-100 lg:max-h-[calc(100dvh-22rem)] lg:overflow-y-auto dark:divide-gray-800"
            >
              {filteredTasks.length === 0 &&
              hasLoaded &&
              !loadError &&
              !isLoading ? (
                <div className="p-8 text-center text-gray-500 dark:text-gray-400">
                  <ClipboardIcon className="mx-auto h-12 w-12 text-gray-400" />
                  <p className="mt-2 text-sm">
                    {filter === 'all' && selectedWorkspace === 'all'
                      ? 'No tasks yet. Create a task to get started.'
                      : 'No tasks match these filters.'}
                  </p>
                  {(filter !== 'all' || selectedWorkspace !== 'all') && (
                    <button
                      type="button"
                      onClick={() => {
                        setFilter('all')
                        setSelectedWorkspace('all')
                      }}
                      className="mt-2 text-sm underline"
                    >
                      Clear filters
                    </button>
                  )}
                </div>
              ) : (
                filteredTasks.map((task) => (
                  <button
                    key={task.id}
                    type="button"
                    aria-pressed={selectedTask?.id === task.id}
                    aria-controls="task-details"
                    className={`block w-full border-l-2 p-4 text-left transition-colors focus-visible:ring-2 focus-visible:ring-cyan-500 focus-visible:outline-none focus-visible:ring-inset ${selectedTask?.id === task.id ? 'border-cyan-600 bg-cyan-50/60 dark:bg-cyan-950/40' : 'border-transparent hover:bg-gray-50 dark:hover:bg-gray-800/60'}`}
                    onClick={(event) => {
                      selectedTaskButton.current = event.currentTarget
                      setSelectedTask(task)
                      setMobileDetailOpen(true)
                      if (window.matchMedia('(max-width: 1023px)').matches)
                        requestAnimationFrame(() =>
                          detailsHeading.current?.focus(),
                        )
                    }}
                  >
                    <span className="flex items-start justify-between gap-3">
                      <span className="min-w-0 flex-1">
                        <span className="line-clamp-2 text-sm leading-6 font-semibold break-words text-gray-900 dark:text-white">
                          {task.title ||
                            task.prompt?.substring(0, 50) ||
                            'Untitled'}
                        </span>
                        <span className="mt-1 block text-xs text-gray-500 dark:text-gray-400">
                          {new Date(task.created_at).toLocaleDateString(
                            undefined,
                            { month: 'short', day: 'numeric' },
                          )}{' '}
                          · {task.agent_type}
                        </span>
                      </span>
                      <span
                        className={`ml-2 inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${getStatusClasses(task.status)}`}
                      >
                        {task.status}
                      </span>
                    </span>
                  </button>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Task Detail */}
        <div
          className={`${mobileDetailOpen ? 'block' : 'hidden'} min-w-0 lg:block`}
        >
          <button
            type="button"
            onClick={() => {
              setMobileDetailOpen(false)
              requestAnimationFrame(() => selectedTaskButton.current?.focus())
            }}
            className="mb-3 inline-flex min-h-10 items-center gap-2 text-sm font-medium text-cyan-800 hover:underline lg:hidden dark:text-cyan-300"
          >
            <span aria-hidden="true">←</span> Back to task queue
          </button>
          <div
            id="task-details"
            className="min-w-0 rounded-xl border border-gray-200 bg-white break-words dark:border-gray-800 dark:bg-gray-900"
          >
            <div className="space-y-3 border-b border-gray-100 p-5 sm:p-6 dark:border-gray-800">
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs font-medium tracking-wider text-gray-500 uppercase dark:text-gray-400">
                  Task details
                </p>
                {selectedTask && (
                  <span
                    className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${getStatusClasses(selectedTask.status)}`}
                  >
                    {selectedTask.status}
                  </span>
                )}
              </div>
              <h2
                ref={detailsHeading}
                tabIndex={-1}
                className="text-xl leading-8 font-semibold tracking-tight break-words text-gray-950 focus-visible:outline-cyan-500 sm:text-2xl dark:text-white"
              >
                {selectedTask
                  ? selectedTask.title || 'Untitled task'
                  : 'Task results'}
              </h2>
            </div>
            <div className="p-5 sm:p-6">
              {selectedTask ? (
                <div className="space-y-4">
                  {selectedTask.error && (
                    <section
                      role="alert"
                      className="rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-900 dark:bg-red-950/30"
                    >
                      <h3 className="text-sm font-semibold text-red-800 dark:text-red-200">
                        Task needs attention
                      </h3>
                      <p className="mt-2 text-sm leading-6 whitespace-pre-wrap text-red-700 dark:text-red-300">
                        {selectedTask.error}
                      </p>
                    </section>
                  )}
                  <section aria-labelledby="task-result-heading">
                    <h3
                      id="task-result-heading"
                      className="mb-4 text-sm font-semibold text-gray-900 dark:text-gray-100"
                    >
                      Result
                    </h3>
                    {selectedTask.result ? (
                      <div className="max-w-prose text-sm leading-7 break-words text-gray-700 dark:text-gray-200 [&_a]:text-cyan-700 [&_a]:underline dark:[&_a]:text-cyan-300 [&_code]:font-mono [&_code]:text-[0.9em] [&_h1]:my-5 [&_h1]:text-xl [&_h1]:font-semibold [&_h2]:my-4 [&_h2]:text-lg [&_h2]:font-semibold [&_h3]:my-3 [&_h3]:font-semibold [&_ol]:my-3 [&_ol]:list-decimal [&_ol]:pl-5 [&_p]:my-3 [&_pre]:my-4 [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:bg-gray-950 [&_pre]:p-4 [&_pre]:text-gray-100 [&_table]:block [&_table]:overflow-x-auto [&_td]:border [&_td]:border-gray-200 [&_td]:p-2 [&_th]:border [&_th]:border-gray-200 [&_th]:p-2 [&_ul]:my-3 [&_ul]:list-disc [&_ul]:pl-5">
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm, remarkBreaks]}
                        >
                          {parseTaskResult(selectedTask.result)}
                        </ReactMarkdown>
                      </div>
                    ) : (
                      <p className="rounded-lg bg-gray-50 p-4 text-sm leading-6 text-gray-500 dark:bg-gray-950 dark:text-gray-400">
                        {selectedTask.status === 'running'
                          ? 'Work is in progress. The result will appear here when it is available.'
                          : selectedTask.status === 'pending'
                            ? 'This task is waiting to start. Its result will appear here.'
                            : 'No result was returned for this task.'}
                      </p>
                    )}
                  </section>
                  {selectedTask.prompt && (
                    <details
                      open={!selectedTask.result}
                      key={`prompt-${selectedTask.id}`}
                      className="rounded-lg border border-gray-200 dark:border-gray-800"
                    >
                      <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-gray-700 marker:text-gray-400 dark:text-gray-300">
                        Task brief
                      </summary>
                      <p className="border-t border-gray-100 px-4 py-4 text-sm leading-7 break-words whitespace-pre-wrap text-gray-600 dark:border-gray-800 dark:text-gray-400">
                        {selectedTask.prompt}
                      </p>
                    </details>
                  )}
                  {showSwarmMonitor && (
                    <details
                      key={`timeline-${selectedTask.id}`}
                      className="rounded-lg border border-gray-200 dark:border-gray-800"
                    >
                      <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-gray-700 marker:text-gray-400 dark:text-gray-300">
                        Execution timeline
                      </summary>
                      <div className="space-y-3 border-t border-gray-200 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-950">
                        <div className="flex items-center justify-between">
                          <p className="text-xs font-semibold text-gray-700 dark:text-gray-300">
                            Swarm progress
                          </p>
                          <span
                            className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium ${
                              selectedTaskSwarmMonitor?.connected
                                ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'
                                : 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
                            }`}
                          >
                            {selectedTaskSwarmMonitor?.connected
                              ? 'LIVE'
                              : 'IDLE'}
                          </span>
                        </div>

                        <div className="grid grid-cols-4 gap-2">
                          <div className="rounded bg-white/80 p-2 text-center dark:bg-gray-900/40">
                            <p className="text-[10px] tracking-wide text-gray-500 uppercase dark:text-gray-400">
                              Pending
                            </p>
                            <p className="text-xs font-semibold text-gray-900 dark:text-white">
                              {swarmCounts.pending}
                            </p>
                          </div>
                          <div className="rounded bg-blue-50 p-2 text-center dark:bg-blue-900/20">
                            <p className="text-[10px] tracking-wide text-blue-600 uppercase dark:text-blue-300">
                              Running
                            </p>
                            <p className="text-xs font-semibold text-blue-700 dark:text-blue-200">
                              {swarmCounts.running}
                            </p>
                          </div>
                          <div className="rounded bg-green-50 p-2 text-center dark:bg-green-900/20">
                            <p className="text-[10px] tracking-wide text-green-600 uppercase dark:text-green-300">
                              Done
                            </p>
                            <p className="text-xs font-semibold text-green-700 dark:text-green-200">
                              {swarmCounts.completed}
                            </p>
                          </div>
                          <div className="rounded bg-red-50 p-2 text-center dark:bg-red-900/20">
                            <p className="text-[10px] tracking-wide text-red-600 uppercase dark:text-red-300">
                              Failed
                            </p>
                            <p className="text-xs font-semibold text-red-700 dark:text-red-200">
                              {swarmCounts.failed}
                            </p>
                          </div>
                        </div>

                        <div className="flex flex-wrap items-center gap-2 text-[11px] text-gray-600 dark:text-gray-300">
                          <span
                            className={`inline-flex items-center rounded-full px-2 py-0.5 font-medium ${getSwarmRunStatusClasses(selectedTaskSwarmMonitor?.status ?? 'idle')}`}
                          >
                            {(
                              selectedTaskSwarmMonitor?.status ?? 'idle'
                            ).toUpperCase()}
                          </span>
                          {selectedTaskSwarmMonitor?.plannedSubtasks !== null &&
                            selectedTaskSwarmMonitor?.plannedSubtasks !==
                              undefined && (
                              <span>
                                planned=
                                {selectedTaskSwarmMonitor.plannedSubtasks}
                              </span>
                            )}
                          {selectedTaskSwarmMonitor?.currentStage !== null &&
                            selectedTaskSwarmMonitor?.currentStage !==
                              undefined && (
                              <span>
                                stage={selectedTaskSwarmMonitor.currentStage}
                              </span>
                            )}
                          {selectedTaskSwarmMonitor?.speedup !== null &&
                            selectedTaskSwarmMonitor?.speedup !== undefined && (
                              <span>
                                speedup=
                                {selectedTaskSwarmMonitor.speedup.toFixed(2)}x
                              </span>
                            )}
                        </div>

                        {swarmSubtasks.length > 0 && (
                          <div className="max-h-28 space-y-1 overflow-y-auto">
                            {swarmSubtasks.slice(0, 8).map((task) => (
                              <div
                                key={task.id}
                                className="rounded border border-gray-200 bg-white/70 p-2 dark:border-gray-700 dark:bg-gray-900/30"
                              >
                                <div className="flex items-center justify-between gap-2">
                                  <span className="font-mono text-[11px] text-gray-700 dark:text-gray-200">
                                    {task.id}
                                  </span>
                                  <span
                                    className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium ${getSwarmSubtaskStatusClasses(task.status)}`}
                                  >
                                    {task.status}
                                  </span>
                                </div>
                                {task.tool && (
                                  <p className="mt-1 text-[10px] text-blue-600 dark:text-blue-300">
                                    tool={task.tool}
                                  </p>
                                )}
                                {task.error && (
                                  <p className="mt-1 text-[10px] whitespace-pre-wrap text-red-600 dark:text-red-300">
                                    {task.error}
                                  </p>
                                )}
                              </div>
                            ))}
                          </div>
                        )}

                        <div className="max-h-32 space-y-1 overflow-y-auto rounded bg-white/70 p-2 dark:bg-gray-900/40">
                          {recentSwarmLines.length === 0 ? (
                            <p className="text-[11px] text-gray-500 dark:text-gray-400">
                              Waiting for swarm output...
                            </p>
                          ) : (
                            recentSwarmLines.map((line, index) => (
                              <p
                                key={`${line}-${index}`}
                                className="font-mono text-[10px] break-words text-gray-700 dark:text-gray-300"
                              >
                                {line}
                              </p>
                            ))
                          )}
                        </div>
                      </div>
                    </details>
                  )}
                  <details
                    key={`metadata-${selectedTask.id}`}
                    className="rounded-lg border border-gray-200 dark:border-gray-800"
                  >
                    <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-gray-700 marker:text-gray-400 dark:text-gray-300">
                      Task information
                    </summary>
                    <div className="grid gap-4 border-t border-gray-100 p-4 text-sm sm:grid-cols-2 dark:border-gray-800">
                      <div>
                        <p className="text-xs text-gray-500">Task ID</p>
                        <p className="mt-1 font-mono text-xs break-all text-gray-700 dark:text-gray-300">
                          {selectedTask.id}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500">Agent</p>
                        <p className="mt-1 text-gray-700 dark:text-gray-300">
                          {selectedTask.agent_type}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500">Priority</p>
                        <span className="mt-1 inline-block">
                          {getPriorityBadge(selectedTask.priority)}
                        </span>
                      </div>
                      {(selectedTask.workspace_id ||
                        selectedTask.codebase_id) && (
                        <div>
                          <p className="text-xs text-gray-500 dark:text-gray-400">
                            Workspace ID
                          </p>
                          <p className="text-sm break-all text-gray-900 dark:text-white">
                            {selectedTask.workspace_id ||
                              selectedTask.codebase_id}
                          </p>
                        </div>
                      )}
                      <div>
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                          Created
                        </p>
                        <p className="text-sm text-gray-900 dark:text-white">
                          {new Date(selectedTask.created_at).toLocaleString()}
                        </p>
                      </div>
                      {selectedTask.started_at && (
                        <div>
                          <p className="text-xs text-gray-500 dark:text-gray-400">
                            Started
                          </p>
                          <p className="text-sm text-gray-900 dark:text-white">
                            {new Date(selectedTask.started_at).toLocaleString()}
                          </p>
                        </div>
                      )}
                      {selectedTask.completed_at && (
                        <div>
                          <p className="text-xs text-gray-500 dark:text-gray-400">
                            Completed
                          </p>
                          <p className="text-sm text-gray-900 dark:text-white">
                            {new Date(
                              selectedTask.completed_at,
                            ).toLocaleString()}
                          </p>
                        </div>
                      )}
                      {selectedTask.worker_id && (
                        <div>
                          <p className="text-xs text-gray-500 dark:text-gray-400">
                            Worker ID
                          </p>
                          <p className="font-mono text-sm text-gray-900 dark:text-white">
                            {selectedTask.worker_id}
                          </p>
                        </div>
                      )}
                      {selectedTask.metadata &&
                        typeof selectedTask.metadata === 'object' &&
                        'dispatched_via_knative' in selectedTask.metadata &&
                        selectedTask.metadata.dispatched_via_knative ===
                          true && (
                          <div className="flex items-center gap-2 rounded bg-indigo-50 p-2 dark:bg-indigo-900/20">
                            <span className="inline-flex items-center rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-700 dark:bg-indigo-800 dark:text-indigo-200">
                              Knative
                            </span>
                            <span className="text-xs text-gray-600 dark:text-gray-300">
                              Dispatched via Knative Eventing
                            </span>
                          </div>
                        )}
                    </div>
                  </details>
                </div>
              ) : (
                <div className="flex min-h-64 flex-col items-center justify-center px-4 py-12 text-center">
                  <ClipboardIcon className="mb-4 h-10 w-10 text-gray-300 dark:text-gray-700" />
                  <p className="text-base font-medium text-gray-700 dark:text-gray-200">
                    Choose a task from the queue
                  </p>
                  <p className="mt-2 max-w-xs text-sm leading-6 text-gray-500 dark:text-gray-400">
                    Read its result here. The brief, execution timeline, and
                    task information stay close when you need them.
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Create Task Modal */}
      <Dialog
        open={showCreateModal}
        onClose={() => {
          if (!dispatchLock.current) setShowCreateModal(false)
        }}
        initialFocus={titleInput}
        className="fixed inset-0 z-50 overflow-y-auto"
      >
        <div className="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
          <DialogBackdrop className="fixed inset-0 bg-gray-900/60 transition-opacity" />
          <DialogPanel
            as="form"
            onSubmit={handleCreateTask}
            aria-busy={isDispatching}
            className="relative w-full transform overflow-hidden rounded-lg bg-white text-left shadow-xl transition-all sm:my-8 sm:max-w-lg dark:bg-gray-800"
          >
            <div className="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4 dark:bg-gray-800">
              <div className="mb-4 flex items-center justify-between">
                <DialogTitle className="text-lg font-semibold text-gray-900 dark:text-white">
                  Create New Task
                </DialogTitle>
                <button
                  type="button"
                  aria-label="Close create task"
                  disabled={isDispatching}
                  onClick={() => setShowCreateModal(false)}
                  className="rounded-md text-gray-400 hover:text-gray-500 dark:hover:text-gray-300"
                >
                  <XIcon className="h-6 w-6" />
                </button>
              </div>

              {dispatchError && (
                <div
                  role="alert"
                  id="task-dispatch-error"
                  className="mb-4 rounded-md bg-red-50 p-3 dark:bg-red-900/20"
                >
                  <p className="text-sm text-red-700 dark:text-red-300">
                    {dispatchError}
                  </p>
                </div>
              )}

              <div className="space-y-4">
                <div>
                  <label
                    htmlFor="title"
                    className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300"
                  >
                    Title
                  </label>
                  <input
                    type="text"
                    id="title"
                    ref={titleInput}
                    required
                    disabled={isDispatching}
                    aria-describedby={
                      dispatchError ? 'task-dispatch-error' : undefined
                    }
                    aria-invalid={Boolean(
                      dispatchError && !newTaskTitle.trim(),
                    )}
                    value={newTaskTitle}
                    onChange={(e) => setNewTaskTitle(e.target.value)}
                    className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-transparent focus:ring-2 focus:ring-indigo-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                    placeholder="Task title..."
                  />
                </div>

                <div>
                  <label
                    htmlFor="description"
                    className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300"
                  >
                    Description
                  </label>
                  <textarea
                    id="description"
                    ref={descriptionInput}
                    aria-describedby={
                      dispatchError ? 'task-dispatch-error' : undefined
                    }
                    aria-invalid={Boolean(
                      dispatchError && !newTaskDescription.trim(),
                    )}
                    required
                    disabled={isDispatching}
                    value={newTaskDescription}
                    onChange={(e) => setNewTaskDescription(e.target.value)}
                    rows={4}
                    className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-transparent focus:ring-2 focus:ring-indigo-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                    placeholder="Describe what you want the agent to do..."
                  />
                </div>

                <div>
                  <label
                    htmlFor="agentType"
                    className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300"
                  >
                    Agent Type
                  </label>
                  <select
                    id="agentType"
                    disabled={isDispatching}
                    value={newTaskAgentType}
                    onChange={(e) => setNewTaskAgentType(e.target.value)}
                    className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-transparent focus:ring-2 focus:ring-indigo-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                  >
                    <option value="build">Build</option>
                    <option value="plan">Plan</option>
                    <option value="general">General</option>
                    <option value="swarm">Swarm (Parallel)</option>
                    <option value="review">Review</option>
                    <option value="test">Test</option>
                  </select>
                </div>
              </div>
            </div>

            <div className="bg-gray-50 px-4 py-3 sm:flex sm:flex-row-reverse sm:px-6 dark:bg-gray-700/50">
              <button
                type="submit"
                disabled={isDispatching}
                className="inline-flex w-full justify-center rounded-lg bg-cyan-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-cyan-800 disabled:cursor-not-allowed disabled:opacity-50 sm:ml-3 sm:w-auto"
              >
                {isDispatching ? (
                  <>
                    <svg
                      className="mr-2 -ml-1 h-4 w-4 animate-spin text-white"
                      fill="none"
                      viewBox="0 0 24 24"
                    >
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                      />
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                      />
                    </svg>
                    Dispatching...
                  </>
                ) : (
                  'Dispatch Task'
                )}
              </button>
              <button
                type="button"
                disabled={isDispatching}
                onClick={() => setShowCreateModal(false)}
                className="mt-3 inline-flex w-full justify-center rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-gray-300 ring-inset hover:bg-gray-50 sm:mt-0 sm:w-auto dark:bg-gray-600 dark:text-white dark:ring-gray-500 dark:hover:bg-gray-500"
              >
                Cancel
              </button>
            </div>
          </DialogPanel>
        </div>
      </Dialog>
    </div>
  )
}
