import type { ResumePayload, TaskStatus } from './contracts'

export function executionError(data: ResumePayload): string | null {
    const status = typeof data.status === 'string' ? data.status.toLowerCase() : ''
    if (data.success === false || data.error || ['failed', 'error', 'cancelled', 'canceled', 'interrupted'].includes(status || '')) {
        if (typeof data.error === 'string' && data.error) return data.error
        return status === 'cancelled' || status === 'canceled' ? 'Task cancelled.' : status === 'interrupted' ? 'Task interrupted.' : 'Execution failed.'
    }
    let result = data.result
    if (typeof result === 'string') {
        try { result = JSON.parse(result) } catch { return null }
    }
    if (result && typeof result === 'object' && !Array.isArray(result)) {
        const nested = result as ResumePayload
        return executionError(nested)
    }
    return null
}
export function directSuccess(data: ResumePayload): boolean {
    const status = typeof data.status === 'string' ? data.status.toLowerCase() : ''
    return ['completed', 'ready', 'resumed', 'initialized'].includes(status) ||
        (data.success === true && !status)
}
export function failureStatus(data: ResumePayload): TaskStatus {
    const status = typeof data.status === 'string' ? data.status.toLowerCase() : ''
    return status === 'canceled' || status === 'cancelled' ? 'cancelled' : status === 'interrupted' ? 'interrupted' : 'failed'
}
export function taskStatus(status: unknown): TaskStatus {
    const aliases: Record<string, TaskStatus> = { accepted: 'pending', submitted: 'pending', executing: 'running', canceled: 'cancelled', error: 'failed' }
    const value = typeof status === 'string' ? status.toLowerCase() : ''
    if (aliases[value]) return aliases[value]
    if (['pending', 'queued', 'running', 'working', 'completed', 'failed', 'cancelled', 'interrupted'].includes(value)) return value as TaskStatus
    throw new Error('Unknown task state; execution outcome is unknown.')
}
export function activeSession(data: ResumePayload, fallback: string): string {
    const id = data.active_session_id ?? data.new_session_id ?? data.session_id ?? fallback
    if (typeof id !== 'string' || !id.trim()) throw new Error('Invalid active session identity.')
    return id
}
