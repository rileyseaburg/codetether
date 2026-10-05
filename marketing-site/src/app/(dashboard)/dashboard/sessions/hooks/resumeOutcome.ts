// Transport success is not execution success. A direct response or a task
// result may contain a terminal error inside an HTTP 200 response.
export function resumeOutcome(data: unknown): { status: 'failed' | 'cancelled'; message: string } | null {
    if (!data || typeof data !== 'object') return null
    const value = data as { status?: string; error?: unknown; result?: unknown }
    if (value.status === 'cancelled' || value.status === 'canceled') {
        return { status: 'cancelled', message: 'Task cancelled.' }
    }
    if (value.status === 'failed' || value.status === 'error' || value.error) {
        const detail = typeof value.error === 'string' ? value.error : 'Unknown error'
        return { status: 'failed', message: `Execution failed: ${detail}` }
    }
    return resumeOutcome(value.result)
}
