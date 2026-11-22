'use client'

import { useState, useCallback, useRef, useEffect } from 'react'
import { create } from '@bufbuild/protobuf'
import { a2aClient, createA2AClient } from '@/lib/grpc/client'
import {
    type Task,
    type AgentCard,
    type StreamResponse,
    TaskState,
    Role,
    GetTaskRequestSchema,
    GetAgentCardRequestSchema,
    SendMessageRequestSchema,
    MessageSchema,
    PartSchema,
    CancelTaskRequestSchema,
    TaskSubscriptionRequestSchema,
} from '@/lib/grpc/gen/a2a_pb'

// Re-export for convenience
export { TaskState, Role }
export type { Task, AgentCard, StreamResponse }

/**
 * Hook to fetch a task by ID via gRPC.
 */
export function useTask(taskId: string | null) {
    const [task, setTask] = useState<Task | null>(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const fetch = useCallback(async () => {
        if (!taskId) return
        setLoading(true)
        setError(null)
        try {
            const request = create(GetTaskRequestSchema, { name: `tasks/${taskId}` })
            const result = await a2aClient.getTask(request)
            setTask(result)
        } catch (err) {
            setError(err instanceof Error ? err.message : String(err))
        } finally {
            setLoading(false)
        }
    }, [taskId])

    useEffect(() => { fetch() }, [fetch])

    return { task, loading, error, refetch: fetch }
}

/**
 * Hook to get the agent card via gRPC.
 */
export function useAgentCard(grpcUrl?: string) {
    const [card, setCard] = useState<AgentCard | null>(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const fetch = useCallback(async () => {
        setLoading(true)
        setError(null)
        try {
            const client = grpcUrl ? createA2AClient(grpcUrl) : a2aClient
            const request = create(GetAgentCardRequestSchema, {})
            const result = await client.getAgentCard(request)
            setCard(result)
        } catch (err) {
            setError(err instanceof Error ? err.message : String(err))
        } finally {
            setLoading(false)
        }
    }, [grpcUrl])

    useEffect(() => { fetch() }, [fetch])

    return { card, loading, error, refetch: fetch }
}

/**
 * Hook to send a message and get a task back via gRPC (unary).
 */
export function useSendMessage() {
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const send = useCallback(async (text: string, contextId?: string) => {
        setLoading(true)
        setError(null)
        try {
            const message = create(MessageSchema, {
                messageId: crypto.randomUUID(),
                role: Role.USER,
                contextId: contextId ?? '',
                content: [create(PartSchema, { part: { case: 'text', value: text } })],
            })
            const request = create(SendMessageRequestSchema, { request: message })
            const response = await a2aClient.sendMessage(request)
            return response
        } catch (err) {
            const msg = err instanceof Error ? err.message : String(err)
            setError(msg)
            return null
        } finally {
            setLoading(false)
        }
    }, [])

    return { send, loading, error }
}

/**
 * Hook to subscribe to a task's streaming updates via gRPC server-streaming.
 * Returns an array of StreamResponse events that accumulates as updates arrive.
 */
export function useTaskSubscription(taskId: string | null) {
    const [events, setEvents] = useState<StreamResponse[]>([])
    const [connected, setConnected] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const abortRef = useRef<AbortController | null>(null)

    useEffect(() => {
        if (!taskId) return

        const abort = new AbortController()
        abortRef.current = abort
        setEvents([])
        setConnected(true)
        setError(null)

            ; (async () => {
                try {
                    const request = create(TaskSubscriptionRequestSchema, { name: `tasks/${taskId}` })
                    for await (const event of a2aClient.taskSubscription(request, { signal: abort.signal })) {
                        setEvents(prev => [...prev, event])
                    }
                } catch (err) {
                    if (!abort.signal.aborted) {
                        setError(err instanceof Error ? err.message : String(err))
                    }
                } finally {
                    setConnected(false)
                }
            })()

        return () => { abort.abort() }
    }, [taskId])

    const disconnect = useCallback(() => {
        abortRef.current?.abort()
    }, [])

    return { events, connected, error, disconnect }
}

/**
 * Hook to cancel a task via gRPC.
 */
export function useCancelTask() {
    const [loading, setLoading] = useState(false)

    const cancel = useCallback(async (taskId: string) => {
        setLoading(true)
        try {
            const request = create(CancelTaskRequestSchema, { name: `tasks/${taskId}` })
            return await a2aClient.cancelTask(request)
        } finally {
            setLoading(false)
        }
    }, [])

    return { cancel, loading }
}
