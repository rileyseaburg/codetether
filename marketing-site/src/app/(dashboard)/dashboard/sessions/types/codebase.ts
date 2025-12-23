export interface Codebase {
    id: string
    name: string
    path: string
    status: string
    worker_id?: string | null
    opencode_port?: number | null
}

export interface Session {
    id: string
    title?: string
    agent?: string
    messageCount?: number
    created?: string
    updated?: string
}
