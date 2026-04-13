// Swarm Monitor Line Parser - Applies SSE lines to state
import type { SwarmMonitorState, SwarmSubtaskStatus } from '../types'
import { normalizeSwarmStatus } from '../utils'

export const applySwarmLine = (
    state: SwarmMonitorState,
    line: string
): SwarmMonitorState => {
    const trimmed = line.trim()
    if (!trimmed.toLowerCase().includes('[swarm]')) {
        return state
    }

    const now = Date.now()
    const next: SwarmMonitorState = {
        ...state,
        lastUpdatedAt: now,
        recentLines: [...state.recentLines, trimmed].slice(-120),
    }

    // Started
    const startedMatch = trimmed.match(/started\b.*planned_subtasks=(\d+)/i)
    if (startedMatch) {
        next.status = 'running'
        const planned = Number(startedMatch[1])
        next.plannedSubtasks = Number.isFinite(planned) ? planned : null
        next.error = undefined
        return next
    }

    // Stage progress
    const stageMatch =
        trimmed.match(/stage=(\d+)\s+completed=(\d+)\s+failed=(\d+)/i) ||
        trimmed.match(/stage\s+(\d+)\s+complete:\s+(\d+)\s+succeeded,\s+(\d+)\s+failed/i)
    if (stageMatch) {
        next.currentStage = Number(stageMatch[1]) || 0
        next.stageCompleted = Number(stageMatch[2]) || 0
        next.stageFailed = Number(stageMatch[3]) || 0
        return next
    }

    // Routing
    const routingMatch = trimmed.match(
        /\[swarm\]\s+routing\s+complexity=([^\s]+)\s+tier=([^\s]+)\s+personality=([^\s]+)\s+target_agent=([^\s]+)/i
    )
    if (routingMatch) {
        next.routing = {
            ...next.routing,
            complexity: routingMatch[1] === 'unknown' ? next.routing?.complexity : routingMatch[1],
            modelTier: routingMatch[2] === 'unknown' ? next.routing?.modelTier : routingMatch[2],
            workerPersonality: routingMatch[3] === 'auto' ? next.routing?.workerPersonality : routingMatch[3],
            targetAgentName: routingMatch[4] === 'auto' ? next.routing?.targetAgentName : routingMatch[4],
            source: 'stream',
            updatedAt: now,
        }
        return next
    }

    // Config tier
    const configTierMatch = trimmed.match(/\[swarm\]\s+config\b.*\btier=([A-Za-z0-9_-]+)/i)
    if (configTierMatch) {
        next.routing = {
            ...next.routing,
            modelTier: configTierMatch[1],
            source: 'stream',
            updatedAt: now,
        }
        return next
    }

    // Subtask status
    const subtaskStatusMatch =
        trimmed.match(/subtask(?:\s+id=|\s+)([A-Za-z0-9_-]+)\s+status=([A-Za-z_]+)/i) ||
        trimmed.match(/subtask\s+([A-Za-z0-9_-]+)\s+->\s+([A-Za-z_]+)/i)
    if (subtaskStatusMatch) {
        const id = subtaskStatusMatch[1]
        const status = normalizeSwarmStatus(subtaskStatusMatch[2])
        next.subtasks = {
            ...next.subtasks,
            [id]: { id, status, updatedAt: now },
        }
        return next
    }

    // Tool execution
    const toolMatch =
        trimmed.match(/subtask(?:\s+id=|\s+)([A-Za-z0-9_-]+)\s+tool(?:=|:\s*)(.+)$/i) ||
        trimmed.match(/\[swarm\]\s+([A-Za-z0-9_-]+)\s+tool:\s+(.+)$/i)
    if (toolMatch) {
        const id = toolMatch[1]
        const tool = toolMatch[2].trim()
        next.subtasks = {
            ...next.subtasks,
            [id]: {
                ...(next.subtasks[id] ?? { id, status: 'running' as SwarmSubtaskStatus, updatedAt: now }),
                id,
                status: next.subtasks[id]?.status ?? 'running',
                tool,
                updatedAt: now,
            },
        }
        return next
    }

    // Subtask error
    const subtaskErrorMatch =
        trimmed.match(/subtask(?:\s+id=|\s+)([A-Za-z0-9_-]+)\s+error(?:=|:\s*)(.+)$/i) ||
        trimmed.match(/\[swarm\]\s+([A-Za-z0-9_-]+)\s+error:\s+(.+)$/i)
    if (subtaskErrorMatch) {
        const id = subtaskErrorMatch[1]
        const error = subtaskErrorMatch[2].trim()
        next.subtasks = {
            ...next.subtasks,
            [id]: { id, status: 'failed', error, updatedAt: now },
        }
        next.status = 'failed'
        return next
    }

    // Completion
    const completeMatch = trimmed.match(/complete(?::|\s)+success=(true|false)\s+subtasks=(\d+)\s+speedup=([0-9.]+)/i)
    if (completeMatch) {
        const success = completeMatch[1].toLowerCase() === 'true'
        const parsedSubtasks = Number(completeMatch[2])
        const parsedSpeedup = Number(completeMatch[3])
        next.status = success ? 'completed' : 'failed'
        next.plannedSubtasks = Number.isFinite(parsedSubtasks) ? parsedSubtasks : next.plannedSubtasks
        next.speedup = Number.isFinite(parsedSpeedup) ? parsedSpeedup : null
        return next
    }

    // Swarm error
    const swarmErrorMatch = trimmed.match(/error(?:\s+message=|:\s*)(.+)$/i)
    if (swarmErrorMatch) {
        next.status = 'failed'
        next.error = swarmErrorMatch[1].trim()
        return next
    }

    return next
}
