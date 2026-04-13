// useSwarmMonitor Hook
// Swarm monitoring state and SSE connection

import { useState, useCallback, useRef, useEffect } from 'react'
import type { SwarmMonitorState } from '../types'
import { INITIAL_SWARM_MONITOR } from '../utils'
import { applySwarmLine } from '../utils/swarm'

interface UseSwarmMonitorReturn {
    swarmMonitor: SwarmMonitorState
    connect: (sessionId: string) => void
    disconnect: () => void
}

export function useSwarmMonitor(apiUrl: string): UseSwarmMonitorReturn {
    const [swarmMonitor, setSwarmMonitor] = useState<SwarmMonitorState>(INITIAL_SWARM_MONITOR)
    const eventSourceRef = useRef<EventSource | null>(null)

    const disconnect = useCallback(() => {
        if (eventSourceRef.current) {
            eventSourceRef.current.close()
            eventSourceRef.current = null
        }
        setSwarmMonitor(prev => ({ ...prev, connected: false }))
    }, [])

    const connect = useCallback((sessionId: string) => {
        disconnect()
        const url = `${apiUrl}/agent/sessions/${sessionId}/events/stream`
        const es = new EventSource(url)
        eventSourceRef.current = es

        es.onopen = () => {
            setSwarmMonitor(prev => ({ ...prev, connected: true }))
        }

        es.onmessage = (event) => {
            const line = event.data
            if (line) {
                setSwarmMonitor(prev => applySwarmLine(prev, line))
            }
        }

        es.onerror = () => {
            disconnect()
        }

        return () => {
            es.close()
        }
    }, [apiUrl, disconnect])

    useEffect(() => {
        return () => {
            disconnect()
        }
    }, [disconnect])

    return { swarmMonitor, connect, disconnect }
}
