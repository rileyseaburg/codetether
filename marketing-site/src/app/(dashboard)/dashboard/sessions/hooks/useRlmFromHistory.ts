import { useMemo } from 'react'
import type { ChatItem } from '../types'
import type { RLMStep, RLMStats } from './useSessionStream'

/**
 * Extract RLM execution data from historical chat items.
 * This allows the RLM pane to show data from past sessions, not just live SSE events.
 */
export function useRlmFromHistory(chatItems: ChatItem[]): { steps: RLMStep[]; stats: RLMStats } {
    return useMemo(() => {
        const steps: RLMStep[] = []
        const stats: RLMStats = { tokens: 0, chunks: 0, subcalls: { completed: 0, total: 0 } }

        for (const item of chatItems) {
            if (!item.tools) continue

            for (const tool of item.tools) {
                if (tool.tool !== 'rlm') continue

                // Extract RLM output
                const output = tool.output as Record<string, unknown> | string | undefined
                let outputText = ''
                let metadata: Record<string, unknown> = {}

                if (typeof output === 'string') {
                    outputText = output
                } else if (output && typeof output === 'object') {
                    outputText = (output.output as string) || ''
                    metadata = (output.metadata as Record<string, unknown>) || output
                }

                // Extract stats from metadata
                if (metadata.iterations) {
                    stats.chunks = Math.max(stats.chunks, metadata.iterations as number)
                }
                if (metadata.totalSubcalls) {
                    stats.subcalls.completed = Math.max(stats.subcalls.completed, metadata.totalSubcalls as number)
                    stats.subcalls.total = Math.max(stats.subcalls.total, metadata.totalSubcalls as number)
                }
                if (metadata.totalSubcallTokens) {
                    stats.tokens = Math.max(stats.tokens, metadata.totalSubcallTokens as number)
                }

                // Create a result step from the output
                if (outputText) {
                    steps.push({
                        id: `rlm-history-${item.key}`,
                        type: 'result',
                        content: outputText.slice(0, 2000) + (outputText.length > 2000 ? '...' : ''),
                        timestamp: new Date(item.createdAt || Date.now()),
                        status: tool.status === 'error' ? 'error' : 'completed',
                    })
                }

                // Add error step if present
                if (tool.error) {
                    const errorText = typeof tool.error === 'string' ? tool.error : JSON.stringify(tool.error)
                    steps.push({
                        id: `rlm-error-${item.key}`,
                        type: 'error',
                        content: errorText,
                        timestamp: new Date(item.createdAt || Date.now()),
                        status: 'error',
                    })
                }
            }
        }

        return { steps, stats }
    }, [chatItems])
}
