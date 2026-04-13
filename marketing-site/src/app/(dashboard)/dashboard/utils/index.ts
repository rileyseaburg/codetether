// Dashboard Utilities
// Helper functions for the dashboard

import type { SwarmMonitorState, SwarmSubtaskStatus, SwarmRoutingSnapshot } from '../types'

export const INITIAL_SWARM_MONITOR: SwarmMonitorState = {
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

export const WORKSPACE_WIZARD_DISMISSED_KEY = 'codetether.workspaceWizardDismissed'

export const buildVmSshCommand = (
    workspace: { vm_ssh_host?: string; vm_ssh_port?: number }
): string => {
    if (!workspace.vm_ssh_host) return ''
    const portSegment = workspace.vm_ssh_port ? `-p ${workspace.vm_ssh_port} ` : ''
    return `ssh ${portSegment}YOUR_USER@${workspace.vm_ssh_host}`
}

const asRecord = (value: unknown): Record<string, unknown> | null => {
    if (!value || typeof value !== 'object') return null
    return value as Record<string, unknown>
}

const getString = (
    record: Record<string, unknown> | null,
    keys: string[]
): string | undefined => {
    if (!record) return undefined
    for (const key of keys) {
        const value = record[key]
        if (typeof value === 'string') {
            const trimmed = value.trim()
            if (trimmed) return trimmed
        }
    }
    return undefined
}

const getBoolean = (
    record: Record<string, unknown> | null,
    keys: string[]
): boolean | undefined => {
    if (!record) return undefined
    for (const key of keys) {
        const value = record[key]
        if (typeof value === 'boolean') return value
        if (typeof value === 'string') {
            const normalized = value.trim().toLowerCase()
            if (normalized === 'true') return true
            if (normalized === 'false') return false
        }
    }
    return undefined
}

export const extractRoutingSnapshot = (
    value: unknown
): Omit<SwarmRoutingSnapshot, 'source' | 'updatedAt'> | null => {
    const root = asRecord(value)
    if (!root) return null
    const nestedRouting = asRecord(root.routing)
    const routing = nestedRouting ?? root
    const complexity = getString(routing, ['complexity'])
    const modelTier = getString(routing, ['model_tier', 'modelTier', 'tier'])
    const modelRef = getString(routing, ['model_ref', 'modelRef'])
    const targetAgentName = getString(routing, ['target_agent_name', 'targetAgentName'])
    const workerPersonality = getString(routing, ['worker_personality', 'workerPersonality'])

    if (!complexity && !modelTier && !modelRef && !targetAgentName && !workerPersonality) {
        return null
    }

    return { complexity, modelTier, modelRef, targetAgentName, workerPersonality }
}

export const isSwarmAgentType = (value: unknown): boolean => {
    if (typeof value !== 'string') return false
    const normalized = value.trim().toLowerCase()
    return normalized === 'swarm' || normalized === 'parallel' || normalized === 'multi-agent'
}

export const normalizeSwarmStatus = (raw: string): SwarmSubtaskStatus => {
    const normalized = raw.trim().toLowerCase().replace(/\s+/g, '_')
    const validStatuses: SwarmSubtaskStatus[] = [
        'pending', 'running', 'completed', 'failed', 'timed_out', 'cancelled'
    ]
    if (validStatuses.includes(normalized as SwarmSubtaskStatus)) {
        return normalized as SwarmSubtaskStatus
    }
    if (normalized === 'timedout') return 'timed_out'
    return 'unknown'
}

export const getSwarmRunStatusClasses = (
    status: SwarmMonitorState['status']
): string => {
    const classes: Record<string, string> = {
        completed: 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300',
        failed: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300',
        running: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300',
        idle: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
    }
    return classes[status] ?? classes.idle
}

export const getSwarmSubtaskStatusClasses = (
    status: SwarmSubtaskStatus
): string => {
    const completed = 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'
    const failed = 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300'
    const running = 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
    const pending = 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300'
    const unknown = 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'

    if (status === 'completed') return completed
    if (['failed', 'timed_out', 'cancelled'].includes(status)) return failed
    if (status === 'running') return running
    if (status === 'pending') return pending
    return unknown
}

export const getSwarmSubtaskStatusLabel = (status: SwarmSubtaskStatus): string => {
    if (status === 'pending') return 'waiting for worker'
    return status
}
