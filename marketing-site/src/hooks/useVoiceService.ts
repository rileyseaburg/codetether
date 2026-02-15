'use client'

import { useState, useCallback, useRef, useEffect } from 'react'
import { create } from '@bufbuild/protobuf'
import { voiceClient } from '@/lib/grpc/client'
import {
    type VoiceSession,
    type VoiceProfile,
    type VoiceEvent,
    VoiceSessionState,
    VoiceAgentState,
    CreateVoiceSessionRequestSchema,
    GetVoiceSessionRequestSchema,
    DeleteVoiceSessionRequestSchema,
    ListVoicesRequestSchema,
    StreamVoiceEventsRequestSchema,
} from '@/lib/grpc/gen/a2a_pb'

// Re-export for convenience
export { VoiceSessionState, VoiceAgentState }
export type { VoiceSession, VoiceProfile, VoiceEvent }

/**
 * Hook to create a voice session via gRPC.
 */
export function useCreateVoiceSession() {
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const createSession = useCallback(async (voiceId?: string, contextId?: string) => {
        setLoading(true)
        setError(null)
        try {
            const request = create(CreateVoiceSessionRequestSchema, {
                voiceId: voiceId ?? '',
                contextId: contextId ?? '',
            })
            const session = await voiceClient.createVoiceSession(request)
            return session
        } catch (err) {
            const msg = err instanceof Error ? err.message : String(err)
            setError(msg)
            return null
        } finally {
            setLoading(false)
        }
    }, [])

    return { createSession, loading, error }
}

/**
 * Hook to get voice session state via gRPC.
 */
export function useVoiceSession(roomName: string | null) {
    const [session, setSession] = useState<VoiceSession | null>(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const fetch = useCallback(async () => {
        if (!roomName) return
        setLoading(true)
        setError(null)
        try {
            const request = create(GetVoiceSessionRequestSchema, { roomName })
            const result = await voiceClient.getVoiceSession(request)
            setSession(result)
        } catch (err) {
            setError(err instanceof Error ? err.message : String(err))
        } finally {
            setLoading(false)
        }
    }, [roomName])

    useEffect(() => { fetch() }, [fetch])

    return { session, loading, error, refetch: fetch }
}

/**
 * Hook to delete (end) a voice session via gRPC.
 */
export function useDeleteVoiceSession() {
    const [loading, setLoading] = useState(false)

    const deleteSession = useCallback(async (roomName: string) => {
        setLoading(true)
        try {
            const request = create(DeleteVoiceSessionRequestSchema, { roomName })
            await voiceClient.deleteVoiceSession(request)
        } finally {
            setLoading(false)
        }
    }, [])

    return { deleteSession, loading }
}

/**
 * Hook to list available voice profiles via gRPC.
 */
export function useVoiceProfiles() {
    const [voices, setVoices] = useState<VoiceProfile[]>([])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const fetch = useCallback(async () => {
        setLoading(true)
        setError(null)
        try {
            const request = create(ListVoicesRequestSchema, {})
            const result = await voiceClient.listVoices(request)
            setVoices(result.voices)
        } catch (err) {
            setError(err instanceof Error ? err.message : String(err))
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => { fetch() }, [fetch])

    return { voices, loading, error, refetch: fetch }
}

/**
 * Hook to subscribe to streaming voice events (transcripts, state changes)
 * for a specific voice session via gRPC server-streaming.
 */
export function useVoiceEvents(roomName: string | null) {
    const [events, setEvents] = useState<VoiceEvent[]>([])
    const [connected, setConnected] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const abortRef = useRef<AbortController | null>(null)

    useEffect(() => {
        if (!roomName) return

        const abort = new AbortController()
        abortRef.current = abort
        setEvents([])
        setConnected(true)
        setError(null)

            ; (async () => {
                try {
                    const request = create(StreamVoiceEventsRequestSchema, { roomName })
                    for await (const event of voiceClient.streamVoiceEvents(request, { signal: abort.signal })) {
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
    }, [roomName])

    const disconnect = useCallback(() => {
        abortRef.current?.abort()
    }, [])

    return { events, connected, error, disconnect }
}
