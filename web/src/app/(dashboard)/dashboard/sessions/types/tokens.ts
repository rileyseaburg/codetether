export type TokenUsage = {
    input?: number
    output?: number
    reasoning?: number
    cache?: { read?: number; write?: number }
}

export type ToolState = {
    status?: string
    title?: string
    input?: unknown
    output?: unknown
    error?: unknown
    metadata?: unknown
    time?: unknown
    raw?: unknown
    attachments?: unknown
}
