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
    slug?: string
    version: string
    projectID: string
    directory: string
    parentID?: string
    title: string
    time: {
        created: number
        updated: number
    }
    summary?: {
        additions: number
        deletions: number
        files: number
    }
}
